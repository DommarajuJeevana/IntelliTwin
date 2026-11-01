"""Phase F: proactive suggestions. Pure-logic tests plus mock-Mongo DB tests."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from app import suggestions as sg

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)  # 15:30 IST, Mon 12 Oct


def T(title, due=None, **kw):
    return {"_id": ObjectId(), "title": title, "dueDate": due, "status": "todo", **kw}


def types(items):
    return sorted(s["type"] for s in items)


def test_empty_workspace_gives_nothing():
    assert sg.build_suggestions([], [], [], NOW, IST) == []


def test_overdue_today_soon_and_boundaries():
    tasks = [
        T("old", datetime(2026, 10, 11)),                         # date-only, yesterday
        T("today", datetime(2026, 10, 12)),                       # date-only, today
        T("soon", datetime(2026, 10, 15)),                        # +3 days, inside window
        T("later", datetime(2026, 10, 16)),                       # +4 days, outside window
    ]
    out = sg.build_suggestions(tasks, [], [], NOW, IST)
    assert types(out) == ["overdue_task", "task_due_soon", "task_due_today"]


def test_timed_due_converted_to_user_timezone():
    # 20:00 UTC on the 12th is 01:30 IST on the 13th -> "due in 1 day" for an IST user, "today" for UTC
    t = T("late", datetime(2026, 10, 12, 20, 0))
    assert types(sg.build_suggestions([t], [], [], NOW, IST)) == ["task_due_soon"]
    assert types(sg.build_suggestions([t], [], [], NOW, timezone.utc)) == ["task_due_today"]


def test_no_due_date_is_single_aggregate_and_scheduled_tasks_excluded():
    tasks = [T("a"), T("b"), T("c", scheduledStart=NOW)]
    out = sg.build_suggestions(tasks, [], [], NOW, IST)
    assert len(out) == 1 and out[0]["type"] == "tasks_no_due_date" and out[0]["count"] == 2


def test_overlap_is_half_open_and_pairs_not_duplicated():
    def ev(title, h, m=0, dur=60):
        s = datetime(2026, 10, 13, h, m, tzinfo=timezone.utc)
        return {"_id": ObjectId(), "title": title, "startsAt": s, "endsAt": s + timedelta(minutes=dur)}

    a, b, c = ev("A", 5), ev("B", 5, 30), ev("C", 6)      # A 5:00-6:00, B 5:30-6:30, C 6:00-7:00
    out = sg.build_suggestions([], [], [a, b, c], NOW, IST)
    assert [s["type"] for s in out] == ["calendar_overlap", "calendar_overlap"]   # A/B and B/C, not A/C
    assert len({s["key"] for s in out}) == 2
    assert sg.build_suggestions([], [], [a, c], NOW, IST) == []                   # back-to-back is not a conflict


def test_event_without_end_uses_default_duration():
    s = datetime(2026, 10, 13, 5, 0, tzinfo=timezone.utc)
    a = {"_id": ObjectId(), "title": "A", "startsAt": s}
    b = {"_id": ObjectId(), "title": "B", "startsAt": s + timedelta(minutes=30), "endsAt": s + timedelta(minutes=90)}
    assert types(sg.build_suggestions([], [], [a, b], NOW, IST)) == ["calendar_overlap"]


def test_suggestions_are_labelled_as_suggestions_and_keys_stable():
    t = T("x", datetime(2026, 10, 11))
    first = sg.build_suggestions([t], [], [], NOW, IST)[0]
    again = sg.build_suggestions([t], [], [], NOW + timedelta(hours=1), IST)[0]
    assert first["kind"] == "suggestion" and first["key"] == again["key"]


def test_goal_reminders():
    g = {"_id": ObjectId(), "title": "Ship", "dueDate": datetime(2026, 10, 14), "status": "in_progress"}
    far = {"_id": ObjectId(), "title": "Far", "dueDate": datetime(2026, 12, 1), "status": "in_progress"}
    out = sg.build_suggestions([], [g, far], [], NOW, IST)
    assert types(out) == ["goal_due_soon"]


# ---- database-backed ---------------------------------------------------------
async def test_user_isolation_and_done_tasks_ignored(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    await db.tasks.insert_one({"user": a["_id"], "title": "mine", "status": "todo", "dueDate": datetime(2026, 10, 1)})
    await db.tasks.insert_one({"user": a["_id"], "title": "finished", "status": "done", "dueDate": datetime(2026, 10, 1)})
    await db.tasks.insert_one({"user": b["_id"], "title": "theirs", "status": "todo", "dueDate": datetime(2026, 10, 1)})
    mine = await sg.get_suggestions(a, NOW)
    assert [s["type"] for s in mine] == ["overdue_task"] and "mine" in mine[0]["message"]
    assert "theirs" not in str(mine)


async def test_dismissal_hides_then_expires_and_is_per_user(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    for u in (a, b):
        await db.tasks.insert_one({"user": u["_id"], "title": "t", "status": "todo", "dueDate": datetime(2026, 10, 1)})
    key = (await sg.get_suggestions(a, NOW))[0]["key"]
    await sg.dismiss_suggestion(a, key, days=2, now=NOW)
    assert await sg.get_suggestions(a, NOW) == []
    assert len(await sg.get_suggestions(b, NOW)) == 1                      # other user unaffected
    assert len(await sg.get_suggestions(a, NOW + timedelta(days=3))) == 1  # expired
    await sg.dismiss_suggestion(a, key, days=2, now=NOW)                   # idempotent upsert
    assert await db.suggestion_dismissals.count_documents({"user": a["_id"]}) == 1


async def test_get_suggestions_never_writes_workspace_records(db, user_factory):
    a = await user_factory("a")
    await db.tasks.insert_one({"user": a["_id"], "title": "t", "status": "todo", "dueDate": datetime(2026, 10, 1)})
    before = await db.tasks.find_one({"user": a["_id"]})
    await sg.get_suggestions(a, NOW)
    assert await db.tasks.find_one({"user": a["_id"]}) == before
    assert await db.suggestion_dismissals.count_documents({}) == 0


async def test_empty_workspace_db(db, user_factory):
    assert await sg.get_suggestions(await user_factory("a"), NOW) == []
