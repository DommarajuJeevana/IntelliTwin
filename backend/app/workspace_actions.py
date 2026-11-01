"""
Direct workspace actions for Mission Control.

Why this exists
---------------
Small local models (llama3.2 via Ollama) are unreliable at *tool calling*:
they send wrong argument types, pick the wrong tool, or skip the tool and just
say "Done, your meeting is scheduled!" - which is exactly how Mission Control
ended up reporting a meeting that never reached the calendar.

For ordinary workspace operations (schedule an event, add/complete a task,
create a goal/note/project, rename or delete something, "what's on my
calendar?") we therefore do NOT rely on the model to call tools. Instead:

  1. One plain LLM call turns the request into a small JSON "operation list"
     (no tool-calling needed - JSON output is something even small models do
     well).
  2. This module validates the operations and executes them through the same
     `workspace_crud` code path the UI/API uses (conflict checks, reminders,
     task<->calendar sync, embeddings).
  3. The reply is built from what the database actually returned. The model
     never gets to claim a success that did not happen.

If the request is not a workspace operation (or the JSON can't be parsed), this
returns None and the normal agent pipeline handles it.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from app.llm import call_llm
from app.owned import get_user_tz, parse_date, set_user_tz
from app.tools.workspace_universal import _id, _run as workspace_crud

logger = logging.getLogger("intellitwin.workspace_actions")

ACTION_MODULES = ("calendar", "tasks", "goals", "projects", "notes", "documents", "research")

# Words that mean "do something in the workspace".
_ACTION_VERBS = (
    r"schedule|reschedule|book|add|create|make|set\s*up|put|remind|new|log|save|"
    r"update|change|edit|rename|move|push|postpone|delay|append|"
    r"delete|remove|cancel|clear|drop|"
    r"mark|complete|finish|done|tick|check\s*off|"
    r"show|list|what(?:'s|\s+is|\s+are)?|which|do\s+i\s+have|any|open|view|see|read|tell\s+me|"
    r"fetch|get|give|summari[sz]e|summary|overview|explain|go\s+through|review|did\s+i\s+have"
)
_MODULE_NOUNS = (
    r"meetings?|events?|appointments?|calls?|calendar|schedule|reminders?|"
    r"tasks?|to[- ]?dos?|goals?|projects?|notes?|documents?|docs?|reports?|research|papers?"
)

# Things the specialist agents do better (research, long-form writing).
_AGENT_ONLY = [
    r"\bresearch\b", r"\blook\s+up\b", r"\bsearch\s+(?:the\s+)?(?:web|internet|online)\b",
    r"\binvestigat", r"\bcompare\b", r"\bpros\s+and\s+cons\b",
    r"\bwhat\s+do\s+(?:you|u)\s+(?:remember|know)\b",
]
_LONG_FORM = [
    r"\b(?:write|draft|compose|generate)\b.{0,40}\b(?:document|doc|note|report|essay|article|summary|proposal|email)\b",
    r"\bdocument\s+(?:about|on)\b", r"\bnote\s+(?:about|on)\b",
]

_DELETE_WORDS = re.compile(r"\b(delete|remove|cancel|clear|drop|get\s+rid)\b", re.I)
_DONE_WORDS = re.compile(r"\b(mark|complete|completed|finish|finished|done|tick|check\s*off)\b", re.I)


def _matches(text: str, patterns) -> bool:
    return any(re.search(p, text or "", re.I) for p in patterns)


def looks_like_workspace_action(message: str) -> bool:
    text = (message or "").strip()
    if len(text) < 4:
        return False
    if _matches(text, _AGENT_ONLY) or _matches(text, _LONG_FORM):
        return False
    return bool(
        re.search(rf"\b(?:{_ACTION_VERBS})\b", text, re.I)
        and re.search(rf"\b(?:{_MODULE_NOUNS})\b", text, re.I)
    )


# ------------------------------------------------------------------ prompt ----

def _now_context(user: dict) -> str:
    tz = get_user_tz(user)
    now = datetime.now(tz)
    tz_name = getattr(tz, "key", None) or now.tzname() or "local"
    return (
        f"Current local date/time: {now.strftime('%A, %Y-%m-%d %H:%M')} ({tz_name}). "
        f"Tomorrow is {(now + timedelta(days=1)).strftime('%A %Y-%m-%d')}."
    )


_EXTRACT_SYSTEM = """You convert a user's request about their workspace into JSON operations.
Return ONLY one JSON object, no markdown, no commentary:

{
  "operations": [
    {
      "module": "calendar" | "tasks" | "goals" | "projects" | "notes" | "documents" | "research",
      "action": "create" | "update" | "delete" | "list" | "read",
      "target": "title/keywords of the EXISTING item (for update/delete/read), else \\"\\"",
      "data": { ...fields... }
    }
  ],
  "question": "ask ONE short question here ONLY if a required detail is missing, else \\"\\""
}

Fields per module (use only these names):
- calendar: title, startsAt, endsAt, location, notes          (meetings, events, appointments, calls, reminders)
- tasks:    title, status(todo|in_progress|done), priority(low|medium|high), dueDate, scheduledStart, scheduledEnd, goal
- goals:    title, description, status(not_started|in_progress|done), progress(0-100), dueDate
- projects: name, description, status(planning|active|on_hold|complete|cancelled)
- notes:    title, body
- documents:title, content, type(brief|draft|summary|report|other), status(draft|final)
- research: (read/list only)

Rules:
- Dates/times: ISO 8601 local time without timezone, e.g. "2026-10-13T15:00:00". Resolve "tomorrow", "next Friday",
  "at 3pm" from the current date/time given. NEVER invent a time the user did not give: if a meeting/event has no
  time, leave startsAt out and put your question in "question".
- For update: put ONLY the changed fields in data, and the item's current title in target.
  Marking something done/completed = update with status "done".
- For list ("show/fetch/what do I have"): data may contain "status" and, ONLY for a specific title keyword, "query".
  Never put words like tasks, events, all, today, meetings in "query". For calendar list ALWAYS give "from" (start of the
  day/range, e.g. 2026-10-12T00:00:00) and "to" (end, e.g. 2026-10-12T23:59:59): "today", "on 12th oct", "this week", etc.
- For read ("read/open/summarize/explain the X document/note/report"): action "read", module = where it most likely lives
  (documents, notes or research), target = ONLY the distinctive title keywords (e.g. "astrology", "federated learning").
- Calendar/task titles must NOT contain dates or times ("Meeting", not "Meeting tomorrow at 2pm").
- Use the user's own wording for titles; keep them short. Do not add emojis.
- Never output delete unless the user clearly asked to delete/remove/cancel.
- If the request is NOT about creating/changing/listing workspace items, return {"operations": [], "question": ""}.
"""


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                value = json.loads(match.group(0))
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                pass
    return {}


# ---------------------------------------------------------------- helpers ----

_FIELD_ALIASES = {
    "calendar": {"start": "startsAt", "starts": "startsAt", "startTime": "startsAt", "start_time": "startsAt",
                 "date": "startsAt", "datetime": "startsAt", "end": "endsAt", "endTime": "endsAt",
                 "end_time": "endsAt", "name": "title", "description": "notes"},
    "tasks": {"name": "title", "task": "title", "task_name": "title", "taskName": "title",
              "label": "title", "summary": "title", "subject": "title", "goal_name": "goal",
              "goalTitle": "goal", "linked_goal": "goal", "due": "dueDate", "due_date": "dueDate", "start": "scheduledStart",
              "end": "scheduledEnd", "description": None},
    "goals": {"name": "title", "due": "dueDate", "due_date": "dueDate"},
    "projects": {"title": "name"},
    "notes": {"name": "title", "content": "body", "text": "body"},
    "documents": {"name": "title", "body": "content", "text": "content"},
    "research": {},
}
_ALLOWED = {
    "calendar": {"title", "startsAt", "endsAt", "location", "notes"},
    "tasks": {"title", "status", "priority", "dueDate", "scheduledStart", "scheduledEnd", "goal"},
    "goals": {"title", "description", "status", "progress", "dueDate"},
    "projects": {"name", "description", "status"},
    "notes": {"title", "body"},
    "documents": {"title", "content", "type", "status"},
    "research": {"query", "summary", "status"},
}
_STATUS_ALIASES = {
    "completed": "done", "complete": "done", "finished": "done", "pending": "todo", "open": "todo",
    "not started": "not_started", "in progress": "in_progress", "started": "in_progress",
    "paused": "on_hold", "on hold": "on_hold",
}
_ENUMS = {
    "tasks": {"status": {"todo", "in_progress", "done"}, "priority": {"low", "medium", "high"}},
    "goals": {"status": {"not_started", "in_progress", "done"}},
    "projects": {"status": {"planning", "active", "in_progress", "on_hold", "paused", "complete",
                            "completed", "cancelled"}},
    "documents": {"type": {"brief", "draft", "summary", "report", "other"}, "status": {"draft", "final"}},
}


def _clean_data(module: str, data: dict) -> dict:
    out: dict = {}
    aliases = _FIELD_ALIASES.get(module, {})
    allowed = _ALLOWED[module]
    for key, value in (data or {}).items():
        key = aliases.get(key, key)
        if key is None or key not in allowed or value in (None, ""):
            continue
        if key in ("status", "priority", "type") and isinstance(value, str):
            value = value.strip().lower()
            value = _STATUS_ALIASES.get(value, value).replace(" ", "_")
            if value not in _ENUMS.get(module, {}).get(key, {value}):
                continue
        if key == "progress":
            try:
                value = max(0, min(int(float(value)), 100))
            except (TypeError, ValueError):
                continue
        out[key] = value
    return out


def _fmt_dt(value, user) -> str:
    dt = parse_date(value) if not isinstance(value, datetime) else value
    if not dt:
        return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(get_user_tz(user))
    return local.strftime("%a %d %b %Y, %I:%M %p").replace(" 0", " ")


def _label(module: str, item: dict) -> str:
    field = {"projects": "name"}.get(module, "title")
    return str(item.get(field) or item.get("query") or "Untitled")


async def _find_target(user, module: str, target: str):
    """Resolve an existing record from its title (fuzzy). Returns (item, error_text)."""
    target = (target or "").strip()
    if not target:
        return None, "I need to know which item you mean."
    ranked = await _fuzzy_find(user, [module], target)
    singular = _module_name(module)
    if not ranked:
        return None, f"I couldn't find a {singular} matching “{target}”."
    top = ranked[0][0]
    close = [r for r in ranked if r[0] >= top - 0.01]
    if len(close) > 1 and top < 100:
        names = "; ".join(f"“{_label(module, r[2])}”" for r in close[:5])
        return None, f"More than one {singular} matches “{target}”: {names}. Which one do you mean?"
    return ranked[0][2], None


_TIME_WORDS = re.compile(
    r"\b(?:day after tomorrow|tomorrow|today|tonight|next\s+\w+day|this\s+\w+day|on\s+(?:mon|tues|wednes|thurs|fri|satur|sun)day|"
    r"at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm)|"
    r"in\s+the\s+(?:morning|afternoon|evening)|(?:this|tomorrow)\s+(?:morning|afternoon|evening))\b",
    re.I,
)


def _clean_title(title: str) -> str:
    """Models like to produce 'Meeting tomorrow at 2pm' - the time belongs in startsAt, not the title."""
    cleaned = _TIME_WORDS.sub(" ", title or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-@")
    cleaned = re.sub(r"\b(?:at|on|for|in)$", "", cleaned, flags=re.I).strip(" ,.-")
    return (cleaned[:1].upper() + cleaned[1:]) if cleaned else (title or "").strip()


_STOP = {"the", "a", "an", "my", "in", "on", "of", "to", "and", "for", "from", "document", "documents", "doc", "docs",
         "note", "notes", "report", "reports", "research", "paper", "file", "task", "tasks", "goal", "goals",
         "project", "projects", "meeting", "event", "summary", "summarize", "summarise", "read", "give", "me"}
_GENERIC_QUERY = {"task", "tasks", "event", "events", "meeting", "meetings", "all", "today", "tomorrow", "calendar",
                  "everything", "goal", "goals", "project", "projects", "note", "notes", "document", "documents",
                  "schedule", "todo", "todos", "to-do", "list", "any", "my"}


def _keywords(text: str) -> list:
    return [w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if w not in _STOP]


def _score(item: dict, module: str, words: list) -> float:
    label = _label(module, item).lower()
    body = " ".join(str(item.get(k) or "") for k in ("content", "body", "summary", "description", "notes")).lower()
    score = 0.0
    for w in words:
        if w in label:
            score += 3
        elif w in body:
            score += 1
    if words and all(w in label for w in words):
        score += 5
    return score


async def _fuzzy_find(user, modules, target: str):
    """Records across `modules` ranked by title/body keyword overlap with `target`."""
    words = _keywords(target) or re.findall(r"[a-z0-9]{2,}", (target or "").lower())
    ranked = []
    for module in modules:
        listed = await workspace_crud(user, {"module": module, "action": "list", "limit": 50})
        for item in listed.get("items") or []:
            if (target or "").strip().lower() == _label(module, item).strip().lower():
                ranked.append((100.0, module, item))
                continue
            sc = _score(item, module, words)
            if sc > 0:
                ranked.append((sc, module, item))
    ranked.sort(key=lambda r: r[0], reverse=True)
    return ranked


async def _available_titles(user, modules) -> str:
    lines = []
    for module in modules:
        listed = await workspace_crud(user, {"module": module, "action": "list", "limit": 10})
        names = [_label(module, i) for i in listed.get("items") or []]
        if names:
            lines.append(f"{module}: " + "; ".join(f"“{n}”" for n in names))
    return "\n".join(lines)


_OVERVIEW_WORDS = re.compile(
    r"\b(overview|summari[sz]e|summary|what\s+(?:i|do i)\s+(?:have|need)\s+to\s+do|prioriti[sz]e|focus|explain|insight)\b", re.I
)


async def _summarise_with_llm(message: str, material: str, kind: str):
    answer = await call_llm(
        system=(
            "You answer ONLY from the provided workspace data. Never invent items, ids or facts that are not in it. "
            "Be concise and well organised. If the data does not contain what is asked, say so."
        ),
        prompt=f"User request: {message}\n\n{kind.upper()} DATA:\n{material[:12000]}",
        max_tokens=900,
    )
    if not answer or answer.startswith(("[LLM request failed", "[offline placeholder")):
        return None
    return answer.strip()


async def _read_item(user: dict, op: dict, message: str) -> dict:
    module = str(op.get("module") or "documents").lower()
    target = str(op.get("target") or "").strip()
    if not target and isinstance(op.get("data"), dict):
        target = " ".join(str(v) for v in op["data"].values())
    order = [module] + [m for m in ("documents", "notes", "research", "projects", "goals") if m != module]
    ranked = await _fuzzy_find(user, order, target)
    tool = f"workspace_read_{module}"
    if not ranked:
        titles = await _available_titles(user, ["documents", "notes", "research"])
        hint = (f"\n\nWhat I can see in your workspace:\n{titles}" if titles
                else "\n\nYour documents, notes and research are empty right now.")
        return {"text": f"I couldn't find anything matching “{target}”.{hint}", "tool": tool, "success": False}
    _, found_module, item = ranked[0]
    full = await workspace_crud(user, {"module": found_module, "action": "read", "id": item["_id"]})
    item = full.get("item") or item
    name = _label(found_module, item)
    body = "\n".join(str(item.get(k)) for k in ("content", "body", "summary", "description", "notes") if item.get(k)).strip()
    if found_module == "research" and item.get("sources"):
        body += "\nSources: " + json.dumps(item["sources"], default=str)[:1500]
    if not body:
        return {"text": f"I found “{name}” in your {found_module}, but it has no content yet.", "tool": tool, "success": True}
    answer = await _summarise_with_llm(message, f"Title: {name}\n\n{body}", found_module)
    if answer is None:
        answer = body[:3000]
    return {"text": f"From your {found_module} — “{name}”:\n\n{answer}", "tool": tool, "success": True, "raw": True}


async def _list_calendar(user: dict, raw: dict, message: str = "") -> list:
    """Date-range query done in the database with half-open [start, end)
    boundaries computed in the user's timezone. The range comes from the user's
    own words (deterministic) before anything the model guessed."""
    from datetime import timedelta as _td
    from app.database import get_db
    from app.date_range import resolve_date_range, to_query
    from app.owned import get_user_tz
    from app.serialization import docs_out

    tz = get_user_tz(user)
    rng = resolve_date_range(message, tz)
    filt: dict = {"user": user["_id"]}
    has_range = False
    if rng:
        filt["startsAt"] = to_query(rng)
        has_range = True
    else:
        lo, hi = parse_date(raw.get("from")), parse_date(raw.get("to"))
        if lo:
            # Models emit "to" as 23:59:59 of the last day or as a bare date; both
            # mean "up to the end of that day", so use the next local midnight.
            if hi:
                from app.date_range import exclusive_end
                hi = exclusive_end(hi, tz)
            if not hi or hi <= lo:
                hi = lo + _td(days=1)
            filt["startsAt"] = {"$gte": lo, "$lt": hi}
            has_range = True
    docs = await get_db().calendar_events.find(filt).sort("startsAt", 1).to_list(length=50)
    items = docs_out(docs)
    if not has_range:  # no range given: upcoming first
        now = datetime.now(timezone.utc).isoformat()
        upcoming = [i for i in items if (i.get("startsAt") or "") >= now]
        items = upcoming or items
    return items


def _module_name(module: str) -> str:
    return {"calendar": "calendar event", "tasks": "task", "goals": "goal", "projects": "project",
            "notes": "note", "documents": "document", "research": "research item"}[module]


def _describe_created(module: str, item: dict, user) -> str:
    name = _label(module, item)
    if module == "calendar":
        when = _fmt_dt(item["startsAt"], user) if item.get("startsAt") else ""
        end = f" – {_fmt_dt(item['endsAt'], user).split(', ')[-1]}" if item.get("endsAt") else ""
        where = f" at {item['location']}" if item.get("location") else ""
        return f"Scheduled “{name}” for {when}{end}{where}."
    extra = ""
    if module == "tasks" and item.get("scheduledStart"):
        extra = f" (scheduled {_fmt_dt(item['scheduledStart'], user)}, linked to your calendar)"
    elif module in ("tasks", "goals") and item.get("dueDate"):
        extra = f" (due {_fmt_dt(item['dueDate'], user)})"
    return f"Created {_module_name(module)} “{name}”{extra}."


def _format_list(module: str, items: list, user) -> str:
    if not items:
        return ("You have no calendar events in that time range." if module == "calendar"
                else f"You have no {module} matching that.")
    lines = []
    for item in items[:15]:
        name = _label(module, item)
        if module == "calendar":
            lines.append(f"- {_fmt_dt(item.get('startsAt'), user)} — {name}" + (f" ({item['location']})" if item.get("location") else ""))
        elif module == "tasks":
            when = f", scheduled {_fmt_dt(item['scheduledStart'], user)}" if item.get("scheduledStart") else (
                f", due {_fmt_dt(item['dueDate'], user)}" if item.get("dueDate") else "")
            lines.append(f"- [{item.get('status', 'todo')}] {name} ({item.get('priority', 'medium')}){when}")
        elif module in ("goals", "projects"):
            lines.append(f"- {name} — {item.get('status', '')}")
        else:
            lines.append(f"- {name}")
    title = {"calendar": "Your calendar", "tasks": "Your tasks", "goals": "Your goals", "projects": "Your projects",
             "notes": "Your notes", "documents": "Your documents", "research": "Your research"}[module]
    return f"{title}:\n" + "\n".join(lines)


# -------------------------------------------------------------- execution ----

async def _execute_operation(user: dict, op: dict, message: str) -> dict:
    """Returns {"text": str, "tool": str, "success": bool}."""
    module = str(op.get("module") or "").lower()
    action = str(op.get("action") or "").lower()
    if module not in ACTION_MODULES or action not in {"create", "update", "delete", "list", "read"}:
        return {"text": "", "tool": "workspace_crud", "success": False, "skip": True}
    data = _clean_data(module, op.get("data") if isinstance(op.get("data"), dict) else {})
    tool = f"workspace_{action}_{module}"
    if module in ("calendar", "tasks") and data.get("title"):
        data["title"] = _clean_title(data["title"])

    if action == "read":
        return await _read_item(user, op, message)

    if action == "list":
        raw = op.get("data") if isinstance(op.get("data"), dict) else {}
        query = str(raw.get("query") or "").strip()
        if not _keywords(query) or query.lower() in _GENERIC_QUERY:
            query = ""
        if module == "calendar":
            items = await _list_calendar(user, raw, message)
        else:
            args = {"module": module, "action": "list", "limit": 50}
            if query:
                args["query"] = query
            if raw.get("status"):
                args["status"] = str(raw["status"])
            result = await workspace_crud(user, args)
            if result.get("error"):
                return {"text": f"I couldn't read your {module}: {result['error']}", "tool": tool, "success": False}
            items = result.get("items") or []
            if not items and (query or raw.get("status")):
                # A wrong filter shouldn't hide everything; check what exists.
                everything = await workspace_crud(user, {"module": module, "action": "list", "limit": 50})
                items = everything.get("items") or []
                if items and not query:
                    items = []  # a status filter genuinely matched nothing
        listing = _format_list(module, items, user)
        if items and _OVERVIEW_WORDS.search(message):
            summary = await _summarise_with_llm(message, listing, module)
            if summary:
                return {"text": f"{summary}\n\n{listing}", "tool": tool, "success": True, "count": len(items), "raw": True}
        return {"text": listing, "tool": tool, "success": True, "count": len(items)}

    if action == "create":
        if not data.get("title") and module in ("tasks", "goals", "notes", "documents") and op.get("target"):
            data["title"] = str(op["target"]).strip()
        if module == "tasks" and data.get("goal"):
            # The model gives a goal *name*; the task stores a goal *id*.
            goal_ref = str(data["goal"]).strip()
            if not _id(goal_ref):
                goal_item, goal_problem = await _find_target(user, "goals", goal_ref)
                if goal_problem:
                    return {"text": f"I couldn't create that task: {goal_problem}", "tool": tool, "success": False}
                data["goal"] = str(goal_item["_id"])
        if module == "tasks" and data.get("scheduledStart") and not data.get("scheduledEnd"):
            start = parse_date(data["scheduledStart"])
            if start:
                data["scheduledEnd"] = (start + timedelta(hours=1)).isoformat()
        result = await workspace_crud(user, {"module": module, "action": "create", "data": data, "agent": "compass"})
        if result.get("error"):
            error = result["error"]
            if "already scheduled" in error.lower() or "conflict" in error.lower():
                error = "another item already starts at that exact time. Pick a different time and I'll add it."
            return {"text": f"I couldn't create that {_module_name(module)}: {error}", "tool": tool, "success": False}
        return {"text": _describe_created(module, result["item"], user), "tool": tool, "success": True,
                "item": result["item"]}

    # update / delete need an existing record
    item, problem = await _find_target(user, module, str(op.get("target") or data.get("title") or data.get("name") or ""))
    if problem:
        return {"text": problem, "tool": tool, "success": False}

    if action == "delete":
        if not _DELETE_WORDS.search(message):
            return {"text": f"I didn't delete “{_label(module, item)}” because you didn't ask me to.", "tool": tool, "success": False}
        result = await workspace_crud(user, {"module": module, "action": "delete", "id": item["_id"]})
        if result.get("error"):
            return {"text": f"I couldn't delete it: {result['error']}", "tool": tool, "success": False}
        return {"text": f"Deleted {_module_name(module)} “{_label(module, item)}”.", "tool": tool, "success": True}

    # update
    if _DONE_WORDS.search(message) and module in ("tasks", "goals") and "status" not in data:
        data["status"] = "done"
    if module == "goals" and data.get("status") == "done" and "progress" not in data:
        data["progress"] = 100
    # Renames: the model puts the *new* title in data.title and the old one in target.
    result = await workspace_crud(user, {"module": module, "action": "update", "id": item["_id"], "data": data})
    if result.get("error"):
        error = result["error"]
        if "already scheduled" in error.lower():
            error = "another item already starts at that exact time."
        return {"text": f"I couldn't update “{_label(module, item)}”: {error}", "tool": tool, "success": False}
    updated = result["item"]
    changes = ", ".join(
        f"{k} → {_fmt_dt(v, user) if k in ('startsAt', 'endsAt', 'dueDate', 'scheduledStart', 'scheduledEnd') else v}"
        for k, v in data.items()
    )
    return {"text": f"Updated {_module_name(module)} “{_label(module, updated)}” ({changes}).", "tool": tool, "success": True}


_CALENDAR_CONTEXT = re.compile(r"\b(events?|calendar|meetings?|appointments?|schedule|scheduled|agenda|dates?)\b", re.I)
_FOLLOWUP_SHAPE = re.compile(
    r"^\s*(?:and\s+|what\s+about\s+|how\s+about\s+|then\s+)?(?:for\s+|on\s+)?"
    r"(?P<when>[\w ,\-/]{2,40}?)\s*\??\s*$", re.I)


def _is_date_followup(message: str, conversation, user=None) -> bool:
    """'Tomorrow?' right after a calendar question means 'what events do I
    have tomorrow?'. Needs a short, date-only message AND calendar context in
    the last few turns."""
    from app.date_range import resolve_date_range
    from app.owned import get_user_tz

    words = (message or "").split()
    if not words or len(words) > 6 or not _FOLLOWUP_SHAPE.match(message or ""):
        return False
    if _matches(message, _AGENT_ONLY) or re.search(rf"\b(?:{_ACTION_VERBS})\b", message, re.I):
        return False
    if resolve_date_range(message, get_user_tz(user)) is None:
        return False
    recent = conversation[-6:-1] if isinstance(conversation, list) else []
    return any(isinstance(m, dict) and _CALENDAR_CONTEXT.search(str(m.get("content") or "")) for m in recent)


async def try_direct_workspace_action(user: dict, message: str, conversation=None) -> dict | None:
    """Run a workspace operation straight from the user's request, or return
    None to let the normal specialist-agent pipeline handle it."""
    if _is_date_followup(message, conversation, user):
        set_user_tz(user)
        items = await _list_calendar(user, {}, message)
        outcome = {"text": _format_list("calendar", items, user), "tool": "workspace_list_calendar",
                   "success": True, "count": len(items), "raw": True}
        return _reply(outcome["text"], [outcome])

    if not looks_like_workspace_action(message):
        return None

    set_user_tz(user)

    recent = ""
    if isinstance(conversation, list):
        lines = []
        for item in conversation[-5:-1]:
            if isinstance(item, dict) and item.get("content"):
                lines.append(f"{item.get('role', 'message')}: {str(item['content'])[:300]}")
        recent = "\n".join(lines)

    prompt = (
        f"{_now_context(user)}\n\n"
        + (f"Recent conversation (only to resolve references like 'it' or 'that'):\n{recent}\n\n" if recent else "")
        + f"User request:\n{message}\n\nReturn the JSON object."
    )
    raw = await call_llm(system=_EXTRACT_SYSTEM, prompt=prompt, max_tokens=700)
    if not raw or raw.startswith(("[LLM request failed", "[offline placeholder")):
        return None
    plan = _extract_json(raw)
    operations = [o for o in (plan.get("operations") or []) if isinstance(o, dict)][:6]
    question = str(plan.get("question") or "").strip()

    if not operations:
        if question:
            return _reply(question, [])
        return None

    outcomes = []
    for op in operations:
        try:
            outcome = await _execute_operation(user, op, message)
        except Exception:  # noqa: BLE001 - never let one op take down Mission Control
            logger.exception("Direct workspace operation failed: %s", op)
            outcome = {"text": "Something went wrong while saving that, so nothing was changed.",
                       "tool": f"workspace_{op.get('action')}_{op.get('module')}", "success": False}
        if outcome.get("skip"):
            continue
        outcomes.append(outcome)

    if not outcomes:
        return _reply(question, []) if question else None

    lines = [
        o["text"] if (o.get("raw") or "\n" in o["text"]) else ("✅ " if o["success"] else "⚠️ ") + o["text"]
        for o in outcomes
    ]
    text = "\n".join(lines)
    if question and not any(o["success"] for o in outcomes):
        text += f"\n\n{question}"
    return _reply(text, outcomes)


def _reply(text: str, outcomes: list) -> dict:
    agents = ["compass"] if outcomes else []
    return {
        "message": text,
        "agents": agents,
        "planned_agents": agents,
        "reason": "Workspace operation executed directly and verified against the database.",
        "dependencies": [],
        "actions": [{"tool": o["tool"], "success": o["success"]} for o in outcomes],
    }