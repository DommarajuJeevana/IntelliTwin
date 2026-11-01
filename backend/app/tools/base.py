"""
Phase 5 - shared tool shape.

A Tool is just: a name + description + JSON Schema Claude sees (input_schema),
plus an async handler that actually does the thing when Claude asks for it.
Every agent-specific tool module (memory_tools.py, workspace.py, web.py)
builds a list of these; app/llm.py's call_llm_with_tools() is the only place
that knows how to turn them into Anthropic's tool-use wire format and run
the request/response loop.
"""
from dataclasses import dataclass
from typing import Awaitable, Callable

ToolHandler = Callable[[dict, dict], Awaitable[dict]]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: ToolHandler  # async (user, args) -> JSON-serializable result

    def to_anthropic_param(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}

    def to_openai_param(self) -> dict:
        """Same tool, OpenAI's chat-completions function-calling wire
        format. The JSON Schema itself (self.input_schema) is identical -
        only the wrapping differs."""
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.input_schema},
        }


def tools_by_name(tools: list[Tool]) -> dict[str, Tool]:
    return {t.name: t for t in tools}
