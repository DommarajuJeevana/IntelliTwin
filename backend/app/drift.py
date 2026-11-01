"""
Semantic drift detection for IntelliTwin.

Drift detection compares recent workspace activity against the user's
stated current focus and interests.

The original implementation used keyword overlap only. This version uses
the same embedding layer as Echo and universal search, so semantically
related activity can be recognized even when the exact words differ.

The feature remains behavioral only:
it compares what the user is doing with what the user said they are focused on.
It does not infer emotions, mental state, motivation, or intent.
"""

from datetime import datetime, timedelta, timezone

from app.memory.embeddings import embed_text
from app.memory.vector_store import cosine_similarity


LOOKBACK_DAYS = 14

MIN_ACTIVITY_FOR_SIGNAL = 3

# An activity is considered related when its semantic similarity to the
# user's focus/interests reaches this threshold.
SEMANTIC_MATCH_THRESHOLD = 0.30

# If less than 20% of recent activity is related, flag possible drift.
LOW_OVERLAP_THRESHOLD = 0.20


def days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def _profile_text(profile: dict) -> str:
    """
    Build the semantic reference text from the user's stated focus
    and interests.
    """
    parts = []

    current_focus = profile.get("currentFocus")

    if current_focus:
        parts.append(
            f"Current focus: {current_focus}"
        )

    interests = profile.get("interests") or []

    if interests:
        parts.append(
            "Interests: " + ", ".join(interests)
        )

    return "\n".join(parts).strip()


def _item_text(item: dict, fields: list[str]) -> str:
    return " ".join(
        str(item.get(field) or "")
        for field in fields
    ).strip()


def _build_activity_items(recent_items: dict) -> list[dict]:
    """
    Convert dashboard collections into one normalized activity list.
    """
    return (
        [
            {
                "item": goal,
                "fields": ["title", "description"],
            }
            for goal in recent_items.get("goals", [])
        ]
        + [
            {
                "item": task,
                "fields": ["title"],
            }
            for task in recent_items.get("tasks", [])
        ]
        + [
            {
                "item": note,
                "fields": ["title", "body"],
            }
            for note in recent_items.get("notes", [])
        ]
        + [
            {
                "item": document,
                "fields": ["title", "content"],
            }
            for document in recent_items.get("documents", [])
        ]
        + [
            {
                "item": research,
                "fields": ["query", "summary"],
            }
            for research in recent_items.get("research", [])
        ]
    )


async def _semantic_overlap(
    profile_text: str,
    activity_items: list[dict],
) -> tuple[int, int]:
    """
    Compare every activity item with the user's profile embedding.

    Returns:
        matching_count, total_activity_count
    """
    if not profile_text or not activity_items:
        return 0, len(activity_items)

    profile_embedding = await embed_text(profile_text)

    matching_count = 0
    valid_activity_count = 0

    for entry in activity_items:
        text = _item_text(
            entry["item"],
            entry["fields"],
        )

        if not text:
            continue

        valid_activity_count += 1

        activity_embedding = await embed_text(text)

        similarity = cosine_similarity(
            profile_embedding,
            activity_embedding,
        )

        if similarity >= SEMANTIC_MATCH_THRESHOLD:
            matching_count += 1

    return matching_count, valid_activity_count


async def compute_drift_insight(
    user: dict,
    recent_items: dict,
) -> dict:
    """
    Calculate whether recent workspace activity still aligns with the
    user's stated focus/interests.

    Returns the same public statuses used by the existing frontend:
        no_profile
        not_enough_activity
        drifting
        aligned
    """
    profile = user.get("profile") or {}

    if not profile.get("currentFocus") and not (
        profile.get("interests") or []
    ):
        return {
            "status": "no_profile",
            "message": (
                "Fill in your current focus on your profile so "
                "your twin knows what to watch for."
            ),
        }

    activity_items = _build_activity_items(
        recent_items
    )

    if len(activity_items) < MIN_ACTIVITY_FOR_SIGNAL:
        return {
            "status": "not_enough_activity",
            "message": (
                "Not enough recent activity yet to compare "
                "against your stated focus."
            ),
        }

    profile_text = _profile_text(profile)

    matching_count, valid_activity_count = (
        await _semantic_overlap(
            profile_text,
            activity_items,
        )
    )

    if valid_activity_count == 0:
        return {
            "status": "not_enough_activity",
            "message": (
                "Not enough recent activity yet to compare "
                "against your stated focus."
            ),
        }

    overlap = matching_count / valid_activity_count

    if overlap < LOW_OVERLAP_THRESHOLD:
        return {
            "status": "drifting",
            "overlap": round(overlap * 100),
            "matchedItems": matching_count,
            "activityCount": valid_activity_count,
            "message": _phrase_insight(
                "drifting",
                profile,
                valid_activity_count,
            ),
        }

    return {
        "status": "aligned",
        "overlap": round(overlap * 100),
        "matchedItems": matching_count,
        "activityCount": valid_activity_count,
        "message": _phrase_insight(
            "aligned",
            profile,
            valid_activity_count,
        ),
    }


def _phrase_insight(
    status: str,
    profile: dict,
    activity_count: int,
) -> str:
    focus = (
        profile.get("currentFocus")
        or "what you said you're focused on"
    )

    if status == "drifting":
        return (
            f'Most of your last {activity_count} items don\'t '
            f'look connected to "{focus}". '
            "Still the priority, or has it shifted?"
        )

    return (
        f'Your recent activity still tracks with "{focus}".'
    )