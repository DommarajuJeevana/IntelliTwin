"""
Every module that holds user-owned data - one place to list them so
overview/export/wipe can't silently drift out of sync as new modules get
added. Direct port of controllers/privacyController.js.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Response

from app.database import get_db
from app.dependencies import require_auth
from app.owned import now_utc
from app.serialization import serialize
from app.user_utils import profile_context, to_safe_json

router = APIRouter()

DATA_MODULES = [
    {"key": "profile", "label": "Profile", "description": "Interests, focus, working style you told your twin directly."},
    {"key": "goals", "label": "Goals", "collection": "goals", "label_field": "title"},
    {"key": "tasks", "label": "Tasks", "collection": "tasks", "label_field": "title"},
    {"key": "calendarEvents", "label": "Calendar events", "collection": "calendar_events", "label_field": "title"},
    {"key": "notes", "label": "Notes", "collection": "notes", "label_field": "title"},
    {"key": "documents", "label": "Documents", "collection": "documents", "label_field": "title"},
    {"key": "research", "label": "Research", "collection": "research_items", "label_field": "query"},
    {"key": "projects", "label": "Projects", "collection": "projects", "label_field": "name"},
    {"key": "memory", "label": "Memory timeline", "collection": "memory_entries", "label_field": "title"},
    {"key": "milestones", "label": "Milestones", "collection": "milestones", "label_field": "label"},
    {"key": "agentMessages", "label": "Agent collaboration logs", "collection": "agent_messages", "label_field": "content"},
]


def _what_agents_see(user: dict) -> dict:
    """
    What every agent actually reads/does before responding, shown
    explicitly so this isn't a black box - the "explainability" half of
    Phase 7's memory controls (the per-response `explanation` field from
    app/explain.py is the other half, showing what a *specific* response
    used rather than what's possible in general).
    """
    return {
        "summary": profile_context(user),
        "used_by": ["Echo", "Atlas", "Compass", "Nova", "Collaboration"],
        "note": (
            "Every agent reads your profile and calls Claude for its response. "
            "Atlas, Compass, and Nova also run Echo's semantic search over your "
            "memories for context relevant to what they're doing, and can act "
            "through tools - reading or creating goals, tasks, calendar events, "
            "documents, and research - not just generating text. Every "
            "individual response includes an 'explanation' field naming what it "
            "actually used."
        ),
    }


@router.get("/overview")
async def overview(user: dict = Depends(require_auth)):
    db = get_db()
    user_id = user["_id"]

    results = []
    for m in DATA_MODULES:
        if "collection" not in m:
            continue
        coll = db[m["collection"]]
        count = await coll.count_documents({"user": user_id})
        sample_cursor = coll.find(
            {"user": user_id}, {m["label_field"]: 1, "createdAt": 1}
        ).sort("createdAt", -1).limit(3)
        sample = await sample_cursor.to_list(length=3)
        results.append(
            {
                "key": m["key"],
                "label": m["label"],
                "count": count,
                "sample": [
                    {
                        "id": s["_id"],
                        "label": str(s.get(m["label_field"]) or "")[:80],
                        "createdAt": s["createdAt"],
                    }
                    for s in sample
                ],
            }
        )

    return serialize(
        {
            "modules": [{"key": "profile", "label": "Profile", "count": None, "sample": []}, *results],
            "agentsView": _what_agents_see(user),
        }
    )


@router.get("/export")
async def export_data(response: Response, user: dict = Depends(require_auth)):
    db = get_db()
    user_id = user["_id"]

    data = {}
    for m in DATA_MODULES:
        if "collection" not in m:
            continue
        items = await db[m["collection"]].find({"user": user_id}).to_list(length=None)
        data[m["key"]] = items

    response.headers["Content-Disposition"] = "attachment; filename=intellitwin-export.json"
    return serialize(
        {
            "exportedAt": now_utc(),
            "account": to_safe_json(user),
            "goals": data.get("goals", []),
            "tasks": data.get("tasks", []),
            "calendarEvents": data.get("calendarEvents", []),
            "notes": data.get("notes", []),
            "documents": data.get("documents", []),
            "research": data.get("research", []),
            "projects": data.get("projects", []),
            "memory": data.get("memory", []),
            "milestones": data.get("milestones", []),
            "agentMessages": data.get("agentMessages", []),
        }
    )


@router.delete("/wipe")
async def wipe(body: dict = Body(default={}), user: dict = Depends(require_auth)):
    if body.get("confirm") != "DELETE":
        raise HTTPException(status_code=400, detail='Send { "confirm": "DELETE" } to confirm this action.')

    db = get_db()
    user_id = user["_id"]
    for m in DATA_MODULES:
        if "collection" not in m:
            continue
        await db[m["collection"]].delete_many({"user": user_id})

    return {"ok": True, "message": "Everything except your account and login has been deleted."}
