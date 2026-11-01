from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.date_range import resolve_date_range, local_day_bounds, exclusive_end
from app.owned import set_user_tz
from app.tools.workspace import _read_calendar
from app.tools.workspace_universal import _run as crud

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)  # 15:30 IST on 12 Oct


# ---- pure date logic -------------------------------------------------------
def test_today_tomorrow_yesterday():
    t = resolve_date_range("what's on today", IST, NOW)
    assert t == local_day_bounds(datetime(2026, 10, 12).date(), IST)
    assert resolve_date_range("Tomorrow?", IST, NOW)[0] == local_day_bounds(datetime(2026, 10, 13).date(), IST)[0]
    assert resolve_date_range("yesterday", IST, NOW)[1] == t[0]


def test_midnight_boundary_uses_local_not_utc():
    late = datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)  # 01:30 IST on the 13th
    s, e = resolve_date_range("today", IST, late)
    assert s == datetime(2026, 10, 12, 18, 30, tzinfo=timezone.utc)
    assert e == datetime(2026, 10, 13, 18, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("text,day", [("11 October 2026", 11), ("11th oct", 11), ("October 11, 2026", 11), ("2026-10-11", 11)])
def test_explicit_dates(text, day):
    s, e = resolve_date_range(text, IST, NOW)
    assert s == local_day_bounds(datetime(2026, 10, day).date(), IST)[0]
    assert e - s == local_day_bounds(datetime(2026, 10, day).date(), IST)[1] - s


def test_week_ranges():
    s, e = resolve_date_range("this week", IST, NOW)  # Mon 12 Oct .. Sun 18 Oct
    assert (e - s).days == 7
    ns, _ = resolve_date_range("next week", IST, NOW)
    assert ns == e


def test_no_date_and_invalid():
    assert resolve_date_range("hello there", IST, NOW) is None
    assert resolve_date_range("31 February 2026", IST, NOW) is None


def test_exclusive_end_for_235959():
    hi = datetime(2026, 10, 11, 23, 59, 59, tzinfo=IST).astimezone(timezone.utc)
    assert exclusive_end(hi, IST) == datetime(2026, 10, 12, 0, 0, tzinfo=IST).astimezone(timezone.utc)


# ---- database-backed -------------------------------------------------------
async def _mk(user, title, start, **kw):
    set_user_tz(user)
    return await crud(user, {"module": "calendar", "action": "create",
                             "data": {"title": title, "startsAt": start, **kw}})


async def test_create_then_retrieve_and_default_duration(db, user_factory):
    u = await user_factory()
    r = await _mk(u, "Dessert date", "2026-10-12T16:00:00")
    assert r["action"] == "created" and "error" not in r
    got = await crud(u, {"module": "calendar", "action": "read", "id": r["item"]["_id"]})
    assert got["item"]["title"] == "Dessert date"
    assert datetime.fromisoformat(got["item"]["endsAt"].replace("Z", "+00:00")) - \
        datetime.fromisoformat(got["item"]["startsAt"].replace("Z", "+00:00")) == __import__("datetime").timedelta(hours=1)


async def test_date_filter_excludes_next_day(db, user_factory):
    u = await user_factory()
    await _mk(u, "On 11th", "2026-10-11T15:00:00")
    await _mk(u, "On 12th", "2026-10-12T09:00:00")
    await _mk(u, "Late 11th", "2026-10-11T23:59:00")
    await _mk(u, "Early 12th", "2026-10-12T00:00:00")
    res = await _read_calendar(u, {"date": "11 October 2026"})
    assert sorted(e["title"] for e in res["events"]) == ["Late 11th", "On 11th"]
    res = await _read_calendar(u, {"from": "2026-10-11T00:00:00", "to": "2026-10-11T23:59:59"})
    assert sorted(e["title"] for e in res["events"]) == ["Late 11th", "On 11th"]


async def test_empty_result_is_empty(db, user_factory):
    u = await user_factory()
    assert (await _read_calendar(u, {"date": "2026-10-20"}))["events"] == []


async def test_duplicate_retry_creates_one_event(db, user_factory):
    u = await user_factory()
    a = await _mk(u, "Standup", "2026-10-13T10:00:00")
    b = await _mk(u, "Standup", "2026-10-13T10:00:00")
    assert b.get("duplicate") and a["item"]["_id"] == b["item"]["_id"]
    assert await db.calendar_events.count_documents({}) == 1


async def test_invalid_input_rejected(db, user_factory):
    u = await user_factory()
    assert "error" in await _mk(u, "x", "not a date")
    assert "error" in await crud(u, {"module": "calendar", "action": "create", "data": {"startsAt": "2026-10-13T10:00:00"}})
    assert "error" in await _mk(u, "Bad", "2026-10-13T10:00:00", endsAt="2026-10-13T09:00:00")
    assert await db.calendar_events.count_documents({}) == 0


async def test_update_and_delete_only_target_event(db, user_factory):
    u = await user_factory()
    a = (await _mk(u, "A", "2026-10-13T10:00:00"))["item"]
    b = (await _mk(u, "B", "2026-10-13T12:00:00"))["item"]
    up = await crud(u, {"module": "calendar", "action": "update", "id": a["_id"], "data": {"startsAt": "2026-10-13T17:00:00"}})
    assert "error" not in up
    assert (await crud(u, {"module": "calendar", "action": "read", "id": b["_id"]}))["item"]["startsAt"] == b["startsAt"]
    assert (await crud(u, {"module": "calendar", "action": "delete", "id": a["_id"], "confirm": True}))["ok"]
    assert await db.calendar_events.count_documents({}) == 1


async def test_cross_user_isolation(db, user_factory):
    u1, u2 = await user_factory("a"), await user_factory("b")
    ev = (await _mk(u1, "Private", "2026-10-13T10:00:00"))["item"]
    assert "error" in await crud(u2, {"module": "calendar", "action": "read", "id": ev["_id"]})
    assert "error" in await crud(u2, {"module": "calendar", "action": "update", "id": ev["_id"], "data": {"title": "x"}})
    assert "error" in await crud(u2, {"module": "calendar", "action": "delete", "id": ev["_id"]})
    assert (await _read_calendar(u2, {"date": "2026-10-13"}))["events"] == []
    assert await db.calendar_events.count_documents({}) == 1


async def test_timezone_boundary_per_user(db, user_factory):
    ist, ny = await user_factory("i", "Asia/Kolkata"), await user_factory("n", "America/New_York")
    await _mk(ist, "ist", "2026-10-12T23:30:00")
    await _mk(ny, "ny", "2026-10-12T23:30:00")
    assert [e["title"] for e in (await _read_calendar(ist, {"date": "2026-10-12"}))["events"]] == ["ist"]
    assert [e["title"] for e in (await _read_calendar(ny, {"date": "2026-10-12"}))["events"]] == ["ny"]


async def test_database_failure_is_reported_not_swallowed(db, user_factory, monkeypatch):
    u = await user_factory()
    async def boom(*a, **k): raise RuntimeError("db down")
    monkeypatch.setattr(type(db.calendar_events), "insert_one", boom)
    with pytest.raises(RuntimeError):
        await _mk(u, "X", "2026-10-13T10:00:00")  # surfaced to caller; caller reports failure
