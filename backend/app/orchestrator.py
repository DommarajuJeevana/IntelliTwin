
import asyncio
import json
import logging
import re
import time
from collections import deque

from app.context_engine import with_context
from app.llm import call_llm, call_llm_with_tools
from app.owned import set_user_tz
from app.workspace_actions import try_direct_workspace_action
from app.tools.registry import (
    ECHO_TOOLS,
    ATLAS_TOOLS,
    COMPASS_TOOLS,
    NOVA_TOOLS,
    GET_WORKSPACE_CONTEXT,
)


logger = logging.getLogger("intellitwin.orchestrator")

AGENT_NAMES = {"echo", "atlas", "compass", "nova"}

AGENT_TOOLS = {
    "echo": ECHO_TOOLS,
    "atlas": ATLAS_TOOLS,
    "compass": COMPASS_TOOLS,
    "nova": NOVA_TOOLS,
}

AGENT_PERSONAS = {
    "echo": (
        "You are Echo, IntelliTwin's memory and personal-context specialist. "
        "Use available memory and workspace context to answer questions about "
        "the user's preferences, history, decisions, and ongoing work. "
        "Save information only when the user explicitly asks you to remember "
        "or save it, or when a memory tool's documented purpose clearly applies. "
        "Do not save every ordinary message as a memory. "
        "Preferences the user states while chatting (liked, changed or disliked) "
        "are recorded automatically after each message, so do not announce that "
        "you saved them unless asked. Use the recent conversation to resolve "
        "references such as 'it', 'that' or 'the other one'; never ask the user "
        "to repeat what you were discussing. "
        "Do not invent personal facts. Distinguish stored information from "
        "reasonable inference. Use the available tools when needed. When a "
        "remembered emotional trigger recurs, acknowledge the emotion without "
        "automatically agreeing with the user's interpretation. Identify the "
        "known trigger, separate facts from assumptions, offer a balanced and "
        "practical next step, and ask a brief clarifying question if context is "
        "missing. Do not diagnose, moralize, or overreact."
    ),
    "atlas": (
        "You are Atlas, IntelliTwin's research specialist. "
        "Investigate questions using available research tools and evidence. "
        "Prefer reliable, relevant sources. When web research is requested, "
        "use the search tools instead of pretending to have searched. "
        "Clearly distinguish verified information, uncertainty, and inference. "
        "Include useful source links when available. Save or link research "
        "to the workspace when the user requests it or when it is an explicit "
        "part of the coordinated task."
    ),
    "compass": (
        "You are Compass, IntelliTwin's planning and scheduling specialist. "
        "Turn goals and requests into clear, actionable plans. "
        "Use workspace tools to read or create goals, tasks, and calendar events "
        "when requested. Check existing workspace data before creating duplicates. "
        "Do not claim an item was created or updated unless the relevant tool "
        "confirms success. Respect dates, times, dependencies, and constraints."
    ),
    "nova": (
        "You are Nova, IntelliTwin's writing and content-creation specialist. "
        "Create useful documents and other content based on the user's request "
        "and any research or context passed to you. Use workspace tools when "
        "the user asks to save or update content. Do not claim that content was "
        "saved unless a tool confirms the operation. Avoid fabricating research."
    ),
}

ORCHESTRATOR_SYSTEM = """
You are the request planner for IntelliTwin Mission Control.

IntelliTwin has four specialists:
- echo: memory, personal context, remembered preferences, and relevant history
- atlas: research, investigation, evidence, and source gathering
- compass: goals, task breakdown, planning, scheduling, and calendar operations
- nova: writing, document creation, and content editing

Select only the agents needed to fulfill the user's current request.
A simple conversational question may need no specialist.
Do not select all agents by default.

When a request contains multiple deliverables, select every specialist needed.
Consider dependencies: a specialist may need the output of an earlier specialist.

Return ONLY a JSON object with this structure:
{
  "agents": ["atlas", "nova"],
  "reason": "Brief explanation",
  "dependencies": [
    {"from": "atlas", "to": "nova"}
  ]
}

Rules:
- Use only the four valid agent names.
- Do not invent agents or dependency types.
- Add a dependency only when one agent needs another agent's output.
- Research followed by writing usually means atlas -> nova.
- Research followed by planning usually means atlas -> compass.
- Personal context used to make a plan may mean echo -> compass.
- If the user explicitly asks to remember research findings, research may need
  to precede the memory operation.
- Do not choose an agent merely because its name appears in the request.
- Do not include markdown fences or commentary outside the JSON.
"""


# These patterns are deliberately intent-oriented. They supplement the LLM
# planner; they do not automatically force all four agents into every request.

ATLAS_PATTERNS = [
    r"\bresearch\b",
    r"\binvestigat(?:e|ion|ing)\b",
    r"\blook\s+up\b",
    r"\bfind\s+out\b",
    r"\bsearch\s+(?:the\s+)?(?:web|internet|online)\b",
    r"\bcurrent(?:ly)?\b",
    r"\blatest\b",
    r"\brecent(?:ly)?\b",
    r"\bsource(?:s|d)?\b",
    r"\bcitations?\b",
    r"\bevidence\b",
    r"\bstatistics\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bpros\s+and\s+cons\b",
    r"\bverify\b",
    r"\bfact[- ]check\b",
    r"\bwho\s+is\b",
]

NOVA_PATTERNS = [
    r"\bwrite\b",
    r"\bdraft\b",
    r"\bcompose\b",
    r"\bprepare\b",
    r"\bcreate\b",
    r"\bgenerate\b",
    r"\bedit\b",
    r"\brewrite\b",
    r"\bpolish\b",
    r"\bformat\b",
    r"\bturn\s+this\s+into\b",
    r"\bput\s+together\b",
    r"\bdocument\b",
    r"\breport\b",
    r"\bessay\b",
    r"\barticle\b",
    r"\bpresentation\b",
    r"\bproposal\b",
    r"\bcover\s+letter\b",
    r"\bemail\b",
    r"\bsummary\b",
    r"\bchecklist\b",
    r"\bguide\b",
    r"\bcontent\b",
]

COMPASS_PATTERNS = [
    r"\bplan\b",
    r"\bplanning\b",
    r"\bschedule\b",
    r"\bscheduling\b",
    r"\bcalendar\b",
    r"\bmeetings?\b",
    r"\bappointments?\b",
    r"\bevents?\b",
    r"\btimetable\b",
    r"\bdeadline\b",
    r"\bpriorit(?:y|ies|ize|ise|izing|ising)\b",
    r"\bgoal\b",
    r"\bgoals\b",
    r"\btask\b",
    r"\btasks\b",
    r"\bto[- ]do\b",
    r"\bbreak\s+(?:this|it|that|the\s+work)\s+down\b",
    r"\bactionable\s+steps\b",
    r"\borganize\s+my\b",
    r"\borganise\s+my\b",
    r"\bmanage\s+my\s+time\b",
    r"\bstudy\s+plan\b",
    r"\bworkout\s+plan\b",
    r"\bweekly\s+plan\b",
    r"\bdaily\s+plan\b",
    r"\bremind\s+me\b",
    r"\badd\s+to\s+(?:my\s+)?calendar\b",
    r"\bwhat\s+should\s+i\s+do\s+first\b",
]

ECHO_PATTERNS = [
    r"\bremember\b",
    r"\bmemor(?:y|ies)\b",
    r"\bwhat\s+do\s+(?:you|u|ya)\s+remember\b",
    r"\bwhat\s+(?:have|did)\s+(?:you|u)\s+(?:learn|learned|learnt|remember)",
    r"\bwhat\s+do\s+(?:you|u|ya)\s+know\s+about\s+me\b",
    r"\bmy\s+preferences?\b",
    r"\bmy\s+usual\b",
    r"\bmy\s+previous\b",
    r"\bwhat\s+did\s+i\s+say\b",
    r"\brecall\b",
    r"\bforget\s+(?:that|this|it|about)\b",
    r"\bsave\s+(?:this|that)\s+to\s+memory\b",
]

RESEARCH_ARTIFACT_PATTERNS = [
    r"\bwrite\b",
    r"\bdraft\b",
    r"\bcreate\b",
    r"\bprepare\b",
    r"\bgenerate\b",
    r"\bmake\b",
    r"\bproduce\b",
    r"\bturn\s+.{0,50}\s+into\b",
    r"\breport\b",
    r"\bdocument\b",
    r"\bpresentation\b",
    r"\bsummary\b",
    r"\bproposal\b",
]

PLANNING_ARTIFACT_PATTERNS = [
    r"\bstudy\s+plan\b",
    r"\bproject\s+plan\b",
    r"\baction\s+plan\b",
    r"\broadmap\b",
    r"\bimplementation\s+plan\b",
    r"\bweekly\s+plan\b",
    r"\bdaily\s+plan\b",
    r"\bschedule\b",
    r"\bcalendar\b",
    r"\btimetable\b",
]

REMEMBER_REQUEST_PATTERNS = [
    r"\bremember\b",
    r"\bsave\s+(?:this|that|it)\b",
    r"\bstore\s+(?:this|that|it)\b",
    r"\bkeep\s+(?:this|that|it)\s+in\s+mind\b",
]


def _matches_any(text, patterns):
    text = (text or "").lower()
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _clean_json_response(value):
    if not value:
        return {}

    if isinstance(value, dict):
        return value

    text = str(value).strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        pass

    # Recover a JSON object if the model included surrounding text.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    return {}


def _normalise_agents(agents):
    if not isinstance(agents, list):
        return []

    result = []
    for agent in agents:
        if not isinstance(agent, str):
            continue

        name = agent.strip().lower()
        if name in AGENT_NAMES and name not in result:
            result.append(name)

    return result


def _normalise_dependencies(dependencies, agents):
    if not isinstance(dependencies, list):
        return []

    allowed = set(agents)
    result = []
    seen = set()

    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue

        source = dependency.get("from")
        target = dependency.get("to")

        if not isinstance(source, str) or not isinstance(target, str):
            continue

        source = source.strip().lower()
        target = target.strip().lower()

        if source not in allowed or target not in allowed or source == target:
            continue

        pair = (source, target)
        if pair not in seen:
            result.append({"from": source, "to": target})
            seen.add(pair)

    return result


_SIMPLE_SOCIAL_MESSAGES = {
    "hi", "hello", "hey", "hiya", "good morning", "good afternoon",
    "good evening", "howdy", "thanks", "thank you", "thank you so much",
    "thx", "ok", "okay", "got it", "great", "cool", "bye", "goodbye",
}


def _normalise_social_message(message: str) -> str:
    value = (message or "").strip().lower()
    value = re.sub(r"^[\s\W_]+|[\s\W_]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _is_simple_social_message(message: str) -> bool:
    """True only for stand-alone pleasantries, never for mixed requests."""
    return _normalise_social_message(message) in _SIMPLE_SOCIAL_MESSAGES


def _needs_personal_context(message: str) -> bool:
    """Avoid vector-memory retrieval for requests that do not need personalization."""
    return _matches_any(message, [
        r"\bmy\b", r"\bme\b", r"\bi\b", r"\bremember\b",
        r"\bpreference", r"\bprevious", r"\brecall\b",
        r"\bwhat do you know about me\b", r"\bwhat do you remember\b",
        r"\busual\b", r"\bpersonaliz",
    ])


def _is_direct_memory_recall_request(message: str) -> bool:
    """Recognize memory-recall questions (typos and texting spellings included)
    that should be answered straight from Echo's store, not via the LLM tool loop."""
    return _matches_any(message, [
        r"\b(?:remember|remembers|know|knows|learn(?:ed|t)?|recall)\b.{0,30}\babout\s+me\b",
        r"\b(?:you|u|ya|yu)\s+(?:still\s+)?(?:remember|recall)\b.{0,25}\b(?:me|my|anything|something)\b",
        r"\b(?:w(?:ha)?t|wat|wht)\b.{0,12}\b(?:you|u|ya|yu)\b.{0,12}\b(?:remember|know|recall)\b",
        r"\btell\s+me\s+what\s+(?:you|u)\s+(?:remember|know)\b",
        r"\bwhat\s+(?:is|are)\s+my\s+preferences?\b",
        r"\bmy preferences?\b",
        r"^\s*(?:please\s+)?(?:search|check|show|open)\s+(?:my\s+)?memor(?:y|ies)\s*[.!?]*$",
        r"\brecall my preferences?\b",
    ])


async def _answer_memory_recall(user: dict, message: str) -> dict:
    """Answer simple recall questions from concise, relevant saved memories."""
    import re
    from app.memory import echo as echo_agent

    started = time.perf_counter()
    lowered = (message or "").lower()
    is_preference_query = _matches_any(lowered, [r"\bpreferences?\b", r"\bprefer\b", r"\blikes?\b", r"\bdislikes?\b"])

    if is_preference_query:
        query = "stable user preferences communication style response style work style likes dislikes"
        memories = await echo_agent.search_memory(user, query, limit=12)
    else:
        memories = await echo_agent.get_recent_memories(user, limit=12)

    def clean_key(value: str) -> str:
        value = (value or "").lower()
        value = re.sub(r"^\s*(?:remember that|echo remembers that)\s+", "", value)
        value = re.sub(r"[^\w\s]", " ", value)
        return " ".join(value.split())

    lines = []
    seen = set()
    for memory in memories:
        title = str(memory.get("title") or "").strip()
        content = str(memory.get("content") or "").strip()
        if not content:
            continue
        low = content.lower().strip()
        if low.endswith("?") or low in {"hello echo", "hello echo!", "what do you remember about me"}:
            continue
        if low.startswith(("echo remembers that", "the user asked", "user asked", "assistant said", "mission control")):
            continue
        if is_preference_query:
            preference_signal = memory.get("category") == "preference" or any(token in (title + " " + content).lower() for token in (
                "prefer", "preference", "likes", "dislikes", "favorite", "favours", "favors",
                "communication style", "concise", "morning", "work style", "enjoys", "avoids",
            ))
            if not preference_signal:
                continue
        key = clean_key(content)
        if not key or key in seen:
            continue
        seen.add(key)
        line = f"- **{title}**: {content}" if title and clean_key(title) not in key else f"- {content}"
        lines.append(line)
        if len(lines) >= (6 if is_preference_query else 8):
            break

    if lines:
        intro = "Here are the saved preferences I found:" if is_preference_query else "Here’s what I currently have saved in memory:"
        answer = intro + "\n\n" + "\n".join(lines)
    elif is_preference_query:
        answer = "I couldn't find any clear saved preferences yet. I won't treat ordinary conversation as a preference; tell me what you'd like me to remember."
    else:
        answer = "I couldn't find any useful saved memories yet."

    elapsed = time.perf_counter() - started
    logger.info("Direct memory recall completed in %.3fs (preference_query=%s, memories=%d)", elapsed, is_preference_query, len(lines))
    return {
        "message": answer,
        "agents": ["echo"],
        "planned_agents": ["echo"],
        "reason": "Direct filtered memory retrieval; skipped planner, agent tool loop, and synthesis.",
        "dependencies": [],
        "actions": [{"tool": "search_memory" if is_preference_query else "get_recent_memories", "success": True, "result_count": len(lines)}],
    }


def _is_explicit_workspace_context_request(message: str) -> bool:
    return _matches_any(message, [
        r"^\s*(?:please\s+)?(?:get|show|fetch|load|give me)\s+(?:my\s+)?workspace context\s*[.!?]*$",
        r"^\s*(?:show|give me)\s+(?:a\s+)?workspace overview\s*[.!?]*$",
        r"^\s*summarize\s+my\s+workspace\s*[.!?]*$",
    ])


def _needs_workspace_snapshot(message: str) -> bool:
    """Fetch broad workspace activity only when the request refers to it."""
    return _matches_any(message, [
        r"\bworkspace context\b", r"\brecent workspace\b",
        r"\bwhat have i been working on\b", r"\bmy (?:tasks|projects|documents|notes|goals)\b",
        r"\b(calendar|meetings?|appointments?|events?|schedule|timetable|deadline|task list|project update)\b",
        r"\bplan my (?:day|week|month)\b",
    ])


def _social_reply(message: str) -> str:
    value = _normalise_social_message(message)
    if value in {"thanks", "thank you", "thank you so much", "thx"}:
        return "You're welcome!"
    if value in {"bye", "goodbye"}:
        return "See you later!"
    if value in {"ok", "okay", "got it", "great", "cool"}:
        return "Sounds good. What would you like to work on next?"
    if value in {"good morning", "good afternoon", "good evening"}:
        return f"{value.capitalize()}! What can I help you with?"
    return "Hi! What can I help you with?"


def _keyword_agents(message, conversation=None):
    """
    Find clear specialist intents in the current request.

    Conversation history is included to help interpret follow-ups, but the
    current message remains the primary signal.
    """
    current = (message or "").strip()
    history = _conversation_text(conversation)
    lowered = current.lower()

    selected = []

    def add(agent):
        if agent not in selected:
            selected.append(agent)

    # Route by current intent. Old turns are only used to resolve an explicit
    # short follow-up; they must never activate Echo for an unrelated greeting.
    if _matches_any(current, ECHO_PATTERNS):
        add("echo")

    atlas_intent = _matches_any(current, ATLAS_PATTERNS)
    if atlas_intent:
        add("atlas")

    compass_intent = _matches_any(current, COMPASS_PATTERNS)
    if compass_intent:
        add("compass")

    nova_intent = _matches_any(current, NOVA_PATTERNS)
    if nova_intent:
        add("nova")

    # A request to produce a research-based deliverable needs research and
    # content creation, even if the planner omits one of the specialists.
    if atlas_intent and _matches_any(lowered, RESEARCH_ARTIFACT_PATTERNS):
        add("nova")

    # A research-dependent plan needs the findings before planning.
    if atlas_intent and _matches_any(lowered, PLANNING_ARTIFACT_PATTERNS):
        add("compass")

    # If the user explicitly asks to remember research findings, Echo must
    # receive the research result rather than storing an unverified request.
    if atlas_intent and _matches_any(lowered, REMEMBER_REQUEST_PATTERNS):
        add("echo")

    # When the current message is a short follow-up, the planner can use the
    # recent conversation to resolve it. Do not automatically activate every
    # agent mentioned in the history.
    short_follow_up = len(current.split()) <= 8 and bool(
        re.search(
            r"\b(it|that|this|those|them|also|instead|continue|do\s+that)\b",
            lowered,
        )
    )
    if short_follow_up and history:
        if _matches_any(history, ECHO_PATTERNS) and _matches_any(
            lowered, [r"\bremember\b", r"\bsave\b", r"\bforget\b"]
        ):
            add("echo")

    return selected


def _dependency_fallback(message, agents):
    """Create obvious dependencies when the planner omits them."""
    text = (message or "").lower()
    available = set(agents)
    dependencies = []

    def add(source, target):
        if source in available and target in available:
            pair = (source, target)
            if not any(
                item["from"] == source and item["to"] == target
                for item in dependencies
            ):
                dependencies.append({"from": source, "to": target})

    if "atlas" in available and "nova" in available:
        if _matches_any(text, RESEARCH_ARTIFACT_PATTERNS):
            add("atlas", "nova")

    if "atlas" in available and "compass" in available:
        if _matches_any(text, PLANNING_ARTIFACT_PATTERNS):
            add("atlas", "compass")

    if "echo" in available and "compass" in available:
        if _matches_any(text, ECHO_PATTERNS) and _matches_any(
            text, COMPASS_PATTERNS
        ):
            add("echo", "compass")

    if "atlas" in available and "echo" in available:
        if _matches_any(text, REMEMBER_REQUEST_PATTERNS):
            add("atlas", "echo")

    return dependencies


def _has_cycle(agents, dependencies):
    graph = {agent: [] for agent in agents}
    indegree = {agent: 0 for agent in agents}

    for item in dependencies:
        source = item["from"]
        target = item["to"]
        if target not in graph[source]:
            graph[source].append(target)
            indegree[target] += 1

    queue = deque(agent for agent in agents if indegree[agent] == 0)
    visited = 0

    while queue:
        current = queue.popleft()
        visited += 1
        for target in graph[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    return visited != len(agents)


def _order_agents(agents, dependencies):
    """Stable topological ordering; retain original order when a cycle exists."""
    agents = list(dict.fromkeys(agents))
    graph = {agent: [] for agent in agents}
    indegree = {agent: 0 for agent in agents}

    for item in dependencies:
        source = item["from"]
        target = item["to"]

        if source not in graph or target not in graph:
            continue
        if target in graph[source]:
            continue

        graph[source].append(target)
        indegree[target] += 1

    queue = deque(agent for agent in agents if indegree[agent] == 0)
    ordered = []

    while queue:
        current = queue.popleft()
        ordered.append(current)

        for target in graph[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(ordered) != len(agents):
        return agents

    return ordered


def _filter_dependencies_for_order(agents, dependencies):
    allowed = set(agents)
    filtered = [
        item
        for item in dependencies
        if item.get("from") in allowed and item.get("to") in allowed
    ]

    if _has_cycle(agents, filtered):
        return _dependency_fallback("", agents)

    return filtered


def _conversation_text(conversation):
    if not conversation:
        return ""

    if isinstance(conversation, str):
        return conversation[-12000:]

    if not isinstance(conversation, list):
        return str(conversation)[-12000:]

    lines = []
    for item in conversation[-12:]:
        if not isinstance(item, dict):
            lines.append(str(item))
            continue

        role = item.get("role") or item.get("speaker") or "message"
        content = (
            item.get("content")
            or item.get("message")
            or item.get("text")
            or ""
        )
        if content:
            lines.append(f"{role}: {content}")

    return "\n".join(lines)[-12000:]


def _call_text(result):
    """Extract text from supported LLM return shapes."""
    if isinstance(result, str):
        return result.strip()

    if isinstance(result, dict):
        for key in ("text", "content", "response", "output"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    value = getattr(result, "text", None)
    if isinstance(value, str):
        return value.strip()

    return ""


async def select_agents(user, message, conversation=None):
    """
    Prefer deterministic routing for clear intents. The LLM planner is a
    fallback only for longer, genuinely multi-step requests that keyword
    routing cannot confidently classify.
    """
    intent_agents = _keyword_agents(message, conversation)

    if intent_agents:
        selected = list(intent_agents)
        dependencies = _dependency_fallback(message, selected)
        return selected, "Selected from the current request's explicit intent.", dependencies

    # Do not spend a planner call on ordinary conversation. The caller will
    # answer directly with one normal generation call (or the social fast path).
    lowered = (message or "").lower()
    # A long sentence is not automatically a multi-agent workflow.
    # In particular, ordinary personal sharing often contains conjunctions
    # such as "and" ("chocolate and black forest") but should not launch
    # Compass or Nova. Invoke the planner only when the message contains a
    # stronger workflow/action signal.
    likely_multi_step = (
        len((message or "").split()) >= 9
        and _matches_any(lowered, [
            r"\bthen\b",
            r"\btogether\b",
            r"\bworkflow\b",
            r"\bfrom\b.{1,80}\bto\b",
            r"\bhelp me (?:organize|organise|manage|prepare|build)\b",
            r"\b(?:first|next|after that)\b.{1,80}\b(?:create|write|plan|schedule|research|prepare)\b",
        ])
    )
    if not likely_multi_step:
        return [], "No specialist is needed for this conversational request.", []

    history = _conversation_text(conversation)
    planner_prompt = (
        f"Recent conversation (use only to resolve references):\n{history or '(none)'}\n\n"
        f"Current user request:\n{message}\n\n"
        "Select only the specialists required by the current request. "
        "Return the required JSON object only."
    )

    try:
        raw = await call_llm(
            system=ORCHESTRATOR_SYSTEM,
            prompt=planner_prompt,
            max_tokens=350,
        )
        parsed = _clean_json_response(_call_text(raw) or raw)
        selected = _normalise_agents(parsed.get("agents"))
        dependencies = _normalise_dependencies(parsed.get("dependencies"), selected)
        if not selected:
            return [], "No specialist is required.", []
        for dependency in _dependency_fallback(message, selected):
            pair = (dependency["from"], dependency["to"])
            if pair not in {(d["from"], d["to"]) for d in dependencies}:
                candidate = dependencies + [dependency]
                if not _has_cycle(selected, candidate):
                    dependencies.append(dependency)
        if _has_cycle(selected, dependencies):
            dependencies = _dependency_fallback(message, selected)
        return selected, str(parsed.get("reason") or "Selected for a multi-step request."), dependencies
    except Exception:
        logger.exception("Agent planning failed; using direct response fallback")
        return [], "Planner unavailable; answered directly.", []


def _get_tool_result(tool_call):
    if not isinstance(tool_call, dict):
        return {}

    result = tool_call.get("result")
    return result if isinstance(result, dict) else {}


def _tool_failed(tool_call):
    result = _get_tool_result(tool_call)

    if result.get("error"):
        return True

    status = str(result.get("search_status") or "").lower()
    return status in {"unavailable", "failed", "error", "invalid_query"}


def _tool_action_summary(tool_call):
    if not isinstance(tool_call, dict):
        return {}

    result = _get_tool_result(tool_call)
    name = tool_call.get("name") or tool_call.get("tool") or "unknown_tool"

    action = {
        "tool": name,
        "success": not _tool_failed(tool_call),
    }

    if result.get("error"):
        action["error"] = str(result["error"])

    if result.get("search_status"):
        action["search_status"] = result["search_status"]

    return action


def _research_sources_from_tool_calls(tool_calls):
    sources = []
    seen = set()

    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue

        name = str(call.get("name") or call.get("tool") or "")
        if name != "search_web" or _tool_failed(call):
            continue

        result = _get_tool_result(call)
        possible_items = []

        for key in ("results", "sources", "items", "data"):
            value = result.get(key)
            if isinstance(value, list):
                possible_items.extend(value)

        if isinstance(result, list):
            possible_items.extend(result)

        for item in possible_items:
            if not isinstance(item, dict):
                continue

            url = item.get("url") or item.get("link")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue

            seen.add(url)
            sources.append(
                {
                    "title": item.get("title") or url,
                    "url": url,
                    "snippet": item.get("snippet") or item.get("description") or "",
                }
            )

    return sources


def _append_research_sources(text, sources):
    if not sources:
        return text

    existing = set(re.findall(r"https?://\S+", text or ""))
    missing = [source for source in sources if source["url"] not in existing]

    if not missing:
        return text

    lines = ["", "Sources:"]
    for source in missing:
        title = str(source.get("title") or source["url"]).replace("\n", " ")
        lines.append(f"- {title}: {source['url']}")

    return (text or "").rstrip() + "\n" + "\n".join(lines)


def _build_collaboration_packet(results):
    packet = []

    for result in results or []:
        if not isinstance(result, dict):
            continue

        packet.append(
            {
                "agent": result.get("agent", "unknown"),
                "text": result.get("text", ""),
                "actions": result.get("actions", []),
                "tool_calls": result.get("tool_calls", []),
            }
        )

    return packet


def _build_collaboration_context(previous_results, dependencies, agent_name):
    if not previous_results:
        return ""

    previous_by_name = {
        item.get("agent"): item
        for item in previous_results
        if isinstance(item, dict)
    }

    required_sources = [
        item["from"]
        for item in dependencies
        if item.get("to") == agent_name
    ]

    # Share upstream output only when the plan explicitly declares a
    # dependency. Merely running after another agent is not a dependency.
    if not required_sources:
        return ""
    chosen_names = required_sources

    sections = []
    for name in chosen_names:
        item = previous_by_name.get(name)
        if not item:
            continue

        sections.append(
            f"Output from {name}:\n{item.get('text', '')}"
        )

    if not sections:
        return ""

    return (
        "COLLABORATION CONTEXT\n"
        "The following are outputs from earlier specialists. Use them when "
        "relevant, verify claims where possible, and do not present an earlier "
        "agent's unverified claims as independently confirmed facts.\n\n"
        + "\n\n".join(sections)
    )



# ---------------------------------------------------------------------------
# Echo - conversation continuity
#
# Mission Control stores every turn, but the orchestrator used to hand the model
# only the latest message, so the user had to restate the topic each time. Echo
# (and Mission Control's own conversational answer) now receive the prior turns.
# ---------------------------------------------------------------------------

_HISTORY_TURNS = 10
_HISTORY_CHARS_PER_TURN = 700


def _history_before_current(conversation, message):
    """Earlier turns (oldest first) as 'User:' / 'Assistant:' lines.

    The API passes the just-saved user message as the last item of
    `conversation`; that turn is the one being answered, so it is left out.
    """
    if isinstance(conversation, str):
        return conversation.strip()[-4000:]
    if not isinstance(conversation, list):
        return ""

    items = list(conversation)
    if items and isinstance(items[-1], dict):
        last = items[-1]
        last_text = str(last.get("content") or last.get("message") or last.get("text") or "").strip()
        if str(last.get("role") or "").lower() == "user" and last_text == (message or "").strip():
            items = items[:-1]

    lines = []
    for item in items[-_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or item.get("message") or item.get("text") or "").strip()
        if not content:
            continue
        if len(content) > _HISTORY_CHARS_PER_TURN:
            content = content[:_HISTORY_CHARS_PER_TURN].rstrip() + "…"
        label = "User" if str(item.get("role") or "").lower() == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _with_history(prompt, history):
    if not history:
        return prompt
    return (
        "Conversation so far (oldest first). Use it to understand what the user is "
        "referring to (\"it\", \"that\", \"the other one\", a short reply). Never ask "
        "them to repeat the topic.\n\n"
        f"{history}\n\nLatest message:\n{prompt}"
    )


def _echo_retrieval_query(message, history):
    """A short follow-up ("what about the second one?") has no topic of its own,
    so Echo's memory search also uses the user's last turns."""
    if not history or len((message or "").split()) >= 8:
        return message
    user_turns = [line[len("User: "):] for line in history.splitlines() if line.startswith("User: ")]
    return " ".join([*user_turns[-2:], message or ""]).strip()[:600]


# ---------------------------------------------------------------------------
# Echo - live preference learning
#
# After every Mission Control message Echo reads the latest message (with the
# recent conversation, so "no, the other one" or "too spicy" can be resolved) and
# records the user's preferences:
#   original - a like / preference / habit stated for the first time
#   changed  - the user changes or reverses an earlier preference
#   disliked - something the user dislikes, avoids or rejects
# It runs after the reply has been produced, so it never slows the chat down.
# ---------------------------------------------------------------------------

_PREFERENCE_SIGNALS = [
    r"\bprefer(?:s|red|ence|ences)?\b", r"\bfavou?rites?\b",
    r"\b(?:love|loves|like|likes|enjoy|enjoys|adore|adores)\b",
    r"\b(?:hate|hates|dislike|dislikes|despise|detest|avoid)\b",
    r"\b(?:can['’]?t|cannot)\s+stand\b", r"\bnot\s+(?:really\s+)?(?:a\s+fan|into|keen)\b",
    r"\b(?:sick|tired)\s+of\b", r"\brather\b", r"\binstead\b",
    r"\bchanged?\s+my\s+mind\b", r"\bno\s+longer\b", r"\bany\s?more\b",
    r"\bfrom\s+now\s+on\b", r"\bswitch(?:ed|ing)?\s+(?:to|from)\b",
    r"\b(?:always|usually|never)\b", r"\bdon['’]?t\s+(?:like|want|enjoy)\b",
    r"\btoo\s+\w+", r"\bnot\s+(?:my|for\s+me)\b",
    r"\bworks?\s+(?:better|best)\s+for\s+me\b", r"\bsuits?\s+me\b",
]

# Short replies that accept / reject something the assistant just proposed.
_SHORT_REPLY_PATTERNS = [
    r"^\s*(?:yes|yeah|yep|yup|sure|perfect|exactly|nope|no|nah|not really)\b",
    r"^\s*(?:that|this|it)\s+(?:works|sounds|is)\b",
    r"^\s*(?:go|going)\s+with\b",
    r"^\s*(?:i['’]ll|i\s+will|let['’]s)\s+(?:take|go\s+with|use)\b",
    r"\bthe\s+(?:first|second|third|last|other)\s+one\b",
]

_PREFERENCE_SYSTEM = (
    "You are Echo, the memory agent of IntelliTwin. Read the conversation and the "
    "user's LATEST message, and find the personal preferences the USER expresses in "
    "that latest message.\n\n"
    "Kinds:\n"
    "- original: a like, preference, habit, favourite or way of working the user states.\n"
    "- changed: the user changes or reverses an earlier preference (\"actually I prefer "
    "tea now\", \"I no longer like...\", \"from now on...\", or switches from one choice "
    "to another). Put what it replaced in \"previous\" when known.\n"
    "- disliked: something the user dislikes, avoids or rejects, including rejecting "
    "something the assistant suggested (\"too spicy\", \"no, not mornings\").\n\n"
    "Rules:\n"
    "- Use earlier turns only to work out what the latest message refers to (\"it\", "
    "\"yes\", \"the second one\", \"too long\"). Do not record preferences that appear "
    "only in earlier turns.\n"
    "- Record only the user's own preferences. An assistant suggestion counts only if "
    "the user clearly accepts or rejects it in the latest message.\n"
    "- Ignore questions, requests, one-off task details, hypotheticals, jokes and "
    "other people's preferences.\n"
    "- Never include passwords, keys, card or ID numbers.\n"
    "- At most 3 items. If there is nothing, return an empty list.\n\n"
    "Return ONLY this JSON, no other text:\n"
    '{"preferences": [{"kind": "original|changed|disliked", '
    '"subject": "short topic, e.g. tea", '
    '"previous": "what it replaced (changed only) or empty string", '
    '"statement": "one sentence in third person starting with The user"}]}'
)

_NEG_POLARITY = re.compile(
    r"\b(?:dislikes?|hates?|avoids?|despises?|no longer|not a fan|can['’]?t stand|cannot stand|"
    r"(?:doesn['’]?t|does not|don['’]?t|do not) (?:like|want|enjoy))\b",
    re.I,
)
_POS_POLARITY = re.compile(r"\b(?:prefers?|likes?|loves?|enjoys?|adores?|favou?rites?|fan of)\b", re.I)

_BACKGROUND_TASKS: set = set()


def _spawn_background(coro):
    """Run a coroutine after the reply is sent, keeping a reference so it is not garbage collected."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


def _polarity(text):
    if _NEG_POLARITY.search(text or ""):
        return -1
    if _POS_POLARITY.search(text or ""):
        return 1
    return 0


def _preference_sentence(kind, subject, previous=""):
    if kind == "disliked":
        return f"The user dislikes {subject}."
    if kind == "changed":
        if previous:
            return f"The user now prefers {subject} instead of {previous}."
        return f"The user now prefers {subject}."
    return f"The user prefers {subject}."


def _clean_preference(item):
    """Validate one preference returned by the model; None if unusable."""
    if not isinstance(item, dict):
        return None
    kind = str(item.get("kind") or item.get("type") or "").strip().lower()
    kind = {"new": "original", "like": "original", "liked": "original", "preference": "original",
            "change": "changed", "updated": "changed", "dislike": "disliked", "avoid": "disliked"}.get(kind, kind)
    if kind not in {"original", "changed", "disliked"}:
        return None

    subject = " ".join(str(item.get("subject") or "").split())[:80]
    previous = " ".join(str(item.get("previous") or "").split())[:80]
    statement = " ".join(str(item.get("statement") or "").split())[:300]
    if not statement.lower().startswith("the user"):
        statement = _preference_sentence(kind, subject, previous) if subject else ""
    if not statement:
        return None

    return {
        "kind": kind,
        "subject": subject,
        "previous": previous if kind == "changed" else "",
        "statement": statement,
        "title": statement[len("The user "):].strip(" .")[:80].capitalize() or "Preference",
        "importance": 3 if kind == "original" else 4,
    }


def _parse_preference_items(raw):
    """List of raw items from the model's reply; None when the reply is not usable JSON."""
    text = (raw or "").strip()
    parsed = _clean_json_response(text)
    items = parsed.get("preferences") if parsed else None
    if items is None:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                items = json.loads(match.group(0))
            except json.JSONDecodeError:
                items = None
    if items is None and parsed and parsed.get("kind"):
        items = [parsed]
    return items if isinstance(items, list) else None


_OBJ = r"(?P<o>[^.!?;\n]{2,80}?)"
_END = r"(?=[.!?;\n,]|\s+(?:but|because|since|so|and\s+i)\b|$)"


def _rule_based_preferences(message):
    """Safety net for when the model is unavailable or returns unusable output:
    only explicit first-person statements are recognised."""
    text = " ".join((message or "").split())
    found = []

    def add(kind, subject, previous="", statement=None):
        subject = subject.strip(" ,")
        if not subject:
            return
        pref = _clean_preference({
            "kind": kind, "subject": subject, "previous": previous.strip(" ,"),
            "statement": statement or _preference_sentence(kind, subject, previous.strip(" ,")),
        })
        if pref:
            found.append(pref)

    m = re.search(rf"\b(?:actually|now|these days|from now on)[, ]+i\s+(?:now\s+)?(?:prefer|like|love|want|use)\s+{_OBJ}"
                  rf"(?:\s+(?:instead\s+of|rather\s+than|over)\s+(?P<p>[^.!?;\n]{{2,60}}?))?{_END}", text, re.I)
    if m:
        add("changed", m.group("o"), m.group("p") or "")

    m = re.search(rf"\bi\s+(?:no\s+longer|(?:don['’]?t|do\s+not)\s+(?:like|want|enjoy|use))\s+{_OBJ}\s+(?:any\s?more)\b", text, re.I) \
        or re.search(rf"\bi\s+no\s+longer\s+(?:like|want|enjoy|use)\s+{_OBJ}{_END}", text, re.I)
    if m:
        add("changed", m.group("o"), statement=f"The user no longer likes {m.group('o').strip(' ,')}.")

    m = re.search(rf"\bi\s+(?:really\s+|absolutely\s+)?(?:hate|dislike|despise|can['’]?t\s+stand|cannot\s+stand|"
                  rf"(?:don['’]?t|do\s+not)\s+like|am\s+not\s+a\s+fan\s+of|avoid)\s+{_OBJ}{_END}", text, re.I)
    if m and not any(p["kind"] == "changed" for p in found):
        add("disliked", m.group("o"))

    m = re.search(rf"\bi\s+(?:really\s+|absolutely\s+)?(?:prefer|love|like|enjoy|adore)\s+{_OBJ}{_END}", text, re.I)
    if m and not found:
        add("original", m.group("o"))

    return found[:3]


def _worth_observing(text, history):
    """Cheap gate so ordinary messages never cost an extra model call."""
    if not text or _is_simple_social_message(text) or _is_direct_memory_recall_request(text):
        return False
    if _matches_any(text, _PREFERENCE_SIGNALS):
        return True
    return bool(history) and len(text.split()) <= 14 and _matches_any(text, _SHORT_REPLY_PATTERNS)


async def _echo_retire_outdated(user, new_entry, pref):
    """Mark older preferences that the new one replaces or contradicts as superseded
    (kept for history, excluded from retrieval) - e.g. 'likes tea' once the user
    says they now prefer coffee, or 'dislikes X' once they say they like X."""
    from bson import ObjectId
    from app.memory import echo as echo_agent

    new_id = str(new_entry.get("_id") or "")
    if not new_id:
        return 0

    new_polarity = _polarity(new_entry.get("content") or pref["statement"])
    targets = []
    if pref["kind"] == "changed" and pref.get("previous"):
        targets.append((pref["previous"], 1))
    if pref.get("subject") and new_polarity:
        targets.append((pref["subject"], -new_polarity))

    retired, seen = 0, set()
    for needle, wanted in targets:
        pattern = re.compile(rf"(?<!\w){re.escape(needle.lower())}(?!\w)")
        for old in await echo_agent.search_memory(user, needle, limit=10):
            old_id = str(old.get("_id") or "")
            content = str(old.get("content") or "")
            if not old_id or old_id == new_id or old_id in seen:
                continue
            if not pattern.search(content.lower()) or _polarity(content) != wanted:
                continue
            seen.add(old_id)
            if await echo_agent._supersede_memory(user, {"_id": ObjectId(old_id)}, ObjectId(new_id)):
                retired += 1
    return retired


async def echo_observe_preferences(user, message, conversation=None):
    """Read the latest Mission Control message and record the user's preferences
    (original, changed or disliked) in Echo's memory. Returns the saved entries."""
    from app.memory import echo as echo_agent
    from app.memory.safety import contains_secret

    text = (message or "").strip()[:1500]
    history = _history_before_current(conversation, message)
    if not _worth_observing(text, history) or contains_secret(text):
        return []

    prompt = (
        (f"Earlier conversation:\n{history}\n\n" if history else "")
        + f"LATEST user message:\n{text}"
    )
    items = None
    try:
        raw = _call_text(await call_llm(system=_PREFERENCE_SYSTEM, prompt=prompt, max_tokens=400))
        if not raw.startswith(("[LLM request failed:", "[offline placeholder response")):
            items = _parse_preference_items(raw)
    except Exception:
        logger.exception("Echo preference extraction failed")

    if items is not None:
        prefs = [p for p in (_clean_preference(item) for item in items) if p][:3]
    else:
        prefs = _rule_based_preferences(text)

    saved = []
    for pref in prefs:
        try:
            entry = await echo_agent.remember(
                user,
                note=pref["statement"],
                title=pref["title"],
                source_interaction=text,
                importance=pref["importance"],
            )
            if entry:
                saved.append(entry)
                await _echo_retire_outdated(user, entry, pref)
        except Exception:
            logger.exception("Echo could not record a %s preference", pref["kind"])

    if saved:
        logger.info("Echo recorded %d preference(s) from Mission Control chat", len(saved))
    return saved


_PERSIST_INTENT = re.compile(
    r"\b(schedule|add\s+(?:it\s+)?to\s+(?:my\s+)?calendar|create\s+(?:a\s+|an\s+|my\s+)?(?:new\s+)?"
    r"(?:task|goal|note|document|doc|event|meeting|project)|save\s+(?:this|it|that)|remind\s+me|"
    r"(?:make|write|draft)\s+(?:a\s+|an\s+)?(?:document|note)|add\s+(?:a\s+)?(?:task|goal|note))\b",
    re.I,
)
_WRITE_TOOLS = {
    "workspace_crud", "create_task", "update_task", "create_goal", "update_goal", "create_schedule",
    "create_document", "update_document", "save_research", "link_research_to_goal", "save_memory",
    "update_memory", "delete_memory", "restore_memory",
}
_CLAIM_WORDS = re.compile(
    r"\b(i(?:'ve| have)?\s+(?:scheduled|created|added|saved|updated|set|booked)|has been (?:scheduled|created|added|saved)|"
    r"(?:successfully|now)\s+(?:scheduled|created|added|saved)|is (?:now )?(?:scheduled|saved))\b",
    re.I,
)


async def _verify_claimed_writes(user, agent_name, message, text, tool_calls):
    """Never let an agent tell the user something was saved when no write
    tool actually succeeded. For Nova, save the generated content so the
    request is still fulfilled; for others, correct the record."""
    if not _PERSIST_INTENT.search(message or ""):
        return text
    succeeded = [
        c for c in tool_calls
        if isinstance(c, dict) and (c.get("name") or c.get("tool")) in _WRITE_TOOLS and not _tool_failed(c)
    ]
    if succeeded:
        return text

    if agent_name == "nova" and text and len(text) > 40 and re.search(r"\b(document|doc|note|save)\b", message, re.I):
        try:
            from app.tools.workspace_universal import _run as workspace_crud
            title = re.sub(r"\s+", " ", re.sub(r"(?i)^(please\s+)?(can you\s+)?(write|draft|create|make|save)\s+(me\s+)?(a|an|the)?\s*", "", message)).strip(" .?!")[:70] or "Nova draft"
            as_note = bool(re.search(r"\bnote\b", message, re.I)) and not re.search(r"\bdocument|doc\b", message, re.I)
            module, body_key = ("notes", "body") if as_note else ("documents", "content")
            saved = await workspace_crud(user, {
                "module": module, "action": "create", "agent": "nova",
                "data": {"title": title.capitalize(), body_key: text},
            })
            if not saved.get("error"):
                tool_calls.append({"name": "workspace_crud", "input": {"module": module}, "result": saved})
                return f"{text}\n\n✅ Saved to your {module} as “{title.capitalize()}”."
        except Exception:
            logger.exception("Nova auto-save fallback failed")

    if _CLAIM_WORDS.search(text or "") or agent_name in {"compass", "nova"}:
        return (
            f"{(text or '').rstrip()}\n\n⚠️ Nothing was actually saved to your workspace by this step. "
            "Tell me the exact details (for example the title and date/time) and I'll add it."
        ).strip()
    return text


async def run_specialist(user, agent_name, message, collaboration_context=None, conversation=None):
    if agent_name not in AGENT_NAMES:
        raise ValueError(f"Unknown agent: {agent_name}")

    set_user_tz(user)
    persona = AGENT_PERSONAS[agent_name]
    # Only Echo is given the earlier turns; the other specialists are unchanged.
    history = _history_before_current(conversation, message) if agent_name == "echo" else ""

    context_started = time.perf_counter()
    context, trace = await with_context(
        user,
        persona,
        query=_echo_retrieval_query(message, history) if history else message,
        include_workspace_activity=_needs_workspace_snapshot(message),
        include_user_model=(agent_name == "echo" or _needs_personal_context(message)),
    )
    logger.info(
        "Context built for %s in %.3fs (memory=%s, workspace=%s)",
        agent_name, time.perf_counter() - context_started,
        agent_name == "echo" or _needs_personal_context(message),
        _needs_workspace_snapshot(message),
    )

    from app.workspace_actions import _now_context

    system_parts = [persona, _now_context(user), str(context or "")]

    if collaboration_context:
        system_parts.append(collaboration_context)

    if agent_name == "atlas":
        system_parts.append(
            """
Research execution requirements:
- Use the available web-search tool for current or source-dependent research.
- Do not claim you searched the web if you did not call the search tool.
- Prefer evidence over unsupported assertions.
- Include source URLs when the tool returns them.
- If search fails or returns no usable results, state that limitation clearly.
- Never invent URLs, article titles, or source details.
"""
        )

    elif agent_name == "nova":
        system_parts.append(
            """
Creation requirements:
- Use upstream research or context when provided.
- Follow the requested format, audience, and level of detail.
- Use workspace tools if the user asks you to save or update a document.
- Report the outcome of workspace operations accurately.
"""
        )

    elif agent_name == "compass":
        system_parts.append(
            """
Planning requirements:
- Inspect relevant workspace data before creating items when possible.
- Break complex work into practical, ordered steps.
- Use available tools for requested goal, task, or calendar operations.
- Respect the user's dates and times. Never invent a time the user did not provide.
- Clearly identify missing information that prevents an operation.
- Do not claim an operation succeeded unless a tool confirms it.
"""
        )

    elif agent_name == "echo":
        system_parts.append(
            """
Memory requirements:
- Use stored memory and available context to answer personal-context questions.
- Do not convert every chat message into a persistent memory.
- Do not invent remembered preferences or personal history.
- Save or forget information only through the appropriate available tool.
- Distinguish what is actually remembered from what is inferred.
- Preferences the user states in chat are recorded automatically; do not ask the user to repeat them.
- Use the conversation so far to understand follow-ups; never ask the user to restate the topic.
"""
        )

    system = "\n\n".join(part for part in system_parts if part)

    prompt = (
        f"User request:\n{message}\n\n"
        f"Your assigned role is {agent_name}. Fulfill the parts of the request "
        "that belong to your role. Use the available tools when needed. "
        "Be explicit about completed actions and any limitations."
    )
    prompt = _with_history(prompt, history)

    result = await call_llm_with_tools(
        system=system,
        prompt=prompt,
        tools=AGENT_TOOLS[agent_name],
        user=user,
        max_tokens=3200 if agent_name == "atlas" else 1800,
        max_turns=6 if agent_name == "atlas" else 3,
    )

    if isinstance(result, dict):
        text = _call_text(result)
        tool_calls = result.get("tool_calls") or []
        trace = result.get("trace") or []
    else:
        text = _call_text(result)
        tool_calls = getattr(result, "tool_calls", []) or []
        trace = getattr(result, "trace", []) or []

    actions = [
        summary
        for summary in (_tool_action_summary(call) for call in tool_calls)
        if summary
    ]

    if agent_name == "atlas":
        sources = _research_sources_from_tool_calls(tool_calls)
        text = _append_research_sources(text, sources)

        search_calls = [
            call
            for call in tool_calls
            if isinstance(call, dict)
            and (call.get("name") or call.get("tool")) == "search_web"
        ]

        if search_calls and all(_tool_failed(call) for call in search_calls):
            warning = (
                "Research limitation: the available web-search operation failed. "
                "The response may be incomplete and should not be treated as "
                "verified current research."
            )
            text = f"{text.rstrip()}\n\n{warning}".strip()

    text = await _verify_claimed_writes(user, agent_name, message, text, tool_calls)

    return {
        "agent": agent_name,
        "text": text,
        "trace": trace,
        "tool_calls": tool_calls,
        "actions": actions,
    }


async def synthesize(user, message, specialist_results, conversation=None):
    if not specialist_results:
        try:
            result = await call_llm(
                system=(
                    "You are IntelliTwin Mission Control, a direct and helpful "
                    "assistant. Answer the user's request conversationally and "
                    "concisely. Give only information needed to answer the request. "
                    "Do not narrate internal processing, mention agents, or invent "
                    "memory/tool failures. Do not claim to have used tools or changed "
                    "workspace data unless that actually happened. Use the conversation "
                    "so far to resolve references; the user should never have to restate "
                    "what you are discussing."
                ),
                prompt=_with_history(message, _history_before_current(conversation, message)),
                max_tokens=1800,
            )
            text = _call_text(result)
            if text and not text.startswith(("[LLM request failed:", "[offline placeholder response")):
                return text
            if text:
                logger.warning("Direct response generation failed or is offline")
        except Exception:
            pass

        return (
            "I'm having trouble generating a response right now. "
            "Please try again shortly."
        )

    sections = []
    has_research = False

    for result in specialist_results:
        agent = result.get("agent", "unknown")
        text = result.get("text", "")
        sections.append(f"{agent.upper()} RESULT:\n{text}")

        if agent == "atlas":
            has_research = True

    synthesis_system = """
You are IntelliTwin Mission Control, responsible for presenting the results
from collaborating specialists as one coherent response.

Requirements:
- Answer the user's original request, not just summarize the agents.
- Combine complementary results and remove repetition.
- Preserve important details, steps, dates, and limitations.
- Never claim that a workspace action succeeded unless the specialist result
  reports that it succeeded.
- If a specialist failed or could not complete an operation, say so clearly.
- Do not invent results, completed actions, sources, or facts.
- Keep the response structured and practical.
"""

    synthesis_prompt = (
        f"Original user request:\n{message}\n\n"
        "Specialist outputs:\n\n"
        + "\n\n".join(sections)
        + "\n\nProduce one coherent final answer for the user."
    )

    try:
        result = await call_llm(
            system=synthesis_system,
            prompt=synthesis_prompt,
            max_tokens=4000 if has_research else 2200,
        )
        text = _call_text(result)
        if text and not text.startswith(("[LLM request failed:", "[offline placeholder response")):
            return text
        if text:
            logger.warning("Synthesis generation failed or is offline")
    except Exception:
        logger.exception("Synthesis generation failed")

    # Fallback: retain all specialist outputs instead of losing work when
    # the final synthesis call fails.
    return "\n\n".join(sections)


async def orchestrate(user, message, conversation=None):
    """Mission Control entry point: answer the request, then let Echo learn from it."""
    result = await _orchestrate(user, message, conversation)

    try:
        actions = result.get("actions") or []
        # If Echo already saved or edited a memory on this turn (an explicit
        # "remember ..." request), do not record the same message a second time.
        echo_saved = any(
            isinstance(a, dict) and a.get("tool") in {"save_memory", "update_memory"} and a.get("success")
            for a in actions
        )
        if not echo_saved and _worth_observing(
            (message or "").strip(), _history_before_current(conversation, message)
        ):
            _spawn_background(echo_observe_preferences(user, message, conversation))
    except Exception:
        logger.exception("Could not schedule Echo preference observation")

    return result


async def _orchestrate(user, message, conversation=None):
    """Run a minimal path for simple requests and a dependency-aware path for tasks."""
    started = time.perf_counter()
    clean_message = (message or "").strip()

    # Zero-LLM fast path: a greeting must never start the planner, Echo,
    # context retrieval, or synthesis.
    if _is_simple_social_message(clean_message):
        return {
            "message": _social_reply(clean_message),
            "agents": [],
            "planned_agents": [],
            "reason": "Simple conversational fast path.",
            "dependencies": [],
            "actions": [],
        }

    # Direct memory recall: do not invoke the LLM tool loop for questions whose
    # answer is already present in Echo's database. This prevents raw tool JSON,
    # similarity scores, and multi-turn tool latency from leaking to the user.
    if _is_direct_memory_recall_request(clean_message):
        try:
            result = await _answer_memory_recall(user, clean_message)
            logger.info("Mission Control memory fast path completed in %.3fs", time.perf_counter() - started)
            return result
        except Exception:
            logger.exception("Direct memory recall failed")
            return {
                "message": "I couldn't retrieve saved memories right now. Please try again shortly.",
                "agents": ["echo"],
                "planned_agents": ["echo"],
                "reason": "Direct memory retrieval failed.",
                "dependencies": [],
                "actions": [{"tool": "search_memory", "success": False}],
            }

    # Explicit workspace snapshot requests map directly to the read-only tool.
    # No planner, memory vector search, specialist generation, or synthesis is
    # needed to return data that already exists in the workspace.
    if _is_explicit_workspace_context_request(clean_message):
        try:
            tool_result = await GET_WORKSPACE_CONTEXT.handler(user, {"query": ""})
            if tool_result.get("error"):
                logger.warning("Workspace context tool returned an error")
                return {
                    "message": "I couldn't load your workspace context right now. Please try again shortly.",
                    "agents": ["echo"],
                    "planned_agents": ["echo"],
                    "reason": "Workspace context retrieval failed.",
                    "dependencies": [],
                    "actions": [{"tool": "get_workspace_context", "success": False}],
                }
            context_text = str(tool_result.get("context") or "").strip()
            if not context_text:
                context_text = "Your workspace has no context to show yet."
            return {
                "message": "Here's your workspace context:\n\n" + context_text[:10000],
                "agents": ["echo"],
                "planned_agents": ["echo"],
                "reason": "Direct read-only workspace context retrieval.",
                "dependencies": [],
                "actions": [{"tool": "get_workspace_context", "success": True}],
            }
        except Exception:
            logger.exception("Direct workspace context retrieval failed")
            return {
                "message": "I couldn't load your workspace context right now. Please try again shortly.",
                "agents": ["echo"],
                "planned_agents": ["echo"],
                "reason": "Workspace context retrieval failed.",
                "dependencies": [],
                "actions": [{"tool": "get_workspace_context", "success": False}],
            }

    # Workspace operations (schedule a meeting, add/complete a task, create a
    # goal/note/project, "what's on my calendar?") are executed by code and
    # verified against the database - never left to a small model's tool
    # calling, and never reported as done unless they actually were.
    set_user_tz(user)

    # Long-form document requests ("write a detailed report on X and save it
    # as Y") use the section-by-section pipeline, which saves and verifies a
    # real document before claiming success.
    from app.doc_generation import extract_report_request, generate_and_save_report

    report_request = extract_report_request(clean_message)
    if report_request:
        try:
            outcome = await generate_and_save_report(user, report_request)
        except Exception:
            logger.exception("Report generation failed")
            outcome = {"ok": False, "message": "Something went wrong while writing the report, so nothing was saved."}
        return {
            "message": outcome["message"],
            "agents": ["nova"],
            "planned_agents": ["nova"],
            "reason": "Detailed document generated section by section and verified in the database.",
            "dependencies": [],
            "actions": [{"tool": "create_document", "success": bool(outcome.get("ok"))}],
        }

    try:
        direct = await try_direct_workspace_action(user, clean_message, conversation)
    except Exception:
        logger.exception("Direct workspace action failed; falling back to agents")
        direct = None
    if direct is not None:
        logger.info("Mission Control workspace action completed in %.3fs", time.perf_counter() - started)
        return direct

    selected_agents, reason, dependencies = await select_agents(
        user, clean_message, conversation
    )

    if not selected_agents:
        final_message = await synthesize(user, clean_message, [], conversation)
        logger.info(
            "Mission Control request completed via direct path in %.3fs (agents=0)",
            time.perf_counter() - started,
        )
        return {
            "message": final_message,
            "agents": [],
            "planned_agents": [],
            "reason": reason,
            "dependencies": [],
            "actions": [],
        }

    effective_dependencies = _filter_dependencies_for_order(
        selected_agents, dependencies
    )
    remaining = set(selected_agents)
    completed: dict[str, dict] = {}
    all_actions: list[dict] = []

    # Execute independent agents concurrently; agents with dependencies only
    # start after their prerequisite results are available.
    while remaining:
        ready = [
            agent for agent in selected_agents
            if agent in remaining and all(
                dep["from"] in completed
                for dep in effective_dependencies if dep.get("to") == agent
            )
        ]
        if not ready:  # Defensive fallback for an invalid/cyclic plan.
            ready = [next(agent for agent in selected_agents if agent in remaining)]

        async def _run_one(agent_name):
            context = _build_collaboration_context(
                list(completed.values()), effective_dependencies, agent_name
            )
            try:
                return await run_specialist(
                    user, agent_name, clean_message, collaboration_context=context,
                    conversation=conversation if agent_name == "echo" else None,
                )
            except Exception:
                logger.exception("Specialist %s failed", agent_name)
                return {
                    "agent": agent_name,
                    "text": "I couldn't complete that part of the request. Please try again, or narrow the request to one step.",
                    "trace": [],
                    "tool_calls": [],
                    "actions": [{"tool": "agent_execution", "success": False}],
                }

        batch = await asyncio.gather(*[_run_one(agent) for agent in ready])
        for agent_name, result in zip(ready, batch):
            # Do not pass raw provider exception strings to synthesis.
            text = str(result.get("text") or "").strip()
            if text.startswith("[LLM request failed:") or text.startswith("[offline placeholder response"):
                logger.warning("Specialist %s returned a provider/configuration failure", agent_name)
                result["text"] = "The language model is temporarily unavailable or not configured. No action was confirmed."
            completed[agent_name] = result
            all_actions.extend(result.get("actions", []))
            remaining.remove(agent_name)

    specialist_results = [completed[agent] for agent in selected_agents if agent in completed]
    # One specialist already returns a final answer; another model call is
    # only justified when we actually need to combine multiple outputs.
    if len(specialist_results) == 1:
        final_message = specialist_results[0].get("text", "").strip() or "I couldn't produce a response right now. Please try again."
    else:
        final_message = await synthesize(user, clean_message, specialist_results)

    logger.info(
        "Mission Control request completed in %.3fs (agents=%s, dependencies=%d)",
        time.perf_counter() - started, selected_agents, len(effective_dependencies),
    )
    return {
        "message": final_message,
        "agents": selected_agents,
        "planned_agents": selected_agents,
        "reason": reason,
        "dependencies": effective_dependencies,
        "actions": all_actions,
    }

