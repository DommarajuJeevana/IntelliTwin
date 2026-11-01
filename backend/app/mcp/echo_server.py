"""
Standalone MCP server that exposes Echo's memory tools (save / search / update /
archive / restore memory) to any MCP-compatible client over stdio.

Run from the `backend/` directory (needs `pip install -r requirements-mcp.txt`):

    ECHO_MCP_USER_EMAIL=you@example.com python -m app.mcp.echo_server

MCP clients run outside the FastAPI request / JWT flow, so ECHO_MCP_USER_EMAIL
tells the server whose memory to operate on. It must match an existing account.

Claude Desktop style client config:

    {
      "mcpServers": {
        "intellitwin-echo": {
          "command": "python",
          "args": ["-m", "app.mcp.echo_server"],
          "cwd": "/path/to/intellitwin/backend",
          "env": { "ECHO_MCP_USER_EMAIL": "you@example.com" }
        }
      }
    }
"""
import asyncio
import json
import logging
import sys

from app.config import settings
from app.database import close_db, connect_db, get_db
from app.serialization import serialize
from app.tools.base import tools_by_name
from app.tools.memory_tools import ECHO_TOOLS

logger = logging.getLogger("intellitwin.mcp")


async def _load_user() -> dict:
    email = (settings.ECHO_MCP_USER_EMAIL or "").strip().lower()
    if not email:
        raise RuntimeError("ECHO_MCP_USER_EMAIL is not set - it must be the email of an existing IntelliTwin account.")
    user = await get_db().users.find_one({"email": email}, {"passwordHash": 0})
    if not user:
        raise RuntimeError(f"No IntelliTwin account found for ECHO_MCP_USER_EMAIL={email!r}.")
    return user


async def run_tool(user: dict, name: str, arguments: dict | None) -> dict:
    """SDK-independent tool dispatch (unit-testable without the MCP package).

    Errors are reported with a generic message: exception text can contain
    database or filesystem details, so it is logged server-side only.
    """
    tool = tools_by_name(ECHO_TOOLS).get(name)
    if tool is None:
        return {"error": "Unknown tool."}
    if arguments is not None and not isinstance(arguments, dict):
        return {"error": "Tool arguments must be an object."}
    try:
        return await tool.handler(user, arguments or {})
    except Exception:  # noqa: BLE001 - report to the client, don't crash the server
        logger.exception("Echo MCP tool %s failed", name)
        return {"error": "The tool failed. See the server log for details."}


async def main() -> None:
    try:
        import mcp.types as types
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
    except ImportError:
        sys.exit("The MCP SDK isn't installed. Run: pip install -r requirements-mcp.txt")

    await connect_db()
    try:
        user = await _load_user()
        server = Server("intellitwin-echo")

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(name=t.name, description=t.description, inputSchema=t.input_schema) for t in ECHO_TOOLS
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
            result = await run_tool(user, name, arguments)
            return [types.TextContent(type="text", text=json.dumps(serialize(result), default=str))]

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
