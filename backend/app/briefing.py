"""
Turns raw activity data into the short, proactive notes shown at the top of
Mission Control - direct port of backend/utils/briefing.js.

Each note is {agent, message}. Kept as plain data so the frontend can render
it however it wants without any agent-specific logic living there.

Phase 7 adds _build_stale_goal_nudge: the roadmap's own proactive-
intelligence example, "You haven't worked on this goal for 8 days."
"""
from datetime import datetime, timezone

STALE_GOAL_DAYS = 8


def _days_between(a: datetime, b: datetime) -> int:
    # Real MongoDB (via Motor/PyMongo) returns naive UTC datetimes by
    # default; some other environments (tests, other drivers) return
    # tz-aware ones. Normalize both to naive-UTC before subtracting so this
    # doesn't blow up either way.
    if a.tzinfo is not None:
        a = a.astimezone(timezone.utc).replace(tzinfo=None)
    if b.tzinfo is not None:
        b = b.astimezone(timezone.utc).replace(tzinfo=None)
    return (b - a).days


def _build_echo_welcome(user: dict, since_visit_items: list[dict]) -> dict:
    if not user.get("previousLoginAt"):
        return {"agent": "echo", "message": "Welcome to IntelliTwin. I'll start remembering things as you go."}

    if len(since_visit_items) == 0:
        return {"agent": "echo", "message": "Welcome back. Nothing new since your last visit — where should we start?"}

    most_recent = since_visit_items[0]
    count = len(since_visit_items)
    plural = "" if count == 1 else "s"
    return {
        "agent": "echo",
        "message": (
            f'Welcome back. Since you were last here you added {count} thing{plural} — '
            f'including "{most_recent["label"]}". Want to pick that back up?'
        ),
    }


def _build_compass_nudge(overdue_task: dict | None, now: datetime) -> dict | None:
    if not overdue_task:
        return None

    days = _days_between(overdue_task["dueDate"], now)
    if days < 1:
        return None

    plural = "" if days == 1 else "s"
    return {
        "agent": "compass",
        "message": f'Would you like to move "{overdue_task["title"]}" up? It\'s {days} day{plural} past its date.',
    }


def _build_stale_goal_nudge(stale_goal: dict | None, now: datetime) -> dict | None:
    """
    Phase 7 - proactive intelligence: flags the least-recently-touched open
    goal if nothing's happened on it in STALE_GOAL_DAYS. `stale_goal` is
    expected to carry a `lastActivityAt` field the caller computed by
    looking at the goal itself plus any tasks/documents/research linked to
    it (see dashboard.py) - "touched" means any of those changed, not just
    the goal document.
    """
    if not stale_goal:
        return None

    days = _days_between(stale_goal["lastActivityAt"], now)
    if days < STALE_GOAL_DAYS:
        return None

    return {
        "agent": "compass",
        "message": f'You haven\'t worked on "{stale_goal["title"]}" in {days} days. Still a priority, or should it wait?',
    }


def build_briefing(
    user: dict,
    since_visit_items: list[dict],
    overdue_task: dict | None,
    now: datetime,
    stale_goal: dict | None = None,
) -> list[dict]:
    notes = [_build_echo_welcome(user, since_visit_items)]
    compass_note = _build_compass_nudge(overdue_task, now)
    if compass_note:
        notes.append(compass_note)
    stale_note = _build_stale_goal_nudge(stale_goal, now)
    if stale_note:
        notes.append(stale_note)
    return notes
