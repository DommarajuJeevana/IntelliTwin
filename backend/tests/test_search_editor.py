import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.dependencies import require_auth
from app.routers.generic_crud import build_module_router
from app.routers.search import run_search
from app.sanitize import sanitize_rich_text


# ---- sanitiser ---------------------------------------------------------------
def test_sanitizer_strips_scripts_and_unsafe_links():
    out = sanitize_rich_text('<p onclick="x()">Hi</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a><a href="https://ok.io">ok</a>')
    assert "<script" not in out and "onclick" not in out and "javascript:" not in out
    assert 'href="https://ok.io"' in out and "noopener" in out


def test_sanitizer_keeps_formatting_and_plain_text():
    html = "<h2>T</h2><p><strong>b</strong> <em>i</em> <u>u</u></p><ul><li>a</li></ul><ol><li>b</li></ol>"
    assert sanitize_rich_text(html) == html
    assert sanitize_rich_text("legacy plain text\nline 2") == "legacy plain text\nline 2"


# ---- search -----------------------------------------------------------------
async def _seed(db, uid, coll, **doc):
    now = datetime.now(timezone.utc)
    await db[coll].insert_one({"user": uid, "createdAt": now, "updatedAt": now, **doc})


async def test_search_each_module_case_insensitive_partial(db, user_factory):
    u = await user_factory()
    uid = u["_id"]
    await _seed(db, uid, "goals", title="Learn Kubernetes", description="")
    await _seed(db, uid, "tasks", title="Fix kubernetes manifest")
    await _seed(db, uid, "calendar_events", title="Kubernetes meetup", location="", notes="", startsAt=datetime.now(timezone.utc))
    await _seed(db, uid, "notes", title="K8s", body="<p>about <b>KUBERNETES</b> pods</p>")
    await _seed(db, uid, "documents", title="Cluster report", content="kubernetes cluster sizing")
    await _seed(db, uid, "research_items", query="kubernetes security", summary="")
    await _seed(db, uid, "projects", name="Platform", description="migrate to kubernetes")
    await _seed(db, uid, "memory_entries", title="Skill", content="Knows kubernetes basics")
    r = await run_search(uid, "  KUBERNETES ", semantic=False, limit=50)
    assert {x["type"] for x in r["results"]} == {"goal", "task", "calendar", "note", "document", "research", "project", "memory"}
    assert all(x["match"] == "keyword" for x in r["results"])
    r = await run_search(uid, "kuber", semantic=False)  # partial
    assert r["total"] == 8
    assert all("embedding" not in x["item"] for x in r["results"])


async def test_search_hrefs_open_actual_record(db, user_factory):
    u = await user_factory()
    await _seed(db, u["_id"], "notes", title="Alpha", body="x")
    res = (await run_search(u["_id"], "alpha", semantic=False))["results"][0]
    assert res["href"] == f"/editor/notes/{res['item']['_id']}"


async def test_search_isolation_empty_filters_pagination(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    await _seed(db, a["_id"], "notes", title="secret plan", body="")
    assert (await run_search(b["_id"], "secret", semantic=False))["results"] == []
    assert (await run_search(a["_id"], "   ", semantic=False))["results"] == []
    assert (await run_search(a["_id"], "nomatchxyz", semantic=False))["total"] == 0
    for i in range(5):
        await _seed(db, a["_id"], "tasks", title=f"report {i}")
    await _seed(db, a["_id"], "notes", title="report note", body="")
    r = await run_search(a["_id"], "report", {"task"}, limit=2, offset=0, semantic=False)
    assert r["total"] == 5 and len(r["results"]) == 2
    r2 = await run_search(a["_id"], "report", {"task"}, limit=2, offset=4, semantic=False)
    assert len(r2["results"]) == 1


async def test_archived_memories_not_searched(db, user_factory):
    u = await user_factory()
    await _seed(db, u["_id"], "memory_entries", title="old", content="likes tea", status="superseded")
    assert (await run_search(u["_id"], "tea", {"memory"}, semantic=False))["total"] == 0


# ---- notes / documents API: persistence, ownership, concurrency ---------------
@pytest.fixture
def client(db, user_factory):
    import asyncio
    app = FastAPI()
    holder = {}
    app.include_router(build_module_router("notes"), prefix="/api/notes")
    app.include_router(build_module_router("documents"), prefix="/api/documents")

    async def fake_auth():
        return holder["user"]
    app.dependency_overrides[require_auth] = fake_auth
    holder["set"] = lambda u: holder.__setitem__("user", u)
    c = TestClient(app)
    c.holder = holder
    return c


async def test_note_rich_text_roundtrip_and_ownership(db, user_factory, client):
    import anyio
    u1, u2 = await user_factory("a"), await user_factory("b")
    html = "<h2>Title</h2><p><strong>bold</strong> and <em>it</em></p><script>x</script>"
    def run():
        client.holder["set"](u1)
        r = client.post("/api/notes", json={"title": "N", "body": html})
        assert r.status_code == 201
        nid = r.json()["item"]["_id"]
        got = client.get(f"/api/notes/{nid}").json()["item"]
        assert "<strong>bold</strong>" in got["body"] and "<script" not in got["body"]
        client.holder["set"](u2)
        assert client.get(f"/api/notes/{nid}").status_code == 404
        assert client.put(f"/api/notes/{nid}", json={"body": "hacked"}).status_code == 404
        client.holder["set"](u1)
        return nid, got["updatedAt"]
    nid, stamp = await anyio.to_thread.run_sync(run)
    assert (await db.notes.find_one({}))["body"].startswith("<h2>")


async def test_stale_save_rejected(db, user_factory, client):
    import anyio
    u = await user_factory()
    def run():
        client.holder["set"](u)
        nid = client.post("/api/documents", json={"title": "D", "content": "<p>v1</p>"}).json()["item"]["_id"]
        v1 = client.get(f"/api/documents/{nid}").json()["item"]["updatedAt"]
        ok = client.put(f"/api/documents/{nid}", json={"content": "<p>v2</p>", "expectedUpdatedAt": v1})
        assert ok.status_code == 200
        stale = client.put(f"/api/documents/{nid}", json={"content": "<p>old</p>", "expectedUpdatedAt": v1})
        assert stale.status_code == 409
        return nid
    nid = await anyio.to_thread.run_sync(run)
    assert (await db.documents.find_one({}))["content"] == "<p>v2</p>"
