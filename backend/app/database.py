"""
MongoDB connection, kept isolated (same reasoning as the old config/db.js)
so it can be swapped/mocked without touching main.py.
"""
import logging
from datetime import timezone

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

logger = logging.getLogger("intellitwin.db")

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if not settings.MONGO_URI:
        raise RuntimeError("MONGO_URI is not set. Copy .env.example to .env and configure it.")

    # tz_aware: MongoDB stores UTC; without this the driver returns *naive* datetimes, which
    # crash when compared with the aware datetimes the app creates (now_utc()).
    _client = AsyncIOMotorClient(settings.MONGO_URI, tz_aware=True, tzinfo=timezone.utc)
    _db = _client.get_default_database()

    # Fail fast if Mongo isn't reachable, same intent as mongoose's connect().
    await _client.admin.command("ping")
    logger.info("[db] connected -> %s", _db.name)
    return _db


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized yet - connect_db() must run first.")
    return _db
