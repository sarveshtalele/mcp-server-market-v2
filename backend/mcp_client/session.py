"""Reusable MCP client session.

Connects to the stock-exchange MCP server through agentgateway (Streamable
HTTP, see `backend/mcp_server/gateway/config.yaml`) rather than spawning
`python -m mcp_server.server` directly — the gateway is what actually spawns
that process, and adds a tool-name allowlist + a per-call audit log in front
of it for every consumer, not just this one. Start the gateway first (see
README "agentgateway"); this client just needs it reachable at
`settings.mcp_gateway_url`.

Discovers tools and adapts them to the OpenAI function-calling schema. Used by
both the CLI chatbot and the AG-UI agent, so the "MCP client calls MCP server"
path is shared. Tool calls are serialised by a lock because the session is
shared across concurrent requests.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from core.config import settings
from core.logging_config import get_logger

_log = get_logger("mcp_client")


class MCPToolClient:
    """Manages a Streamable HTTP connection (via agentgateway) to the stock-exchange MCP server."""

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._tools: list[Any] = []
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect to the MCP server through agentgateway and initialise the session."""
        self._stack = AsyncExitStack()
        read, write, _get_session_id = await self._stack.enter_async_context(
            streamablehttp_client(settings.mcp_gateway_url)
        )
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        self._tools = (await self._session.list_tools()).tools

    @property
    def tool_names(self) -> list[str]:
        return [t.name for t in self._tools]

    def openai_tools(self) -> list[dict]:
        """Return tool definitions in the OpenAI function-calling format.

        The LiteLLM proxy is OpenAI-compatible, so this is the schema both the
        AG-UI agent and the CLI chatbot use.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": (t.description or "").strip(),
                    "parameters": t.inputSchema
                    or {"type": "object", "properties": {}},
                },
            }
            for t in self._tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Invoke an MCP tool and return its result as a JSON string.

        FastMCP serialises a tool that returns a *list* as one TextContent
        block per element (not a single JSON array), so we reassemble:
          * structuredContent, if the server provided it; else
          * a single block -> its JSON; else
          * many blocks -> a JSON array of the parsed blocks.
        """
        if self._session is None:
            raise RuntimeError("MCPToolClient.connect() not called")
        _log.debug("call_tool %s args=%s", name, arguments)
        # Serialise: the stdio session is shared across concurrent requests.
        async with self._lock:
            result = await self._session.call_tool(name, arguments)

        # Prefer structured content when the server supplies it.
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            # FastMCP wraps non-dict returns under "result".
            payload = structured.get("result", structured)
            return json.dumps(payload, separators=(",", ":"))

        parts: list[str] = [
            block.text
            for block in result.content
            if getattr(block, "text", None) is not None
        ]
        if not parts:
            return "{}"
        if len(parts) == 1:
            try:
                return json.dumps(json.loads(parts[0]), separators=(",", ":"))
            except (json.JSONDecodeError, TypeError):
                return parts[0]

        # Multiple blocks: try to parse each as JSON and emit a single array.
        try:
            items = [json.loads(p) for p in parts]
            return json.dumps(items, separators=(",", ":"))
        except (json.JSONDecodeError, TypeError):
            return "\n".join(parts)

    async def close(self) -> None:
        if self._stack is None:
            return
        try:
            await self._stack.aclose()
        except BaseException:  # noqa: BLE001 - benign anyio stdio teardown noise
            # anyio stdio teardown can raise a cancel-scope/GeneratorExit error
            # during shutdown; the subprocess still exits.
            pass
        finally:
            self._stack = None
            self._session = None
