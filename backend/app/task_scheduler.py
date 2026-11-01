
"""
Task scheduling service.

Synchronizes a task's scheduled start time with its calendar event.
Calendar conflict detection uses the start timestamp only.
"""

from bson import ObjectId
from pymongo import ReturnDocument

from app.calendar_conflicts import (
    find_calendar_conflicts,
    raise_calendar_conflict,
)
from app.database import get_db
from app.notifications import (
    cancel_calendar_reminders,
    sync_calendar_reminder,
)
from app.owned import now_utc
from app.serialization import doc_out


def _calendar_collection():
    return get_db().calendar_events


def _task_collection():
    return get_db().tasks


async def _delete_linked_calendar_event(
    user_id: ObjectId,
    task: dict,
) -> None:
    """Delete a task's linked calendar event and cancel its reminder."""

    event_id = task.get("calendarEventId")

    if not event_id:
        return

    await cancel_calendar_reminders(
        user_id=user_id,
        event_id=event_id,
    )

    await _calendar_collection().delete_one(
        {
            "_id": event_id,
            "user": user_id,
            "taskId": task.get("_id"),
        }
    )


async def sync_task_calendar(
    user_id: ObjectId,
    task: dict,
) -> dict:
    """
    Synchronize the task with its calendar event.

    - No scheduledStart: remove any linked calendar event.
    - scheduledStart exists: create or update its calendar event.
    - Conflicts are checked before modifying the calendar event.
    - scheduledEnd is not used for conflict detection.
    """

    task_id = task["_id"]
    scheduled_start = task.get("scheduledStart")
    scheduled_end = task.get("scheduledEnd")
    existing_event_id = task.get("calendarEventId")

    # No schedule: remove any previously linked event.
    if not scheduled_start:
        if existing_event_id:
            await _delete_linked_calendar_event(
                user_id=user_id,
                task=task,
            )

            updated_task = await _task_collection().find_one_and_update(
                {
                    "_id": task_id,
                    "user": user_id,
                },
                {
                    "$set": {
                        "calendarEventId": None,
                        "updatedAt": now_utc(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )

            return doc_out(updated_task)

        return doc_out(task)

    # Find the task's current linked event, if it exists.
    existing_event = None

    if existing_event_id:
        existing_event = await _calendar_collection().find_one(
            {
                "_id": existing_event_id,
                "user": user_id,
                "taskId": task_id,
            }
        )

    # Reject a conflicting start time before changing the calendar.
    conflicts = await find_calendar_conflicts(
        user_id=user_id,
        starts_at=scheduled_start,
        exclude_event_id=(
            existing_event["_id"]
            if existing_event
            else None
        ),
    )

    raise_calendar_conflict(conflicts)

    # Build the linked calendar event.
    event_data = {
        "title": task.get("title") or "Scheduled task",
        "startsAt": scheduled_start,
        "endsAt": scheduled_end,
        "location": "",
        "notes": (
            f"Scheduled from task: "
            f"{task.get('title') or 'Untitled task'}"
        ),
        "taskId": task_id,
        "agent": "compass",
        "tags": ["task"],
        "updatedAt": now_utc(),
    }

    # Update an existing linked event.
    if existing_event:
        updated_event = await _calendar_collection().find_one_and_update(
            {
                "_id": existing_event["_id"],
                "user": user_id,
                "taskId": task_id,
            },
            {"$set": event_data},
            return_document=ReturnDocument.AFTER,
        )

        await cancel_calendar_reminders(
            user_id=user_id,
            event_id=existing_event["_id"],
        )

        await sync_calendar_reminder(
            user_id=user_id,
            event=updated_event,
        )

        refreshed_task = await _task_collection().find_one(
            {
                "_id": task_id,
                "user": user_id,
            }
        )

        return doc_out(refreshed_task)

    # Create a new linked calendar event.
    event_data["createdAt"] = now_utc()

    result = await _calendar_collection().insert_one(
        {
            "user": user_id,
            **event_data,
        }
    )

    event_id = result.inserted_id

    created_event = await _calendar_collection().find_one(
        {
            "_id": event_id,
            "user": user_id,
        }
    )

    await sync_calendar_reminder(
        user_id=user_id,
        event=created_event,
    )

    # Store the calendar link on the task.
    updated_task = await _task_collection().find_one_and_update(
        {
            "_id": task_id,
            "user": user_id,
        },
        {
            "$set": {
                "calendarEventId": event_id,
                "updatedAt": now_utc(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return doc_out(updated_task)


async def remove_task_calendar_link(
    user_id: ObjectId,
    task: dict,
) -> None:
    """Remove a task's linked calendar event and reminder."""

    await _delete_linked_calendar_event(
        user_id=user_id,
        task=task,
    )
