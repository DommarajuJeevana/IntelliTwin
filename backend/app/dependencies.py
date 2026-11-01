"""
Protects a route: expects `Authorization: Bearer <token>`.
On success returns the user document (minus passwordHash) - the FastAPI
equivalent of req.user being attached by middleware/auth.js.
"""
from bson import ObjectId
from fastapi import Header, HTTPException

from app.database import get_db
from app.security import verify_token


async def require_auth(authorization: str | None = Header(default=None)) -> dict:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :]

    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token.")

    try:
        payload = verify_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    try:
        user_id = ObjectId(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    db = get_db()
    user = await db.users.find_one({"_id": user_id}, {"passwordHash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists.")

    return user
