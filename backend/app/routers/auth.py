from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.dependencies import require_auth
from app.owned import now_utc
from app.security import hash_password, sign_token, verify_password
from app.user_utils import PROFILE_FIELDS, default_user_fields, to_safe_json

router = APIRouter()


class RegisterBody(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdateBody(BaseModel):
    bio: str | None = None
    interests: list[str] | None = None
    workingHours: str | None = None
    timezone: str | None = None
    communicationStyle: str | None = None
    currentFocus: str | None = None


@router.post("/register", status_code=201)
async def register(body: RegisterBody):
    db = get_db()

    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user_doc = {
        "name": body.name,
        "email": body.email.lower(),
        "passwordHash": hash_password(body.password),
        "createdAt": now_utc(),
        "updatedAt": now_utc(),
        **default_user_fields(),
    }
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    await db.milestones.insert_one(
        {
            "user": user_doc["_id"],
            "agent": None,
            "tags": [],
            "label": "Joined IntelliTwin",
            "detail": "Your twin started learning about you.",
            "icon": "seedling",
            "earnedAt": now_utc(),
            "createdAt": now_utc(),
            "updatedAt": now_utc(),
        }
    )

    token = sign_token(str(user_doc["_id"]), user_doc["email"])
    return {"token": token, "user": to_safe_json(user_doc)}


@router.post("/login")
async def login(body: LoginBody):
    db = get_db()

    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    previous_login_at = user.get("lastLoginAt")
    last_login_at = now_utc()
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"previousLoginAt": previous_login_at, "lastLoginAt": last_login_at}},
    )
    user["previousLoginAt"] = previous_login_at
    user["lastLoginAt"] = last_login_at

    token = sign_token(str(user["_id"]), user["email"])
    return {"token": token, "user": to_safe_json(user)}


@router.get("/me")
async def me(user: dict = Depends(require_auth)):
    return {"user": to_safe_json(user)}


@router.put("/profile")
async def update_profile(body: ProfileUpdateBody, user: dict = Depends(require_auth)):
    db = get_db()

    updates = {}
    payload = body.model_dump(exclude_unset=True)
    for key in PROFILE_FIELDS:
        if key in payload:
            updates[f"profile.{key}"] = payload[key]

    if updates:
        updates["updatedAt"] = now_utc()
        await db.users.update_one({"_id": user["_id"]}, {"$set": updates})

    updated = await db.users.find_one({"_id": user["_id"]}, {"passwordHash": 0})
    return {"user": to_safe_json(updated)}
