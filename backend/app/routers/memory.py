"""
Phase 3 - Echo-specific memory routes, layered on top of the generic
`/api/memory` CRUD (app/routers/generic_crud.py, still mounted for plain
list/create/get/update/delete). This router adds the operations that need
Echo's pipeline rather than a plain Mongo write:

    GET  /api/memory/recent      -> get_recent_memories()
    GET  /api/memory/search      -> search_memory()  (semantic, not regex)
    POST /api/memory/summarize   -> summarize_memories()
    GET  /api/memory/archived    -> list_archived_memories()  (post-rating improvement)
    POST /api/memory/{id}/restore -> restore_memory()          (post-rating improvement)

Registered in main.py *before* the generic module router for "memory", so
these fixed paths win over the generic router's `/{item_id}` route.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import require_auth
from app.memory import echo as echo_agent

router = APIRouter()


@router.get("/timeline")
async def memory_timeline(
    view: str = Query(default="all"),
    limit: int = Query(default=200, ge=1, le=500),
    user: dict = Depends(require_auth),
):
    """Memory Timeline data: active, superseded and archived memories, labelled."""
    try:
        items = await echo_agent.get_memory_timeline(user, view=view, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"items": items}


@router.get("/recent")
async def recent_memories(limit: int = Query(default=10, ge=1, le=100), user: dict = Depends(require_auth)):
    items = await echo_agent.get_recent_memories(user, limit=limit)
    return {"items": items}


@router.get("/search")
async def search_memories(
    q: str | None = Query(default=None), limit: int = Query(default=5, ge=1, le=50), user: dict = Depends(require_auth)
):
    if not q:
        raise HTTPException(status_code=400, detail="q is required.")
    items = await echo_agent.search_memory(user, q, limit=limit)
    return {"items": items}


@router.post("/summarize")
async def summarize(limit: int = Query(default=20, ge=1, le=100), user: dict = Depends(require_auth)):
    digest = await echo_agent.summarize_memories(user, limit=limit)
    return {"summary": digest}


@router.get("/archived")
async def archived_memories(limit: int = Query(default=50, ge=1, le=200), user: dict = Depends(require_auth)):
    """
    Post-rating improvement: agent-triggered deletes are now soft (see
    echo.py's delete_memory docstring) - this is how a person actually sees
    and recovers what got archived, so "reversible" is true in practice and
    not just in the data model.
    """
    items = await echo_agent.list_archived_memories(user, limit=limit)
    return {"items": items}


@router.post("/{memory_id}/restore")
async def restore(memory_id: str, user: dict = Depends(require_auth)):
    restored = await echo_agent.restore_memory(user, memory_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="No archived memory found with that id.")
    return {"item": restored}


@router.post("/consolidate")
async def consolidate(user: dict = Depends(require_auth)):
    """Post-rating improvement: dedup near-duplicate memories. See
    echo.py's consolidate_memories() for what this actually does."""
    result = await echo_agent.consolidate_memories(user)
    return result
