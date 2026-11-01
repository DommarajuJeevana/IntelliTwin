"""
Phase 7 - explainability: 'Nova created this using your previous research
and your preferred writing style.'

`ContextTrace` records what with_context() (app/routers/agents.py) actually
found and included for a given call - which profile fields, which memories.
`explain()` combines that with what call_llm_with_tools() actually did
(app/llm.py's AgentRunResult.tool_calls) into one human-readable sentence,
so every agent response can say *why* it looks the way it does instead of
being a black box. This is deliberately just a plain-language summary, not
a full trace viewer - the goal is a one-line "here's what I used", not a
debugger.
"""
from dataclasses import dataclass, field


@dataclass
class ContextTrace:
    used_profile: bool = False
    memory_titles: list[str] = field(default_factory=list)


_READABLE_TOOL_NAMES = {
    "search_web": "searched the web",
    "search_documents": "searched your documents",
    "search_memory": "searched your memories",
    "save_research": "saved research",
    "link_research_to_goal": "linked research to a goal",
    "read_goal": "read a goal",
    "read_calendar": "checked your calendar",
    "create_task": "created tasks",
    "create_schedule": "scheduled an event",
    "update_goal": "updated a goal",
    "read_research": "read past research",
    "read_documents": "read a past document",
    "create_document": "created a document",
    "update_document": "updated a document",
    "save_memory": "saved a memory",
    "update_memory": "updated a memory",
    "delete_memory": "deleted a memory",
}


def explain(agent_name: str, trace: ContextTrace, tool_calls: list[dict] | None = None) -> str:
    """One sentence: what context this agent drew on and what it actually
    did with its tools. Skips failed tool calls (result has an "error" key)
    since those aren't part of what shaped the answer."""
    clauses = []

    if trace.memory_titles:
        titles = ", ".join(f'"{t}"' for t in trace.memory_titles[:3])
        clauses.append(f"{len(trace.memory_titles)} relevant memor{'y' if len(trace.memory_titles) == 1 else 'ies'} ({titles})")
    if trace.used_profile:
        clauses.append("your profile")

    used_str = f"Used {' and '.join(clauses)}. " if clauses else ""

    action_names = []
    for call in tool_calls or []:
        result = call.get("result")
        if isinstance(result, dict) and result.get("error"):
            continue
        label = _READABLE_TOOL_NAMES.get(call["name"], call["name"])
        if label not in action_names:
            action_names.append(label)

    if action_names:
        did_str = f"{agent_name} {', '.join(action_names[:-1]) + ' and ' + action_names[-1] if len(action_names) > 1 else action_names[0]}."
    else:
        did_str = f"{agent_name} answered directly, without using any tools."

    if not clauses and not action_names:
        return f"{agent_name} answered from the prompt alone - no stored memories or tools were relevant here."

    return (used_str + did_str).strip()
