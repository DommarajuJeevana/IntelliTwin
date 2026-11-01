"""
Every user-owned module (goals, tasks, notes, documents, projects, memory
entries, research items, agent messages...) shares the same base shape: it
belongs to a user, can be tagged, can be linked to the agent that
created/touched it, and has timestamps. Direct equivalent of
backend/utils/schemaFactory.js's ownedSchema().
"""
from contextvars import ContextVar
from datetime import datetime, timezone, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId

VALID_AGENTS = {"echo", "atlas", "compass", "nova", None}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_owned_doc(user_id: ObjectId, agent: Optional[str] = None, tags: Optional[list[str]] = None) -> dict:
    ts = now_utc()
    return {
        "user": user_id,
        "agent": agent,
        "tags": tags or [],
        "createdAt": ts,
        "updatedAt": ts,
    }


_current_tz: ContextVar[Optional[tzinfo]] = ContextVar("intellitwin_user_tz", default=None)


def get_user_tz(user: Optional[dict] = None) -> tzinfo:
    """The user's timezone: profile.timezone if valid, else this machine's
    local timezone (IntelliTwin runs on the user's own computer)."""
    name = ((user or {}).get("profile") or {}).get("timezone") if user else None
    if name:
        try:
            return ZoneInfo(str(name).strip())
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            pass
    return datetime.now().astimezone().tzinfo or timezone.utc


def set_user_tz(user: Optional[dict]) -> None:
    """Called wherever agents act on behalf of a user, so naive datetimes the
    LLM produces ("2026-10-13T15:00:00") are read in the user's own timezone
    instead of silently being treated as UTC (which shifted or hid events)."""
    _current_tz.set(get_user_tz(user))


def parse_date(value):
    """Frontend sends dates as ISO strings; Mongo needs real datetimes.
    Timezone-aware input is honoured. Naive input (what LLMs usually emit) is
    interpreted in the active user's timezone, then stored as UTC."""
    if value is None or value == "":
        return None
    parsed = None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text.replace(" ", "T", 1))
            except ValueError:
                return None
    if parsed.tzinfo is None:
        tz = _current_tz.get()
        if tz is not None:
            parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed
