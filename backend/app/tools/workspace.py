"""
Phase 5 - workspace tools.

Read/write access to goals, tasks, calendar events, documents, and research
items. These tools allow Compass, Atlas, and Nova to act on IntelliTwin's
workspace instead of only generating text.

Agent-created semantic workspace items are embedded immediately after
creation/update so they can participate in universal semantic search.
"""

import re

from bson import ObjectId
from pymongo import ReturnDocument

from app.database import get_db
from app.memory.embeddings import embed_text
from app.memory.vector_store import upsert_embedding
from app.owned import new_owned_doc, now_utc, parse_date
from app.serialization import doc_out, docs_out
from app.tools.base import Tool


def _oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


async def _embed_document(
    collection_name: str,
    document: dict,
    fields: list[str],
) -> None:
    """
    Generate and store an embedding for a workspace document.

    Embedding failures are intentionally ignored because semantic search
    should never prevent the underlying workspace operation from succeeding.
    """
    try:
        text = " ".join(
            str(document.get(field) or "")
            for field in fields
        ).strip()

        if not text:
            return

        embedding = await embed_text(text)

        await upsert_embedding(
            collection_name,
            document["_id"],
            embedding,
        )

        document["embedding"] = embedding

    except Exception:
        pass


# ---------------------------------------------------------------- Compass --


async def _read_goal(user: dict, args: dict) -> dict:
    db = get_db()
    goal_id = args.get("goal_id")

    if goal_id:
        oid = _oid(goal_id)

        if not oid:
            return {
                "error": f"Invalid goal_id {goal_id!r}."
            }

        goal = await db.goals.find_one(
            {
                "_id": oid,
                "user": user["_id"],
            }
        )

        if not goal:
            return {
                "error": f"No goal found with id {goal_id!r}."
            }

        return {
            "goal": doc_out(goal)
        }

    goals = (
        await db.goals.find(
            {
                "user": user["_id"],
            }
        )
        .sort("createdAt", -1)
        .to_list(length=20)
    )

    return {
        "goals": docs_out(goals)
    }


async def _create_goal(user: dict, args: dict) -> dict:
    title = (args.get("title") or "").strip()

    if not title:
        return {
            "error": "title is required."
        }

    db = get_db()

    goal = new_owned_doc(
        user["_id"],
        agent="compass",
    )

    goal.update(
        {
            "title": title,
            "description": args.get(
                "description",
                "",
            ),
            "status": args.get(
                "status",
                "not_started",
            ),
            "progress": int(
                args.get(
                    "progress",
                    0,
                )
            ),
            "dueDate": parse_date(
                args.get("dueDate")
            ),
        }
    )

    result = await db.goals.insert_one(goal)

    goal["_id"] = result.inserted_id

    await _embed_document(
        "goals",
        goal,
        [
            "title",
            "description",
        ],
    )

    return {
        "goal": doc_out(goal)
    }


async def _read_tasks(user: dict, args: dict) -> dict:
    db = get_db()

    filt: dict = {
        "user": user["_id"]
    }

    goal_id = args.get("goal_id")

    if goal_id:
        goal_oid = _oid(goal_id)

        if not goal_oid:
            return {
                "error": (
                    f"Invalid goal_id "
                    f"{goal_id!r}."
                )
            }

        if not await db.goals.find_one(
            {
                "_id": goal_oid,
                "user": user["_id"],
            }
        ):
            return {
                "error": (
                    f"No goal found with id "
                    f"{goal_id!r}."
                )
            }

        filt["goal"] = goal_oid

    status = args.get("status")

    if status:
        filt["status"] = status

    limit = min(
        int(args.get("limit", 20)),
        50,
    )

    tasks = (
        await db.tasks.find(filt)
        .sort("createdAt", -1)
        .to_list(length=limit)
    )

    return {
        "tasks": docs_out(tasks)
    }


async def _create_task(user: dict, args: dict) -> dict:
    if not args.get("title"):
        return {
            "error": "title is required."
        }

    db = get_db()

    goal_oid = None

    if args.get("goal_id"):
        goal_oid = _oid(args["goal_id"])

        if (
            not goal_oid
            or not await db.goals.find_one(
                {
                    "_id": goal_oid,
                    "user": user["_id"],
                }
            )
        ):
            return {
                "error": (
                    f"Invalid or unknown goal_id "
                    f"{args.get('goal_id')!r}."
                )
            }

    task = new_owned_doc(
        user["_id"],
        agent="compass",
    )

    task.update(
        {
            "title": args["title"],
            "goal": goal_oid,
            "status": args.get(
                "status",
                "todo",
            ),
            "priority": args.get(
                "priority",
                "medium",
            ),
            "dueDate": parse_date(
                args.get("dueDate")
            ),
        }
    )

    result = await db.tasks.insert_one(task)

    task["_id"] = result.inserted_id

    await _embed_document(
        "tasks",
        task,
        ["title"],
    )

    return {
        "task": doc_out(task)
    }


async def _update_task(user: dict, args: dict) -> dict:
    oid = _oid(
        args.get(
            "task_id",
            "",
        )
    )

    if not oid:
        return {
            "error": (
                f"Invalid task_id "
                f"{args.get('task_id')!r}."
            )
        }

    updates: dict = {
        "updatedAt": now_utc()
    }

    for field in (
        "title",
        "status",
        "priority",
    ):
        if args.get(field) is not None:
            updates[field] = args[field]

    if "dueDate" in args:
        updates["dueDate"] = parse_date(
            args["dueDate"]
        )

    if "goal_id" in args:
        goal_id = args.get("goal_id")

        if goal_id:
            goal_oid = _oid(goal_id)

            if (
                not goal_oid
                or not await get_db().goals.find_one(
                    {
                        "_id": goal_oid,
                        "user": user["_id"],
                    }
                )
            ):
                return {
                    "error": (
                        f"Invalid or unknown goal_id "
                        f"{goal_id!r}."
                    )
                }

            updates["goal"] = goal_oid
        else:
            updates["goal"] = None

    db = get_db()

    updated = await db.tasks.find_one_and_update(
        {
            "_id": oid,
            "user": user["_id"],
        },
        {
            "$set": updates
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated:
        return {
            "error": (
                f"No task found with id "
                f"{args.get('task_id')!r}."
            )
        }

    await _embed_document(
        "tasks",
        updated,
        ["title"],
    )

    return {
        "task": doc_out(updated)
    }


async def _read_calendar(
    user: dict,
    args: dict,
) -> dict:
    db = get_db()

    filt: dict = {
        "user": user["_id"],
    }

    from_value = args.get("from")
    to_value = args.get("to")
    on_value = args.get("date") or args.get("on")

    if on_value:
        # A single local date: [00:00, next 00:00) in the user's timezone.
        from app.date_range import resolve_date_range, to_query
        from app.owned import get_user_tz

        rng = resolve_date_range(str(on_value), get_user_tz(user))
        if not rng:
            return {"error": f"Could not parse date {on_value!r}."}
        filt["startsAt"] = to_query(rng)
    else:
        parsed_from = parse_date(from_value) if from_value else None
        parsed_to = parse_date(to_value) if to_value else None
        if from_value and not parsed_from:
            return {"error": f"Could not parse from date {from_value!r}."}
        if to_value and not parsed_to:
            return {"error": f"Could not parse to date {to_value!r}."}
        if parsed_from:
            filt.setdefault("startsAt", {})["$gte"] = parsed_from
        if parsed_to:
            # "to" is exclusive so adjacent days never overlap.
            from app.date_range import exclusive_end
            from app.owned import get_user_tz

            filt.setdefault("startsAt", {})["$lt"] = exclusive_end(parsed_to, get_user_tz(user))

    try:
        limit = min(
            int(args.get("limit", 20)),
            50,
        )
    except (TypeError, ValueError):
        limit = 20

    events = (
        await db.calendar_events.find(filt)
        .sort("startsAt", 1)
        .to_list(length=limit)
    )

    return {
        "events": docs_out(events)
    }


async def _create_schedule(user: dict, args: dict) -> dict:
    """Create a calendar event through the same path as the Calendar page
    (conflict check, reminders, embeddings) so agent-made events actually
    show up and behave like user-made ones."""
    if not args.get("title") or not args.get("startsAt"):
        return {"error": "title and startsAt are required."}

    from app.tools.workspace_universal import _run as workspace_crud

    if not parse_date(args["startsAt"]):
        return {"error": f"Could not parse startsAt {args['startsAt']!r} as a date. Use ISO format like 2026-10-13T15:00:00."}

    result = await workspace_crud(
        user,
        {
            "module": "calendar",
            "action": "create",
            "agent": "compass",
            "data": {
                "title": args["title"],
                "startsAt": args["startsAt"],
                "endsAt": args.get("endsAt"),
                "location": args.get("location", ""),
                "notes": args.get("notes", ""),
            },
        },
    )
    if result.get("error"):
        return result
    return {"event": result["item"], "created": True}


async def _update_goal(user: dict, args: dict) -> dict:
    oid = _oid(
        args.get(
            "goal_id",
            "",
        )
    )

    if not oid:
        return {
            "error": (
                f"Invalid goal_id "
                f"{args.get('goal_id')!r}."
            )
        }

    updates: dict = {
        "updatedAt": now_utc()
    }

    for field in (
        "title",
        "description",
        "status",
        "progress",
    ):
        if args.get(field) is not None:
            updates[field] = args[field]

    if "dueDate" in args:
        updates["dueDate"] = parse_date(
            args["dueDate"]
        )

    db = get_db()

    updated = await db.goals.find_one_and_update(
        {
            "_id": oid,
            "user": user["_id"],
        },
        {
            "$set": updates
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated:
        return {
            "error": (
                f"No goal found with id "
                f"{args.get('goal_id')!r}."
            )
        }

    await _embed_document(
        "goals",
        updated,
        [
            "title",
            "description",
        ],
    )

    return {
        "goal": doc_out(updated)
    }


READ_GOAL = Tool(
    name="read_goal",
    description=(
        "Read one goal by id, or list the user's "
        "recent goals if no id is given."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "goal_id": {
                "type": "string",
                "description": (
                    "Optional. Omit to list recent "
                    "goals instead."
                ),
            }
        },
    },
    handler=_read_goal,
)


CREATE_GOAL = Tool(
    name="create_goal",
    description=(
        "Create a new goal in the user's workspace. "
        "Use this when the user explicitly asks to create "
        "or establish a new goal."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short name of the goal.",
            },
            "description": {
                "type": "string",
                "description": "Optional description of the goal.",
            },
            "status": {
                "type": "string",
                "enum": [
                    "not_started",
                    "in_progress",
                    "done",
                ],
            },
            "progress": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "dueDate": {
                "type": "string",
                "description": "Optional ISO date.",
            },
        },
        "required": ["title"],
    },
    handler=_create_goal,
)


READ_TASKS = Tool(
    name="read_tasks",
    description=(
        "List the user's tasks, optionally filtered by goal "
        "or status. Use this before modifying existing tasks."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "goal_id": {
                "type": "string",
                "description": "Optional goal _id.",
            },
            "status": {
                "type": "string",
                "description": "Optional task status filter.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
            },
        },
    },
    handler=_read_tasks,
)


CREATE_TASK = Tool(
    name="create_task",
    description=(
        "Create a new task, optionally attached to a goal."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string"
            },
            "goal_id": {
                "type": "string",
                "description": (
                    "Optional goal _id to attach this task to."
                ),
            },
            "priority": {
                "type": "string",
                "enum": [
                    "low",
                    "medium",
                    "high",
                ],
            },
            "status": {
                "type": "string",
                "description": "Optional task status.",
            },
            "dueDate": {
                "type": "string",
                "description": "Optional ISO date.",
            },
        },
        "required": ["title"],
    },
    handler=_create_task,
)


UPDATE_TASK = Tool(
    name="update_task",
    description=(
        "Update an existing task's title, status, priority, "
        "due date, or goal. Use read_tasks first when the "
        "task id is not already known."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string"
            },
            "title": {
                "type": "string"
            },
            "status": {
                "type": "string"
            },
            "priority": {
                "type": "string",
                "enum": [
                    "low",
                    "medium",
                    "high",
                ],
            },
            "dueDate": {
                "type": "string"
            },
            "goal_id": {
                "type": "string",
                "description": (
                    "Optional goal id. Set to null to detach "
                    "the task from its current goal."
                ),
            },
        },
        "required": ["task_id"],
    },
    handler=_update_task,
)


READ_CALENDAR = Tool(
    name="read_calendar",
    description=(
        "Read/list the user's saved calendar events. Use this tool whenever "
        "the user asks what meetings, appointments, or events they have, "
        "including today, tomorrow, a named date, or a date range. For a "
        "specific day, provide both 'from' and 'to' as ISO-8601 local-time "
        "boundaries for the start and end of that day, including the user's "
        "UTC offset when known. Do not guess event details; answer from the "
        "returned events. If no date range is requested, it may list recent "
        "upcoming events."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "from": {
                "type": "string",
                "description": (
                    "Inclusive ISO-8601 start boundary for filtering events. "
                    "For today/tomorrow, use the beginning of that local day "
                    "with the correct UTC offset. Optional."
                ),
            },
            "to": {
                "type": "string",
                "description": (
                    "Inclusive ISO-8601 end boundary for filtering events. "
                    "For today/tomorrow, use the end of that local day "
                    "with the correct UTC offset. Optional."
                ),
            },
            "date": {
                "type": "string",
                "description": (
                    "A single local date (YYYY-MM-DD, 'today', 'tomorrow'). "
                    "Preferred for one-day queries; overrides from/to."
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
            },
        },
    },
    handler=_read_calendar,
)


CREATE_SCHEDULE = Tool(
    name="create_schedule",
    description="Create a new calendar event.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string"
            },
            "startsAt": {
                "type": "string",
                "description": "ISO date/time.",
            },
            "endsAt": {
                "type": "string",
                "description": (
                    "Optional ISO date/time."
                ),
            },
            "location": {
                "type": "string"
            },
            "notes": {
                "type": "string"
            },
        },
        "required": [
            "title",
            "startsAt",
        ],
    },
    handler=_create_schedule,
)


UPDATE_GOAL = Tool(
    name="update_goal",
    description=(
        "Update a goal's title, description, status, "
        "progress, or due date."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "goal_id": {
                "type": "string"
            },
            "title": {
                "type": "string"
            },
            "description": {
                "type": "string"
            },
            "status": {
                "type": "string",
                "enum": [
                    "not_started",
                    "in_progress",
                    "done",
                ],
            },
            "progress": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "dueDate": {
                "type": "string"
            },
        },
        "required": ["goal_id"],
    },
    handler=_update_goal,
)


COMPASS_WORKSPACE_TOOLS = [
    READ_GOAL,
    CREATE_GOAL,
    READ_TASKS,
    CREATE_TASK,
    UPDATE_TASK,
    READ_CALENDAR,
    CREATE_SCHEDULE,
    UPDATE_GOAL,
]


# ------------------------------------------------------------------ Atlas --


async def _search_documents(
    user: dict,
    args: dict,
) -> dict:
    query = args.get(
        "query",
        "",
    )

    if not query:
        return {
            "error": "query is required."
        }

    db = get_db()

    rx = {
        "$regex": re.escape(query),
        "$options": "i",
    }

    limit = min(
        int(args.get("limit", 5)),
        20,
    )

    docs = (
        await db.documents.find(
            {
                "user": user["_id"],
                "$or": [
                    {
                        "title": rx
                    },
                    {
                        "content": rx
                    },
                ],
            }
        )
        .sort("createdAt", -1)
        .to_list(length=limit)
    )

    return {
        "documents": docs_out(docs)
    }


async def _save_research(
    user: dict,
    args: dict,
) -> dict:
    if (
        not args.get("query")
        or not args.get("summary")
    ):
        return {
            "error": (
                "query and summary are required."
            )
        }

    db = get_db()

    item = new_owned_doc(
        user["_id"],
        agent="atlas",
    )

    item.update(
        {
            "query": args["query"],
            "summary": args["summary"],
            "sources": args.get(
                "sources",
                [],
            ),
            "status": "complete",
        }
    )

    result = await db.research_items.insert_one(
        item
    )

    item["_id"] = result.inserted_id

    await _embed_document(
        "research_items",
        item,
        [
            "query",
            "summary",
        ],
    )

    return {
        "item": doc_out(item)
    }


async def _link_research_to_goal(
    user: dict,
    args: dict,
) -> dict:
    research_oid = _oid(
        args.get(
            "research_id",
            "",
        )
    )

    goal_oid = _oid(
        args.get(
            "goal_id",
            "",
        )
    )

    if not research_oid or not goal_oid:
        return {
            "error": (
                "Valid research_id and goal_id "
                "are required."
            )
        }

    db = get_db()

    if not await db.goals.find_one(
        {
            "_id": goal_oid,
            "user": user["_id"],
        }
    ):
        return {
            "error": (
                f"No goal found with id "
                f"{args.get('goal_id')!r}."
            )
        }

    updated = await db.research_items.find_one_and_update(
        {
            "_id": research_oid,
            "user": user["_id"],
        },
        {
            "$set": {
                "goal": goal_oid,
                "updatedAt": now_utc(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated:
        return {
            "error": (
                f"No research item found with id "
                f"{args.get('research_id')!r}."
            )
        }

    return {
        "item": doc_out(updated)
    }


SEARCH_DOCUMENTS = Tool(
    name="search_documents",
    description=(
        "Keyword search over the user's documents "
        "(title and content)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string"
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    },
    handler=_search_documents,
)


SAVE_RESEARCH = Tool(
    name="save_research",
    description=(
        "Save a completed piece of research "
        "(query, summary, and any sources) as a research item."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string"
            },
            "summary": {
                "type": "string"
            },
            "sources": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": (
                    "Optional list of source URLs or citations."
                ),
            },
        },
        "required": [
            "query",
            "summary",
        ],
    },
    handler=_save_research,
)


LINK_RESEARCH_TO_GOAL = Tool(
    name="link_research_to_goal",
    description=(
        "Attach a saved research item to one of "
        "the user's goals."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "research_id": {
                "type": "string"
            },
            "goal_id": {
                "type": "string"
            },
        },
        "required": [
            "research_id",
            "goal_id",
        ],
    },
    handler=_link_research_to_goal,
)


# ------------------------------------------------------------------- Nova --


async def _read_research(
    user: dict,
    args: dict,
) -> dict:
    db = get_db()

    research_id = args.get(
        "research_id"
    )

    if research_id:
        oid = _oid(research_id)

        if not oid:
            return {
                "error": (
                    f"Invalid research_id "
                    f"{research_id!r}."
                )
            }

        item = await db.research_items.find_one(
            {
                "_id": oid,
                "user": user["_id"],
            }
        )

        if not item:
            return {
                "error": (
                    f"No research item found with id "
                    f"{research_id!r}."
                )
            }

        return {
            "item": doc_out(item)
        }

    items = (
        await db.research_items.find(
            {
                "user": user["_id"],
            }
        )
        .sort("createdAt", -1)
        .to_list(length=10)
    )

    return {
        "items": docs_out(items)
    }


async def _read_documents(
    user: dict,
    args: dict,
) -> dict:
    db = get_db()

    document_id = args.get(
        "document_id"
    )

    if document_id:
        oid = _oid(document_id)

        if not oid:
            return {
                "error": (
                    f"Invalid document_id "
                    f"{document_id!r}."
                )
            }

        item = await db.documents.find_one(
            {
                "_id": oid,
                "user": user["_id"],
            }
        )

        if not item:
            return {
                "error": (
                    f"No document found with id "
                    f"{document_id!r}."
                )
            }

        return {
            "document": doc_out(item)
        }

    items = (
        await db.documents.find(
            {
                "user": user["_id"],
            }
        )
        .sort("createdAt", -1)
        .to_list(length=10)
    )

    return {
        "documents": docs_out(items)
    }


async def _create_document(
    user: dict,
    args: dict,
) -> dict:
    if not args.get("title"):
        return {
            "error": "title is required."
        }

    db = get_db()

    doc = new_owned_doc(
        user["_id"],
        agent="nova",
    )

    doc.update(
        {
            "title": args["title"],
            "type": args.get(
                "type",
                "draft",
            ),
            "content": args.get(
                "content",
                "",
            ),
            "status": "draft",
        }
    )

    result = await db.documents.insert_one(
        doc
    )

    doc["_id"] = result.inserted_id

    await _embed_document(
        "documents",
        doc,
        [
            "title",
            "content",
        ],
    )

    return {
        "document": doc_out(doc)
    }


async def _update_document(
    user: dict,
    args: dict,
) -> dict:
    oid = _oid(
        args.get(
            "document_id",
            "",
        )
    )

    if not oid:
        return {
            "error": (
                f"Invalid document_id "
                f"{args.get('document_id')!r}."
            )
        }

    updates: dict = {
        "updatedAt": now_utc()
    }

    for field in (
        "title",
        "content",
        "type",
        "status",
    ):
        if args.get(field) is not None:
            updates[field] = args[field]

    db = get_db()

    updated = await db.documents.find_one_and_update(
        {
            "_id": oid,
            "user": user["_id"],
        },
        {
            "$set": updates
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated:
        return {
            "error": (
                f"No document found with id "
                f"{args.get('document_id')!r}."
            )
        }

    await _embed_document(
        "documents",
        updated,
        [
            "title",
            "content",
        ],
    )

    return {
        "document": doc_out(updated)
    }


READ_RESEARCH = Tool(
    name="read_research",
    description=(
        "Read one research item by id, or list "
        "recent research items if no id is given."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "research_id": {
                "type": "string"
            }
        },
    },
    handler=_read_research,
)


READ_DOCUMENTS = Tool(
    name="read_documents",
    description=(
        "Read one document by id, or list "
        "recent documents if no id is given."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string"
            }
        },
    },
    handler=_read_documents,
)


CREATE_DOCUMENT = Tool(
    name="create_document",
    description=(
        "Create a new document "
        "(draft, brief, summary, or report)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string"
            },
            "content": {
                "type": "string"
            },
            "type": {
                "type": "string",
                "enum": [
                    "brief",
                    "draft",
                    "summary",
                    "report",
                    "other",
                ],
            },
        },
        "required": ["title"],
    },
    handler=_create_document,
)


UPDATE_DOCUMENT = Tool(
    name="update_document",
    description=(
        "Update an existing document's title, content, "
        "type, or status."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string"
            },
            "title": {
                "type": "string"
            },
            "content": {
                "type": "string"
            },
            "type": {
                "type": "string",
                "enum": [
                    "brief",
                    "draft",
                    "summary",
                    "report",
                    "other",
                ],
            },
            "status": {
                "type": "string",
                "enum": [
                    "draft",
                    "final",
                ],
            },
        },
        "required": [
            "document_id"
        ],
    },
    handler=_update_document,
)


NOVA_WORKSPACE_TOOLS = [
    READ_RESEARCH,
    READ_DOCUMENTS,
    CREATE_DOCUMENT,
    UPDATE_DOCUMENT,
]


ATLAS_WORKSPACE_TOOLS = [
    SEARCH_DOCUMENTS,
    SAVE_RESEARCH,
    LINK_RESEARCH_TO_GOAL,
]