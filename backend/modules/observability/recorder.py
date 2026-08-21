"""ASGI middleware that records every MCP call reaching this server.

Why record here rather than parse agentgateway's access log:

* Every consumer already passes through the gateway, and the gateway forwards to
  this endpoint — so this middleware sees exactly the same traffic, with the
  request body available, which is where ``_meta.clientInfo`` lives.
* It needs no knowledge of the gateway's log schema, so it works on any gateway
  version and on a machine where the gateway is not running at all.

What it cannot see: calls the gateway **refused** (a tool outside the allowlist
never reaches us). Those come from the optional log ingester — see
``ingester.py`` — which is why both paths write to the same table with a
``via`` column.
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

from core.config import settings
from core.logging_config import get_logger
from modules.observability import attribution as attr
from modules.observability.hub import hub
from modules.observability.models import McpCall
from modules.observability.store import ObsSessionLocal

log = get_logger("observability")

# Legacy-handshake identity, keyed by the session id the compatibility path
# mints. Under 2026-07-28 identity travels in `_meta` on every request and none
# of this is needed — but a client arriving through the `mcp-remote` bridge
# speaks the older revision, where identity is sent once, at `initialize`.
# Sessions were removed from the transport in this revision; the compatibility
# path still issues one, and that is what makes bridged hosts attributable.
# Bounded so a long-running server cannot accumulate identities without limit.
_SESSION_IDENTITY: OrderedDict[str, tuple[str | None, str | None]] = OrderedDict()
_SESSION_IDENTITY_MAX = 256


def remember_session_identity(session_id: str, name: str | None, version: str | None) -> None:
    if not session_id or not name:
        return
    _SESSION_IDENTITY[session_id] = (name, version)
    _SESSION_IDENTITY.move_to_end(session_id)
    while len(_SESSION_IDENTITY) > _SESSION_IDENTITY_MAX:
        _SESSION_IDENTITY.popitem(last=False)


def identity_for_session(session_id: str | None) -> tuple[str | None, str | None]:
    if not session_id:
        return None, None
    found = _SESSION_IDENTITY.get(session_id)
    if found:
        _SESSION_IDENTITY.move_to_end(session_id)
        return found
    return None, None

# JSON-RPC methods whose "name" is worth recording, and what kind of thing it is.
_RESOURCE_TYPE = {
    "tools/call": "tool",
    "resources/read": "resource",
    "prompts/get": "prompt",
}


def _name_for(method: str, params: dict) -> str | None:
    if method == "resources/read":
        uri = params.get("uri")
        return str(uri) if uri else None
    name = params.get("name")
    return str(name) if name else None


def _args_preview(params: dict, limit: int) -> str | None:
    args = params.get("arguments")
    if args is None:
        return None
    try:
        blob = json.dumps(args, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return None
    if len(blob) <= limit:
        return blob
    return blob[:limit] + f"...[+{len(blob) - limit} chars]"


def record(
    *,
    method: str,
    params: dict | None = None,
    status: str = "ok",
    error_code: int | None = None,
    error_message: str | None = None,
    latency_ms: float = 0.0,
    via: str = "backend",
    route_hint: str | None = None,
    ts: datetime | None = None,
    identity: tuple[str | None, str | None] | None = None,
) -> dict:
    """Write one audit row and publish it to live listeners. Returns the row."""
    params = params or {}
    meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}

    caller_name, caller_version = attr.client_info_from_meta(meta)
    if not caller_name and identity:
        caller_name, caller_version = identity
    source = attr.source_for(caller_name, route_hint)
    when = ts or datetime.now(UTC).replace(tzinfo=None)

    with ObsSessionLocal() as db:
        row = McpCall(
            ts=when,
            source=source,
            caller_name=caller_name,
            caller_version=caller_version,
            conversation_id=attr.conversation_from_meta(meta),
            episode=_next_episode(db, source, when),
            method=method,
            resource_type=_RESOURCE_TYPE.get(method),
            resource_name=_name_for(method, params),
            args_preview=_args_preview(params, settings.audit_args_max_chars),
            status=status,
            error_code=error_code,
            error_message=(error_message or None) and str(error_message)[:500],
            latency_ms=latency_ms,
            protocol_version=meta.get("io.modelcontextprotocol/protocolVersion"),
            trace_id=attr.trace_id_from_meta(meta),
            via=via,
            extra_meta=attr.extra_meta(meta, settings.audit_meta_max_chars),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        payload = row.as_dict()

    hub.publish(payload)
    return payload


def _next_episode(db: Any, source: str, when: datetime) -> int:
    """Group calls from one source separated by an idle gap.

    An inferred reading aid, never an identity — MCP carries no conversation id
    for external hosts, and a gap in time is not a conversation boundary.
    """
    from sqlalchemy import select

    stmt = (
        select(McpCall.episode, McpCall.ts)
        .where(McpCall.source == source)
        .order_by(McpCall.ts.desc())
        .limit(1)
    )
    previous = db.execute(stmt).first()
    if previous is None:
        return 1
    last_episode, last_ts = previous
    if (when - last_ts).total_seconds() > settings.episode_idle_gap_s:
        return int(last_episode) + 1
    return int(last_episode)


class CallRecorderMiddleware:
    """Pure-ASGI wrapper around the MCP app."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        body = bytearray()
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.request":
                body.extend(message.get("body", b""))
                more = message.get("more_body", False)
            elif message["type"] == "http.disconnect":
                more = False

        replayed = {"done": False}

        async def replay() -> dict:
            """Hand the buffered body over once, then defer to the real stream.

            Delegating afterwards matters: the transport keeps awaiting
            ``receive`` to notice a client disconnect, and answering that with a
            synthetic ``http.disconnect`` makes it abandon the request before it
            has sent a response.
            """
            if not replayed["done"]:
                replayed["done"] = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        request: dict[str, Any] = {}
        try:
            parsed = json.loads(bytes(body) or b"{}")
            if isinstance(parsed, dict):
                request = parsed
        except (json.JSONDecodeError, UnicodeDecodeError):
            request = {}

        method = str(request.get("method") or "")
        params = request.get("params") if isinstance(request.get("params"), dict) else {}

        state: dict[str, Any] = {
            "status": 200,
            "chunks": bytearray(),
            "json": False,
            "session_id": None,
        }
        started = time.perf_counter()

        async def capture(message: dict) -> None:
            if message["type"] == "http.response.start":
                state["status"] = message.get("status", 200)
                headers = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in message.get("headers", [])
                }
                state["json"] = "application/json" in headers.get("content-type", "")
                # The 2026-07-28 transport has no sessions, but the legacy
                # compatibility path still mints one — and it is the only thing
                # that ties a bridged host's later calls back to the identity it
                # gave at `initialize`.
                state["session_id"] = headers.get("mcp-session-id")
            elif message["type"] == "http.response.body" and state["json"]:
                # Bounded: only enough to read a JSON-RPC error object.
                if len(state["chunks"]) < 65_536:
                    state["chunks"].extend(message.get("body", b""))
            await send(message)

        request_session = _header(scope, "mcp-session-id")

        try:
            await self.app(scope, replay, capture)
        finally:
            if method:
                elapsed = (time.perf_counter() - started) * 1000
                status, code, message_text = _outcome(state)

                # A legacy `initialize` carries identity in its params; remember
                # it against the session the server just issued, so the calls
                # that follow are attributable too.
                identity: tuple[str | None, str | None] | None = None
                if method == "initialize":
                    identity = attr.client_info_from_params(params)
                    remember_session_identity(
                        state.get("session_id") or request_session or "", *identity
                    )
                elif request_session:
                    identity = identity_for_session(request_session)

                try:
                    record(
                        method=method,
                        params=params,
                        identity=identity,
                        status=status,
                        error_code=code,
                        error_message=message_text,
                        latency_ms=elapsed,
                        route_hint=scope.get("headers") and _header(scope, "x-mcp-source"),
                    )
                except Exception as exc:  # noqa: BLE001 - auditing must never 500 a call
                    log.warning("audit record failed for %s: %s", method, exc)


def _header(scope: dict, name: str) -> str | None:
    target = name.encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == target:
            return value.decode("latin-1")
    return None


def _outcome(state: dict) -> tuple[str, int | None, str | None]:
    """Derive (status, error_code, message) from the captured response."""
    if state["status"] >= 400:
        code, message = _jsonrpc_error(state["chunks"])
        return "error", code, message or f"HTTP {state['status']}"
    code, message = _jsonrpc_error(state["chunks"])
    if code is not None:
        return "error", code, message
    return "ok", None, None


def _jsonrpc_error(raw: bytearray) -> tuple[int | None, str | None]:
    if not raw:
        return None, None
    try:
        parsed = json.loads(bytes(raw))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, None
    if not isinstance(parsed, dict):
        return None, None
    error = parsed.get("error")
    if isinstance(error, dict):
        return error.get("code"), error.get("message")
    # A tool that failed reports isError on an otherwise successful response.
    result = parsed.get("result")
    if isinstance(result, dict) and result.get("isError"):
        return None, "tool reported an error"
    return None, None
