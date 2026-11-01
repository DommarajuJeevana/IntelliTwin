"""
IntelliTwin user model.

The user model is the shared identity/context layer used by Mission Control
and all four specialist agents:

    Echo    -> memory
    Atlas   -> research
    Compass -> planning / scheduling
    Nova    -> writing / creation

Important:
- Echo remains the owner of long-term memory.
- This module does NOT create or modify memories.
- It only assembles the current user picture for agent context.
- Superseded and archived memories are excluded by Echo's normal retrieval.
"""

from __future__ import annotations

from typing import Any

from app.memory import echo as echo_agent
from app.user_utils import profile_context


# Keep the number of memories passed into an LLM bounded.
DEFAULT_MEMORY_LIMIT = 8
MAX_MEMORY_LIMIT = 20


def _safe_limit(
    value: Any,
    default: int = DEFAULT_MEMORY_LIMIT,
) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default

    return max(
        1,
        min(value, MAX_MEMORY_LIMIT),
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _memory_summary(memory: dict) -> dict:
    """
    Convert an Echo memory into the compact representation that agents need.

    We deliberately do not expose the embedding or internal database fields.
    """
    return {
        "id": (
            str(memory["_id"])
            if memory.get("_id") is not None
            else None
        ),
        "title": _clean_text(
            memory.get("title")
        ),
        "content": _clean_text(
            memory.get("content")
        ),
        "importance": memory.get(
            "importance",
            3,
        ),
        "confidence": memory.get(
            "confidence"
        ),
        "source": memory.get(
            "source"
        ),
        "status": memory.get(
            "status",
            "active",
        ),
    }


async def build_user_model(
    user: dict,
    *,
    query: str | None = None,
    memory_limit: int = DEFAULT_MEMORY_LIMIT,
) -> dict:
    """
    Build the current shared model of the user.

    If a query is supplied, Echo performs semantic retrieval so that the
    returned memories are relevant to the current request.

    If no query is supplied, the most recent active memories are used.

    This function is read-only.
    """
    limit = _safe_limit(memory_limit)

    profile = profile_context(user)

    memories: list[dict] = []

    if query and query.strip():
        memories = await echo_agent.search_memory(
            user,
            query.strip(),
            limit=limit,
        )
    else:
        memories = await echo_agent.get_recent_memories(
            user,
            limit=limit,
        )

    return {
        "profile": profile or "",
        "memories": [
            _memory_summary(memory)
            for memory in memories
        ],
    }


def format_user_model(
    model: dict,
) -> str:
    """
    Convert the user model into a controlled prompt section.

    This is intentionally factual and compact. It should not make
    psychological claims or invent preferences that are not present
    in the stored user information.
    """
    sections: list[str] = []

    profile = _clean_text(
        model.get("profile")
    )

    if profile:
        sections.append(
            "USER PROFILE\n"
            + profile
        )

    memories = model.get("memories") or []

    if memories:
        lines = [
            "RELEVANT LONG-TERM MEMORY"
        ]

        for memory in memories:
            title = _clean_text(
                memory.get("title")
            )

            content = _clean_text(
                memory.get("content")
            )

            if not content:
                continue

            importance = memory.get(
                "importance",
                3,
            )

            confidence = memory.get(
                "confidence"
            )

            line = (
                f"- {title}: {content}"
                if title
                else f"- {content}"
            )

            line += (
                f" [importance={importance}"
            )

            if confidence is not None:
                line += (
                    f", confidence={confidence}"
                )

            line += "]"

            lines.append(line)

        if len(lines) > 1:
            sections.append(
                "\n".join(lines)
            )

    if not sections:
        return (
            "USER MODEL\n"
            "No stored user information is currently "
            "relevant to this request."
        )

    return "\n\n".join(sections)