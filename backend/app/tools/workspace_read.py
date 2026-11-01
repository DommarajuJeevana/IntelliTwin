"""
Shared read-only workspace tools.

Every IntelliTwin agent can use these tools.

These tools never mutate workspace data. Mutation remains controlled by
the specialized agent tools in workspace.py and memory_tools.py.
"""

from app.tools.base import Tool
from app.workspace_context import (
    build_workspace_context,
    get_recent_workspace_activity,
    get_workspace_entity,
    search_workspace,
)


async def _search_workspace(
    user: dict,
    args: dict,
) -> dict:
    query = (args.get("query") or "").strip()

    if not query:
        return {
            "error": "query is required."
        }

    try:
        limit = int(args.get("limit", 3))
    except (TypeError, ValueError):
        limit = 3

    limit = max(1, min(limit, 5))

    results = await search_workspace(
        user,
        query,
        limit_per_module=limit,
    )

    return {
        "query": query,
        "results": results,
    }


async def _get_workspace_context(
    user: dict,
    args: dict,
) -> dict:
    query = (args.get("query") or "").strip()

    context = await build_workspace_context(
        user,
        query=query,
    )

    return {
        "context": context,
    }


async def _get_workspace_entity(
    user: dict,
    args: dict,
) -> dict:
    entity_type = (
        args.get("entity_type") or ""
    ).strip()

    entity_id = (
        args.get("entity_id") or ""
    ).strip()

    if not entity_type or not entity_id:
        return {
            "error": (
                "entity_type and entity_id "
                "are required."
            )
        }

    entity = await get_workspace_entity(
        user,
        entity_type,
        entity_id,
    )

    if entity is None:
        return {
            "error": (
                f"No {entity_type} found with "
                f"id {entity_id!r}."
            )
        }

    return {
        "entity_type": entity_type,
        "entity": entity,
    }


async def _get_recent_activity(
    user: dict,
    args: dict,
) -> dict:
    try:
        limit = int(args.get("limit", 3))
    except (TypeError, ValueError):
        limit = 3

    limit = max(1, min(limit, 5))

    activity = await get_recent_workspace_activity(
        user,
        limit_per_module=limit,
    )

    return {
        "items": activity,
    }


SEARCH_WORKSPACE = Tool(
    name="search_workspace",
    description=(
        "Search the user's entire IntelliTwin workspace "
        "for information relevant to a query. This searches "
        "goals, tasks, calendar, notes, documents, research, "
        "projects, and Echo memory. Use this "
        "when the user's request refers to something that may "
        "already exist somewhere in the workspace."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The topic, entity, or information "
                    "to find across the workspace."
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": (
                    "Maximum results per workspace "
                    "module."
                ),
            },
        },
        "required": ["query"],
    },
    handler=_search_workspace,
)


GET_WORKSPACE_CONTEXT = Tool(
    name="get_workspace_context",
    description=(
        "Get a compact snapshot of the user's relevant "
        "workspace state. Use this when you need to understand "
        "what the user currently has across goals, tasks, "
        "calendar, notes, documents, research, projects, "
        "and memory."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Optional topic to focus the workspace "
                    "context on."
                ),
            },
        },
    },
    handler=_get_workspace_context,
)


GET_WORKSPACE_ENTITY = Tool(
    name="get_workspace_entity",
    description=(
        "Retrieve one exact workspace entity by its type "
        "and ID. Use this after search_workspace identifies "
        "a specific document, research item, goal, task, "
        "project, note, calendar event, or "
        "memory that needs full details."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "entity_type": {
                "type": "string",
                "enum": [
                    "goals",
                    "tasks",
                    "calendar",
                    "notes",
                    "documents",
                    "research",
                    "projects",
                    "memory",
                ],
            },
            "entity_id": {
                "type": "string",
                "description": (
                    "The MongoDB ID of the workspace entity."
                ),
            },
        },
        "required": [
            "entity_type",
            "entity_id",
        ],
    },
    handler=_get_workspace_entity,
)


GET_RECENT_WORKSPACE_ACTIVITY = Tool(
    name="get_recent_workspace_activity",
    description=(
        "Read recent activity across the user's workspace. "
        "Use this for requests such as what the user has "
        "been working on recently, what is active, or what "
        "was recently created or updated."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
            },
        },
    },
    handler=_get_recent_activity,
)


WORKSPACE_READ_TOOLS = [
    SEARCH_WORKSPACE,
    GET_WORKSPACE_CONTEXT,
    GET_WORKSPACE_ENTITY,
    GET_RECENT_WORKSPACE_ACTIVITY,
]