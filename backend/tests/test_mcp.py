"""Echo MCP dispatch tests (SDK-independent; the mcp package is not needed)."""
from app.mcp import echo_server


async def test_unknown_tool_is_generic():
    assert await echo_server.run_tool({}, "nope", {}) == {"error": "Unknown tool."}


async def test_bad_arguments_rejected():
    assert "error" in await echo_server.run_tool({}, "nope", ["x"])


async def test_exception_text_not_leaked(monkeypatch):
    class T:
        name = "boom"

        async def handler(self, user, args):
            raise RuntimeError("mongodb://user:pw@host secret detail")

    monkeypatch.setattr(echo_server, "ECHO_TOOLS", [T()])
    out = await echo_server.run_tool({}, "boom", {})
    assert "secret" not in str(out) and "pw" not in str(out)
