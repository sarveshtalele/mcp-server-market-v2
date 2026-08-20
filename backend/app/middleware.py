"""Pure-ASGI request logging.

Starlette's ``BaseHTTPMiddleware`` (what ``@app.middleware("http")`` builds)
buffers the request/response cycle and cannot sit in front of a mounted ASGI app
that streams or replays ``receive`` — it raises ``RuntimeError: No response
returned.`` against the MCP endpoint. This does the same job at the raw ASGI
layer, where streaming and body replay both work.
"""

from __future__ import annotations

import time
from typing import Any

from core.logging_config import get_logger

log = get_logger("app")


class RequestLogMiddleware:
    """Log method, path, status and latency for every HTTP request."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status = {"code": 0}

        async def observed(message: dict) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, observed)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            log.info(
                "%s %s -> %d (%.1f ms)",
                scope.get("method", "?"),
                scope.get("path", "?"),
                status["code"],
                elapsed_ms,
            )


class ProtocolGuardMiddleware:
    """Enforce a single protocol revision on the MCP endpoint (decision D-3).

    SDK v2 happily serves both `2026-07-28` and the legacy `2025-11-25`
    `initialize` handshake from one endpoint, and offers no switch to turn the
    old one off. This project targets one revision, so the policy is applied
    here: anything that is not `2026-07-28` is refused with `-32022`
    (`UnsupportedProtocolVersion`) and told what the server does support.

    Set ``STRICT_PROTOCOL=false`` to accept legacy clients instead — the single
    change needed if a bridge such as `mcp-remote` turns out to speak only the
    older revision.
    """

    UNSUPPORTED_PROTOCOL_VERSION = -32022

    def __init__(self, app: Any, *, version: str, strict: bool = True) -> None:
        self.app = app
        self.version = version
        self.strict = strict

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if not self.strict or scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        body, replay = await _buffer_body(receive)
        request = _json_or_empty(body)
        method = str(request.get("method") or "")
        params = request.get("params") if isinstance(request.get("params"), dict) else {}
        meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
        declared = meta.get("io.modelcontextprotocol/protocolVersion")

        problem: str | None = None
        if method in ("initialize", "notifications/initialized"):
            problem = (
                f"This server implements MCP {self.version}, which removed the "
                "initialize handshake. Send requests directly with per-request _meta."
            )
        elif method and declared is None:
            problem = (
                "Missing io.modelcontextprotocol/protocolVersion in _meta. "
                f"This server implements MCP {self.version}."
            )
        elif method and declared != self.version:
            problem = f"Unsupported protocol version {declared!r}."

        if problem is None:
            await self.app(scope, replay, send)
            return

        await _send_json(
            send,
            400,
            {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": self.UNSUPPORTED_PROTOCOL_VERSION,
                    "message": problem,
                    "data": {"supported": [self.version]},
                },
            },
        )


async def _buffer_body(receive: Any) -> tuple[bytes, Any]:
    """Read the whole request body and return it with a replaying `receive`."""
    chunks = bytearray()
    more = True
    while more:
        message = await receive()
        if message["type"] == "http.request":
            chunks.extend(message.get("body", b""))
            more = message.get("more_body", False)
        elif message["type"] == "http.disconnect":
            more = False

    state = {"sent": False}

    async def replay() -> dict:
        if not state["sent"]:
            state["sent"] = True
            return {"type": "http.request", "body": bytes(chunks), "more_body": False}
        return await receive()

    return bytes(chunks), replay


def _json_or_empty(body: bytes) -> dict:
    import json

    try:
        parsed = json.loads(body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def _send_json(send: Any, status: int, payload: dict) -> None:
    import json

    raw = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": raw})
