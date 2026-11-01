import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/intellitwin_test")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LLM_PROVIDER", "ollama")

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import app.database as database


@pytest.fixture
def db(monkeypatch):
    """Isolated in-memory database per test; never touches a real Mongo."""
    client = AsyncMongoMockClient()
    test_db = client["intellitwin_test"]
    monkeypatch.setattr(database, "_db", test_db)
    return test_db


async def make_user(db, name="u", tz="Asia/Kolkata"):
    res = await db.users.insert_one({"name": name, "email": f"{name}@x.io", "profile": {"timezone": tz}})
    return await db.users.find_one({"_id": res.inserted_id})


@pytest.fixture
def user_factory(db):
    async def _f(name="u", tz="Asia/Kolkata"):
        return await make_user(db, name, tz)
    return _f
