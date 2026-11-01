"""
Chat History API: browse every stored Mission Control chat by day.

    GET /api/chat-history              days that have chats (?q= filters by text)
    GET /api/chat-history/{YYYY-MM-DD} all messages of that day

Read-only. The messages themselves are written by the Mission Control chat.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app import chat_history
from app.conversation import messages_out
from app.dependencies import require_auth

router = APIRouter()


@router.get("")
async def list_chat_days(
    q: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_auth),
):
    days = await chat_history.list_days(user, q)
    return {"days": days, "total": sum(d["count"] for d in days)}


@router.get("/{day}")
async def get_chat_day(day: str, user: dict = Depends(require_auth)):
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD.")
    messages = await chat_history.get_day(user, parsed)
    return {"date": parsed.isoformat(), "messages": messages_out(messages)}
