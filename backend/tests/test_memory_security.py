"""Phases C, E and G regression tests: memory privacy, secret rejection, timeline, output hygiene.

Unit tests on a mock Mongo and the offline embedding backend; no real MongoDB or model.
"""
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.memory import echo
from app.memory.embeddings import embed_text
from app.memory.safety import reject_secret_memory
from app.memory.vector_store import cosine_similarity
from app.sanitize import clean_tags, sanitize_rich_text
from app.serialization import doc_out, docs_out

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


async def add_mem(db, user, title, content="", days=0, **extra):
    doc = {"user": user["_id"], "title": title, "content": content, "importance": 3,
           "createdAt": T0, "updatedAt": T0, "occurredAt": T0 + timedelta(days=days),
           "embedding": await embed_text(echo._embed_source(title, content)), **extra}
    res = await db.memory_entries.insert_one(doc)
    return res.inserted_id


# ---- output hygiene ----------------------------------------------------------
def test_serializers_drop_raw_embeddings():
    d = {"_id": ObjectId(), "title": "t", "embedding": [0.1, 0.2]}
    assert "embedding" not in doc_out(d) and "embedding" not in docs_out([d])[0]
    assert doc_out(d)["title"] == "t" and "embedding" in d  # input untouched


async def test_memory_reads_never_return_embeddings(db, user_factory):
    u = await user_factory()
    await add_mem(db, u, "Prefers dark mode", "editors")
    for items in (await echo.search_memory(u, "dark mode"), await echo.get_recent_memories(u),
                  await echo.get_memory_timeline(u)):
        assert items and all("embedding" not in i for i in items)


# ---- secrets -----------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "my password is hunter2", "api key: abc", "token sk-abcdefghijklmnopqrstuv",
    "card 4111 1111 1111 1111", "mongodb://user:pw@host/db", "123-45-6789",
])
def test_secret_texts_rejected(text):
    with pytest.raises(ValueError):
        reject_secret_memory("title", text)


@pytest.mark.parametrize("text", ["I prefer dark mode", "My project is called Atlas", "Learning federated learning"])
def test_normal_texts_allowed(text):
    reject_secret_memory(text, "details")


async def test_editing_a_memory_cannot_introduce_a_secret(db, user_factory):
    u = await user_factory()
    mid = await add_mem(db, u, "Prefers tea")
    with pytest.raises(ValueError):
        await echo.update_memory(u, str(mid), {"content": "my password is hunter2"})
    assert (await db.memory_entries.find_one({"_id": mid}))["content"] == ""


async def test_update_validates_importance_and_ownership(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    mid = await add_mem(db, a, "Goal: learn Rust")
    assert (await echo.update_memory(a, str(mid), {"importance": 99}))["importance"] == 5
    with pytest.raises(ValueError):
        await echo.update_memory(a, str(mid), {"importance": "high"})
    assert await echo.update_memory(b, str(mid), {"title": "hijack"}) is None
    assert await echo.update_memory(a, "not-an-id", {"title": "x"}) is None
    assert (await db.memory_entries.find_one({"_id": mid}))["title"] == "Goal: learn Rust"


async def test_edit_re_embeds_so_retrieval_follows_the_new_text(db, user_factory):
    u = await user_factory()
    mid = await add_mem(db, u, "Likes chess", "plays chess weekly")
    before = (await db.memory_entries.find_one({"_id": mid}))["embedding"]
    await echo.update_memory(u, str(mid), {"title": "Likes swimming", "content": "swims every morning"})
    assert (await db.memory_entries.find_one({"_id": mid}))["embedding"] != before


# ---- retrieval, privacy, lifecycle -------------------------------------------
async def test_search_is_user_scoped_and_excludes_archived_and_superseded(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    await add_mem(db, a, "Uses Python for backend work")
    await add_mem(db, b, "Uses Python for secret work")
    await add_mem(db, a, "Uses Python archived", archived=True, status="archived")
    await add_mem(db, a, "Uses Python old", status="superseded")
    titles = [m["title"] for m in await echo.search_memory(a, "Python backend", limit=10)]
    assert titles == ["Uses Python for backend work"]


async def test_timeline_views_labels_and_supersede_links(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    new_id = await add_mem(db, a, "Works at Acme", days=3)
    await add_mem(db, a, "Works at OldCo", days=1, status="superseded", supersededBy=new_id)
    await add_mem(db, a, "Archived note", days=2, archived=True, status="archived")
    other = await add_mem(db, b, "Other user's current job", days=2)
    await add_mem(db, a, "Points at another user's memory", days=0, status="superseded", supersededBy=other)

    everything = await echo.get_memory_timeline(a, "all")
    assert len(everything) == 4 and "Other user's current job" not in str(everything)
    by_title = {m["title"]: m for m in everything}
    assert by_title["Works at Acme"]["lifecycle"] == "active"
    assert by_title["Archived note"]["lifecycle"] == "archived"
    assert by_title["Works at OldCo"]["lifecycle"] == "superseded"
    assert by_title["Works at OldCo"]["supersededByTitle"] == "Works at Acme"
    assert by_title["Points at another user's memory"].get("supersededByTitle") is None
    assert [m["title"] for m in everything][0] == "Works at Acme"                      # newest first

    assert [m["title"] for m in await echo.get_memory_timeline(a, "active")] == ["Works at Acme"]
    assert len(await echo.get_memory_timeline(a, "superseded")) == 2
    assert [m["title"] for m in await echo.get_memory_timeline(a, "archived")] == ["Archived note"]
    with pytest.raises(ValueError):
        await echo.get_memory_timeline(a, "$ne")


async def test_restore_and_delete_respect_ownership(db, user_factory):
    a, b = await user_factory("a"), await user_factory("b")
    mid = await add_mem(db, a, "Temp", archived=True, status="archived")
    assert await echo.restore_memory(b, str(mid)) is None
    assert (await echo.restore_memory(a, str(mid)))["status"] == "active"
    assert await echo.delete_memory(b, str(mid)) is False
    assert await echo.delete_memory(a, "garbage") is False


# ---- embeddings --------------------------------------------------------------
async def test_offline_embedding_is_deterministic_unit_length_and_discriminates():
    from app.config import settings
    v1 = await embed_text("I like dark mode editors")
    v2 = await embed_text("I LIKE dark mode editors!!")
    v3 = await embed_text("quarterly tax filing deadline")
    assert len(v1) == settings.EMBEDDING_DIM and abs(sum(x * x for x in v1) - 1) < 1e-6
    assert cosine_similarity(v1, v2) >= echo.MERGE_SIMILARITY_THRESHOLD
    assert cosine_similarity(v1, v3) < 0.5
    assert await embed_text("   ") == [0.0] * settings.EMBEDDING_DIM


def test_dimension_mismatch_scores_zero_not_crash():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


# ---- Phase G input hygiene ---------------------------------------------------
def test_clean_tags():
    assert clean_tags("x") is None and clean_tags({"$ne": 1}) is None
    assert clean_tags(["a", 1, None, " b ", "x" * 99]) == ["a", "b", "x" * 50]
    assert len(clean_tags(["t"] * 100)) == 20


def test_rich_text_is_sanitised():
    dirty = ('<p onclick="x()">hi</p><script>alert(1)</script><a href="javascript:alert(1)">l</a>'
             '<img src=x onerror=alert(1)><iframe src="//evil"></iframe><a href="https://ok.example">ok</a>')
    clean = sanitize_rich_text(dirty)
    for bad in ("<script", "onclick", "javascript:", "<img", "onerror", "<iframe"):
        assert bad not in clean
    assert 'href="https://ok.example"' in clean and "noopener" in clean
