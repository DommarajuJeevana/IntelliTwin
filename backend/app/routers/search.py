"""
IntelliTwin universal workspace search.

Searches the user's workspace using semantic embeddings rather than relying
only on exact keyword matches.

Supported workspace data:
    goals
    tasks
    calendar
    notes
    documents
    research
    projects
    memory

The response contract remains:

    {"results": [{"type": "...", "item": {...}}]}

so the existing frontend does not need to change.
"""

import re
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.dependencies import require_auth
from app.memory.embeddings import embed_text
from app.memory.vector_store import cosine_similarity
from app.serialization import serialize

router = APIRouter()


# Maximum number of recent documents considered per collection.
# This keeps first-time semantic indexing bounded.
BACKFILL_LIMIT = 25

# Maximum semantic candidates returned from each collection.
PER_TYPE_LIMIT = 5

# Final number of results shown to the user.
FINAL_LIMIT = 25

# A small lexical boost helps exact matches remain strong, especially when
# the offline hashing-based embedding backend is being used.
LEXICAL_BOOST = 0.15


SEARCH_CONFIG = {
    "goal": {
        "collection": "goals",
        "fields": ["title", "description"],
    },
    "task": {
        "collection": "tasks",
        "fields": ["title"],
    },
    "calendar": {
        "collection": "calendar_events",
        "fields": ["title", "location", "notes"],
    },
    "note": {
        "collection": "notes",
        "fields": ["title", "body"],
    },
    "document": {
        "collection": "documents",
        "fields": ["title", "content"],
    },
    "research": {
        "collection": "research_items",
        "fields": ["query", "summary"],
    },
    "project": {
        "collection": "projects",
        "fields": ["name", "description"],
    },
    "memory": {
        "collection": "memory_entries",
        "fields": ["title", "content"],
    },
}


def _search_text(
    document: dict,
    fields: list[str],
) -> str:
    """
    Build the text representation that gets embedded.
    """
    return "\n".join(
        str(document.get(field) or "")
        for field in fields
    ).strip()


def _lexical_overlap(
    query: str,
    text: str,
) -> float:
    """
    Calculate a small exact-word overlap score.

    This is not the primary search mechanism. It is only a ranking boost
    for obvious exact matches.
    """
    query_words = {
        word
        for word in re.findall(
            r"[a-z0-9]+",
            query.lower(),
        )
        if len(word) >= 3
    }

    if not query_words:
        return 0.0

    text_words = set(
        re.findall(
            r"[a-z0-9]+",
            text.lower(),
        )
    )

    overlap = query_words.intersection(
        text_words
    )

    return len(overlap) / len(query_words)


async def _ensure_embedding(
    collection_name: str,
    document: dict,
    text: str,
) -> list[float]:
    """
    Return an existing embedding or create one.

    Existing workspace records from the older version of IntelliTwin may
    not have embeddings yet. We gradually backfill them when they are
    encountered by search instead of requiring a migration.
    """
    existing = document.get("embedding")

    if (
        isinstance(existing, list)
        and existing
    ):
        return existing

    embedding = await embed_text(text)

    if embedding:
        db = get_db()

        await db[
            collection_name
        ].update_one(
            {
                "_id": document["_id"],
            },
            {
                "$set": {
                    "embedding": embedding,
                }
            },
        )

    return embedding


# --- keyword layer (primary, exact) + semantic layer (supplementary) --------
SEMANTIC_MIN_SCORE = 0.30     # semantic-only hits below this are noise
SEMANTIC_CANDIDATES = 100     # bounded scan for the semantic layer
KEYWORD_SCAN_LIMIT = 200      # per collection, hits are ranked in Python
MAX_QUERY_CHARS = 200
MAX_PAGE_SIZE = 50
ROUTES = {  # frontend destinations, so a result opens the actual record
    "goal": "/goals", "task": "/tasks", "calendar": "/calendar", "project": "/projects",
    "research": "/research", "memory": "/memory-timeline",
    "note": "/editor/notes/{id}", "document": "/editor/documents/{id}",
}


def normalize_query(q: str) -> str:
    return re.sub(r"\s+", " ", (q or "").strip())[:MAX_QUERY_CHARS]


def _plain(text: str) -> str:
    """Rich-text content is stored as HTML; search the visible text only."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def _snippet(text: str, terms: list[str], width: int = 160) -> str:
    text = _plain(text)
    low = text.lower()
    pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=0)
    start = max(0, pos - 40)
    return ("…" if start else "") + text[start:start + width]


def _public_item(doc: dict, fields: list[str], terms: list[str]) -> dict:
    """Never expose embeddings or raw rich-text bodies in search results."""
    out = {k: v for k, v in doc.items() if k not in ("embedding", "user", "body", "content")}
    big = next((f for f in fields if f in ("body", "content", "summary", "description", "notes")), None)
    if big:
        out["snippet"] = _snippet(doc.get(big) or "", terms)
    return out


async def _keyword_hits(db, user_id, type_name, config, terms, query):
    fields = config["fields"]
    clauses = [{f: {"$regex": re.escape(t), "$options": "i"}} for t in terms for f in fields]
    flt = {"user": user_id, "$or": clauses}
    if type_name == "memory":
        flt.update({"archived": {"$ne": True}, "status": {"$ne": "superseded"}})
    docs = await db[config["collection"]].find(flt).sort("updatedAt", -1).to_list(length=KEYWORD_SCAN_LIMIT)
    hits = []
    for d in docs:
        text = _plain(_search_text(d, fields)).lower()
        matched = sum(1 for t in terms if t in text)
        if not matched:
            continue
        title = str(d.get(fields[0]) or "").lower()
        score = 1.0 + matched / len(terms) + (0.5 if query.lower() in title else 0)
        hits.append({"type": type_name, "item": d, "_score": score, "match": "keyword"})
    return hits


async def _semantic_hits(db, user_id, type_name, config, query, query_embedding, skip_ids):
    flt = {"user": user_id}
    if type_name == "memory":
        flt.update({"archived": {"$ne": True}, "status": {"$ne": "superseded"}})
    docs = await db[config["collection"]].find(flt).sort("updatedAt", -1).to_list(length=SEMANTIC_CANDIDATES)
    hits = []
    for d in docs:
        if d["_id"] in skip_ids:
            continue
        text = _plain(_search_text(d, config["fields"]))
        if not text:
            continue
        emb = await _ensure_embedding(config["collection"], d, text)
        score = cosine_similarity(query_embedding, emb) + _lexical_overlap(query, text) * LEXICAL_BOOST
        if score >= SEMANTIC_MIN_SCORE:
            hits.append({"type": type_name, "item": d, "_score": score, "match": "semantic"})
    hits.sort(key=lambda h: h["_score"], reverse=True)
    return hits[:PER_TYPE_LIMIT]


async def run_search(user_id, query, modules=None, limit=20, offset=0, semantic=True, date_from=None, date_to=None):
    """Core of Universal Search; always scoped to `user_id`."""
    db = get_db()
    query = normalize_query(query)
    terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if t]
    if not terms:
        return {"results": [], "total": 0, "limit": limit, "offset": offset}
    selected = {k: v for k, v in SEARCH_CONFIG.items() if not modules or k in modules}
    query_embedding = None
    if semantic:
        try:
            query_embedding = await embed_text(query)
        except Exception:  # semantic layer is optional; keyword search still works
            query_embedding = None
    hits = []
    for type_name, config in selected.items():
        kw = await _keyword_hits(db, user_id, type_name, config, terms, query)
        hits.extend(kw)
        if query_embedding is not None:
            try:
                hits.extend(await _semantic_hits(db, user_id, type_name, config, query, query_embedding, {h["item"]["_id"] for h in kw}))
            except Exception:
                pass
    if date_from or date_to:
        def _in_range(h):
            ts = h["item"].get("startsAt") or h["item"].get("updatedAt") or h["item"].get("createdAt")
            if not isinstance(ts, datetime):
                return False
            ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            return (not date_from or ts >= date_from) and (not date_to or ts < date_to)
        hits = [h for h in hits if _in_range(h)]
    hits.sort(key=lambda h: (h["match"] != "keyword", -h["_score"]))
    page = hits[offset:offset + limit]
    results = []
    for h in page:
        cfg = SEARCH_CONFIG[h["type"]]
        item = _public_item(h["item"], cfg["fields"], terms)
        results.append({
            "type": h["type"], "match": h["match"], "item": item,
            "href": ROUTES[h["type"]].replace("{id}", str(h["item"]["_id"])),
        })
    return {"results": serialize(results), "total": len(hits), "limit": limit, "offset": offset}


def _parse_day(value: str | None, end: bool = False):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must be ISO formatted (YYYY-MM-DD).")
    return d + timedelta(days=1) if end else d


@router.get("")
async def search(
    q: str | None = Query(default=None),
    modules: str | None = Query(default=None, description="comma separated: goal,task,calendar,note,document,research,project,memory"),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    semantic: bool = Query(default=True),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    user: dict = Depends(require_auth),
):
    """Keyword results first (exact, case-insensitive, partial), then clearly
    labelled semantic matches. Only the authenticated user's records."""
    if not normalize_query(q or ""):
        raise HTTPException(status_code=400, detail="q is required.")
    wanted = {m.strip() for m in modules.split(",")} & set(SEARCH_CONFIG) if modules else None
    if modules and not wanted:
        raise HTTPException(status_code=400, detail="Unknown module filter.")
    return await run_search(
        user["_id"], q, wanted, limit, offset, semantic,
        _parse_day(date_from), _parse_day(date_to, end=True),
    )
