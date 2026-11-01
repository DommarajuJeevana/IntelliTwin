"""
Shared context engine for IntelliTwin.

The context engine is the bridge between the user's current request and
the information already known by IntelliTwin.

Every specialist agent can use the same context-building rules:

    User Model
        +
    Relevant workspace information
        +
    Current request
        +
    Agent persona
        =
    Agent context

This module is READ-ONLY.

It does not:
- create memories
- modify workspace data
- decide which agent should act
- execute tools

Those responsibilities belong to Echo, workspace tools, and Mission Control.
"""

from __future__ import annotations

from app.explain import ContextTrace
from app.memory import echo as echo_agent
from app.user_model import (
    build_user_model,
    format_user_model,
)


async def with_context(
    user: dict,
    persona: str,
    query: str | None = None,
    include_workspace_activity: bool = True,
    include_user_model: bool = True,
) -> tuple[str, ContextTrace]:
    """
    Build shared context for an IntelliTwin specialist agent.

    Context contains:

    1. Agent persona
    2. Current user model
    3. Relevant Echo memories
    4. A small amount of recent workspace activity

    The returned ContextTrace is used by IntelliTwin's explainability layer.
    """

    trace = ContextTrace()

    sections: list[str] = []

    # ------------------------------------------------------------------
    # 1. Agent persona
    # ------------------------------------------------------------------

    if persona:
        sections.append(
            "YOUR ROLE\n"
            + persona.strip()
        )

    # ------------------------------------------------------------------
    # 2. Shared user model
    # ------------------------------------------------------------------

    if include_user_model:
        user_model = await build_user_model(
            user,
            query=query,
        )

        user_model_text = format_user_model(user_model)
        if user_model_text:
            sections.append(user_model_text)
            if user_model.get("profile"):
                trace.used_profile = True
            memory_items = user_model.get("memories", [])
            trace.memory_titles = [
                memory.get("title", "")
                for memory in memory_items
                if memory.get("title")
            ]

    # ------------------------------------------------------------------
    # 3. Recent workspace activity
    # ------------------------------------------------------------------
    #
    # This is intentionally lightweight.
    #
    # The agents still have workspace tools that can retrieve complete
    # records when they need them. This section simply lets an agent know
    # what has recently been happening without flooding the prompt.
    # ------------------------------------------------------------------

    if include_workspace_activity:
        recent_activity = await _recent_workspace_activity(
            user
        )

        if recent_activity:
            sections.append(
                "RECENT WORKSPACE ACTIVITY\n"
                + recent_activity
            )

    # ------------------------------------------------------------------
    # 4. Current request
    # ------------------------------------------------------------------

    if query and query.strip():
        sections.append(
            "CURRENT REQUEST\n"
            + query.strip()
        )

    return "\n\n".join(sections), trace


async def _recent_workspace_activity(
    user: dict,
    limit_per_collection: int = 5,
) -> str:
    """
    Retrieve a compact snapshot of recent workspace activity.

    This is deliberately not semantic search.

    The purpose here is to give agents awareness of the current workspace
    state. Agents can use their specialized tools when they need complete
    or highly specific information.

    All queries are scoped to the authenticated user.
    """

    from app.database import get_db

    db = get_db()
    user_id = user["_id"]

    collections = [
        (
            "goals",
            "title",
            "description",
        ),
        (
            "tasks",
            "title",
            None,
        ),
        (
            "calendar_events",
            "title",
            "notes",
        ),
        (
            "notes",
            "title",
            "body",
        ),
        (
            "documents",
            "title",
            None,
        ),
        (
            "research_items",
            "query",
            "summary",
        ),
        (
            "projects",
            "name",
            "description",
        ),
    ]

    activity: list[tuple] = []

    for (
        collection_name,
        title_field,
        secondary_field,
    ) in collections:

        try:
            documents = await db[
                collection_name
            ].find(
                {
                    "user": user_id,
                }
            ).sort(
                "updatedAt",
                -1,
            ).limit(
                limit_per_collection
            ).to_list(
                length=limit_per_collection
            )

        except Exception:
            # A missing optional collection or an unavailable collection
            # should not prevent an agent from functioning.
            continue

        for document in documents:
            title = str(
                document.get(title_field)
                or ""
            ).strip()

            secondary = ""

            if secondary_field:
                secondary = str(
                    document.get(
                        secondary_field
                    )
                    or ""
                ).strip()

            if not title and not secondary:
                continue

            item_type = _display_type(
                collection_name
            )

            if secondary:
                secondary = _compact(
                    secondary,
                    160,
                )

                activity.append(
                    (
                        document.get(
                            "updatedAt"
                        ),
                        f"- {item_type}: "
                        f"{title} — {secondary}",
                    )
                )
            else:
                activity.append(
                    (
                        document.get(
                            "updatedAt"
                        ),
                        f"- {item_type}: {title}",
                    )
                )

    # Newest activity first.
    activity.sort(
        key=lambda item: item[0]
        or "",
        reverse=True,
    )

    # Keep the prompt bounded even if the workspace is large.
    lines = [
        line
        for _, line in activity[:20]
    ]

    return "\n".join(lines)


def _display_type(
    collection_name: str,
) -> str:
    mapping = {
        "goals": "Goal",
        "tasks": "Task",
        "calendar_events": "Calendar event",
        "notes": "Note",
        "documents": "Document",
        "research_items": "Research",
        "projects": "Project",
    }

    return mapping.get(
        collection_name,
        collection_name,
    )


def _compact(
    value: str,
    limit: int,
) -> str:
    value = " ".join(
        value.split()
    )

    if len(value) <= limit:
        return value

    return value[:limit - 1] + "…"