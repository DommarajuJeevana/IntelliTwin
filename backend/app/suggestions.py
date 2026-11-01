"""Phase F - proactive workspace suggestions.

Read-only intelligence over the user's *stored* tasks, goals and calendar.
Nothing here creates or changes workspace records: a suggestion is advice
(`kind: "suggestion"`), never an action already performed. The only write is the
user's own dismissal record in `suggestion_dismissals`.

Rules (all evaluated in the user's timezone):
  overdue_task      open task whose due date is before today
  task_due_today    open task due today
  task_due_soon     open task due in the next DUE_SOON_DAYS days
  goal_due_soon     open goal due within GOAL_SOON_DAYS days (or overdue)
  calendar_overlap  two upcoming events whose time ranges overlap (half-open:
                    back-to-back events are NOT a conflict)
  tasks_no_due_date one aggregate suggestion when open tasks have no due date

Date-only due dates are stored as midnight UTC; a due value at exactly 00:00:00
UTC is therefore read as that calendar date, any other value is converted to
the user's local date.
"""
from datetime import date, datetime, timedelta, timezone

from app.database import get_db
from app.owned import get_user_tz, now_utc

DUE_SOON_DAYS = 3
GOAL_SOON_DAYS = 7
CONFLICT_WINDOW_DAYS = 14
DEFAULT_EVENT_MINUTES = 60
DEFAULT_DISMISS_DAYS = 7
MAX_SUGGESTIONS = 20
MAX_RECORDS = 500

_SEVERITY = {"high": 0, "medium": 1, "low": 2}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _due_date(value: datetime, tz) -> date:
    v = _utc(value)
    if v.hour == v.minute == v.second == v.microsecond == 0:
        return v.date()
    return v.astimezone(tz).date()


def _s(key, type_, severity, message, module=None, record_id=None, extra=None):
    out = {
        "kind": "suggestion",           # never an action already performed
        "key": key,
        "type": type_,
        "severity": severity,
        "message": message,
        "module": module,
        "recordId": str(record_id) if record_id else None,
    }
    if extra:
        out.update(extra)
    return out


def build_suggestions(tasks: list[dict], goals: list[dict], events: list[dict], now: datetime, tz) -> list[dict]:
    """Pure function: no database access, fully deterministic for a given `now`."""
    today = _utc(now).astimezone(tz).date()
    out: list[dict] = []

    undated = 0
    for t in tasks:
        title = str(t.get("title") or "Untitled task")[:80]
        due = t.get("dueDate")
        if not due:
            if not t.get("scheduledStart"):
                undated += 1
            continue
        d = _due_date(due, tz)
        days = (d - today).days
        if days < 0:
            n = -days
            out.append(_s(f"overdue_task:{t['_id']}:{d.isoformat()}", "overdue_task", "high",
                          f'"{title}" is {n} day{"s" if n != 1 else ""} past its due date.', "tasks", t["_id"],
                          {"dueDate": d.isoformat()}))
        elif days == 0:
            out.append(_s(f"task_due_today:{t['_id']}:{d.isoformat()}", "task_due_today", "high",
                          f'"{title}" is due today.', "tasks", t["_id"], {"dueDate": d.isoformat()}))
        elif days <= DUE_SOON_DAYS:
            out.append(_s(f"task_due_soon:{t['_id']}:{d.isoformat()}", "task_due_soon", "medium",
                          f'"{title}" is due in {days} day{"s" if days != 1 else ""}.', "tasks", t["_id"],
                          {"dueDate": d.isoformat()}))

    if undated:
        out.append(_s("tasks_no_due_date", "tasks_no_due_date", "low",
                      f"{undated} open task{'s have' if undated != 1 else ' has'} no due date or schedule.",
                      "tasks", None, {"count": undated}))

    for g in goals:
        due = g.get("dueDate")
        if not due:
            continue
        d = _due_date(due, tz)
        days = (d - today).days
        if days <= GOAL_SOON_DAYS:
            title = str(g.get("title") or "Untitled goal")[:80]
            if days < 0:
                msg = f'Goal "{title}" is {-days} day{"s" if days != -1 else ""} past its target date.'
            elif days == 0:
                msg = f'Goal "{title}" targets today.'
            else:
                msg = f'Goal "{title}" targets a date {days} day{"s" if days != 1 else ""} away.'
            out.append(_s(f"goal_due_soon:{g['_id']}:{d.isoformat()}", "goal_due_soon",
                          "high" if days < 0 else "medium", msg, "goals", g["_id"], {"dueDate": d.isoformat()}))

    # Overlapping events (half-open intervals) in the upcoming window.
    spans = []
    for e in events:
        if not e.get("startsAt"):
            continue
        s0 = _utc(e["startsAt"])
        e0 = _utc(e["endsAt"]) if e.get("endsAt") else s0 + timedelta(minutes=DEFAULT_EVENT_MINUTES)
        if e0 <= s0:
            e0 = s0 + timedelta(minutes=DEFAULT_EVENT_MINUTES)
        spans.append((s0, e0, e))
    spans.sort(key=lambda x: x[0])
    for i, (s1, e1, a) in enumerate(spans):
        for s2, e2, b in spans[i + 1:]:
            if s2 >= e1:
                break
            if s1 < e2 and s2 < e1:
                ids = sorted([str(a["_id"]), str(b["_id"])])
                at = max(s1, s2).astimezone(tz).strftime("%a %d %b %H:%M")
                out.append(_s(f"calendar_overlap:{ids[0]}:{ids[1]}", "calendar_overlap", "medium",
                              f'"{str(a.get("title") or "Event")[:60]}" overlaps "{str(b.get("title") or "Event")[:60]}" at {at}.',
                              "calendar", a["_id"], {"otherRecordId": str(b["_id"])}))

    out.sort(key=lambda s: (_SEVERITY[s["severity"]], s["key"]))
    return out[:MAX_SUGGESTIONS]


async def active_dismissed_keys(user_id, now: datetime) -> set[str]:
    rows = await get_db().suggestion_dismissals.find({"user": user_id}).to_list(length=1000)
    return {r["key"] for r in rows if r.get("expiresAt") and _utc(r["expiresAt"]) > _utc(now)}


async def get_suggestions(user: dict, now: datetime | None = None) -> list[dict]:
    now = now or now_utc()
    tz = get_user_tz(user)
    uid = user["_id"]
    db = get_db()
    tasks = await db.tasks.find({"user": uid, "status": {"$ne": "done"}}).to_list(length=MAX_RECORDS)
    goals = await db.goals.find({"user": uid, "status": {"$ne": "done"}}).to_list(length=MAX_RECORDS)
    events = await db.calendar_events.find({
        "user": uid,
        "startsAt": {"$gte": _utc(now) - timedelta(hours=24), "$lt": _utc(now) + timedelta(days=CONFLICT_WINDOW_DAYS)},
    }).to_list(length=MAX_RECORDS)
    # Only events that have not finished yet can be an actionable conflict.
    events = [e for e in events if _utc(e.get("endsAt") or e["startsAt"] + timedelta(minutes=DEFAULT_EVENT_MINUTES)) > _utc(now)]
    dismissed = await active_dismissed_keys(uid, now)
    return [s for s in build_suggestions(tasks, goals, events, now, tz) if s["key"] not in dismissed]


async def dismiss_suggestion(user: dict, key: str, days: int = DEFAULT_DISMISS_DAYS, now: datetime | None = None) -> dict:
    now = now or now_utc()
    days = max(1, min(int(days), 90))
    expires = _utc(now) + timedelta(days=days)
    await get_db().suggestion_dismissals.update_one(
        {"user": user["_id"], "key": key},
        {"$set": {"expiresAt": expires, "updatedAt": _utc(now)}},
        upsert=True,
    )
    return {"key": key, "dismissedUntil": expires.isoformat()}
