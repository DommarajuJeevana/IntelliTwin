from fastapi import APIRouter, Depends

from app.database import get_db
from app.dependencies import require_auth
from app.serialization import docs_out

router = APIRouter()


@router.get("")
async def list_milestones(user: dict = Depends(require_auth)):
    db = get_db()
    cursor = db.milestones.find({"user": user["_id"]}).sort("earnedAt", -1)
    items = await cursor.to_list(length=None)
    return {"items": docs_out(items)}
