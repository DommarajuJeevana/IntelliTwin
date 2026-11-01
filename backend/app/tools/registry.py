"""
IntelliTwin agent tool registry.

Each agent receives only the tools relevant to its responsibility.

This is intentionally narrower than giving every agent the entire
workspace-read toolkit. Narrow toolsets reduce unnecessary LLM/tool
loops, improve reliability, and make agent responsibilities clearer.
"""

from app.tools.memory_tools import (
    ALL as MEMORY_TOOLS,
    SEARCH_MEMORY,
)
from app.tools.web import SEARCH_WEB
from app.tools.workspace import (
    ATLAS_WORKSPACE_TOOLS,
    COMPASS_WORKSPACE_TOOLS,
    NOVA_WORKSPACE_TOOLS,
)
from app.tools.workspace_universal import WORKSPACE_CRUD_TOOLS
from app.tools.workspace_read import (
    GET_WORKSPACE_CONTEXT,
    GET_WORKSPACE_ENTITY,
    GET_RECENT_WORKSPACE_ACTIVITY,
)


# ---------------------------------------------------------------------------
# Shared read tools
# ---------------------------------------------------------------------------

# These are deliberately selective.
#
# SEARCH_WORKSPACE is NOT included by default because it searches the entire
# workspace and is expensive/noisy for an LLM agent. Agents should use their
# specialized tools whenever possible.
#
# GET_WORKSPACE_ENTITY is useful when an agent already knows the exact entity
# it needs.
#
# GET_WORKSPACE_CONTEXT is useful for broad personal/workspace context.
#
# GET_RECENT_WORKSPACE_ACTIVITY is useful for "what have I been doing?"
# style requests.

CONTEXT_READ_TOOLS = [
    GET_WORKSPACE_CONTEXT,
    GET_WORKSPACE_ENTITY,
    GET_RECENT_WORKSPACE_ACTIVITY,
]


# ---------------------------------------------------------------------------
# Echo
# ---------------------------------------------------------------------------

# Echo is the memory specialist. It needs memory tools and limited workspace
# context, but it should not search every workspace module for every message.

ECHO_TOOLS = [
    *CONTEXT_READ_TOOLS,
    *WORKSPACE_CRUD_TOOLS,
    *MEMORY_TOOLS,
]


# ---------------------------------------------------------------------------
# Compass
# ---------------------------------------------------------------------------

# Compass has specialized tools for goals, tasks, and calendar.
# SEARCH_MEMORY allows it to retrieve personal preferences when necessary.

COMPASS_TOOLS = [
    *CONTEXT_READ_TOOLS,
    *WORKSPACE_CRUD_TOOLS,
    *COMPASS_WORKSPACE_TOOLS,
    SEARCH_MEMORY,
]


# ---------------------------------------------------------------------------
# Atlas
# ---------------------------------------------------------------------------

# Atlas should prefer live web research for research requests.
#
# SEARCH_DOCUMENTS is already part of ATLAS_WORKSPACE_TOOLS, so Atlas can
# search the user's saved documents when that is actually relevant.
#
# We intentionally do NOT expose generic SEARCH_WORKSPACE here. It caused
# unnecessary broad workspace searches during research tasks.

ATLAS_TOOLS = [
    SEARCH_WEB,
    *WORKSPACE_CRUD_TOOLS,
    *CONTEXT_READ_TOOLS,
    *ATLAS_WORKSPACE_TOOLS,
    SEARCH_MEMORY,
]


# ---------------------------------------------------------------------------
# Nova
# ---------------------------------------------------------------------------

# Nova receives research/document-specific tools and memory.
# It does not need generic workspace-wide search for a normal creation task.

NOVA_TOOLS = [
    *CONTEXT_READ_TOOLS,
    *WORKSPACE_CRUD_TOOLS,
    SEARCH_MEMORY,
    *NOVA_WORKSPACE_TOOLS,
]