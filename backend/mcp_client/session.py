"""Reusable MCP client session (protocol 2026-07-28).

Connects to the stock-exchange MCP server **through agentgateway**, never
directly to the backend's ``/mcp``. The extra hop out to :3111 and back is
deliberate: it is what puts this project's own tool calls in the same audit log
as calls made from Claude Desktop or an IDE. See CLAUDE.md invariant #7.

Two things changed with the 2026-07-28 revision and SDK v2:

* **No handshake, no session.** Every request carries its own protocol version,
  client identity and capabilities in ``_meta``. There is nothing to initialise.
* **No lock.** The old client serialised every call behind an ``asyncio.Lock``
  because one long-lived ``ClientSession`` was shared across concurrent web
  requests. With no session to share, calls run concurrently.

Connection is **lazy**: the gateway forwards to this same backend process, so
connecting at startup would deadlock a cold start. The first tool call connects.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import Client, Implementation

from core.config import PROTOCOL_VERSION, settings
from core.logging_config import get_logger

_log = get_logger("mcp_client")


class MCPClientError(RuntimeError):
    """Raised when the MCP server cannot be reached or a call fails."""


def _root_cause(exc: BaseException) -> str:
    """Unwrap nested ExceptionGroups down to the message that explains it."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__


async def _quietly_close(stack: AsyncExitStack) -> None:
    """Close a partially-opened stack without masking the original failure."""
    try:
        await stack.aclose()
    except BaseException:  # noqa: BLE001 - teardown noise is not the real error
        pass


def request_meta(conversation_id: str | None = None) -> dict[str, Any]:
    """Per-request ``_meta`` additions.

    MCP defines no conversation identifier — no revision ever has. Only a client
    we control can supply one, and the W3C ``baggage`` key is the slot the spec
    reserves for exactly this sort of correlation data. External hosts leave it
    empty, and the audit log shows ``n/a`` rather than inventing a thread.
    """
    if not conversation_id:
        return {}
    return {"baggage": f"conversationId={conversation_id}"}


class MCPToolClient:
    """Talks to the stock-exchange MCP server through agentgateway."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or settings.mcp_gateway_url
        self._client: Client | None = None
        self._stack: AsyncExitStack | None = None
        self._tools: list[Any] = []
        # Guards connection setup only — not tool execution. Concurrent callers
        # must not each open their own client, but once connected they run in
        # parallel.
        self._connect_lock = asyncio.Lock()

    @property
    def client_info(self) -> Implementation:
        return Implementation(name=settings.client_name, version=settings.client_version)

    async def connect(self) -> None:
        """Open the connection and cache the tool list (idempotent)."""
        async with self._connect_lock:
            if self._client is not None:
                return
            stack = AsyncExitStack()
            try:
                client = await stack.enter_async_context(
                    Client(
                        self.url,
                        client_info=self.client_info,
                        # Pin the revision: this project is 2026-07-28 only, so a
                        # silent downgrade would be a bug, not a convenience.
                        mode=PROTOCOL_VERSION,
                        raise_exceptions=True,
                    )
                )
                # Inside the try on purpose: the transport connects lazily, so a
                # dead endpoint only fails here, on the first real request.
                listing = await client.list_tools()
            except (KeyboardInterrupt, SystemExit):
                await _quietly_close(stack)
                raise
            except BaseException as exc:
                # A failed connect surfaces as an anyio ExceptionGroup, which is
                # a BaseExceptionGroup and therefore not caught by `except
                # Exception`. Catch broadly, then re-raise the two things that
                # must never be swallowed (above).
                await _quietly_close(stack)
                raise MCPClientError(
                    f"Cannot reach the MCP server at {self.url}: "
                    f"{_root_cause(exc)}. If this is the gateway URL, start "
                    "agentgateway (see README) — every consumer goes through it "
                    "so that all calls are audited."
                ) from exc
            self._stack = stack
            self._client = client
            self._tools = list(listing.tools)
            _log.info(
                "MCP connected via %s — protocol %s, %d tool(s)",
                self.url,
                client.protocol_version,
                len(self._tools),
            )

    async def ensure_connected(self) -> Client:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        return self._client

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def protocol_version(self) -> str | None:
        return self._client.protocol_version if self._client else None

    @property
    def server_info(self) -> Any:
        return self._client.server_info if self._client else None

    @property
    def tool_names(self) -> list[str]:
        return [t.name for t in self._tools]

    async def capabilities(self) -> dict:
        """Capability surface for the UI, from one connection."""
        client = await self.ensure_connected()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts = await client.list_prompts()
        info = client.server_info
        return {
            "protocol_version": client.protocol_version,
            "server_name": getattr(info, "name", None),
            "server_version": getattr(info, "version", None),
            "instructions": client.instructions,
            "tools": self.tool_names,
            "resources": [r.uri for r in resources.resources],
            "resource_templates": [t.uri_template for t in templates.resource_templates],
            "prompts": [p.name for p in prompts.prompts],
            "gateway_url": self.url,
        }

    def openai_tools(self) -> list[dict]:
        """Tool definitions in the OpenAI function-calling format.

        Attribute names are snake_case under SDK v2 (``input_schema``); the wire
        format is unchanged.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": (t.description or "").strip(),
                    "parameters": t.input_schema or {"type": "object", "properties": {}},
                },
            }
            for t in self._tools
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict,
        *,
        conversation_id: str | None = None,
        progress_callback: Any = None,
    ) -> str:
        """Invoke a tool and return its result as a JSON string.

        The SDK serialises a tool returning a *list* as one text block per
        element (with ``structuredContent`` alongside), while a plain ``dict``
        comes back as a single text block and no structured content. Both shapes
        are reassembled here into one JSON payload for the LLM.
        """
        client = await self.ensure_connected()
        _log.debug("call_tool %s args=%s", name, arguments)
        result = await client.call_tool(
            name,
            arguments,
            progress_callback=progress_callback,
            meta=request_meta(conversation_id) or None,
        )

        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            payload = structured.get("result", structured)
            return json.dumps(payload, separators=(",", ":"), default=str)

        parts = [block.text for block in result.content if getattr(block, "text", None) is not None]
        if not parts:
            return "{}"
        if len(parts) == 1:
            try:
                return json.dumps(json.loads(parts[0]), separators=(",", ":"))
            except (json.JSONDecodeError, TypeError):
                return parts[0]
        try:
            items = [json.loads(p) for p in parts]
            return json.dumps(items, separators=(",", ":"))
        except (json.JSONDecodeError, TypeError):
            return "\n".join(parts)

    async def read_resource(self, uri: str, *, conversation_id: str | None = None) -> str:
        """Read an MCP resource and return its text payload."""
        client = await self.ensure_connected()
        result = await client.read_resource(uri, meta=request_meta(conversation_id) or None)
        parts = [
            getattr(block, "text", None)
            for block in result.contents
            if getattr(block, "text", None) is not None
        ]
        return "\n".join(p for p in parts if p) or "{}"

    async def get_prompt(self, name: str, arguments: dict[str, str] | None = None) -> str:
        """Render a server-declared prompt to text."""
        client = await self.ensure_connected()
        result = await client.get_prompt(name, arguments or {})
        chunks = []
        for message in result.messages:
            text = getattr(message.content, "text", None)
            if text:
                chunks.append(text)
        return "\n\n".join(chunks)

    async def close(self) -> None:
        stack, self._stack = self._stack, None
        self._client = None
        self._tools = []
        if stack is None:
            return
        try:
            await stack.aclose()
        except BaseException:  # noqa: BLE001 - benign anyio teardown noise
            pass
