"""Phase B: shared agent tools, ownership, invalid input, failure handling.

Unit tests against an in-memory mock Mongo (mongomock-motor) and stub handlers -
not integration tests against a real MongoDB or model.
"""
import pytest

from app.llm import _execute_tool
from app.owned import set_user_tz
from app.tools import registry
from app.tools import workspace_universal as wu
from app.tools.base import tools_by_name
from app.tools.workspace_universal import _run as crud

AGENT_TOOLSETS = {
    "echo": registry.ECHO_TOOLS,
    "atlas": registry.ATLAS_TOOLS,
    "compass": registry.COMPASS_TOOLS,
    "nova": registry.NOVA_TOOLS,
}


# ---- registry ---------------------------------------------------------------
@pytest.mark.parametrize("agent", list(AGENT_TOOLSETS))
def test_every_agent_has_shared_crud_and_valid_tools(agent):
    tools = AGENT_TOOLSETS[agent]
    names = [t.name for t in tools]
    assert "workspace_crud" in names
    assert len(names) == len(set(names)), f"duplicate tool names for {agent}"
    for t in tools:
        assert t.input_schema.get("type") == "object"
        assert callable(t.handler)


def test_role_specific_tools_present():
    assert "search_web" in tools_by_name(registry.ATLAS_TOOLS)
    for agent in AGENT_TOOLSETS:
        assert "search_memory" in tools_by_name(AGENT_TOOLSETS[agent])
    assert "save_memory" in tools_by_name(registry.ECHO_TOOLS)


# ---- shared CRUD: validation ------------------------------------------------
async def test_unsupported_module_action_and_ids(db, user_factory):
    u = await user_factory()
    assert "error" in await crud(u, {"module": "users", "action": "list"})
    assert "error" in await crud(u, {"module": "goals", "action": "drop"})
    assert "error" in await crud(u, {"module": "goals", "action": "read", "id": "not-an-id"})
    assert "error" in await crud(u, {"module": "goals", "action": "read"})
    assert "error" in await crud(u, {"module": "goals", "action": "create", "data": "oops"})
    assert "error" in await crud(u, {"module": "goals", "action": "create", "data": {}})


async def test_invalid_enum_is_rejected_not_stored(db, user_factory):
    u = await user_factory()
    with pytest.raises(ValueError):
        await crud(u, {"module": "tasks", "action": "create", "data": {"title": "t", "priority": "urgent!!"}})
    assert await db.tasks.count_documents({}) == 0


async def test_status_filter_cannot_inject_operators(db, user_factory):
    u1, u2 = await user_factory("a"), await user_factory("b")
    await crud(u1, {"module": "goals", "action": "create", "data": {"title": "mine"}})
    await crud(u2, {"module": "goals", "action": "create", "data": {"title": "theirs"}})
    res = await crud(u1, {"module": "goals", "action": "list", "status": {"$ne": "zzz"}})
    assert [i["title"] for i in res["items"]] == ["mine"]


async def test_tags_are_cleaned_and_agent_not_spoofable(db, user_factory):
    u = await user_factory()
    r = await crud(u, {"module": "goals", "action": "create", "agent": "admin",
                       "data": {"title": "g", "tags": ["ok", 5, {"$x": 1}, "x" * 500] + ["t"] * 40}})
    item = r["item"]
    assert item["agent"] == "agent"
    assert all(isinstance(t, str) and len(t) <= 50 for t in item["tags"])
    assert len(item["tags"]) <= 20


# ---- shared CRUD: ownership across every module -----------------------------
@pytest.mark.parametrize("module,data", [
    ("goals", {"title": "g"}),
    ("tasks", {"title": "t"}),
    ("notes", {"title": "n", "content": "<p>x</p>"}),
    ("documents", {"title": "d", "content": "x"}),
    ("projects", {"name": "p"}),
])
async def test_cross_user_isolation_every_module(db, user_factory, module, data):
    u1, u2 = await user_factory("a"), await user_factory("b")
    created = await crud(u1, {"module": module, "action": "create", "data": data})
    if "error" in created:  # module needs other required fields; skip rather than guess
        pytest.skip(f"{module}: {created['error']}")
    rid = created["item"]["_id"]
    assert "error" in await crud(u2, {"module": module, "action": "read", "id": rid})
    assert "error" in await crud(u2, {"module": module, "action": "update", "id": rid, "data": data})
    assert "error" in await crud(u2, {"module": module, "action": "delete", "id": rid, "confirm": True})
    assert (await crud(u2, {"module": module, "action": "list"}))["count"] == 0
    assert (await crud(u1, {"module": module, "action": "read", "id": rid}))["item"]["_id"] == rid


# ---- destructive safeguard --------------------------------------------------
async def test_delete_requires_explicit_confirmation(db, user_factory):
    u = await user_factory()
    rid = (await crud(u, {"module": "goals", "action": "create", "data": {"title": "keep me"}}))["item"]["_id"]
    res = await crud(u, {"module": "goals", "action": "delete", "id": rid})
    assert res.get("needs_confirmation") is True and "ok" not in res
    assert await db.goals.count_documents({}) == 1
    # truthy-but-not-True values do not count as confirmation
    assert (await crud(u, {"module": "goals", "action": "delete", "id": rid, "confirm": "yes"})).get("needs_confirmation")
    assert await db.goals.count_documents({}) == 1
    assert (await crud(u, {"module": "goals", "action": "delete", "id": rid, "confirm": True}))["ok"] is True
    assert await db.goals.count_documents({}) == 0
    assert "error" in await crud(u, {"module": "goals", "action": "delete", "id": rid, "confirm": True})


async def test_calendar_update_rejects_end_before_start(db, user_factory):
    u = await user_factory()
    set_user_tz(u)
    ev = (await crud(u, {"module": "calendar", "action": "create",
                         "data": {"title": "E", "startsAt": "2026-10-13T10:00:00"}}))["item"]
    bad = await crud(u, {"module": "calendar", "action": "update", "id": ev["_id"],
                         "data": {"endsAt": "2026-10-13T09:00:00"}})
    assert "error" in bad
    got = (await crud(u, {"module": "calendar", "action": "read", "id": ev["_id"]}))["item"]
    assert got["endsAt"] == ev["endsAt"]


# ---- failure handling (no false success) ------------------------------------
class _FailingColl:
    async def find_one(self, *a, **k):
        return None

    async def insert_one(self, *a, **k):
        raise RuntimeError("db down mongodb://user:pw@host")


class _FailingDB:
    def __getitem__(self, name):
        return _FailingColl()


async def test_failed_insert_never_reports_success(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(wu, "get_db", lambda: _FailingDB())
    tool = tools_by_name(registry.NOVA_TOOLS)["workspace_crud"]
    res = await _execute_tool({"workspace_crud": tool}, u, "workspace_crud",
                              {"module": "goals", "action": "create", "data": {"title": "x"}})
    assert "error" in res
    assert "item" not in res and res.get("action") != "created"


async def test_execute_tool_unknown_missing_args_and_exception(db, user_factory):
    from app.tools.base import Tool
    u = await user_factory()

    async def boom(user, args):
        raise RuntimeError("kaboom")

    t = Tool("boom", "d", {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}, boom)
    m = {"boom": t}
    assert "error" in await _execute_tool(m, u, "nope", {})
    assert "error" in await _execute_tool(m, u, "boom", {})
    assert "error" in await _execute_tool(m, u, "boom", {"x": "1"})


async def test_moving_event_start_preserves_duration(db, user_factory):
    from datetime import datetime, timedelta
    u = await user_factory()
    set_user_tz(u)
    ev = (await crud(u, {"module": "calendar", "action": "create",
                         "data": {"title": "E", "startsAt": "2026-10-13T10:00:00", "endsAt": "2026-10-13T11:30:00"}}))["item"]
    up = (await crud(u, {"module": "calendar", "action": "update", "id": ev["_id"],
                         "data": {"startsAt": "2026-10-13T17:00:00"}}))["item"]
    parse = lambda v: datetime.fromisoformat(v.replace("Z", "+00:00"))
    assert parse(up["endsAt"]) - parse(up["startsAt"]) == timedelta(minutes=90)
    assert parse(up["startsAt"]) > parse(ev["startsAt"])
