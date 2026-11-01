from datetime import datetime, timedelta, timezone

from app import conversation
from app.owned import set_user_tz
from app.routers.chat import _history_prompt, HISTORY_MESSAGES
from app.tools.workspace_universal import _run as crud
from app.workspace_actions import try_direct_workspace_action, _is_date_followup


def msgs(*pairs):
    return [{"role": r, "content": c} for r, c in pairs]


def test_followup_detection_needs_calendar_context():
    ctx = msgs(("user", "What events do I have today?"), ("assistant", "You have 1 event"), ("user", "Tomorrow?"))
    assert _is_date_followup("Tomorrow?", ctx)
    assert not _is_date_followup("Tomorrow?", msgs(("user", "hello"), ("user", "Tomorrow?")))
    assert not _is_date_followup("Tomorrow?", [])
    assert not _is_date_followup("Move the dessert date to tomorrow", ctx)
    assert not _is_date_followup("Explain what tomorrow means in Spanish please now", ctx)


async def test_tomorrow_followup_lists_tomorrows_events(db, user_factory):
    u = await user_factory()
    set_user_tz(u)
    now = datetime.now(timezone.utc).astimezone(__import__("app.owned", fromlist=["x"]).get_user_tz(u))
    today, tomorrow = now.strftime("%Y-%m-%d"), (now + timedelta(days=1)).strftime("%Y-%m-%d")
    await crud(u, {"module": "calendar", "action": "create", "data": {"title": "Dessert date", "startsAt": f"{today}T16:00:00"}})
    await crud(u, {"module": "calendar", "action": "create", "data": {"title": "Dentist", "startsAt": f"{tomorrow}T11:00:00"}})
    conv = msgs(("user", "What events do I have today?"), ("assistant", "Dessert date at 4 PM"), ("user", "Tomorrow?"))
    r = await try_direct_workspace_action(u, "Tomorrow?", conv)
    assert "Dentist" in r["message"] and "Dessert date" not in r["message"]
    conv2 = msgs(("user", "events tomorrow?"), ("assistant", "x"), ("user", "today?"))
    r2 = await try_direct_workspace_action(u, "today?", conv2)
    assert "Dessert date" in r2["message"] and "Dentist" not in r2["message"]


async def test_no_events_is_honest(db, user_factory):
    u = await user_factory()
    conv = msgs(("user", "what meetings do I have today"), ("assistant", "none"), ("user", "tomorrow?"))
    r = await try_direct_workspace_action(u, "tomorrow?", conv)
    assert "no calendar events" in r["message"].lower()


async def test_history_is_recent_bounded_and_isolated(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(30):
        await db.agent_messages.insert_one({"user": a["_id"], "thread": "t1", "author": "user",
                                            "content": f"msg-{i}", "createdAt": base + timedelta(minutes=i)})
    await db.agent_messages.insert_one({"user": b["_id"], "thread": "t1", "author": "user", "content": "B-SECRET", "createdAt": base})
    await db.agent_messages.insert_one({"user": a["_id"], "thread": "other", "author": "user", "content": "OTHER-THREAD", "createdAt": base})
    out = await _history_prompt(a["_id"], "t1")
    lines = [l for l in out.splitlines() if l.startswith("user:")]
    assert len(lines) == HISTORY_MESSAGES
    assert lines[-1] == "user: msg-29" and "msg-0" not in out       # most recent, not oldest
    assert "B-SECRET" not in out and "OTHER-THREAD" not in out
    assert await _history_prompt(a["_id"], None) == ""
    assert await _history_prompt(a["_id"], "missing") == ""


async def test_mission_control_thread_isolation(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    await conversation.create_message(a["_id"], "user", "hi from a")
    await conversation.create_message(b["_id"], "user", "hi from b")
    assert [m["content"] for m in await conversation.get_messages(a["_id"])] == ["hi from a"]
    for i in range(150):
        await conversation.create_message(a["_id"], "user", f"m{i}")
    assert len(await conversation.get_messages(a["_id"], limit=1000)) == 100  # hard cap
