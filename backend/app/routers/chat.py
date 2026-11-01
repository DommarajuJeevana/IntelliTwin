"""
Unified IntelliTwin agent conversation endpoint.

The dashboard has one workspace, but the user can switch between Echo,
Atlas, Compass, and Nova without leaving that workspace. This router keeps
that interaction separate from the older action-oriented agent endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.context_engine import with_context
from app.database import get_db
from app.dependencies import require_auth
from app.llm import call_llm_with_tools
from app.memory import echo as echo_agent
from app.owned import new_owned_doc
from app.serialization import serialize
from app.tools.registry import (
    ATLAS_TOOLS,
    COMPASS_TOOLS,
    ECHO_TOOLS,
    NOVA_TOOLS,
)

router = APIRouter()

AGENT_CONFIG = {
    "echo": {
        "name": "Echo",
        "role": "Memory",
        "tools": ECHO_TOOLS,
        "persona": (
            "You are Echo, IntelliTwin's memory agent. Help the person "
            "understand, retrieve, update, and intentionally save useful "
            "long-term context. Use memory tools when the request calls "
            "for an actual memory operation. Do not save trivial or "
            "temporary conversation details unless the person clearly asks "
            "you to remember them. Answer naturally and concisely."
        ),
    },
    "atlas": {
        "name": "Atlas",
        "role": "Research",
        "tools": ATLAS_TOOLS,
        "persona": (
            "You are Atlas, IntelliTwin's research agent. Help the person "
            "investigate questions, search the web when useful, search "
            "their workspace when useful, and save useful research when "
            "appropriate. Distinguish facts from uncertainty and do not "
            "invent sources. Answer with a useful research-oriented result."
        ),
    },
    "compass": {
        "name": "Compass",
        "role": "Planning",
        "tools": COMPASS_TOOLS,
        "persona": (
            "You are Compass, IntelliTwin's planning agent. Help the person "
            "turn goals into practical next steps. Use workspace tools when "
            "the person asks you to create or modify tasks, schedules, or "
            "goals. Keep plans concrete and avoid creating unnecessary "
            "workspace items."
        ),
    },
    "nova": {
        "name": "Nova",
        "role": "Creation",
        "tools": NOVA_TOOLS,
        "persona": (
            "You are Nova, IntelliTwin's creation agent. Help the person "
            "turn ideas, research, memories, and existing documents into "
            "useful drafts and finished workspace content. Use document "
            "tools when the person asks you to create or update an actual "
            "document."
        ),
    },
}


class ChatBody(BaseModel):
    agent: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=12000)
    thread: str | None = Field(default=None, max_length=120)


def _validate_agent(agent: str) -> dict:
    config = AGENT_CONFIG.get(agent.lower())
    if not config:
        raise HTTPException(
            status_code=400,
            detail="agent must be one of: echo, atlas, compass, nova.",
        )
    return config


HISTORY_MESSAGES = 12        # bounded: never send an unlimited transcript
HISTORY_CHARS_PER_MESSAGE = 600


async def _history_prompt(user_id, thread: str | None) -> str:
    """The most recent messages of THIS user's THIS thread, oldest first.
    (Previously this returned the first 12 messages, so long threads lost
    their recent context.) Missing or malformed history yields no context."""
    if not thread:
        return ""

    try:
        db = get_db()
        messages = (
            await db.agent_messages.find({"user": user_id, "thread": thread})
            .sort("createdAt", -1)
            .limit(HISTORY_MESSAGES)
            .to_list(length=HISTORY_MESSAGES)
        )
    except Exception:
        return ""
    messages.reverse()

    lines = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        author = item.get("author") or item.get("agent") or "user"
        content = str(item.get("content") or "").strip()[:HISTORY_CHARS_PER_MESSAGE]
        if content:
            lines.append(f"{author}: {content}")

    if not lines:
        return ""

    return (
        "Recent conversation in this thread (reference only - it is not proof of "
        "what exists in the workspace; verify with tools before acting):\n" + "\n".join(lines)
    )


async def _save_message(
    user: dict,
    thread: str,
    author: str,
    agent: str | None,
    content: str,
) -> dict:
    db = get_db()

    message = new_owned_doc(
        user["_id"],
        agent=agent,
    )

    message.update(
        {
            "thread": thread,
            "author": author,
            "content": content,
        }
    )

    result = await db.agent_messages.insert_one(message)
    message["_id"] = result.inserted_id

    return message


@router.post("/chat")
async def chat(
    body: ChatBody,
    user: dict = Depends(require_auth),
):
    agent_id = body.agent.lower().strip()
    config = _validate_agent(agent_id)

    message = body.message.strip()
    if not message:
        raise HTTPException(
            status_code=400,
            detail="message is required.",
        )

    thread = (body.thread or "").strip()
    if not thread:
        # The frontend normally supplies a session thread. This fallback
        # keeps the endpoint usable directly from Swagger as well.
        import uuid

        thread = str(uuid.uuid4())

    history = await _history_prompt(
        user["_id"],
        thread,
    )

    system, trace = await with_context(
        user,
        config["persona"],
        query=message,
    )

    if history:
        system = f"{system}\n\n{history}"

    await _save_message(
        user,
        thread,
        "user",
        None,
        message,
    )

    run = await call_llm_with_tools(
        system,
        message,
        config["tools"],
        user,
        max_tokens=1400,
        max_turns=5,
    )

    reply = (
        run.text.strip()
        if run.text and run.text.strip()
        else f"{config['name']} couldn't produce a response right now."
    )

    assistant_message = await _save_message(
        user,
        thread,
        agent_id,
        agent_id,
        reply,
    )

    # Capture durable personal information from ordinary conversation.
    # Echo's remember() performs conservative extraction, rejects questions /
    # greetings / secrets, and skips duplicates. Memory failures must never
    # make an otherwise successful chat request fail.
    try:
        await echo_agent.remember(
            user,
            source_interaction=message,
        )
    except Exception:
        import logging

        logging.getLogger("intellitwin.chat").exception(
            "Automatic Echo memory capture failed for chat message."
        )

    return serialize(
        {
            "thread": thread,
            "agent": {
                "id": agent_id,
                "name": config["name"],
                "role": config["role"],
            },
            "message": assistant_message,
            "explanation": {
                "agent": config["name"],
                "memoryTitles": trace.memory_titles,
                "usedProfile": trace.used_profile,
                "toolCalls": [
                    call["name"]
                    for call in run.tool_calls
                ],
            },
        }
    )


@router.get("/chat/history")
async def chat_history(
    thread: str = Query(min_length=1, max_length=120),
    user: dict = Depends(require_auth),
):
    db = get_db()

    messages = (
        await db.agent_messages.find(
            {
                "user": user["_id"],
                "thread": thread,
            }
        )
        .sort("createdAt", 1)
        .to_list(length=100)
    )

    return {
        "thread": thread,
        "messages": serialize(messages),
    }
