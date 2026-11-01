from datetime import datetime, timedelta, timezone

import pytest

from app import chat_history
from app.conversation import COLLECTION, get_messages

IST = timezone(timedelta(hours=5, minutes=30))


async def _msg(db, user, when, role, text):
    await db[COLLECTION].insert_one(
        {"user": user["_id"], "thread": "mission-control", "role": role,
         "content": text, "createdAt": when.astimezone(timezone.utc)}
    )


@pytest.mark.asyncio
async def test_today_filter_and_archive(db, user_factory):
    user = await user_factory()
    now = datetime.now(IST)
    today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today_noon - timedelta(days=1)
    await _msg(db, user, yesterday, "user", "old question")
    await _msg(db, user, today_noon, "user", "new question")

    since = chat_history.today_start_utc(user)
    today_only = await get_messages(user["_id"], since=since)
    assert [m["content"] for m in today_only] == ["new question"]

    # nothing is lost: the archive still has both days
    days = await chat_history.list_days(user)
    assert [d["count"] for d in days] == [1, 1]
    assert days[0]["date"] > days[1]["date"]

    old = await chat_history.get_day(user, yesterday.date())
    assert [m["content"] for m in old] == ["old question"]

    found = await chat_history.list_days(user, "OLD")
    assert len(found) == 1 and found[0]["preview"] == "old question"
