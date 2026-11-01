import json
import pytest

import app.memory.echo as echo
from app.memory.embeddings import embed_text
from app.memory.safety import contains_secret


def fake_llm(extraction=None, relationship="UNRELATED"):
    """Deterministic stand-in for the model provider."""
    async def _call(system, prompt, max_tokens=1000):
        if "relationship" in system.lower() or "EXISTING MEMORY" in prompt:
            return json.dumps({"relationship": relationship})
        return json.dumps(extraction or {"should_remember": False})
    return _call


EXTRACT_PREF = {"should_remember": True, "title": "Prefers concise explanations",
                "content": "User prefers short, concise explanations.", "importance": 3,
                "confidence": 0.9, "category": "preference"}


async def test_automatic_extraction_stores_with_provenance(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(echo, "call_llm", fake_llm(EXTRACT_PREF))
    r = await echo.remember(u, source_interaction="I like my explanations short and concise.")
    assert r and r["category"] == "preference"
    stored = await db.memory_entries.find_one({})
    assert stored["user"] == u["_id"] and stored["status"] == "active"
    assert stored["confidence"] == pytest.approx(0.9) and stored.get("source") and stored["embedding"]


@pytest.mark.parametrize("msg", ["hi", "what time is it?", "Explain recursion to me", "what do you remember about me"])
async def test_transient_messages_are_not_stored(db, user_factory, monkeypatch, msg):
    u = await user_factory()
    monkeypatch.setattr(echo, "call_llm", fake_llm(EXTRACT_PREF))  # even if the model were over-eager
    assert await echo.remember(u, source_interaction=msg) is None
    assert await db.memory_entries.count_documents({}) == 0


async def test_model_says_not_worth_remembering(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(echo, "call_llm", fake_llm({"should_remember": False, "title": "t", "content": "c"}))
    assert await echo.remember(u, source_interaction="I had toast this morning.") is None


async def test_llm_failure_stores_nothing(db, user_factory, monkeypatch):
    u = await user_factory()
    async def boom(*a, **k): raise RuntimeError("model down")
    monkeypatch.setattr(echo, "call_llm", boom)
    assert await echo.remember(u, source_interaction="I am learning Rust for my thesis.") is None
    assert await db.memory_entries.count_documents({}) == 0


@pytest.mark.parametrize("text", [
    "my password is hunter2", "remember that my api key is sk-abcdefghijklmnopqrstuv",
    "my card is 4111 1111 1111 1111", "remember my ssn 123-45-6789",
])
async def test_secrets_never_stored(db, user_factory, monkeypatch, text):
    u = await user_factory()
    monkeypatch.setattr(echo, "call_llm", fake_llm(EXTRACT_PREF))
    assert contains_secret(text)
    assert await echo.remember(u, note=text) is None
    assert await echo.remember(u, source_interaction=text) is None
    assert await db.memory_entries.count_documents({}) == 0


async def test_exact_duplicate_not_stored_twice(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(echo, "call_llm", fake_llm())
    a = await echo.remember(u, note="Prefers dark mode")
    b = await echo.remember(u, note="prefers   dark mode ")
    assert a["_id"] == b["_id"] and await db.memory_entries.count_documents({}) == 1


async def test_semantic_repeat_is_merged(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(echo, "call_llm", fake_llm(relationship="SAME"))
    a = await echo.remember(u, note="User is studying machine learning at university")
    b = await echo.remember(u, note="User studies machine learning at their university")
    assert await db.memory_entries.count_documents({}) == 1
    assert b["_id"] == a["_id"]


async def test_correction_supersedes_old_fact(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(echo, "call_llm", fake_llm(relationship="SUPERSEDES"))
    old = await echo.remember(u, note="User lives in Chennai and works there")
    new = await echo.remember(u, note="User now lives in Bengaluru and works there")
    assert new["supersedes"] == [old["_id"]]
    statuses = {d["content"]: d["status"] async for d in db.memory_entries.find({})}
    assert statuses["User lives in Chennai and works there"] == "superseded"
    assert statuses["User now lives in Bengaluru and works there"] == "active"
    hits = await echo.search_memory(u, "where does the user live", limit=5)
    assert all(h.get("status") != "superseded" for h in hits)


async def test_semantic_retrieval_and_user_isolation(db, user_factory, monkeypatch):
    a, b = await user_factory("a"), await user_factory("b")
    monkeypatch.setattr(echo, "call_llm", fake_llm())
    await echo.remember(a, note="Allergic to peanuts so avoids peanut dishes")
    await echo.remember(a, note="Working on a federated learning thesis project")
    await echo.remember(b, note="Peanut butter is the favourite snack of this user")
    hits = await echo.search_memory(a, "federated learning project", limit=3)
    assert hits and "federated" in hits[0]["content"].lower()
    ids_b = {str(d["_id"]) async for d in db.memory_entries.find({"user": b["_id"]})}
    assert not ids_b & {h["_id"] for h in hits}
    assert await echo.search_memory(b, "federated learning", limit=3) == [] or \
        all("federated" not in h["content"].lower() for h in await echo.search_memory(b, "federated", limit=3))


async def test_offline_embedding_fallback_is_deterministic(monkeypatch):
    v1, v2 = await embed_text("learning rust"), await embed_text("learning rust")
    assert v1 == v2 and len(v1) == __import__("app.config", fromlist=["settings"]).settings.EMBEDDING_DIM


async def test_update_delete_restore_and_cross_user_blocked(db, user_factory, monkeypatch):
    a, b = await user_factory("a"), await user_factory("b")
    monkeypatch.setattr(echo, "call_llm", fake_llm())
    m = await echo.remember(a, note="Likes green tea")
    assert await echo.update_memory(b, m["_id"], {"content": "hacked"}) is None
    assert await echo.delete_memory(b, m["_id"]) is False
    up = await echo.update_memory(a, m["_id"], {"content": "Likes jasmine tea"})
    assert up["content"] == "Likes jasmine tea"
    assert await echo.delete_memory(a, m["_id"]) is True
    assert await echo.search_memory(a, "tea", limit=5) == []
    assert (await echo.restore_memory(a, m["_id"])) is not None
    assert await echo.delete_memory(a, m["_id"], hard=True) is True
    assert await db.memory_entries.count_documents({}) == 0
