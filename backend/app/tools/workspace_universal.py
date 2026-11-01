"""Shared, user-scoped CRUD access for all workspace modules."""
import re
from datetime import timedelta, timezone

from bson import ObjectId
from pymongo import ReturnDocument

from app.calendar_conflicts import find_calendar_conflicts, raise_calendar_conflict
from app.database import get_db
from app.memory.embeddings import embed_text
from app.modules_config import MODULES
from app.notifications import cancel_calendar_reminders, sync_calendar_reminder
from app.owned import VALID_AGENTS, new_owned_doc, now_utc, parse_date
from app.serialization import doc_out, docs_out
from app.task_scheduler import remove_task_calendar_link, sync_task_calendar
from app.tools.base import Tool

# Memory entries remain managed by Echo's dedicated memory tools.
# Applied when an event is created without an end time (documented in README).
DEFAULT_EVENT_MINUTES = 60

WORKSPACE_MODULES = ("goals", "tasks", "calendar", "notes", "documents", "research", "projects")


def _id(value):
    try:
        return ObjectId(str(value))
    except Exception:
        return None


from app.sanitize import clean_tags as _clean_tags


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _fields(config):
    return set(config.get("required", [])) | set(config.get("defaults", {}).keys())


def _coerce(field, value, config):
    if field in config.get("rich_fields", []):
        from app.sanitize import sanitize_rich_text
        return sanitize_rich_text(value)
    if field in config.get("date_fields", []):
        return parse_date(value)
    if field in config.get("ref_fields", []):
        if value in (None, ""):
            return None
        result = _id(value)
        if result is None:
            raise ValueError(f"Invalid reference for '{field}'.")
        return result
    enums = config.get("enums", {}).get(field, [])
    if enums and value not in enums:
        raise ValueError(f"'{value}' is not a valid value for '{field}'.")
    return value


async def _embed(module, document):
    fields = MODULES[module].get("embed_fields", [])
    if not fields:
        return
    content = "\n".join(str(document.get(field) or "") for field in fields).strip()
    if not content:
        return
    try:
        document["embedding"] = await embed_text(content)
    except Exception:
        # Embeddings must not block ordinary workspace writes.
        pass


async def _calendar_conflict(user_id, starts_at, exclude_id=None):
    conflicts = await find_calendar_conflicts(
        user_id=user_id, starts_at=starts_at, exclude_event_id=exclude_id
    )
    raise_calendar_conflict(conflicts)


async def _run(user, args):
    module = str(args.get("module", "")).lower()
    action = str(args.get("action", "")).lower()
    if module not in WORKSPACE_MODULES:
        return {"error": "Unsupported module. Use goals, tasks, calendar, notes, documents, research, or projects."}
    if action not in {"list", "read", "create", "update", "replace", "delete"}:
        return {"error": "Unsupported action. Use list, read, create, update, replace, or delete."}

    config = MODULES[module]
    collection = get_db()[config["collection"]]
    uid = user["_id"]
    record_id = args.get("id")
    data = args.get("data") or {}
    if not isinstance(data, dict):
        return {"error": "data must be an object."}

    # Some local models put calendar fields at the top level instead of
    # inside the generic tool's `data` object. Normalize both shapes so a
    # user-provided title such as "lunch" is not silently discarded.
    if module == "calendar" and action in {"create", "update", "replace"}:
        data = dict(data)
        for field in ("title", "startsAt", "endsAt", "location", "notes"):
            if data.get(field) in (None, "") and args.get(field) not in (None, ""):
                data[field] = args[field]

    if action == "list":
        query = {"user": uid}
        # Only plain strings: never let a caller smuggle a Mongo operator object into the filter.
        if isinstance(args.get("status"), str) and args["status"]:
            query["status"] = args["status"]
        term = str(args.get("query") or "").strip()
        if term and config.get("searchable"):
            query["$or"] = [
                {field: {"$regex": re.escape(term), "$options": "i"}}
                for field in config["searchable"]
            ]
        try:
            limit = max(1, min(int(args.get("limit", 20)), 50))
        except (ValueError, TypeError):
            limit = 20
        items = await collection.find(query).sort("updatedAt", -1).to_list(length=limit)
        return {"module": module, "items": docs_out(items), "count": len(items)}

    oid = _id(record_id) if record_id else None
    if action in {"read", "update", "replace", "delete"} and oid is None:
        return {"error": "A valid record id is required for this action."}

    if action == "read":
        item = await collection.find_one({"_id": oid, "user": uid})
        return {"module": module, "item": doc_out(item)} if item else {"error": f"No {module} record found with that id."}

    if action == "create":
        for field in config.get("required", []):
            if data.get(field) in (None, ""):
                return {"error": f"'{field}' is required."}
        agent = args.get("agent")
        doc = new_owned_doc(uid, agent=agent if agent in VALID_AGENTS and agent else "agent")
        for field in _fields(config):
            if field in data:
                doc[field] = _coerce(field, data[field], config)
            elif field in config.get("defaults", {}):
                doc[field] = config["defaults"][field]
        if isinstance(data.get("tags"), list):
            doc["tags"] = _clean_tags(data["tags"])
        if config.get("default_occurred_at_now") and not doc.get("occurredAt"):
            doc["occurredAt"] = now_utc()
        if module == "calendar":
            if not doc.get("startsAt"):
                return {"error": "Could not understand the start date/time; nothing was created."}
            if not doc.get("endsAt"):
                doc["endsAt"] = doc["startsAt"] + timedelta(minutes=DEFAULT_EVENT_MINUTES)
            elif doc["endsAt"] <= doc["startsAt"]:
                return {"error": "The end time must be after the start time."}
            # Idempotent retries: same title at the same start is the same event.
            twin = await collection.find_one(
                {"user": uid, "startsAt": doc["startsAt"], "title": doc.get("title")}
            )
            if twin:
                return {"module": module, "action": "created", "item": doc_out(twin), "duplicate": True}
        try:
            if module == "calendar":
                await _calendar_conflict(uid, doc.get("startsAt"))
            elif module == "tasks" and doc.get("scheduledStart"):
                await _calendar_conflict(uid, doc["scheduledStart"])
        except Exception as exc:
            return {"error": str(getattr(exc, "detail", exc))}
        await _embed(module, doc)
        inserted = await collection.insert_one(doc)
        doc["_id"] = inserted.inserted_id
        if not await collection.find_one({"_id": doc["_id"], "user": uid}, {"_id": 1}):
            return {"error": f"The {module} record could not be verified after saving."}
        if module == "calendar":
            await sync_calendar_reminder(user_id=uid, event=doc)
        elif module == "tasks":
            await sync_task_calendar(user_id=uid, task=doc)
            doc = await collection.find_one({"_id": doc["_id"], "user": uid}) or doc
        return {"module": module, "action": "created", "item": doc_out(doc)}

    existing = await collection.find_one({"_id": oid, "user": uid})
    if not existing:
        return {"error": f"No {module} record found with that id."}

    if action == "delete":
        # Destructive: a model must make an explicit second call with confirm=true.
        if args.get("confirm") is not True:
            label = existing.get("title") or existing.get("name") or str(oid)
            return {
                "needs_confirmation": True,
                "module": module,
                "id": str(oid),
                "message": f"Deleting {module} record {str(label)[:80]!r} is permanent. Ask the user to confirm, "
                           "then call again with confirm=true. Nothing was deleted.",
            }
        deleted = await collection.find_one_and_delete({"_id": oid, "user": uid})
        if not deleted:
            return {"error": f"The {module} record could not be deleted."}
        if module == "calendar":
            await cancel_calendar_reminders(user_id=uid, event_id=oid)
        elif module == "tasks":
            await remove_task_calendar_link(user_id=uid, task=deleted)
        return {"module": module, "action": "deleted", "id": str(oid), "ok": True}

    allowed = _fields(config)
    updates = {field: _coerce(field, value, config) for field, value in data.items() if field in allowed}
    if isinstance(data.get("tags"), list):
        updates["tags"] = _clean_tags(data["tags"])
    if not updates:
        return {"error": "data must contain editable fields for this module."}
    if module == "calendar" and updates.get("startsAt") and "endsAt" not in updates:
        # Moving an event keeps its length ("move it to 5 PM"), instead of leaving the old end behind.
        old_start, old_end = existing.get("startsAt"), existing.get("endsAt")
        length = _utc(old_end) - _utc(old_start) if old_start and old_end else timedelta(minutes=DEFAULT_EVENT_MINUTES)
        if length <= timedelta(0):
            length = timedelta(minutes=DEFAULT_EVENT_MINUTES)
        updates["endsAt"] = _utc(updates["startsAt"]) + length
    future = {**existing, **updates}
    for field in config.get("required", []):
        if future.get(field) in (None, ""):
            return {"error": f"'{field}' cannot be empty."}
    if module == "calendar":
        if not future.get("startsAt"):
            return {"error": "Could not understand the start date/time; nothing was changed."}
        # Mongo returns naive (UTC) datetimes while parsed input is aware: normalise before comparing.
        if future.get("endsAt") and _utc(future["endsAt"]) <= _utc(future["startsAt"]):
            return {"error": "The end time must be after the start time."}
    try:
        if module == "calendar":
            await _calendar_conflict(uid, future.get("startsAt"), exclude_id=oid)
        elif module == "tasks" and future.get("scheduledStart"):
            await _calendar_conflict(uid, future["scheduledStart"], exclude_id=existing.get("calendarEventId"))
    except Exception as exc:
        return {"error": str(getattr(exc, "detail", exc))}

    if any(field in updates for field in config.get("embed_fields", [])):
        await _embed(module, future)
        if "embedding" in future:
            updates["embedding"] = future["embedding"]
    updates["updatedAt"] = now_utc()
    updated = await collection.find_one_and_update(
        {"_id": oid, "user": uid}, {"$set": updates}, return_document=ReturnDocument.AFTER
    )
    if not updated:
        return {"error": f"Failed to update {module} record."}
    if module == "calendar":
        await cancel_calendar_reminders(user_id=uid, event_id=oid)
        await sync_calendar_reminder(user_id=uid, event=updated)
    elif module == "tasks":
        await sync_task_calendar(user_id=uid, task=updated)
        updated = await collection.find_one({"_id": oid, "user": uid}) or updated
    return {"module": module, "action": "replaced" if action == "replace" else "updated", "item": doc_out(updated)}


WORKSPACE_CRUD = Tool(
    name="workspace_crud",
    description=(
        "Manage existing IntelliTwin workspace content across goals, tasks, calendar events, notes, documents, "
        "research items, and projects. Use list to find records, read to inspect one, create to add one, update "
        "to change selected fields, replace to rewrite supplied fields (including the full content/body of a note "
        "or document), and delete only when explicitly requested. For existing content, list/search first if its id "
        "is unknown, then read before editing if needed. For calendar create actions, provide both title and startsAt "
        "inside data; top-level title/startsAt are accepted as a compatibility fallback. This tool is available to every agent. Calendar changes "
        "check conflicts and synchronize reminders; task schedule changes synchronize linked calendar events."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "module": {"type": "string", "enum": list(WORKSPACE_MODULES)},
            "action": {"type": "string", "enum": ["list", "read", "create", "update", "replace", "delete"]},
            "id": {"type": "string"},
            "data": {
                "type": "object",
                "description": "Fields for the selected workspace item. For calendar events, include title and startsAt here; top-level calendar fields are also accepted for compatibility.",
            },
            # Calendar-specific compatibility fields. Some local models
            # produce these at top level rather than nested under data.
            "title": {"type": "string", "description": "Calendar event title, e.g. Lunch."},
            "startsAt": {"type": "string", "description": "Calendar event start date/time in ISO format."},
            "endsAt": {"type": "string", "description": "Optional calendar event end date/time in ISO format."},
            "location": {"type": "string", "description": "Optional event location."},
            "notes": {"type": "string", "description": "Optional event notes."},
            "query": {"type": "string"},
            "status": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "agent": {"type": "string"},
            "confirm": {"type": "boolean", "description": "Required (true) for delete, only after the user explicitly confirmed."}
        },
        "required": ["module", "action"]
    },
    handler=_run,
)

WORKSPACE_CRUD_TOOLS = [WORKSPACE_CRUD]
