"""
Persistent Mission Control conversation storage.

Conversation history is separate from:
- Echo long-term memory
- agent activity logs
- workspace entities
"""

from datetime import datetime, timezone

from app.database import get_db
from app.serialization import serialize


COLLECTION = "mission_control_messages"

DEFAULT_THREAD = "mission-control"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_message(
    user_id,
    role: str,
    content: str,
    thread_id: str = DEFAULT_THREAD,
    *,
    agents: list[str] | None = None,
    actions: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    """
    Store one Mission Control message.
    """
    db = get_db()

    document = {
        "user": user_id,
        "thread": thread_id,
        "role": role,
        "content": content,
        "createdAt": _now(),
        "agents": agents or [],
        "actions": actions or [],
        "metadata": metadata or {},
    }

    result = await db[COLLECTION].insert_one(
        document
    )

    document["_id"] = result.inserted_id

    return document


async def get_messages(
    user_id,
    thread_id: str = DEFAULT_THREAD,
    limit: int = 30,
    since: datetime | None = None,
) -> list[dict]:
    """
    Return recent messages in chronological order.

    `since` (UTC) restricts the result to messages created at or after it;
    Mission Control uses this to show only today's conversation.
    """
    db = get_db()

    limit = max(
        1,
        min(int(limit), 100),
    )

    query = {
        "user": user_id,
        "thread": thread_id,
    }

    if since is not None:
        query["createdAt"] = {"$gte": since}

    messages = (
        await db[COLLECTION]
        .find(query)
        .sort(
            "createdAt",
            -1,
        )
        .limit(limit)
        .to_list(
            length=limit
        )
    )

    messages.reverse()

    return messages


async def get_recent_messages(
    user_id,
    thread_id: str = DEFAULT_THREAD,
    limit: int = 12,
    since: datetime | None = None,
) -> list[dict]:
    return await get_messages(
        user_id,
        thread_id,
        limit,
        since=since,
    )


def messages_out(
    messages: list[dict],
) -> list[dict]:
    """
    Serialize messages for an API response.
    """
    return [
        serialize(message)
        for message in messages
    ]


async def clear_thread(
    user_id,
    thread_id: str = DEFAULT_THREAD,
) -> int:
    """
    Delete one Mission Control thread.

    This does not touch Echo memories, workspace data, or agent activity.
    """
    db = get_db()

    result = await db[COLLECTION].delete_many(
        {
            "user": user_id,
            "thread": thread_id,
        }
    )

    return result.deleted_count