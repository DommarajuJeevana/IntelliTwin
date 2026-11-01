"""Proactive suggestions API.

  GET  /api/suggestions               rule-based suggestions (fast, deterministic)
  POST /api/suggestions/dismiss       hide one suggestion (rule-based or AI) for N days
  GET  /api/suggestions/ai            cached Compass AI suggestions (never calls the model)
  POST /api/suggestions/ai/refresh    generate AI suggestions now (can be slow with a local model)
"""
import re

from fastapi import APIRouter, Depends, HTTPException

from app import ai_suggestions
from app.dependencies import require_auth
from app.suggestions import dismiss_suggestion, get_suggestions

router = APIRouter()
_KEY_RE = re.compile(r"^[a-z_]+(:[A-Za-z0-9-]{1,40}){0,3}$")


@router.get("")
async def list_suggestions(user: dict = Depends(require_auth)):
    items = await get_suggestions(user)
    return {"suggestions": items, "count": len(items)}


@router.get("/ai")
async def ai_suggestions_cached(user: dict = Depends(require_auth)):
    return await ai_suggestions.get_cached(user)


@router.post("/ai/refresh")
async def ai_suggestions_refresh(body: dict | None = None, user: dict = Depends(require_auth)):
    force = bool((body or {}).get("force"))
    return await ai_suggestions.refresh(user, force=force)


@router.post("/dismiss")
async def dismiss(body: dict, user: dict = Depends(require_auth)):
    key = body.get("key")
    if not isinstance(key, str) or len(key) > 200 or not _KEY_RE.match(key):
        raise HTTPException(status_code=400, detail="A valid suggestion key is required.")
    try:
        days = int(body.get("days", 7))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="days must be a number.")
    return await dismiss_suggestion(user, key, days)
