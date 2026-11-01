"""
Mirrors the instance methods that lived on the Mongoose User model
(backend/models/User.js): toSafeJSON() and profileContext().
"""
from app.serialization import serialize

DEFAULT_PROFILE = {
    "bio": "",
    "interests": [],
    "workingHours": "",
    "timezone": "",
    "communicationStyle": "",
    "currentFocus": "",
}

PROFILE_FIELDS = ["bio", "interests", "workingHours", "timezone", "communicationStyle", "currentFocus"]


def default_user_fields() -> dict:
    """New-user defaults, matching the Mongoose schema defaults exactly."""
    return {
        "role": "Member",
        "avatarUrl": "",
        "signal": 20,
        "signalToNextLevel": 100,
        "level": 1,
        "profile": dict(DEFAULT_PROFILE),
        "lastLoginAt": None,
        "previousLoginAt": None,
    }


def to_safe_json(user: dict) -> dict:
    return serialize(
        {
            "id": user["_id"],
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role", "Member"),
            "avatarUrl": user.get("avatarUrl", ""),
            "signal": user.get("signal", 20),
            "signalToNextLevel": user.get("signalToNextLevel", 100),
            "level": user.get("level", 1),
            "profile": {**DEFAULT_PROFILE, **(user.get("profile") or {})},
        }
    )


def profile_context(user: dict) -> str:
    """
    Turns the structured profile into a short paragraph agents can drop
    straight into a system prompt - same phrasing/order as profileContext()
    in the old User.js, so every agent stays consistent.
    """
    p = user.get("profile") or {}
    lines = []
    if user.get("name"):
        lines.append(f"Name: {user['name']}")
    if p.get("currentFocus"):
        lines.append(f"Currently focused on: {p['currentFocus']}")
    if p.get("interests"):
        lines.append(f"Interests: {', '.join(p['interests'])}")
    if p.get("workingHours"):
        lines.append(f"Working hours: {p['workingHours']}")
    if p.get("timezone"):
        lines.append(f"Timezone: {p['timezone']}")
    if p.get("communicationStyle"):
        lines.append(f"Preferred communication style: {p['communicationStyle']}")
    if p.get("bio"):
        lines.append(f"About them: {p['bio']}")
    return "\n".join(lines)
