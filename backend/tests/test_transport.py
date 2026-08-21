"""SPECS MCP-1, MCP-3 — Streamable HTTP transport behaviour, over real HTTP."""

from __future__ import annotations

import json

import httpx2
import pytest
from mcp import Implementation

from core.config import PROTOCOL_VERSION
from tests.conftest import connected


def _rpc(method: str, params: dict | None = None) -> dict:
    body: dict = {"jsonrpc": "2.0", "id": 1, "method": method}
    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "pytest-raw", "version": "1.0"},
    }
    body["params"] = {**(params or {}), "_meta": meta}
    return body


def _headers(method: str, name: str | None = None, **extra: str) -> dict:
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name:
        headers["Mcp-Name"] = name
    headers.update(extra)
    return headers


def test_get_and_delete_are_method_not_allowed(live_server) -> None:
    """MCP-1.2 — the GET stream and DELETE termination left the transport."""
    for verb in ("GET", "DELETE"):
        response = httpx2.request(verb, f"{live_server}/mcp", timeout=10)
        assert response.status_code == 405, verb
        assert "2026-07-28" in response.text


def test_post_without_protocol_header_is_rejected(live_server) -> None:
    """MCP-3.1."""
    response = httpx2.post(
        f"{live_server}/mcp",
        json=_rpc("tools/list"),
        headers={
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        },
        timeout=10,
    )
    assert response.status_code == 400


def test_header_body_mismatch_is_rejected(live_server) -> None:
    """MCP-3.2 — mirrored headers must agree with the body they mirror."""
    body = _rpc("tools/call", {"name": "list_sectors", "arguments": {}})
    response = httpx2.post(
        f"{live_server}/mcp",
        json=body,
        headers=_headers("tools/call", name="get_company"),  # wrong name
        timeout=10,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32020


async def test_strict_mode_rejects_an_older_revision() -> None:
    """MCP-3.4 / MCP-5 — what STRICT_PROTOCOL=true actually enforces.

    Exercised against the guard directly rather than the running server, so the
    assertion holds regardless of how the deployment is configured. The shipped
    default is dual-revision; see the test below for why.
    """
    from app.middleware import ProtocolGuardMiddleware

    sent: list[dict] = []

    async def receive():
        body = json.dumps(_rpc("tools/list")).encode()
        body = body.replace(PROTOCOL_VERSION.encode(), b"2025-11-25")
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    async def never_called(scope, receive_, send_):  # pragma: no cover
        raise AssertionError("the guard must not forward an unsupported revision")

    guard = ProtocolGuardMiddleware(never_called, version=PROTOCOL_VERSION, strict=True)
    await guard({"type": "http", "method": "POST", "headers": []}, receive, send)

    assert sent[0]["status"] == 400
    error = json.loads(sent[1]["body"])["error"]
    assert error["code"] == -32022
    assert error["data"]["supported"] == [PROTOCOL_VERSION]


async def test_strict_mode_rejects_the_legacy_handshake() -> None:
    """The reason the default is off: this is what bridged hosts hit."""
    from app.middleware import ProtocolGuardMiddleware

    sent: list[dict] = []

    async def receive():
        body = json.dumps(
            {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
        ).encode()
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    async def never_called(scope, receive_, send_):  # pragma: no cover
        raise AssertionError("the guard must not forward a legacy handshake")

    guard = ProtocolGuardMiddleware(never_called, version=PROTOCOL_VERSION, strict=True)
    await guard({"type": "http", "method": "POST", "headers": []}, receive, send)

    assert sent[0]["status"] == 400
    assert json.loads(sent[1]["body"])["error"]["code"] == -32022


def test_legacy_initialize_handshake_is_accepted_by_default(live_server) -> None:
    """MCP-5 — dual-revision is the default, and that default is load-bearing.

    `mcp-remote` — the bridge Claude Desktop and Antigravity use — opens with
    the legacy `initialize` handshake. Refusing it means neither host can
    connect at all, so STRICT_PROTOCOL defaults to false. Set it true only for
    single-revision conformance work.
    """
    response = httpx2.post(
        f"{live_server}/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "legacy", "version": "1.0"},
            },
        },
        headers={
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        },
        timeout=10,
    )
    assert response.status_code == 200, (
        "the legacy handshake must work out of the box or the bridged hosts break"
    )


def test_missing_client_capabilities_is_invalid_params(live_server) -> None:
    """MCP-3 — clientCapabilities is a required per-request _meta field."""
    body = _rpc("tools/list")
    del body["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"]
    response = httpx2.post(
        f"{live_server}/mcp", json=body, headers=_headers("tools/list"), timeout=10
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32602


def test_invalid_origin_is_forbidden(live_server) -> None:
    """MCP-1.5 — DNS-rebinding protection is mandatory for this transport."""
    response = httpx2.post(
        f"{live_server}/mcp",
        json=_rpc("tools/list"),
        headers=_headers("tools/list", Origin="http://evil.example.com"),
        timeout=10,
    )
    assert response.status_code == 403


def test_allowed_origin_passes(live_server) -> None:
    """MCP-1.5 — the configured browser origin is not blocked."""
    response = httpx2.post(
        f"{live_server}/mcp",
        json=_rpc("tools/list"),
        headers=_headers("tools/list", Origin="http://localhost:3000"),
        timeout=10,
    )
    assert response.status_code == 200


def test_session_and_resumption_headers_are_ignored(live_server) -> None:
    """MCP-1.3 / MCP-1.4 — no sessions, no stream resumption in this revision."""
    response = httpx2.post(
        f"{live_server}/mcp",
        json=_rpc("tools/list"),
        headers=_headers(
            "tools/list",
            **{"Mcp-Session-Id": "abc123", "Last-Event-ID": "42"},
        ),
        timeout=10,
    )
    assert response.status_code == 200
    assert "mcp-session-id" not in {k.lower() for k in response.headers}


def test_server_discover_over_http(live_server) -> None:
    """MCP-2.1 — discovery answers without any prior request."""
    response = httpx2.post(
        f"{live_server}/mcp",
        json=_rpc("server/discover"),
        headers=_headers("server/discover"),
        timeout=10,
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert PROTOCOL_VERSION in result["supportedVersions"]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 3_600_000
    assert result["cacheScope"] == "public"
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "mcp-market-mcp-server"
    assert "capabilities" in result


def test_rest_and_mcp_share_one_process(live_server) -> None:
    """MCP-1.1 — one service exposes REST, MCP and the audit API."""
    health = httpx2.get(f"{live_server}/health", timeout=10).json()
    assert health["protocol_version"] == PROTOCOL_VERSION
    assert health["data"] == "synthetic"
    assert httpx2.get(f"{live_server}/listings/sectors", timeout=10).status_code == 200
    assert httpx2.get(f"{live_server}/filings/AAPL", timeout=10).status_code == 200
    assert httpx2.get(f"{live_server}/observability/calls", timeout=10).status_code == 200


@pytest.mark.anyio
async def test_sdk_client_over_http(live_server) -> None:
    """The shipped client works against the real endpoint, not just in memory."""
    async with connected(
        f"{live_server}/mcp",
        client_info=Implementation(name="control-room", version="2.0.0"),
        mode=PROTOCOL_VERSION,
    ) as client:
        assert client.protocol_version == PROTOCOL_VERSION
        result = await client.call_tool("get_company", {"symbol": "AAPL"})
    assert json.loads(result.content[0].text)["symbol"] == "AAPL"
