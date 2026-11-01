
from bson import ObjectId
from fastapi import HTTPException

from app.database import get_db
from app.serialization import docs_out


async def find_calendar_conflicts(
    user_id: ObjectId,
    starts_at,
    exclude_event_id: ObjectId | None = None,
) -> list[dict]:
    """
    Find calendar events for the same user with the
    exact same start timestamp.

    End times are not used for conflict detection.
    """

    if starts_at is None:
        return []

    query = {
        "user": user_id,
        "startsAt": starts_at,
    }

    if exclude_event_id is not None:
        query["_id"] = {"$ne": exclude_event_id}

    cursor = (
        get_db()
        .calendar_events
        .find(
            query,
            {
                "_id": 1,
                "title": 1,
                "startsAt": 1,
                "location": 1,
                "taskId": 1,
            },
        )
        .sort("startsAt", 1)
    )

    conflicts = await cursor.to_list(length=100)

    return docs_out(conflicts)


def raise_calendar_conflict(
    conflicts: list[dict],
) -> None:
    """Raise HTTP 409 when another item occupies the start time."""

    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Another calendar item is already "
                    "scheduled for this start time."
                ),
                "conflicts": conflicts,
            },
        )
