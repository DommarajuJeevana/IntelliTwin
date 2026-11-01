"""
Echo - IntelliTwin's long-term memory agent.

Memory lifecycle:

    interaction
        ↓
    extraction
        ↓
    importance + confidence
        ↓
    embedding
        ↓
    related-memory detection
        ↓
    contradiction / supersession detection
        ↓
    active memory

A memory can therefore be:

    active
    superseded
    archived

Superseded memories are retained for history but are excluded from normal
memory retrieval. They remain linked to the newer memory that replaced them.
"""

import json
import logging

from bson import ObjectId
from pymongo import ReturnDocument

from app.config import settings
from app.database import get_db
from app.llm import call_llm
from app.memory.embeddings import embed_text
from app.memory.vector_store import cosine_similarity
from app.memory.vector_store import search as vector_search
from app.owned import new_owned_doc, now_utc
from app.serialization import doc_out, docs_out
from app.user_utils import profile_context

logger = logging.getLogger("intellitwin.echo")

MEMORY_COLLECTION = "memory_entries"

MERGE_SIMILARITY_THRESHOLD = 0.93

# Only memories above this semantic similarity are candidates for
# contradiction/supersession analysis.
EVOLUTION_SIMILARITY_THRESHOLD = 0.78
# The offline hashed-word embedding scores true corrections ("lives in A" vs
# "lives in B") around 0.4, so it needs a lower candidate threshold. The LLM
# relationship check remains the arbiter, so extra candidates are harmless.
OFFLINE_EVOLUTION_SIMILARITY_THRESHOLD = 0.35


def _evolution_threshold() -> float:
    return EVOLUTION_SIMILARITY_THRESHOLD if settings.OPENAI_API_KEY else OFFLINE_EVOLUTION_SIMILARITY_THRESHOLD

MAX_EVOLUTION_CANDIDATES = 5

_EXTRACTION_SYSTEM = (
    "You are Echo, the memory agent for a personal digital twin app. "
    "Given a piece of raw user activity or a message, decide whether it "
    "contains a useful long-term memory about the person. Automatically capture "
    "clear durable preferences and personal facts even when the person does not "
    "explicitly ask you to remember them (for example, 'I love desserts, mainly "
    "cakes'). Explicit memory instructions such as 'remember that', 'don't forget', "
    "'keep in mind', or 'save this' are additional strong signals, not a requirement. "
    "Do NOT store greetings, questions, requests, commands, temporary conversation, "
    "or requests asking what Echo already "
    "remembers. A question about an existing preference is not itself a "
    "memory. Trivial or purely transactional text may not be worth "
    "remembering. Store only durable, useful personal information: stable "
    "preferences, communication/work style, personal facts the user volunteers, "
    "long-term goals, ongoing commitments, and meaningful recurring patterns. "
    "Do not store every message, greetings, questions, raw conversation, one-off "
    "tasks, or assistant-generated summaries. Explicit 'remember that' requests "
    "are strong evidence but do not justify saving conversational noise. "
    "For emotionally significant events, record the user's stated emotion, the "
    "stated trigger/cause, and what response they say helps, when known. Never "
    "diagnose or invent a cause. Only describe an emotional pattern as recurring "
    "when multiple events support it.\n\n"
    "Respond with ONLY a JSON object, no other text:\n"
    '{"should_remember": true|false, '
    '"title": "short title (<=8 words)", '
    '"content": "1-3 sentence memory, written in third person about the user", '
    '"category": "preference|personal_fact|goal|commitment|emotional_pattern|other", '
    '"emotion": "stated emotion or empty string", '
    '"trigger": "stated cause/trigger or empty string", '
    '"helpful_response": "user-stated helpful response or empty string", '
    '"importance": 1-5, '
    '"confidence": 0.0-1.0}'
)

_EVOLUTION_SYSTEM = (
    "You are Echo, a long-term memory consistency agent. "
    "Compare a NEW memory with ONE EXISTING memory about the same person.\n\n"
    "Determine whether the new memory changes or contradicts the existing "
    "memory, merely repeats it, or is unrelated.\n\n"
    "Return ONLY JSON:\n"
    '{"relationship": "UNRELATED|SAME|SUPERSEDES", '
    '"reason": "short explanation"}\n\n'
    "Use SUPERSEDES when the new memory represents a changed preference, "
    "fact, decision, plan, or other information that should replace the "
    "older memory for future personalization.\n"
    "Use SAME when both memories communicate essentially the same fact.\n"
    "Use UNRELATED when they can both remain true independently."
)


def _embed_source(title: str, content: str) -> str:
    return f"{title}\n{content}".strip()


def _normalise_memory_text(value: str) -> str:
    """Normalize for exact duplicate detection; avoid fuzzy destructive merges."""
    import re
    text = (value or "").strip().lower()
    text = re.sub(r"^remember that\s+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _title_from_text(text: str, max_words: int = 8) -> str:
    words = text.strip().split()
    title = " ".join(words[:max_words])

    if len(words) > max_words:
        title += "…"

    return title or "Memory entry"


def _normalise_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5

    return max(0.0, min(1.0, confidence))


def _memory_source(
    note: str | None,
    source_interaction: str | None,
) -> str:
    if source_interaction:
        return "interaction"

    if note:
        return "agent_or_manual"

    return "unknown"


def _looks_like_non_memory_message(text: str) -> bool:
    """
    Reject obvious conversational messages before asking the LLM to extract
    long-term memory.
    """
    value = " ".join(text.strip().lower().split())

    if not value:
        return True

    greetings = (
        "hello", "hi", "hey", "hello echo", "hi echo", "hey echo",
        "good morning", "good afternoon", "good evening",
    )
    if value in greetings:
        return True

    memory_questions = (
        "what do you remember",
        "what do you know about me",
        "show me what you remember",
        "tell me what you remember",
        "what are your memories",
        "what memories do you have",
    )
    if any(value == p or value.startswith(p + " ") for p in memory_questions):
        return True

    if value.endswith("?"):
        return True

    conversational_prefixes = (
        "tell me ", "explain ", "how do i ", "how can i ", "can you ",
        "could you ", "would you ", "why ", "when ", "where ", "who ",
        "what ", "which ", "is ", "are ", "do ", "does ", "did ",
    )
    return value.startswith(conversational_prefixes)


def _has_explicit_memory_intent(text: str) -> bool:
    """
    Detect strong intent to create a persistent memory.
    """
    value = " ".join(text.strip().lower().split())

    explicit_prefixes = (
        "remember that ",
        "remember this: ",
        "remember this ",
        "don't forget that ",
        "dont forget that ",
        "keep in mind that ",
        "keep this in mind: ",
        "save this: ",
        "save this ",
        "store this: ",
        "store this ",
        "note that ",
        "make a note that ",
        "make a note of ",
    )

    return value.startswith(explicit_prefixes)


async def _extract(
    user: dict,
    raw_text: str,
) -> dict:
    """
    Extract a potentially useful long-term memory.

    If the LLM fails, do NOT automatically save the raw interaction.
    This prevents extraction failures from polluting long-term memory.
    """
    if _looks_like_non_memory_message(raw_text) and not _has_explicit_memory_intent(raw_text):
        return {
            "should_remember": False,
            "title": "",
            "content": "",
            "importance": 1,
            "confidence": 0.0,
        }

    system = _EXTRACTION_SYSTEM

    context = profile_context(user)

    if context:
        system += (
            "\n\nWhat you already know about this person:\n"
            f"{context}"
        )

    try:
        raw = await call_llm(
            system,
            raw_text,
            max_tokens=300,
        )
    except Exception:
        logger.exception(
            "Echo extraction failed during LLM call."
        )
        return {
            "should_remember": False,
            "title": "",
            "content": "",
            "importance": 1,
            "confidence": 0.0,
        }

    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1

        parsed = json.loads(
            raw[start:end]
        )

        title = str(
            parsed.get("title") or ""
        ).strip()

        content = str(
            parsed.get("content") or ""
        ).strip()

        importance = int(
            parsed.get("importance", 3)
        )

        raw_should_remember = parsed.get(
            "should_remember",
            False,
        )

        if isinstance(
            raw_should_remember,
            str,
        ):
            should_remember = (
                raw_should_remember.strip().lower()
                == "true"
            )
        else:
            should_remember = bool(
                raw_should_remember
            )

        confidence = _normalise_confidence(
            parsed.get("confidence", 0.5)
        )

        if title and content:
            return {
                "should_remember": should_remember,
                "title": title[:120],
                "content": content,
                "importance": max(
                    1,
                    min(5, importance),
                ),
                "confidence": confidence,
                "category": str(parsed.get("category") or "other").strip().lower(),
                "emotion": str(parsed.get("emotion") or "").strip(),
                "trigger": str(parsed.get("trigger") or "").strip(),
                "helpful_response": str(parsed.get("helpful_response") or "").strip(),
            }

    except (
        ValueError,
        json.JSONDecodeError,
        TypeError,
    ):
        logger.warning(
            "Echo returned an invalid extraction response."
        )

    return {
        "should_remember": False,
        "title": "",
        "content": "",
        "importance": 1,
        "confidence": 0.0,
    }


async def _classify_relationship(
    new_memory: dict,
    existing_memory: dict,
) -> str:
    """
    Determine whether a new memory is unrelated, the same fact, or
    supersedes the existing memory.

    This is deliberately conservative. Any malformed LLM response is
    treated as UNRELATED rather than automatically changing old memory.
    """
    prompt = (
        "NEW MEMORY:\n"
        f"Title: {new_memory.get('title', '')}\n"
        f"Content: {new_memory.get('content', '')}\n\n"
        "EXISTING MEMORY:\n"
        f"Title: {existing_memory.get('title', '')}\n"
        f"Content: {existing_memory.get('content', '')}"
    )

    try:
        raw = await call_llm(
            _EVOLUTION_SYSTEM,
            prompt,
            max_tokens=180,
        )

        start = raw.index("{")
        end = raw.rindex("}") + 1

        parsed = json.loads(
            raw[start:end]
        )

        relationship = str(
            parsed.get("relationship", "")
        ).strip().upper()

        if relationship in {
            "UNRELATED",
            "SAME",
            "SUPERSEDES",
        }:
            return relationship

    except Exception:
        logger.exception(
            "Echo memory relationship check failed."
        )

    return "UNRELATED"


async def _find_evolution_candidates(
    user: dict,
    embedding: list[float],
    limit: int = MAX_EVOLUTION_CANDIDATES,
) -> list[dict]:
    """
    Find active memories that are semantically close enough to potentially
    represent the same evolving fact.
    """
    hits = await vector_search(
        MEMORY_COLLECTION,
        user["_id"],
        embedding,
        limit=limit,
        extra_filter={
            "archived": {"$ne": True},
            "status": {"$ne": "superseded"},
        },
    )

    candidates = []

    for hit in hits:
        if hit.score < _evolution_threshold():
            continue

        document = dict(hit.doc)
        document["_similarity"] = hit.score
        candidates.append(document)

    return candidates


async def _supersede_memory(
    user: dict,
    old_memory: dict,
    new_memory_id: ObjectId,
) -> bool:
    """
    Mark an old memory as superseded by a newer memory.

    The old record is retained rather than permanently deleted.
    """
    db = get_db()

    result = await db[MEMORY_COLLECTION].update_one(
        {
            "_id": old_memory["_id"],
            "user": user["_id"],
            "archived": {"$ne": True},
        },
        {
            "$set": {
                "status": "superseded",
                "supersededBy": new_memory_id,
                "supersededAt": now_utc(),
                "updatedAt": now_utc(),
            }
        },
    )

    return result.modified_count > 0


async def remember(
    user: dict,
    note: str | None = None,
    title: str | None = None,
    source_interaction: str | None = None,
    importance: int | None = None,
    force: bool = False,
) -> dict | None:
    """
    Main Echo write path.

    Two modes:

    1. note is supplied:
       The caller explicitly provides something to remember.

    2. note is omitted:
       Echo extracts a memory from source_interaction.

    `force=False` is intentional. If extraction fails or decides that
    something is not worth remembering, nothing is stored.
    """
    db = get_db()

    from app.memory.safety import contains_secret

    if contains_secret(f"{note or ''}\n{source_interaction or ''}"):
        # Never silently persist passwords, tokens, card or ID numbers.
        logger.info("Echo refused to store a message that looks like it contains a secret.")
        return None

    if note and note.strip():
        title = title or _title_from_text(note)

        content = note.strip()

        final_importance = (
            importance
            if importance is not None
            else 3
        )

        confidence = 1.0

        source = _memory_source(
            note,
            source_interaction,
        )

    else:
        raw_text = (
            source_interaction
            or ""
        ).strip()

        if not raw_text:
            return None

        if (
            _looks_like_non_memory_message(raw_text)
            and not _has_explicit_memory_intent(raw_text)
        ):
            return None

        extracted = await _extract(
            user,
            raw_text,
        )

        if (
            not extracted["should_remember"]
            and not force
        ):
            return None

        if not extracted["title"] or not extracted["content"]:
            return None

        title = extracted["title"]
        content = extracted["content"]

        final_importance = (
            importance
            if importance is not None
            else extracted["importance"]
        )

        confidence = extracted["confidence"]

        source = _memory_source(
            note,
            source_interaction,
        )

    # Idempotency guard: repeated tool calls must not create repeated memories.
    normalized_content = _normalise_memory_text(content)
    db = get_db()
    existing_cursor = db[MEMORY_COLLECTION].find({
        "user": user["_id"],
        "archived": {"$ne": True},
        "status": {"$ne": "superseded"},
    }).sort("occurredAt", -1).limit(200)
    existing_memories = await existing_cursor.to_list(length=200)
    for existing in existing_memories:
        if _normalise_memory_text(existing.get("content", "")) == normalized_content:
            logger.info("Echo skipped duplicate memory for user=%s", user.get("_id"))
            return doc_out(existing)

    embedding = await embed_text(
        _embed_source(
            title,
            content,
        )
    )

    entry = new_owned_doc(
        user["_id"],
        agent="echo",
    )

    entry.update(
        {
            "title": title,
            "content": content,
            "importance": max(
                1,
                min(5, final_importance),
            ),
            "confidence": confidence,
            "category": extracted.get("category", "other") if not (note and note.strip()) else "other",
            "emotion": extracted.get("emotion", "") if not (note and note.strip()) else "",
            "trigger": extracted.get("trigger", "") if not (note and note.strip()) else "",
            "helpful_response": extracted.get("helpful_response", "") if not (note and note.strip()) else "",
            "source": source,
            "status": "active",
            "occurredAt": now_utc(),
            "embedding": embedding,
        }
    )

    result = await db[
        MEMORY_COLLECTION
    ].insert_one(entry)

    entry["_id"] = result.inserted_id

    # ---------------------------------------------------------
    # Memory evolution
    # ---------------------------------------------------------
    #
    # Only newly-created memories participate. The new memory is now
    # available as the canonical active record that can supersede older
    # records.
    #
    # We intentionally limit this to a small number of semantically
    # related memories to avoid turning every save into an expensive
    # full-memory scan.
    # ---------------------------------------------------------

    candidates = await _find_evolution_candidates(
        user,
        embedding,
    )

    superseded = []

    for old_memory in candidates:
        # The vector search can theoretically return the newly-created
        # record. Ignore it explicitly.
        if old_memory["_id"] == entry["_id"]:
            continue

        relationship = await _classify_relationship(
            entry,
            old_memory,
        )

        if relationship == "SUPERSEDES":
            changed = await _supersede_memory(
                user,
                old_memory,
                entry["_id"],
            )

            if changed:
                superseded.append(
                    {
                        "id": str(
                            old_memory["_id"]
                        ),
                        "title": old_memory.get(
                            "title",
                            "",
                        ),
                    }
                )

        elif relationship == "SAME":
            # A semantic repeat: keep the original record, drop the new
            # duplicate and refresh the original's timestamp.
            await db[MEMORY_COLLECTION].delete_one({"_id": entry["_id"], "user": user["_id"]})
            await db[MEMORY_COLLECTION].update_one(
                {"_id": old_memory["_id"], "user": user["_id"]},
                {"$set": {"updatedAt": now_utc()}},
            )
            return doc_out(old_memory)

    if superseded:
        entry["supersedes"] = [
            item["id"]
            for item in superseded
        ]

        await db[
            MEMORY_COLLECTION
        ].update_one(
            {"_id": entry["_id"]},
            {
                "$set": {
                    "supersedes": entry[
                        "supersedes"
                    ]
                }
            },
        )

    return doc_out(entry)


async def search_memory(
    user: dict,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """
    Semantic search over active memories.

    Superseded and archived memories are excluded from normal retrieval.
    """
    if not query or not query.strip():
        return []

    query_embedding = await embed_text(
        query
    )

    hits = await vector_search(
        MEMORY_COLLECTION,
        user["_id"],
        query_embedding,
        limit=limit,
        extra_filter={
            "archived": {"$ne": True},
            "status": {"$ne": "superseded"},
        },
    )

    out = []

    for hit in hits:
        document = dict(hit.doc)
        document["relevance"] = round(
            hit.score,
            4,
        )
        out.append(document)

    return docs_out(out)


async def get_recent_memories(
    user: dict,
    limit: int = 10,
    include_archived: bool = False,
) -> list[dict]:
    db = get_db()

    filt = {
        "user": user["_id"],
        "status": {"$ne": "superseded"},
    }

    if not include_archived:
        filt["archived"] = {
            "$ne": True
        }

    cursor = (
        db[MEMORY_COLLECTION]
        .find(filt)
        .sort("occurredAt", -1)
        .limit(limit)
    )

    items = await cursor.to_list(
        length=limit
    )

    return docs_out(items)


async def get_memory_timeline(user: dict, view: str = "all", limit: int = 200) -> list[dict]:
    """Everything the user can inspect on the Memory Timeline, newest first.

    view: all | active | superseded | archived. Each item carries `lifecycle`
    (active / superseded / archived) and, for superseded memories, the title of
    the memory that replaced it, so history is visible rather than silently hidden.
    """
    if view not in {"all", "active", "superseded", "archived"}:
        raise ValueError("view must be all, active, superseded or archived.")
    limit = max(1, min(int(limit), 500))
    db = get_db()
    filt: dict = {"user": user["_id"]}
    if view == "active":
        filt.update({"archived": {"$ne": True}, "status": {"$ne": "superseded"}})
    elif view == "superseded":
        filt["status"] = "superseded"
    elif view == "archived":
        filt["archived"] = True
    items = await db[MEMORY_COLLECTION].find(filt).sort("occurredAt", -1).to_list(length=limit)

    replacement_ids = [i["supersededBy"] for i in items if i.get("supersededBy")]
    titles = {}
    if replacement_ids:
        found = await db[MEMORY_COLLECTION].find(
            {"_id": {"$in": replacement_ids}, "user": user["_id"]}, {"title": 1}
        ).to_list(length=len(replacement_ids))
        titles = {d["_id"]: d.get("title") for d in found}

    out = []
    for item in items:
        lifecycle = "archived" if item.get("archived") else ("superseded" if item.get("status") == "superseded" else "active")
        row = {**item, "lifecycle": lifecycle}
        if item.get("supersededBy"):
            row["supersededByTitle"] = titles.get(item["supersededBy"])
        out.append(row)
    return docs_out(out)


async def update_memory(
    user: dict,
    memory_id: str,
    updates: dict,
) -> dict | None:
    db = get_db()

    try:
        oid = ObjectId(memory_id)
    except Exception:
        return None

    existing = await db[
        MEMORY_COLLECTION
    ].find_one(
        {
            "_id": oid,
            "user": user["_id"],
        }
    )

    if not existing:
        return None

    from app.memory.safety import reject_secret_memory

    reject_secret_memory(updates.get("title"), updates.get("content"))
    if "importance" in updates and updates["importance"] is not None:
        try:
            updates = {**updates, "importance": max(1, min(5, int(updates["importance"])))}
        except (TypeError, ValueError):
            raise ValueError("importance must be a number from 1 to 5.")

    set_fields = {
        "updatedAt": now_utc()
    }

    for field in (
        "title",
        "content",
        "importance",
        "tags",
    ):
        if (
            field in updates
            and updates[field] is not None
        ):
            set_fields[field] = updates[field]

    if (
        "title" in set_fields
        or "content" in set_fields
    ):
        new_title = set_fields.get(
            "title",
            existing.get("title", ""),
        )

        new_content = set_fields.get(
            "content",
            existing.get("content", ""),
        )

        set_fields["embedding"] = await embed_text(
            _embed_source(
                new_title,
                new_content,
            )
        )

    updated = await db[
        MEMORY_COLLECTION
    ].find_one_and_update(
        {
            "_id": oid,
            "user": user["_id"],
        },
        {"$set": set_fields},
        return_document=ReturnDocument.AFTER,
    )

    return (
        doc_out(updated)
        if updated
        else None
    )


async def delete_memory(
    user: dict,
    memory_id: str,
    hard: bool = False,
) -> bool:
    """
    Soft-delete by default.

    Agent-triggered deletion becomes reversible. Hard deletion remains
    available for explicit REST CRUD deletion.
    """
    db = get_db()

    try:
        oid = ObjectId(memory_id)
    except Exception:
        return False

    if hard:
        result = await db[
            MEMORY_COLLECTION
        ].find_one_and_delete(
            {
                "_id": oid,
                "user": user["_id"],
            }
        )

        return result is not None

    updated = await db[
        MEMORY_COLLECTION
    ].find_one_and_update(
        {
            "_id": oid,
            "user": user["_id"],
        },
        {
            "$set": {
                "archived": True,
                "archivedAt": now_utc(),
                "status": "archived",
                "updatedAt": now_utc(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return updated is not None


async def restore_memory(
    user: dict,
    memory_id: str,
) -> dict | None:
    db = get_db()

    try:
        oid = ObjectId(memory_id)
    except Exception:
        return None

    updated = await db[
        MEMORY_COLLECTION
    ].find_one_and_update(
        {
            "_id": oid,
            "user": user["_id"],
            "archived": True,
        },
        {
            "$unset": {
                "archived": "",
                "archivedAt": "",
            },
            "$set": {
                "updatedAt": now_utc(),
                "status": "active",
            },
        },
        return_document=ReturnDocument.AFTER,
    )

    return (
        doc_out(updated)
        if updated
        else None
    )


async def list_archived_memories(
    user: dict,
    limit: int = 50,
) -> list[dict]:
    db = get_db()

    cursor = (
        db[MEMORY_COLLECTION]
        .find(
            {
                "user": user["_id"],
                "archived": True,
            }
        )
        .sort(
            "archivedAt",
            -1,
        )
        .limit(limit)
    )

    items = await cursor.to_list(
        length=limit
    )

    return docs_out(items)


async def summarize_memories(
    user: dict,
    limit: int = 20,
) -> str:
    memories = await get_recent_memories(
        user,
        limit=limit,
    )

    if not memories:
        return (
            "Echo has no memories stored yet "
            "for this person."
        )

    bullet_lines = "\n".join(
        (
            f"- ({m.get('importance', 3)}/5) "
            f"{m['title']}: {m['content']}"
        )
        for m in memories
    )

    system = (
        "You are Echo, the memory agent. Below is a list of active "
        "memory entries for one person, most recent first, each tagged "
        "with importance (1-5). Write a short 4-6 sentence digest of "
        "what really matters about this person right now - patterns, "
        "priorities, preferences. Weight higher-importance entries "
        "more heavily. Do not mention archived or superseded memories. "
        "Plain prose, no headers."
    )

    return await call_llm(
        system,
        bullet_lines,
        max_tokens=350,
    )


async def _merge_cluster(
    user: dict,
    group: list[dict],
) -> dict:
    contents = [
        f"- {d['title']}: {d['content']}"
        for d in group
    ]

    system = (
        "You are Echo, the memory agent. These memory entries about "
        "the same person appear to be near-duplicates or restatements "
        "of each other. Merge them into ONE consolidated memory that "
        "keeps everything distinct they add and drops redundancy. "
        "Respond with ONLY JSON:\n"
        '{"title": "short title (<=8 words)", '
        '"content": "1-3 sentence merged memory"}'
    )

    raw = await call_llm(
        system,
        "\n".join(contents),
        max_tokens=250,
    )

    title = None
    content = None

    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1

        parsed = json.loads(
            raw[start:end]
        )

        title = str(
            parsed.get("title") or ""
        ).strip()

        content = str(
            parsed.get("content") or ""
        ).strip()

    except (
        ValueError,
        json.JSONDecodeError,
    ):
        pass

    if not (title and content):
        best = max(
            group,
            key=lambda d: len(
                d.get("content", "")
            ),
        )

        title = best["title"]
        content = best["content"]

    importance = max(
        d.get("importance", 3)
        for d in group
    )

    merged = await remember(
        user,
        note=content,
        title=title,
        importance=importance,
    )

    return merged


async def consolidate_memories(
    user: dict,
    limit: int = 300,
) -> dict:
    """
    Merge near-duplicate active memories.

    Superseded and archived memories are excluded.
    """
    db = get_db()

    docs = (
        await db[MEMORY_COLLECTION]
        .find(
            {
                "user": user["_id"],
                "archived": {
                    "$ne": True
                },
                "status": {
                    "$ne": "superseded"
                },
                "embedding": {
                    "$exists": True,
                    "$ne": None,
                },
            }
        )
        .sort(
            "createdAt",
            1,
        )
        .to_list(
            length=limit
        )
    )

    clustered_ids: set = set()
    clusters: list[list[dict]] = []

    for i, doc in enumerate(docs):
        if doc["_id"] in clustered_ids:
            continue

        group = [doc]
        clustered_ids.add(doc["_id"])

        for other in docs[i + 1:]:
            if other["_id"] in clustered_ids:
                continue

            similarity = cosine_similarity(
                doc.get("embedding") or [],
                other.get("embedding") or [],
            )

            if (
                similarity
                >= MERGE_SIMILARITY_THRESHOLD
            ):
                group.append(other)
                clustered_ids.add(
                    other["_id"]
                )

        if len(group) > 1:
            clusters.append(group)

    merges = []

    for group in clusters:
        merged_entry = await _merge_cluster(
            user,
            group,
        )

        for original in group:
            await delete_memory(
                user,
                str(original["_id"]),
            )

        merges.append(
            {
                "mergedInto": merged_entry["_id"],
                "title": merged_entry["title"],
                "archivedOriginals": [
                    str(d["_id"])
                    for d in group
                ],
            }
        )

    return {
        "clustersMerged": len(clusters),
        "memoriesArchived": sum(
            len(group)
            for group in clusters
        ),
        "merges": merges,
    }