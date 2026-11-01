"""
Goal progress service.

Goal progress is derived from the user's tasks.

A task belongs to a goal through:

    task.goal = goal._id

Progress is calculated dynamically:

    completed tasks / total tasks * 100

Goal status is also derived from task progress:

    0%       -> not_started
    1-99%    -> in_progress
    100%     -> done

The progress and derived status are intentionally calculated dynamically
so they cannot become stale when task status changes.
"""

from bson import ObjectId

from app.database import get_db


def _tasks_collection():
    return get_db().tasks


async def get_goal_progress(
    user_id: ObjectId,
    goal_id: ObjectId,
) -> dict:
    query = {
        "user": user_id,
        "goal": goal_id,
    }

    total_tasks = await _tasks_collection().count_documents(
        query
    )

    completed_tasks = await _tasks_collection().count_documents(
        {
            **query,
            "status": "done",
        }
    )

    if total_tasks == 0:
        progress = 0.0
    else:
        progress = round(
            (completed_tasks / total_tasks) * 100,
            1,
        )

    return {
        "totalTasks": total_tasks,
        "completedTasks": completed_tasks,
        "remainingTasks": total_tasks - completed_tasks,
        "progress": progress,
    }


async def attach_goal_progress(
    user_id: ObjectId,
    goal: dict,
) -> dict:
    """
    Attach calculated progress and derived status to one goal.
    """

    goal_id = goal.get("_id")

    if not goal_id:
        return goal

    progress = await get_goal_progress(
        user_id=user_id,
        goal_id=goal_id,
    )

    percentage = progress["progress"]

    if percentage >= 100:
        derived_status = "done"
    elif percentage > 0:
        derived_status = "in_progress"
    else:
        derived_status = "not_started"

    return {
        **goal,
        **progress,
        "status": derived_status,
    }


async def attach_goals_progress(
    user_id: ObjectId,
    goals: list[dict],
) -> list[dict]:
    """
    Attach calculated progress and derived status to multiple goals.
    """

    enriched_goals = []

    for goal in goals:
        enriched_goals.append(
            await attach_goal_progress(
                user_id=user_id,
                goal=goal,
            )
        )

    return enriched_goals