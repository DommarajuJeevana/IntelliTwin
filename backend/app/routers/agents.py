"""
IntelliTwin agent routes.

The four specialized agents are:

- Echo    -> memory
- Atlas   -> research
- Compass -> planning
- Nova    -> creation

Mission Control uses the /chat endpoints below for natural-language
agent conversations. Each agent is given the appropriate tools and
is responsible for deciding when those tools should be used.

The older /echo, /atlas, /compass and /nova endpoints are retained
for backward compatibility with existing frontend/API consumers.
"""

import asyncio
import json
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.context_engine import with_context
from app.database import get_db
from app.dependencies import require_auth
from app.explain import explain
from app.llm import call_llm, call_llm_with_tools
from app.memory import echo as echo_agent
from app.owned import new_owned_doc, now_utc, parse_date
from app.serialization import doc_out, docs_out
from app.tools.memory_tools import ECHO_TOOLS
from app.tools.registry import (
    ATLAS_TOOLS,
    COMPASS_TOOLS,
    NOVA_TOOLS,
)
from app.conversation import (
    DEFAULT_THREAD,
    create_message,
    get_recent_messages,
    messages_out,
)
from app.orchestrator import orchestrate
from app.chat_history import today_start_utc

router = APIRouter()


AGENTS = [
    {
        "id": "echo",
        "name": "Echo",
        "role": "Memory",
        "description": "Remembers meaningful context over time.",
    },
    {
        "id": "atlas",
        "name": "Atlas",
        "role": "Research",
        "description": "Explores questions and gathers sources.",
    },
    {
        "id": "compass",
        "name": "Compass",
        "role": "Planning",
        "description": "Turns goals into an actionable plan.",
    },
    {
        "id": "nova",
        "name": "Nova",
        "role": "Creation",
        "description": "Drafts documents, notes, and content.",
    },
]


DEFAULT_STARTER_TASKS = [
    "Clarify the outcome",
    "Break into first 3 steps",
    "Set a check-in date",
]


# ---------------------------------------------------------------------------
# Shared conversational-agent support
# ---------------------------------------------------------------------------

class AgentChatBody(BaseModel):
    message: str | None = None
    thread: str | None = None


def _clean_message(message: str | None) -> str:
    if not message or not message.strip():
        raise HTTPException(
            status_code=400,
            detail="message is required.",
        )

    return message.strip()


def _current_date_context() -> str:
    """
    Gives planning agents a stable current-date reference so that
    relative dates such as "next Friday" can be interpreted.
    """
    today = datetime.now(timezone.utc).date().isoformat()

    return (
        f"Current UTC date: {today}. "
        "When the user gives a relative date, interpret it from this "
        "current date unless the workspace provides a more appropriate "
        "timezone or date context."
    )


def _tool_action_summary(
    tool_calls: list[dict],
) -> list[dict]:
    """
    Convert raw tool-loop records into a small response-safe action list.

    The frontend does not need the complete tool result payload. It only
    needs to know what the agent actually attempted and whether the tool
    returned an error.
    """
    actions: list[dict] = []

    for call in tool_calls:
        name = call.get("name")

        if not name:
            continue

        result = call.get("result")

        action = {
            "tool": name,
            "success": not (
                isinstance(result, dict)
                and result.get("error")
            ),
        }

        if isinstance(result, dict) and result.get("error"):
            action["error"] = str(result["error"])

        actions.append(action)

    return actions


async def _run_agent_chat(
    *,
    agent_name: str,
    persona: str,
    message: str,
    tools: list,
    user: dict,
    max_tokens: int = 1500,
    max_turns: int = 6,
):
    """
    Common conversational-agent execution path.

    Context is assembled first. The LLM then receives the user's natural
    language request and can call the tools assigned to that agent.
    """

    system, trace = await with_context(
        user,
        persona,
        query=message,
    )

    system = (
        f"{system}\n\n"
        f"{_current_date_context()}\n\n"
        "GENERAL AGENT RULES:\n"
        "1. Understand the user's request before acting.\n"
        "2. Use workspace tools when the request requires reading or "
        "changing workspace data.\n"
        "3. Never claim that something was created, updated, saved, "
        "scheduled, researched, or remembered unless the corresponding "
        "tool actually succeeded.\n"
        "4. Read existing workspace information before modifying it "
        "when doing so would prevent duplicates or incorrect updates.\n"
        "5. If a tool returns an error, do not pretend the operation "
        "succeeded. Explain the limitation briefly.\n"
        "6. Use the user's existing context and memories when relevant, "
        "but do not invent facts that are not present in the context "
        "or tool results.\n"
        "7. Your final response should be concise and conversational. "
        "Mention important actions you actually completed.\n"
    )

    run = await call_llm_with_tools(
        system,
        message,
        tools,
        user,
        max_tokens=max_tokens,
        max_turns=max_turns,
    )

    return run, trace


# ---------------------------------------------------------------------------
# Agent status
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_status():
    return {"agents": AGENTS}


# ---------------------------------------------------------------------------
# Echo
# ---------------------------------------------------------------------------

class EchoBody(BaseModel):
    note: str | None = None


@router.post("/echo", status_code=201)
async def invoke_echo(
    body: EchoBody,
    user: dict = Depends(require_auth),
):
    """
    Legacy explicit-memory endpoint.

    This endpoint is intentionally kept separate from conversational Echo.
    If the caller explicitly sends a note, it is treated as a request to
    remember that information.
    """

    entry = await echo_agent.remember(
        user,
        note=body.note,
    )

    return {"entry": entry}


@router.post("/echo/chat")
async def chat_with_echo(
    body: AgentChatBody,
    user: dict = Depends(require_auth),
):
    """
    Conversational Echo.

    Echo decides whether the user is asking to:
    - recall memory
    - save a memory
    - update a memory
    - archive a memory
    - restore a memory
    - simply have a conversation without changing memory
    """

    message = _clean_message(body.message)

    persona = (
        "You are Echo, IntelliTwin's long-term memory agent.\n\n"
        "Your job is to help the user manage and retrieve meaningful "
        "long-term memories.\n\n"
        "IMPORTANT MEMORY BEHAVIOR:\n"
        "- If the user asks what you remember, search_memory first and "
        "answer from the returned memories.\n"
        "- If the user explicitly asks you to remember something, use "
        "save_memory.\n"
        "- If the user asks to correct an existing memory, use "
        "search_memory first when needed, then update_memory.\n"
        "- If the user asks to forget/remove something, use delete_memory "
        "rather than pretending it was permanently erased.\n"
        "- If the user asks to restore an archived memory, use "
        "restore_memory.\n"
        "- Do NOT save every conversational message as memory.\n"
        "- Do NOT turn a question such as 'what do you remember about me?' "
        "into a new memory.\n"
        "- Only save information when the user clearly wants it remembered.\n"
    )

    run, trace = await _run_agent_chat(
        agent_name="Echo",
        persona=persona,
        message=message,
        tools=ECHO_TOOLS,
        user=user,
        max_tokens=1200,
        max_turns=5,
    )

    return {
        "agent": "echo",
        "thread": body.thread,
        "message": run.text
        or "I couldn't produce a response this time.",
        "actions": _tool_action_summary(run.tool_calls),
        "explanation": explain(
            "Echo",
            trace,
            run.tool_calls,
        ),
    }


# ---------------------------------------------------------------------------
# Atlas
# ---------------------------------------------------------------------------

class AtlasBody(BaseModel):
    query: str | None = None


@router.post("/atlas", status_code=201)
async def invoke_atlas(
    body: AtlasBody,
    user: dict = Depends(require_auth),
):
    """
    Legacy Atlas endpoint.

    Kept for compatibility. New Mission Control conversations should use
    /atlas/chat.
    """

    if not body.query:
        raise HTTPException(
            status_code=400,
            detail="query is required.",
        )

    db = get_db()

    system, trace = await with_context(
        user,
        (
            "You are Atlas, the research agent. You have tools to search "
            "the live web, search the user's existing documents and "
            "memories, and to save or link research. Use whatever tools "
            "actually help, then answer with a clear, well-organized "
            "research summary as your final message."
        ),
        query=body.query,
    )

    run = await call_llm_with_tools(
        system,
        body.query,
        ATLAS_TOOLS,
        user,
        max_tokens=1500,
    )

    item = new_owned_doc(
        user["_id"],
        agent="atlas",
    )

    item.update(
        {
            "query": body.query,
            "summary": (
                run.text
                or "Atlas didn't return a summary this time."
            ),
            "sources": _sources_from_tool_calls(
                run.tool_calls
            ),
            "status": "complete",
        }
    )

    result = await db.research_items.insert_one(item)
    item["_id"] = result.inserted_id

    return {
        "item": doc_out(item),
        "explanation": explain(
            "Atlas",
            trace,
            run.tool_calls,
        ),
    }


@router.post("/atlas/chat")
async def chat_with_atlas(
    body: AgentChatBody,
    user: dict = Depends(require_auth),
):
    """
    Conversational Atlas.

    Atlas decides whether to search the web, search the user's documents
    or memories, save research, or link research to an existing goal.
    """

    message = _clean_message(body.message)

    persona = (
        "You are Atlas, IntelliTwin's research agent.\n\n"
        "Your job is to investigate questions and turn useful findings "
        "into research that can be reused inside the user's workspace.\n\n"
        "RESEARCH BEHAVIOR:\n"
        "- Use search_web when current or external information is needed.\n"
        "- Use search_documents when the user's existing documents may "
        "contain relevant information.\n"
        "- Use search_memory when the user's past context is relevant.\n"
        "- If the user explicitly asks you to save, keep, record, or add "
        "the research to IntelliTwin, use save_research.\n"
        "- If useful research should be associated with an existing goal, "
        "use link_research_to_goal after identifying the correct goal.\n"
        "- Do not claim that research was saved unless save_research "
        "actually succeeded.\n"
        "- Do not fabricate sources or URLs.\n"
        "- Distinguish external research from information retrieved from "
        "the user's own workspace.\n"
    )

    run, trace = await _run_agent_chat(
        agent_name="Atlas",
        persona=persona,
        message=message,
        tools=ATLAS_TOOLS,
        user=user,
        max_tokens=1600,
        max_turns=6,
    )

    return {
        "agent": "atlas",
        "thread": body.thread,
        "message": run.text
        or "I couldn't complete the research request this time.",
        "actions": _tool_action_summary(run.tool_calls),
        "explanation": explain(
            "Atlas",
            trace,
            run.tool_calls,
        ),
    }


def _sources_from_tool_calls(
    tool_calls: list[dict],
) -> list[str]:
    """
    Extract URLs from Atlas search_web tool calls.
    """
    urls: list[str] = []

    for call in tool_calls:
        if call["name"] != "search_web":
            continue

        for result_item in (
            call.get("result") or {}
        ).get("results") or []:
            url = result_item.get("url")

            if url and url not in urls:
                urls.append(url)

    return urls[:8]


# ---------------------------------------------------------------------------
# Compass
# ---------------------------------------------------------------------------

class CompassBody(BaseModel):
    title: str | None = None
    dueDate: str | None = None


async def _generate_starter_task_titles(
    user: dict,
    title: str,
) -> list[str]:
    """
    Legacy fallback path for the old /compass endpoint.
    """

    system = (
        "You are Compass, the planning agent. "
        "Break a goal into 3 to 5 concrete, ordered starter tasks. "
        "Respond with ONLY a JSON array of short task title strings, "
        'e.g. ["Task one", "Task two"]. No other text.'
    )

    raw = await call_llm(
        system,
        f'Goal: "{title}"',
        max_tokens=300,
    )

    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1

        parsed = json.loads(
            raw[start:end]
        )

        tasks = [
            str(task).strip()
            for task in parsed
            if str(task).strip()
        ]

        if tasks:
            return tasks[:5]

    except (
        ValueError,
        json.JSONDecodeError,
    ):
        pass

    return DEFAULT_STARTER_TASKS


async def _insert_tasks(
    user: dict,
    goal_id,
    titles: list[str],
) -> list[dict]:
    """
    Legacy fallback used only by the old /compass endpoint.
    """

    db = get_db()

    task_docs = []

    for title in titles:
        task = new_owned_doc(
            user["_id"],
            agent="compass",
        )

        task.update(
            {
                "title": title,
                "goal": goal_id,
                "status": "todo",
                "priority": "medium",
                "dueDate": None,
            }
        )

        task_docs.append(task)

    if task_docs:
        result = await db.tasks.insert_many(
            task_docs
        )

        for doc, object_id in zip(
            task_docs,
            result.inserted_ids,
        ):
            doc["_id"] = object_id

    return docs_out(task_docs)


async def _plan_starter_tasks(
    user: dict,
    goal: dict,
) -> tuple[list[dict], str]:
    """
    Legacy planning helper used only by /compass.
    """

    system, trace = await with_context(
        user,
        (
            "You are Compass, the planning agent. A new goal was just "
            "created for this person. Use create_task to add 3 to 5 "
            "concrete, ordered starter tasks for it. If a check-in date "
            "or refined description would help, you may also use "
            "create_schedule or update_goal. When you're done acting, "
            "reply with one short sentence summarizing the plan."
        ),
        query=goal["title"],
    )

    prompt = (
        f'New goal (goal_id: {goal["_id"]}): '
        f'"{goal["title"]}"'
    )

    run = await call_llm_with_tools(
        system,
        prompt,
        COMPASS_TOOLS,
        user,
        max_tokens=1200,
        max_turns=5,
    )

    created = [
        call["result"]["task"]
        for call in run.tool_calls
        if (
            call["name"] == "create_task"
            and isinstance(
                call.get("result"),
                dict,
            )
            and "task" in call["result"]
        )
    ]

    if created:
        return (
            created[:5],
            explain(
                "Compass",
                trace,
                run.tool_calls,
            ),
        )

    titles = await _generate_starter_task_titles(
        user,
        goal["title"],
    )

    tasks = await _insert_tasks(
        user,
        goal["_id"],
        titles,
    )

    fallback_note = (
        "Compass generated a starter plan directly "
        "(no tool calls were made this time)."
    )

    return (
        tasks,
        (
            explain(
                "Compass",
                trace,
                run.tool_calls,
            )
            if run.tool_calls
            else fallback_note
        ),
    )


@router.post("/compass", status_code=201)
async def invoke_compass(
    body: CompassBody,
    user: dict = Depends(require_auth),
):
    """
    Legacy Compass endpoint.

    Kept for compatibility. Mission Control should use /compass/chat.
    """

    if not body.title:
        raise HTTPException(
            status_code=400,
            detail="title is required.",
        )

    db = get_db()

    goal = new_owned_doc(
        user["_id"],
        agent="compass",
    )

    goal.update(
        {
            "title": body.title,
            "description": "",
            "status": "in_progress",
            "progress": 0,
            "dueDate": parse_date(body.dueDate),
        }
    )

    goal_result = await db.goals.insert_one(goal)
    goal["_id"] = goal_result.inserted_id

    tasks, explanation = await _plan_starter_tasks(
        user,
        goal,
    )

    return {
        "goal": doc_out(goal),
        "tasks": tasks,
        "explanation": explanation,
    }


@router.post("/compass/chat")
async def chat_with_compass(
    body: AgentChatBody,
    user: dict = Depends(require_auth),
):
    """
    Conversational Compass.

    Compass is responsible for planning through workspace tools rather
    than hard-coded route logic.
    """

    message = _clean_message(body.message)

    persona = (
        "You are Compass, IntelliTwin's planning agent.\n\n"
        "Your job is to turn natural-language intentions into an "
        "organized, actionable workspace plan.\n\n"
        "PLANNING BEHAVIOR:\n"
        "- First understand what the user is trying to accomplish.\n"
        "- Read existing goals before creating a new one when there is "
        "a possibility that the requested goal already exists.\n"
        "- Read existing tasks when necessary to avoid creating duplicates.\n"
        "- Create a goal when the user's request represents a meaningful "
        "new objective and no suitable existing goal exists.\n"
        "- Create tasks for concrete actionable work.\n"
        "- Update an existing goal or task when the user is asking to "
        "change existing planning information.\n"
        "- Use create_schedule when the user asks for a study session, "
        "meeting, deadline-related calendar event, or another scheduled "
        "activity. For create_schedule, ALWAYS pass the event title and "
        "startsAt as explicit arguments. If using workspace_crud instead, "
        "put title and startsAt inside the nested data object; do not omit "
        "title even if the user repeats it in a follow-up. For relative dates "
        "such as 'today at 1 pm', resolve the date using the user's local "
        "timezone and pass a complete ISO datetime.\n"
        "- Do not create arbitrary calendar events just because a goal "
        "exists.\n"
        "- Preserve existing workspace information unless the user asks "
        "to change it.\n"
        "- If a request is ambiguous and a destructive or substantial "
        "change would be required, ask a concise clarification instead "
        "of guessing.\n"
        "- Confirm only actions that were actually completed by tools.\n"
    )

    run, trace = await _run_agent_chat(
        agent_name="Compass",
        persona=persona,
        message=message,
        tools=COMPASS_TOOLS,
        user=user,
        max_tokens=1600,
        max_turns=7,
    )

    return {
        "agent": "compass",
        "thread": body.thread,
        "message": run.text
        or "I couldn't complete the planning request this time.",
        "actions": _tool_action_summary(run.tool_calls),
        "explanation": explain(
            "Compass",
            trace,
            run.tool_calls,
        ),
    }


# ---------------------------------------------------------------------------
# Nova
# ---------------------------------------------------------------------------

class NovaBody(BaseModel):
    title: str | None = None
    brief: str | None = None


@router.post("/nova", status_code=201)
async def invoke_nova(
    body: NovaBody,
    user: dict = Depends(require_auth),
):
    """
    Legacy Nova endpoint.

    Kept for compatibility. Mission Control should use /nova/chat.
    """

    if not body.title:
        raise HTTPException(
            status_code=400,
            detail="title is required.",
        )

    db = get_db()

    nova_query = body.brief or body.title

    system, trace = await with_context(
        user,
        (
            "You are Nova, the creation agent. You have tools to search "
            "the user's memories, and to read their past research and "
            "documents. Use them if they'd make this draft more personal "
            "or accurate, then write the actual draft content as your "
            "final message (no preamble about what tools you used)."
        ),
        query=nova_query,
    )

    run = await call_llm_with_tools(
        system,
        (
            f'Title: "{body.title}"\n'
            f"Brief: {nova_query}"
        ),
        NOVA_TOOLS,
        user,
        max_tokens=1500,
    )

    document = new_owned_doc(
        user["_id"],
        agent="nova",
    )

    document.update(
        {
            "title": body.title,
            "type": "draft",
            "content": run.text,
            "status": "draft",
        }
    )

    result = await db.documents.insert_one(
        document
    )

    document["_id"] = result.inserted_id

    return {
        "document": doc_out(document),
        "explanation": explain(
            "Nova",
            trace,
            run.tool_calls,
        ),
    }


@router.post("/nova/chat")
async def chat_with_nova(
    body: AgentChatBody,
    user: dict = Depends(require_auth),
):
    """
    Conversational Nova.

    Nova uses its document tools to create or update real workspace
    documents rather than simply returning generated text.
    """

    message = _clean_message(body.message)

    persona = (
        "You are Nova, IntelliTwin's creation agent.\n\n"
        "Your job is to turn the user's ideas, plans, research, and "
        "existing workspace information into useful artifacts.\n\n"
        "CREATION BEHAVIOR:\n"
        "- Read existing research or documents when they are relevant "
        "to what the user wants created.\n"
        "- Search memory when personalization or known user preferences "
        "would materially improve the result.\n"
        "- If the user asks you to create a document, notes, guide, "
        "checklist, draft, summary, study material, or similar artifact, "
        "use create_document.\n"
        "- If the user asks you to modify an existing document, identify "
        "the correct document and use update_document.\n"
        "- Do not merely describe what you would create when the user "
        "has asked you to actually create it.\n"
        "- Do not claim that a document exists unless create_document or "
        "update_document succeeded.\n"
        "- If the user only asks a question and does not ask for an "
        "artifact, answer normally without unnecessarily creating a "
        "document.\n"
    )

    run, trace = await _run_agent_chat(
        agent_name="Nova",
        persona=persona,
        message=message,
        tools=NOVA_TOOLS,
        user=user,
        max_tokens=1800,
        max_turns=6,
    )

    return {
        "agent": "nova",
        "thread": body.thread,
        "message": run.text
        or "I couldn't complete the creation request this time.",
        "actions": _tool_action_summary(run.tool_calls),
        "explanation": explain(
            "Nova",
            trace,
            run.tool_calls,
        ),
    }


# ---------------------------------------------------------------------------
# Mission Control
# ---------------------------------------------------------------------------

class MissionControlBody(BaseModel):
    message: str | None = None
    thread: str | None = None


@router.get("/chat")
async def get_mission_control_history(
    thread: str | None = None,
    user: dict = Depends(require_auth),
):
    """
    Load today's Mission Control conversation.

    Every message stays stored; older days are browsed in the Chat History
    module (/api/chat-history). "Today" is the user's local calendar day.
    """
    thread_id = (
        thread.strip()
        if thread and thread.strip()
        else DEFAULT_THREAD
    )

    messages = await get_recent_messages(
        user["_id"],
        thread_id=thread_id,
        limit=50,
        since=today_start_utc(user),
    )

    return {
        "thread": thread_id,
        "messages": messages_out(messages),
    }


@router.post("/chat")
async def mission_control_chat(
    body: MissionControlBody,
    user: dict = Depends(require_auth),
):
    """
    Unified Mission Control conversation.

    The user talks to one interface. Mission Control decides which
    specialist agents are needed and combines their work into one response.
    """
    message = _clean_message(
        body.message
    )

    thread_id = (
        body.thread.strip()
        if body.thread and body.thread.strip()
        else DEFAULT_THREAD
    )

    conversation = await get_recent_messages(
        user["_id"],
        thread_id=thread_id,
        limit=12,
    )

    user_message = await create_message(
        user["_id"],
        "user",
        message,
        thread_id=thread_id,
    )

    # Include the just-created message in the orchestration context.
    conversation_for_run = [
        *conversation,
        user_message,
    ]

    result = await orchestrate(
        user,
        message,
        conversation_for_run,
    )

    assistant_message = await create_message(
        user["_id"],
        "assistant",
        result["message"],
        thread_id=thread_id,
        agents=result["agents"],
        actions=result["actions"],
        metadata={
            "reason": result["reason"],
        },
    )

    return {
        "thread": thread_id,
        "message": result["message"],
        "agents": result["agents"],
        "actions": result["actions"],
        "assistantMessage": messages_out(
            [assistant_message]
        )[0],
    }

# ---------------------------------------------------------------------------
# Multi-agent collaboration
# ---------------------------------------------------------------------------

class CollaborateBody(BaseModel):
    topic: str | None = None


@router.post("/collaborate", status_code=201)
async def collaborate(
    body: CollaborateBody,
    user: dict = Depends(require_auth),
):
    """
    Multi-agent collaboration flow.

    Compass creates a plan.
    Atlas researches the topic.
    Nova creates a document using the resulting context.
    Echo records the collaboration.
    """

    if not body.topic:
        raise HTTPException(
            status_code=400,
            detail="topic is required.",
        )

    db = get_db()
    topic = body.topic

    thread = (
        f"collab-{int(time.time() * 1000)}"
    )

    log = []

    async def push(
        author: str,
        content: str,
    ):
        message = new_owned_doc(
            user["_id"],
            agent=(
                None
                if author == "user"
                else author
            ),
        )

        message.update(
            {
                "thread": thread,
                "author": author,
                "content": content,
            }
        )

        result = await db.agent_messages.insert_one(
            message
        )

        message["_id"] = result.inserted_id
        log.append(message)

    await push("user", topic)

    goal = new_owned_doc(
        user["_id"],
        agent="compass",
    )

    goal.update(
        {
            "title": topic,
            "description": (
                "Created from a multi-agent collaboration."
            ),
            "status": "in_progress",
            "progress": 0,
            "dueDate": None,
        }
    )

    goal_result = await db.goals.insert_one(goal)
    goal["_id"] = goal_result.inserted_id

    compass_persona = (
        "You are Compass, the planning agent, collaborating with "
        "Atlas and Nova on this topic for a goal that already exists "
        f"(goal_id: {goal['_id']}). Use create_task to add 3-5 "
        "concrete ordered tasks to that goal, and create_schedule if "
        "a specific check-in or session date would help. Then reply "
        "with 1-2 sentences summarizing the plan for the team."
    )

    atlas_persona = (
        "Atlas, the research agent, collaborating with Compass and "
        "Nova on a goal that already exists "
        f"(goal_id: {goal['_id']}). Research this topic using "
        "search_web and/or search_documents, then call save_research "
        "with a useful summary and link_research_to_goal to attach "
        "it to that goal_id. Then reply with 1-2 sentences on what "
        "you found."
    )

    (
        (compass_system, compass_trace),
        (atlas_system, atlas_trace),
    ) = await asyncio.gather(
        with_context(
            user,
            compass_persona,
            query=topic,
        ),
        with_context(
            user,
            atlas_persona,
            query=topic,
        ),
    )

    (
        compass_run,
        atlas_run,
    ) = await asyncio.gather(
        call_llm_with_tools(
            compass_system,
            topic,
            COMPASS_TOOLS,
            user,
            max_tokens=400,
            max_turns=4,
        ),
        call_llm_with_tools(
            atlas_system,
            f"Research context needed for: {topic}",
            ATLAS_TOOLS,
            user,
            max_tokens=700,
            max_turns=4,
        ),
    )

    await push(
        "compass",
        compass_run.text,
    )

    created_tasks = [
        call["result"]["task"]
        for call in compass_run.tool_calls
        if (
            call["name"] == "create_task"
            and isinstance(
                call.get("result"),
                dict,
            )
            and "task" in call["result"]
        )
    ]

    await push(
        "atlas",
        atlas_run.text,
    )

    research_items = [
        call["result"]["item"]
        for call in atlas_run.tool_calls
        if (
            call["name"] == "save_research"
            and isinstance(
                call.get("result"),
                dict,
            )
            and "item" in call["result"]
        )
    ]

    research_item = (
        research_items[-1]
        if research_items
        else None
    )

    nova_context = (
        f'The goal is: "{topic}".'
    )

    if research_item:
        nova_context += (
            " Atlas researched it and found: "
            f'{research_item["summary"][:500]}'
        )

    nova_system, nova_trace = await with_context(
        user,
        (
            "Nova, the creation agent, collaborating with Compass "
            "and Atlas. Use create_document to produce real material "
            "for this goal (e.g. study notes, a brief, or a checklist, "
            "depending on what the topic calls for) - don't just "
            "describe what you'd write. Then reply with 1-2 sentences "
            "about what you created."
        ),
        query=topic,
    )

    nova_run = await call_llm_with_tools(
        nova_system,
        nova_context,
        NOVA_TOOLS,
        user,
        max_tokens=1200,
        max_turns=4,
    )

    await push(
        "nova",
        nova_run.text,
    )

    documents = [
        call["result"]["document"]
        for call in nova_run.tool_calls
        if (
            call["name"] == "create_document"
            and isinstance(
                call.get("result"),
                dict,
            )
            and "document" in call["result"]
        )
    ]

    document = (
        documents[-1]
        if documents
        else None
    )

    await push(
        "echo",
        (
            f'Logged this collaboration on '
            f'"{topic}" to long-term memory.'
        ),
    )

    await echo_agent.remember(
        user,
        note=(
            f'Compass, Atlas, and Nova collaborated '
            f'on "{topic}".'
        ),
        title=f"Collaboration: {topic}",
        importance=3,
    )

    existing = await db.milestones.find_one(
        {
            "user": user["_id"],
            "label": "First multi-agent collaboration",
        }
    )

    if not existing:
        milestone = new_owned_doc(
            user["_id"]
        )

        milestone.update(
            {
                "label": (
                    "First multi-agent collaboration"
                ),
                "detail": (
                    "Compass, Atlas and Nova worked "
                    "together for the first time."
                ),
                "icon": "spark",
                "earnedAt": now_utc(),
            }
        )

        await db.milestones.insert_one(
            milestone
        )

    return {
        "thread": thread,
        "log": docs_out(log),
        "goal": doc_out(goal),
        "tasks": created_tasks,
        "researchItem": research_item,
        "document": document,
        "explanations": {
            "compass": explain(
                "Compass",
                compass_trace,
                compass_run.tool_calls,
            ),
            "atlas": explain(
                "Atlas",
                atlas_trace,
                atlas_run.tool_calls,
            ),
            "nova": explain(
                "Nova",
                nova_trace,
                nova_run.tool_calls,
            ),
        },
    }