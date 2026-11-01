"""
Phase 5 - Echo's operations exposed as Claude tools.

Thin wrappers around app/memory/echo.py so any agent (Echo itself, but also
Compass/Atlas/Nova once they're given this tool) can search or write memory
mid-conversation instead of only receiving memory as pre-fetched context
(that's what Phase 4's with_context() still does for the initial prompt -
these tools let an agent go back for *more*, or write something new, while
it's reasoning).
"""
from app.memory import echo as echo_agent
from app.tools.base import Tool


def _as_int(value, default):
    try:
        return max(1, min(int(float(value)), 20))
    except (TypeError, ValueError):
        return default


async def _save_memory(user: dict, args: dict) -> dict:
    entry = await echo_agent.remember(
        user, note=args.get("content"), importance=args.get("importance")
    )
    return entry or {"saved": False}


async def _search_memory(user: dict, args: dict) -> dict:
    items = await echo_agent.search_memory(user, args.get("query", ""), limit=_as_int(args.get("limit"), 5))
    return {"items": items}


async def _update_memory(user: dict, args: dict) -> dict:
    updated = await echo_agent.update_memory(
        user,
        args["memory_id"],
        {"title": args.get("title"), "content": args.get("content"), "importance": args.get("importance")},
    )
    if updated is None:
        return {"error": f"No memory found with id {args.get('memory_id')!r}."}
    return updated


async def _delete_memory(user: dict, args: dict) -> dict:
    ok = await echo_agent.delete_memory(user, args["memory_id"])
    return {"archived": ok}


async def _restore_memory(user: dict, args: dict) -> dict:
    restored = await echo_agent.restore_memory(user, args["memory_id"])
    if restored is None:
        return {"error": f"No archived memory found with id {args.get('memory_id')!r}."}
    return restored


SAVE_MEMORY = Tool(
    name="save_memory",
    description="Store only durable, useful user information: stable preferences, personal facts, long-term goals, ongoing commitments, or meaningful emotional patterns. Never save greetings, questions, raw conversation, one-off tasks, assistant summaries, or duplicates. For emotional memories, include only the user-stated emotion, trigger/cause, and helpful response when known.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "What to remember, written in third person about the user."},
            "importance": {"type": "integer", "minimum": 1, "maximum": 5, "description": "1 (minor) to 5 (critical). Optional."},
        },
        "required": ["content"],
    },
    handler=_save_memory,
)

SEARCH_MEMORY = Tool(
    name="search_memory",
    description="Semantically search the user's stored memories for ones relevant to a query.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Max results. Defaults to 5."},
        },
        "required": ["query"],
    },
    handler=_search_memory,
)

UPDATE_MEMORY = Tool(
    name="update_memory",
    description="Edit an existing memory entry (correct it, add detail, or bump/lower its importance).",
    input_schema={
        "type": "object",
        "properties": {
            "memory_id": {"type": "string", "description": "The _id of the memory entry to edit."},
            "title": {"type": "string"},
            "content": {"type": "string"},
            "importance": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        "required": ["memory_id"],
    },
    handler=_update_memory,
)

DELETE_MEMORY = Tool(
    name="delete_memory",
    description=(
        "Archive a memory entry, e.g. because it's outdated or was wrong. This is "
        "reversible (it can be restored with restore_memory) - it does not "
        "permanently erase anything."
    ),
    input_schema={
        "type": "object",
        "properties": {"memory_id": {"type": "string", "description": "The _id of the memory entry to archive."}},
        "required": ["memory_id"],
    },
    handler=_delete_memory,
)

RESTORE_MEMORY = Tool(
    name="restore_memory",
    description="Un-archive a memory entry that was previously removed with delete_memory.",
    input_schema={
        "type": "object",
        "properties": {"memory_id": {"type": "string", "description": "The _id of the archived memory entry to restore."}},
        "required": ["memory_id"],
    },
    handler=_restore_memory,
)

ALL = [
    SAVE_MEMORY,
    SEARCH_MEMORY,
    UPDATE_MEMORY,
    DELETE_MEMORY,
    RESTORE_MEMORY,
]

ECHO_TOOLS = ALL