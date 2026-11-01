
"""
IntelliTwin notification service.

Calendar events create persistent reminders scheduled 10 minutes
before their start time.

When notifications are requested:
- Upcoming events with due reminders can notify the user.
- Reminders for events that have already started are expired.
- Reminders for deleted events are expired.
- Existing overdue notifications are also checked.
"""

from datetime import datetime, timezone, timedelta

from bson import ObjectId

from app.database import get_db
from app.owned import now_utc
from app.serialization import doc_out, docs_out


DEFAULT_REMINDER_MINUTES = 10


def _as_utc(value):
    """Datetimes read back from MongoDB can be naive (UTC); make them aware before comparing."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _notification_collection():
    return get_db().notifications


def _calendar_collection():
    return get_db().calendar_events


async def create_calendar_reminder(
    user_id: ObjectId,
    event_id: ObjectId,
    event_title: str,
    starts_at: datetime,
    reminder_minutes: int = DEFAULT_REMINDER_MINUTES,
) -> dict:
    """Create or replace the reminder for a calendar event."""

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)

    scheduled_for = starts_at - timedelta(
        minutes=reminder_minutes
    )

    collection = _notification_collection()

    # Remove previous active reminders for this event.
    await collection.delete_many(
        {
            "user": user_id,
            "type": "calendar_reminder",
            "eventId": event_id,
            "status": {"$in": ["scheduled", "due"]},
        }
    )

    # Do not create a reminder for an event that has already started.
    if starts_at <= now_utc():
        return None

    notification = {
        "user": user_id,
        "type": "calendar_reminder",
        "eventId": event_id,
        "title": f"Upcoming: {event_title}",
        "message": (
            f"{event_title} starts in "
            f"{reminder_minutes} minutes."
        ),
        "scheduledFor": scheduled_for,
        "status": (
            "due" if scheduled_for <= now_utc() else "scheduled"
        ),
        "read": False,
        "createdAt": now_utc(),
        "updatedAt": now_utc(),
    }

    result = await collection.insert_one(notification)
    notification["_id"] = result.inserted_id

    return doc_out(notification)


async def cancel_calendar_reminders(
    user_id: ObjectId,
    event_id: ObjectId,
) -> int:
    """Cancel active reminders for a calendar event."""

    result = await _notification_collection().update_many(
        {
            "user": user_id,
            "type": "calendar_reminder",
            "eventId": event_id,
            "status": {"$in": ["scheduled", "due"]},
        },
        {
            "$set": {
                "status": "cancelled",
                "updatedAt": now_utc(),
            }
        },
    )

    return result.modified_count


async def sync_calendar_reminder(
    user_id: ObjectId,
    event: dict,
) -> dict | None:
    """Synchronize a reminder with its calendar event."""

    event_id = event.get("_id")
    starts_at = event.get("startsAt")

    if not event_id or not starts_at:
        return None

    return await create_calendar_reminder(
        user_id=user_id,
        event_id=event_id,
        event_title=str(
            event.get("title") or "Calendar event"
        ),
        starts_at=starts_at,
    )


async def mark_due_notifications() -> int:
    """
    Update scheduled reminders whose reminder time has arrived.

    Expire reminders if their event has already started or the event
    no longer exists. This also cleans up previously due notifications.
    """

    notifications = _notification_collection()
    calendar_events = _calendar_collection()
    now = now_utc()

    cursor = notifications.find(
        {
            "type": "calendar_reminder",
            "status": {"$in": ["scheduled", "due"]},
            "scheduledFor": {"$lte": now},
        }
    )

    pending = await cursor.to_list(length=1000)
    modified_count = 0

    for notification in pending:
        event = await calendar_events.find_one(
            {
                "_id": notification.get("eventId"),
                "user": notification.get("user"),
            }
        )

        starts_at = _as_utc(event.get("startsAt")) if event else None

        # Expire reminders for deleted events or events that have
        # already started. Do not surface stale reminders.
        if not starts_at or starts_at <= now:
            result = await notifications.update_one(
                {
                    "_id": notification["_id"],
                    "status": {"$in": ["scheduled", "due"]},
                },
                {
                    "$set": {
                        "status": "expired",
                        "updatedAt": now,
                    }
                },
            )
            modified_count += result.modified_count
            continue

        # The event is still upcoming. Make the reminder available
        # once its scheduled reminder time has arrived.
        if notification.get("status") == "scheduled":
            result = await notifications.update_one(
                {
                    "_id": notification["_id"],
                    "status": "scheduled",
                },
                {
                    "$set": {
                        "status": "due",
                        "updatedAt": now,
                    }
                },
            )
            modified_count += result.modified_count

    return modified_count


async def get_user_notifications(
    user_id: ObjectId,
    include_read: bool = False,
) -> list[dict]:
    """Return active due notifications for the authenticated user."""

    await mark_due_notifications()

    query = {
        "user": user_id,
        "type": "calendar_reminder",
        "status": "due",
    }

    if include_read:
        query = {
            "user": user_id,
            "type": "calendar_reminder",
            "status": {"$in": ["due", "read"]},
        }
    else:
        query["read"] = False

    cursor = (
        _notification_collection()
        .find(query)
        .sort("scheduledFor", -1)
    )

    notifications = await cursor.to_list(length=100)

    return docs_out(notifications)


async def mark_notification_read(
    user_id: ObjectId,
    notification_id: ObjectId,
) -> dict | None:
    """Mark one notification as read."""

    from pymongo import ReturnDocument

    notification = await _notification_collection().find_one_and_update(
        {
            "_id": notification_id,
            "user": user_id,
            "status": "due",
        },
        {
            "$set": {
                "read": True,
                "status": "read",
                "updatedAt": now_utc(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return doc_out(notification) if notification else None
