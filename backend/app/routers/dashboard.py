"""
One call that feeds "Mission Control" - counts + recent items across every
module, so the dashboard doesn't have to fan out into 9 separate requests.

Also provides:
- semantic drift detection
- proactive briefing
- stale-goal detection
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.briefing import build_briefing
from app.database import get_db
from app.dependencies import require_auth
from app.drift import (
    LOOKBACK_DAYS,
    compute_drift_insight,
    days_ago,
)
from app.serialization import serialize
from app.user_utils import to_safe_json


router = APIRouter()


def _to_labeled(
    items: list[dict],
    label_field: str,
) -> list[dict]:
    return [
        {
            "label": item.get(label_field),
            "createdAt": item["createdAt"],
        }
        for item in items
    ]


async def _last_activity_at(
    db,
    user_id,
    goal: dict,
) -> datetime:
    """
    A goal counts as worked on if the goal itself changed, or if a
    task/research item linked to it changed.
    """
    latest = (
        goal.get("updatedAt")
        or goal["createdAt"]
    )

    for collection_name in (
        "tasks",
        "research_items",
    ):
        doc = await db[
            collection_name
        ].find_one(
            {
                "user": user_id,
                "goal": goal["_id"],
            },
            sort=[
                ("createdAt", -1),
            ],
        )

        if doc and doc["createdAt"] > latest:
            latest = doc["createdAt"]

    return latest


async def _find_stale_goal(
    db,
    user_id,
) -> dict | None:
    """
    Find the least-recently-touched open goal.
    """
    open_goals = await db.goals.find(
        {
            "user": user_id,
            "status": {
                "$ne": "done",
            },
        }
    ).to_list(
        length=None
    )

    if not open_goals:
        return None

    scored = []

    for goal in open_goals:
        last_activity = await _last_activity_at(
            db,
            user_id,
            goal,
        )

        scored.append(
            (
                goal,
                last_activity,
            )
        )

    scored.sort(
        key=lambda pair: pair[1]
    )

    oldest_goal, oldest_activity = scored[0]

    return {
        "title": oldest_goal["title"],
        "lastActivityAt": oldest_activity,
    }


@router.get("/summary")
async def summary(
    user: dict = Depends(require_auth),
):
    db = get_db()
    user_id = user["_id"]

    now = datetime.now(timezone.utc)
    since = days_ago(LOOKBACK_DAYS)

    goals_count = await db.goals.count_documents(
        {
            "user": user_id,
        }
    )

    tasks_open_count = await db.tasks.count_documents(
        {
            "user": user_id,
            "status": {
                "$ne": "done",
            },
        }
    )

    notes_count = await db.notes.count_documents(
        {
            "user": user_id,
        }
    )

    documents_count = (
        await db.documents.count_documents(
            {
                "user": user_id,
            }
        )
    )

    research_count = (
        await db.research_items.count_documents(
            {
                "user": user_id,
            }
        )
    )

    memories = await db.memory_entries.find(
        {
            "user": user_id,
        }
    ).sort(
        "occurredAt",
        -1,
    ).to_list(
        length=5
    )

    milestones = await db.milestones.find(
        {
            "user": user_id,
        }
    ).sort(
        "earnedAt",
        -1,
    ).to_list(
        length=9
    )

    recent_thread_msgs = (
        await db.agent_messages.find(
            {
                "user": user_id,
            }
        ).sort(
            "createdAt",
            -1,
        ).to_list(
            length=6
        )
    )

    recent_goals = await db.goals.find(
        {
            "user": user_id,
            "createdAt": {
                "$gte": since,
            },
        }
    ).to_list(
        length=None
    )

    recent_tasks = await db.tasks.find(
        {
            "user": user_id,
            "createdAt": {
                "$gte": since,
            },
        }
    ).to_list(
        length=None
    )

    recent_notes = await db.notes.find(
        {
            "user": user_id,
            "createdAt": {
                "$gte": since,
            },
        }
    ).to_list(
        length=None
    )

    recent_documents = await db.documents.find(
        {
            "user": user_id,
            "createdAt": {
                "$gte": since,
            },
        }
    ).to_list(
        length=None
    )

    recent_research = (
        await db.research_items.find(
            {
                "user": user_id,
                "createdAt": {
                    "$gte": since,
                },
            }
        ).to_list(
            length=None
        )
    )

    oldest_overdue_task = await db.tasks.find_one(
        {
            "user": user_id,
            "status": {
                "$ne": "done",
            },
            "dueDate": {
                "$lt": now,
            },
        },
        sort=[
            ("dueDate", 1),
        ],
    )

    stale_goal = await _find_stale_goal(
        db,
        user_id,
    )

    drift = await compute_drift_insight(
        user,
        {
            "goals": recent_goals,
            "tasks": recent_tasks,
            "notes": recent_notes,
            "documents": recent_documents,
            "research": recent_research,
        },
    )

    combined = (
        _to_labeled(
            recent_goals,
            "title",
        )
        + _to_labeled(
            recent_tasks,
            "title",
        )
        + _to_labeled(
            recent_notes,
            "title",
        )
        + _to_labeled(
            recent_documents,
            "title",
        )
        + _to_labeled(
            recent_research,
            "query",
        )
    )

    combined.sort(
        key=lambda item: item["createdAt"],
        reverse=True,
    )

    previous_login_at = user.get(
        "previousLoginAt"
    )

    since_visit_items = (
        [
            item
            for item in combined
            if previous_login_at
            and item["createdAt"] > previous_login_at
        ]
        if previous_login_at
        else []
    )

    briefing = build_briefing(
        user,
        since_visit_items,
        oldest_overdue_task,
        now,
        stale_goal,
    )

    return serialize(
        {
            "counts": {
                "goals": goals_count,
                "tasksOpen": tasks_open_count,
                "notes": notes_count,
                "documents": documents_count,
                "research": research_count,
            },
            "recentMemories": memories,
            "milestones": milestones,
            "recentAgentActivity": recent_thread_msgs,
            "drift": drift,
            "briefing": briefing,
            "user": to_safe_json(user),
        }
    )