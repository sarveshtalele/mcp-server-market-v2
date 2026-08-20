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


def test_unsupported_protocol_version_is_rejected(live_server) -> None:
    """MCP-3.4 — the server is 2026-07-28 only (decision D-3)."""
    body = _rpc("tools/list")
    body["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] = "2025-11-25"
    response = httpx2.post(
        f"{live_server}/mcp",
        json=body,
        headers=_headers("tools/list", **{"MCP-Protocol-Version": "2025-11-25"}),
        timeout=10,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32022


def test_legacy_initialize_handshake_is_refused(live_server) -> None:
    """MCP-5 — no handshake support; this revision is stateless."""
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
    assert response.status_code >= 400


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
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "stock-exchange"
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
