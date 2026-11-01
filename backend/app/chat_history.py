"""
Chat History module: the permanent record of every Mission Control chat.

Messages are written once, by conversation.py, into `mission_control_messages`
and are never removed by the dashboard. The Mission Control panel shows only
today's slice of that store; this module is how every other day is read.

All day boundaries are the user's local calendar days (profile timezone),
computed deterministically with date_range - never by the model.
"""

import re
from datetime import date, datetime, timezone

from app.conversation import COLLECTION
from app.database import get_db
from app.date_range import local_day_bounds
from app.owned import get_user_tz

MAX_SCAN = 5000          # bounded: never load an unlimited archive
PREVIEW_CHARS = 140


def today_start_utc(user: dict) -> datetime:
    """Start of the user's current local day, as UTC."""
    tz = get_user_tz(user)
    today = datetime.now(tz).date()
    return local_day_bounds(today, tz)[0]


def _local_date(value: datetime, tz) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz).date()


def _preview(text: str) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1].rstrip() + "…"


async def list_days(user: dict, query: str | None = None) -> list[dict]:
    """One summary per local day that has chats, newest day first.
    With `query`, only days containing a matching message are returned."""
    tz = get_user_tz(user)
    filt: dict = {"user": user["_id"]}
    if query and query.strip():
        filt["content"] = {"$regex": re.escape(query.strip()), "$options": "i"}

    rows = (
        await get_db()[COLLECTION]
        .find(filt, {"role": 1, "content": 1, "createdAt": 1})
        .sort("createdAt", -1)
        .limit(MAX_SCAN)
        .to_list(length=MAX_SCAN)
    )

    days: dict[date, dict] = {}
    for row in rows:  # newest first
        created = row.get("createdAt")
        if not isinstance(created, datetime):
            continue
        day = _local_date(created, tz)
        entry = days.setdefault(
            day, {"date": day.isoformat(), "count": 0, "preview": "", "lastAt": created}
        )
        entry["count"] += 1
        # Preview = the first thing the user said that day (rows arrive newest
        # first, so later iterations overwrite with older user messages).
        if row.get("role") == "user":
            entry["preview"] = _preview(row.get("content"))
        elif not entry["preview"]:
            entry["preview"] = _preview(row.get("content"))

    out = sorted(days.values(), key=lambda d: d["date"], reverse=True)
    for entry in out:
        entry["lastAt"] = entry["lastAt"].isoformat()
    return out


async def get_day(user: dict, day: date) -> list[dict]:
    """Every message of one local day, oldest first."""
    start, end = local_day_bounds(day, get_user_tz(user))
    return (
        await get_db()[COLLECTION]
        .find({"user": user["_id"], "createdAt": {"$gte": start, "$lt": end}})
        .sort("createdAt", 1)
        .to_list(length=MAX_SCAN)
    )
