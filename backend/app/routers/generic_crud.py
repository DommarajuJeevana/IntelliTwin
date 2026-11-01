
"""
Builds the standard REST endpoints for modules configured
in app/modules_config.py.
"""

import re
from datetime import timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.calendar_conflicts import (
    find_calendar_conflicts,
    raise_calendar_conflict,
)
from app.database import get_db
from app.dependencies import require_auth
from app.memory.embeddings import embed_text
from app.memory.safety import reject_secret_memory
from app.sanitize import clean_tags
from app.modules_config import MODULES
from app.notifications import (
    cancel_calendar_reminders,
    sync_calendar_reminder,
)
from app.task_scheduler import (
    remove_task_calendar_link,
    sync_task_calendar,
)
from app.owned import (
    VALID_AGENTS,
    new_owned_doc,
    now_utc,
    parse_date,
)
from app.goal_progress import (
    attach_goal_progress,
    attach_goals_progress,
)
from app.serialization import doc_out, docs_out


def _coerce_value(field: str, value, config: dict):
    if field in config.get("rich_fields", []):
        from app.sanitize import sanitize_rich_text
        try:
            return sanitize_rich_text(value)
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc))
    if field in config.get("date_fields", []):
        return parse_date(value)

    if field in config.get("ref_fields", []):
        if not value:
            return None

        try:
            return ObjectId(value)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid reference for '{field}'.",
            )

    enums = config.get("enums", {})

    if field in enums and value not in enums[field]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{value}' is not a valid value "
                f"for '{field}'."
            ),
        )

    return value


def _known_fields(config: dict) -> set[str]:
    return set(config["defaults"].keys()) | set(
        config["required"]
    )


async def _maybe_embed(config: dict, doc: dict) -> None:
    """Compute semantic-search embeddings for configured fields."""

    fields = config.get("embed_fields")

    if not fields:
        return

    text = "\n".join(
        str(doc.get(field) or "")
        for field in fields
    ).strip()

    doc["embedding"] = await embed_text(text)


async def _check_calendar_conflict(
    user_id: ObjectId,
    starts_at,
    exclude_event_id: ObjectId | None = None,
) -> None:
    conflicts = await find_calendar_conflicts(
        user_id=user_id,
        starts_at=starts_at,
        exclude_event_id=exclude_event_id,
    )

    raise_calendar_conflict(conflicts)


def build_module_router(module_key: str) -> APIRouter:
    config = MODULES[module_key]
    router = APIRouter()

    def collection():
        return get_db()[config["collection"]]

    # LIST

    @router.get("")
    async def list_items(
        status: str | None = Query(default=None),
        q: str | None = Query(default=None),
        user: dict = Depends(require_auth),
    ):
        filt = {"user": user["_id"]}

        if status:
            filt["status"] = status

        if q and config.get("searchable"):
            rx = {
                "$regex": re.escape(q),
                "$options": "i",
            }

            filt["$or"] = [
                {field: rx}
                for field in config["searchable"]
            ]

        cursor = (
            collection()
            .find(filt)
            .sort("createdAt", -1)
        )

        items = await cursor.to_list(length=None)

        if module_key == "goals":
            items = await attach_goals_progress(
                user_id=user["_id"],
                goals=items,
            )

        return {"items": docs_out(items)}

    # CREATE

    @router.post("", status_code=201)
    async def create_item(
        body: dict,
        user: dict = Depends(require_auth),
    ):
        for field in config["required"]:
            if body.get(field) in (None, ""):
                raise HTTPException(
                    status_code=400,
                    detail=f"'{field}' is required.",
                )

        doc = new_owned_doc(
            user["_id"],
            agent=(
                body.get("agent")
                if body.get("agent") in VALID_AGENTS
                else None
            ),
        )

        for field in _known_fields(config):
            if field in body:
                doc[field] = _coerce_value(
                    field,
                    body[field],
                    config,
                )
            elif field in config["defaults"]:
                doc[field] = config["defaults"][field]

        if (
            config.get("default_occurred_at_now")
            and not doc.get("occurredAt")
        ):
            doc["occurredAt"] = now_utc()

        # Check before inserting a calendar event.
        if module_key == "calendar":
            await _check_calendar_conflict(
                user_id=user["_id"],
                starts_at=doc.get("startsAt"),
            )

        # Check scheduled tasks against existing calendar events.
        # The scheduler also checks before creating/updating links.
        if (
            module_key == "tasks"
            and doc.get("scheduledStart")
        ):
            await _check_calendar_conflict(
                user_id=user["_id"],
                starts_at=doc["scheduledStart"],
            )

        if module_key == "memory":
            try:
                reject_secret_memory(doc.get("title"), doc.get("content"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

        await _maybe_embed(config, doc)

        result = await collection().insert_one(doc)
        doc["_id"] = result.inserted_id

        if module_key == "calendar":
            await sync_calendar_reminder(
                user_id=user["_id"],
                event=doc,
            )

        if module_key == "tasks":
            await sync_task_calendar(
                user_id=user["_id"],
                task=doc,
            )

            refreshed_task = await collection().find_one(
                {
                    "_id": doc["_id"],
                    "user": user["_id"],
                }
            )

            if refreshed_task:
                doc = refreshed_task

        if module_key == "goals":
            doc = await attach_goal_progress(
                user_id=user["_id"],
                goal=doc,
            )

        return {
            "item": doc_out(doc),
            "conflicts": [],
        }

    # GET ONE

    @router.get("/{item_id}")
    async def get_one(
        item_id: str,
        user: dict = Depends(require_auth),
    ):
        try:
            oid = ObjectId(item_id)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail="Not found.",
            )

        item = await collection().find_one(
            {
                "_id": oid,
                "user": user["_id"],
            }
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Not found.",
            )

        if module_key == "goals":
            item = await attach_goal_progress(
                user_id=user["_id"],
                goal=item,
            )

        return {"item": doc_out(item)}

    # UPDATE

    @router.put("/{item_id}")
    async def update_item(
        item_id: str,
        body: dict,
        user: dict = Depends(require_auth),
    ):
        try:
            oid = ObjectId(item_id)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail="Not found.",
            )

        existing = await collection().find_one(
            {
                "_id": oid,
                "user": user["_id"],
            }
        )

        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Not found.",
            )

        # Optimistic concurrency: an editor that holds a stale copy must not
        # silently overwrite a newer save (opt-in via expectedUpdatedAt).
        expected = body.get("expectedUpdatedAt")
        if expected:
            expected_dt = parse_date(expected)
            current = existing.get("updatedAt")
            if expected_dt and current:
                cur = current if current.tzinfo else current.replace(tzinfo=timezone.utc)
                if abs((cur - expected_dt).total_seconds()) > 0.002:
                    raise HTTPException(
                        status_code=409,
                        detail={"message": "This item was changed elsewhere. Reload before saving.",
                                "updatedAt": cur.isoformat()},
                    )

        updates = {}

        for field in _known_fields(config):
            if field in body:
                updates[field] = _coerce_value(
                    field,
                    body[field],
                    config,
                )

        if "tags" in body:
            tags = clean_tags(body["tags"])
            if tags is None:
                raise HTTPException(status_code=400, detail="tags must be a list of strings.")
            updates["tags"] = tags

        if module_key == "memory":
            try:
                reject_secret_memory(updates.get("title"), updates.get("content"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

        updates["updatedAt"] = now_utc()

        future_document = {
            **existing,
            **updates,
        }

        # A calendar event excludes itself from the conflict search.
        if module_key == "calendar":
            await _check_calendar_conflict(
                user_id=user["_id"],
                starts_at=future_document.get("startsAt"),
                exclude_event_id=oid,
            )

        # A scheduled task excludes its own linked calendar event.
        if (
            module_key == "tasks"
            and future_document.get("scheduledStart")
        ):
            await _check_calendar_conflict(
                user_id=user["_id"],
                starts_at=future_document["scheduledStart"],
                exclude_event_id=existing.get(
                    "calendarEventId"
                ),
            )

        embed_fields = config.get("embed_fields")

        if embed_fields and any(
            field in updates
            for field in embed_fields
        ):
            await _maybe_embed(config, future_document)
            updates["embedding"] = future_document["embedding"]

        result = await collection().find_one_and_update(
            {
                "_id": oid,
                "user": user["_id"],
            },
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Not found.",
            )

        if module_key == "calendar":
            await cancel_calendar_reminders(
                user_id=user["_id"],
                event_id=oid,
            )

            await sync_calendar_reminder(
                user_id=user["_id"],
                event=result,
            )

        if module_key == "tasks":
            await sync_task_calendar(
                user_id=user["_id"],
                task=result,
            )

            refreshed_task = await collection().find_one(
                {
                    "_id": oid,
                    "user": user["_id"],
                }
            )

            if refreshed_task:
                result = refreshed_task

        if module_key == "goals":
            result = await attach_goal_progress(
                user_id=user["_id"],
                goal=result,
            )

        return {
            "item": doc_out(result),
            "conflicts": [],
        }

    # DELETE

    @router.delete("/{item_id}")
    async def remove_item(
        item_id: str,
        user: dict = Depends(require_auth),
    ):
        try:
            oid = ObjectId(item_id)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail="Not found.",
            )

        result = await collection().find_one_and_delete(
            {
                "_id": oid,
                "user": user["_id"],
            }
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Not found.",
            )

        if module_key == "calendar":
            await cancel_calendar_reminders(
                user_id=user["_id"],
                event_id=oid,
            )

        if module_key == "tasks":
            await remove_task_calendar_link(
                user_id=user["_id"],
                task=result,
            )

        return {"ok": True}

    return router
