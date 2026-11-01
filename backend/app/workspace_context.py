"""
Shared workspace intelligence for IntelliTwin.

This module provides a read-only view across the user's entire workspace.

Agents should use this layer to understand what already exists before
acting. It does not grant mutation permissions.

Workspace modules:
    goals
    tasks
    calendar
    notes
    documents
    research
    projects
    memory

Memory is intentionally retrieved through Echo because Echo owns the
specialized memory lifecycle: semantic retrieval, supersession,
archiving, consolidation, and relevance filtering.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.database import get_db
from app.memory import echo as echo_agent
from app.memory.embeddings import embed_text
from app.memory.vector_store import search as vector_search
from app.modules_config import MODULES
from app.serialization import doc_out, docs_out


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE_MODULES = {
    "goals": {
        "collection": "goals",
        "label": "Goals",
        "title_field": "title",
        "summary_fields": ["title", "description", "status", "progress", "dueDate"],
    },
    "tasks": {
        "collection": "tasks",
        "label": "Tasks",
        "title_field": "title",
        "summary_fields": ["title", "status", "priority", "dueDate", "goal"],
    },
    "calendar": {
        "collection": "calendar_events",
        "label": "Calendar",
        "title_field": "title",
        "summary_fields": ["title", "startsAt", "endsAt", "location", "notes"],
    },
    "notes": {
        "collection": "notes",
        "label": "Notes",
        "title_field": "title",
        "summary_fields": ["title", "body", "pinned"],
    },
    "documents": {
        "collection": "documents",
        "label": "Documents",
        "title_field": "title",
        "summary_fields": ["title", "type", "status", "content"],
    },
    "research": {
        "collection": "research_items",
        "label": "Research",
        "title_field": "query",
        "summary_fields": ["query", "summary", "status", "sources"],
    },
    "projects": {
        "collection": "projects",
        "label": "Projects",
        "title_field": "name",
        "summary_fields": ["name", "description", "status", "goals"],
    },
}


# Keep context compact. The full entities remain available through
# get_workspace_entity/read_* tools when an agent needs them.
DEFAULT_RESULTS_PER_MODULE = 3
MAX_RESULTS_PER_MODULE = 5
MAX_CONTEXT_CHARS = 14000
MAX_FIELD_CHARS = 1200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_limit(value: Any, default: int, maximum: int) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default

    return max(1, min(value, maximum))


def _stringify(value: Any, max_chars: int = MAX_FIELD_CHARS) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        text = ", ".join(_stringify(item, max_chars=500) for item in value)
    elif isinstance(value, dict):
        parts = []

        for key, item in value.items():
            parts.append(
                f"{key}: {_stringify(item, max_chars=500)}"
            )

        text = "; ".join(parts)
    else:
        text = str(value)

    text = text.strip()

    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."

    return text


def _entity_title(module_key: str, document: dict) -> str:
    config = WORKSPACE_MODULES[module_key]
    field = config["title_field"]

    return _stringify(
        document.get(field) or f"{config['label']} item"
    )


def _entity_summary(module_key: str, document: dict) -> str:
    config = WORKSPACE_MODULES[module_key]

    parts = []

    for field in config["summary_fields"]:
        value = document.get(field)

        if value in (None, "", [], {}):
            continue

        parts.append(
            f"{field}={_stringify(value)}"
        )

    return " | ".join(parts)


def _serializable_entity(
    module_key: str,
    document: dict,
    relevance: float | None = None,
) -> dict:
    """
    Return a compact, model-safe workspace entity representation.

    The complete entity can still be fetched by ID.
    """
    entity_id = document.get("_id")

    result = {
        "type": module_key,
        "id": str(entity_id) if entity_id is not None else None,
        "title": _entity_title(module_key, document),
        "summary": _entity_summary(module_key, document),
    }

    if relevance is not None:
        result["relevance"] = round(float(relevance), 4)

    return result


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------

async def _semantic_search_module(
    user: dict,
    module_key: str,
    query_embedding: list[float],
    limit: int,
) -> list[dict]:
    """
    Semantic search one workspace module.

    Missing embeddings are simply ignored. The generic CRUD router gradually
    creates embeddings for configured modules, while agent-created records
    already embed themselves.
    """
    config = WORKSPACE_MODULES[module_key]

    try:
        hits = await vector_search(
            config["collection"],
            user["_id"],
            query_embedding,
            limit=limit,
        )
    except Exception:
        return []

    results = []

    for hit in hits:
        document = dict(hit.doc)

        # Memory is not searched through this function.
        # This function only handles the regular workspace modules.
        results.append(
            _serializable_entity(
                module_key,
                document,
                relevance=hit.score,
            )
        )

    return results


async def search_workspace(
    user: dict,
    query: str,
    *,
    limit_per_module: int = DEFAULT_RESULTS_PER_MODULE,
) -> list[dict]:
    """
    Search the entire workspace semantically.

    Returns compact entities from all regular workspace modules plus Echo
    memory results.

    The same query embedding is reused across modules.
    """
    query = (query or "").strip()

    if not query:
        return []

    limit = _safe_limit(
        limit_per_module,
        DEFAULT_RESULTS_PER_MODULE,
        MAX_RESULTS_PER_MODULE,
    )

    query_embedding = await embed_text(query)

    module_keys = list(WORKSPACE_MODULES.keys())

    tasks = [
        _semantic_search_module(
            user,
            module_key,
            query_embedding,
            limit,
        )
        for module_key in module_keys
    ]

    module_results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    results = []

    for module_key, module_result in zip(
        module_keys,
        module_results,
    ):
        if isinstance(module_result, Exception):
            continue

        results.extend(module_result)

    # Echo memory uses its own retrieval rules.
    try:
        memories = await echo_agent.search_memory(
            user,
            query,
            limit=limit,
        )
    except Exception:
        memories = []

    for memory in memories:
        results.append(
            {
                "type": "memory",
                "id": str(memory.get("_id")),
                "title": memory.get("title", "Memory"),
                "summary": _stringify(
                    memory.get("content", "")
                ),
                "relevance": memory.get("relevance", 0),
            }
        )

    # Highest semantic relevance first.
    results.sort(
        key=lambda item: item.get("relevance", 0),
        reverse=True,
    )

    return results


# ---------------------------------------------------------------------------
# Recent workspace state
# ---------------------------------------------------------------------------

async def _recent_collection(
    user: dict,
    module_key: str,
    limit: int,
) -> list[dict]:
    config = WORKSPACE_MODULES[module_key]

    try:
        items = (
            await get_db()[config["collection"]]
            .find(
                {
                    "user": user["_id"],
                }
            )
            .sort("updatedAt", -1)
            .to_list(length=limit)
        )
    except Exception:
        return []

    return [
        _serializable_entity(
            module_key,
            item,
        )
        for item in items
    ]


async def get_recent_workspace_activity(
    user: dict,
    *,
    limit_per_module: int = 3,
) -> list[dict]:
    """
    Return recent items across the user's workspace.

    This is chronological workspace awareness rather than semantic search.
    """
    limit = _safe_limit(
        limit_per_module,
        3,
        5,
    )

    module_keys = list(WORKSPACE_MODULES.keys())

    results = await asyncio.gather(
        *[
            _recent_collection(
                user,
                module_key,
                limit,
            )
            for module_key in module_keys
        ],
        return_exceptions=True,
    )

    activity = []

    for module_key, module_result in zip(
        module_keys,
        results,
    ):
        if isinstance(module_result, Exception):
            continue

        activity.extend(module_result)

    # Sort by the database timestamp when available.
    # The compact representation intentionally does not expose every field,
    # so this is only a secondary ordering step. MongoDB already returned
    # each collection in recent order.
    return activity


# ---------------------------------------------------------------------------
# Exact entity lookup
# ---------------------------------------------------------------------------

async def get_workspace_entity(
    user: dict,
    entity_type: str,
    entity_id: str,
) -> dict | None:
    """
    Retrieve one exact workspace entity by module and ID.

    Memory is delegated to Echo's memory collection because memory has its
    own lifecycle rules.
    """
    entity_type = (entity_type or "").strip().lower()

    if entity_type == "memory":
        try:
            from bson import ObjectId

            oid = ObjectId(entity_id)
        except Exception:
            return None

        document = await get_db().memory_entries.find_one(
            {
                "_id": oid,
                "user": user["_id"],
                "archived": {"$ne": True},
                "status": {"$ne": "superseded"},
            }
        )

        if not document:
            return None

        return doc_out(document)

    config = WORKSPACE_MODULES.get(entity_type)

    if not config:
        return None

    try:
        from bson import ObjectId

        oid = ObjectId(entity_id)
    except Exception:
        return None

    document = await get_db()[config["collection"]].find_one(
        {
            "_id": oid,
            "user": user["_id"],
        }
    )

    if not document:
        return None

    return doc_out(document)


# ---------------------------------------------------------------------------
# Workspace context
# ---------------------------------------------------------------------------

def _format_entity(entity: dict) -> str:
    entity_type = entity.get("type", "workspace")
    title = entity.get("title", "")
    summary = entity.get("summary", "")
    relevance = entity.get("relevance")

    line = f"- [{entity_type}] {title}"

    if summary:
        line += f": {summary}"

    if relevance is not None:
        line += f" (relevance={relevance})"

    return line


async def build_workspace_context(
    user: dict,
    query: str | None = None,
    *,
    semantic_limit: int = 3,
    recent_limit: int = 2,
) -> str:
    """
    Build a compact workspace snapshot suitable for an LLM system prompt.

    If a query is supplied:
        1. relevant workspace entities are retrieved semantically
        2. recent workspace state is added as supporting context

    The result is deliberately compact. Agents can use exact read tools to
    retrieve full documents/research/tasks when needed.
    """
    query = (query or "").strip()

    sections: list[str] = []

    if query:
        relevant = await search_workspace(
            user,
            query,
            limit_per_module=semantic_limit,
        )

        if relevant:
            grouped: dict[str, list[dict]] = {}

            for entity in relevant:
                grouped.setdefault(
                    entity["type"],
                    [],
                ).append(entity)

            sections.append(
                "RELEVANT WORKSPACE CONTEXT"
            )

            for module_key, entities in grouped.items():
                label = WORKSPACE_MODULES.get(
                    module_key,
                    {},
                ).get(
                    "label",
                    module_key.title(),
                )

                sections.append(
                    f"{label}:"
                )

                for entity in entities:
                    sections.append(
                        _format_entity(entity)
                    )

    recent = await get_recent_workspace_activity(
        user,
        limit_per_module=recent_limit,
    )

    if recent:
        sections.append(
            "RECENT WORKSPACE ACTIVITY"
        )

        # Keep the snapshot bounded.
        for entity in recent[:18]:
            sections.append(
                _format_entity(entity)
            )

    context = "\n".join(sections).strip()

    if not context:
        return (
            "WORKSPACE CONTEXT\n"
            "No relevant workspace information was found."
        )

    if len(context) > MAX_CONTEXT_CHARS:
        context = (
            context[:MAX_CONTEXT_CHARS]
            .rstrip()
            + "\n[Workspace context truncated. "
              "Use workspace read tools for more detail.]"
        )

    return context