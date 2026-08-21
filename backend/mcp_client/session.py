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

It is also **self-healing**. One `Client` is shared by every web request and
outlives any single call, so its HTTP connection eventually gets closed by the
peer. Nothing in the SDK re-opens it, so a call that hits a closed connection
reconnects and retries once — see `_with_reconnect`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any, TypeVar

from mcp import Client, Implementation, MCPError
from mcp.types import CONNECTION_CLOSED

from core.config import PROTOCOL_VERSION, settings
from core.logging_config import get_logger

_log = get_logger("mcp_client")

T = TypeVar("T")


class MCPClientError(RuntimeError):
    """Raised when the MCP server cannot be reached or a call fails."""


def _is_dead_connection(exc: BaseException) -> bool:
    """Does this failure mean the cached client can never work again?

    A ``Client`` here is long-lived and shared by every web request, so the
    underlying HTTP connection outlives any single call. When the peer closes it
    — an idle timeout on the gateway, a gateway restart — the SDK fails the call
    with ``CONNECTION_CLOSED`` and stays failed: nothing re-opens it. Without
    this check the first dropped connection breaks the chat until the backend is
    restarted, and every answer becomes "the market data server is unavailable".
    """
    if isinstance(exc, KeyboardInterrupt | SystemExit | asyncio.CancelledError):
        return False
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    if isinstance(exc, MCPError):
        # Only the transport code. A tool that raised, or an unknown tool name,
        # is a real answer — retrying it would just call it twice.
        return exc.code == CONNECTION_CLOSED
    if isinstance(exc, RuntimeError):
        # The SDK raises this from `Client.session` once its exit stack has been
        # unwound, which is the same dead-client state arriving by a different
        # door. Matched on the message because the SDK offers no way to ask a
        # Client whether it is still usable; `test_client.py` pins the string so
        # an SDK upgrade that reworded it fails loudly instead of silently
        # reinstating the never-recovers bug.
        return "async context manager" in str(exc)
    return isinstance(exc, ConnectionError | OSError)


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

    async def _discard(self, dead: Client) -> None:
        """Drop a client whose connection is gone, so the next call re-opens one.

        Guarded on identity: several tool calls run concurrently, so two of them
        can fail on the same dead connection while a third has already replaced
        it. Tearing down the replacement would turn one dropped connection into
        a cascade.
        """
        async with self._connect_lock:
            if self._client is not dead:
                return
            stack, self._stack = self._stack, None
            self._client = None
            self._tools = []
        if stack is not None:
            await _quietly_close(stack)

    async def _with_reconnect(self, what: str, call: Callable[[Client], Awaitable[T]]) -> T:
        """Run `call`, and retry it once on a fresh connection if the old one died."""
        client = await self.ensure_connected()
        try:
            return await call(client)
        except BaseException as exc:
            if not _is_dead_connection(exc):
                raise
            _log.warning(
                "MCP connection to %s is closed (%s) - reconnecting and retrying %s.",
                self.url,
                _root_cause(exc),
                what,
            )
            await self._discard(client)
        # Outside the handler: a failure here is about the new connection, and
        # chaining it to the old one's error would report the wrong cause.
        client = await self.ensure_connected()
        return await call(client)

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
        return await self._with_reconnect("capabilities", self._capabilities)

    async def _capabilities(self, client: Client) -> dict:
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
        _log.debug("call_tool %s args=%s", name, arguments)
        result = await self._with_reconnect(
            f"tool {name}",
            lambda client: client.call_tool(
                name,
                arguments,
                progress_callback=progress_callback,
                meta=request_meta(conversation_id) or None,
            ),
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
        result = await self._with_reconnect(
            f"resource {uri}",
            lambda client: client.read_resource(uri, meta=request_meta(conversation_id) or None),
        )
        parts = [
            getattr(block, "text", None)
            for block in result.contents
            if getattr(block, "text", None) is not None
        ]
        return "\n".join(p for p in parts if p) or "{}"

    async def get_prompt(self, name: str, arguments: dict[str, str] | None = None) -> str:
        """Render a server-declared prompt to text."""
        result = await self._with_reconnect(
            f"prompt {name}",
            lambda client: client.get_prompt(name, arguments or {}),
        )
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
