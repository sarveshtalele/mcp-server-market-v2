"""SPECS GOV-1..GOV-3 — the gateway path, against a running agentgateway.

These are the assertions that cannot be made in-process: that the gateway is new
enough to speak this revision, that it forwards the protocol faithfully, that the
allowlist actually blocks, and what it does *not* forward.

Skipped unless a gateway is reachable, so the default suite stays hermetic:

    pytest -m gateway

Point them elsewhere with MCP_GATEWAY_URL. They also need the backend running,
because the gateway forwards to it.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import pytest
from mcp import Client, Implementation

from core.config import PROTOCOL_VERSION

GATEWAY_URL = os.environ.get("MCP_GATEWAY_URL", "http://127.0.0.1:3111/mcp")


def _reachable(url: str) -> bool:
    parsed = urlparse(url)
    try:
        with socket.create_connection(
            (parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=1
        ):
            return True
    except OSError:
        return False


# A loud skip, naming the prerequisite: a silent skip reads like a pass.
pytestmark = [
    pytest.mark.gateway,
    pytest.mark.skipif(
        not _reachable(GATEWAY_URL),
        reason=(
            f"no agentgateway at {GATEWAY_URL} — start it with "
            "`python scripts/dev.py gateway` (and the backend it forwards to)"
        ),
    ),
]


def _client(name: str = "pytest-gateway") -> Client:
    return Client(
        GATEWAY_URL,
        client_info=Implementation(name=name, version="1.0.0"),
        mode=PROTOCOL_VERSION,
        raise_exceptions=True,
    )


async def test_protocol_survives_the_gateway_hop() -> None:
    """GOV-2.2 / GOV-2.3 — the revision is negotiated through the proxy."""
    async with _client() as client:
        assert client.protocol_version == PROTOCOL_VERSION


async def test_tools_are_proxied() -> None:
    """GOV-2.2 — every allowlisted tool reaches the client."""
    async with _client() as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert "get_company" in names
    assert "read_market_resource" in names
    assert len(names) == 11


async def test_tool_call_returns_real_data_through_the_gateway() -> None:
    import json

    async with _client() as client:
        result = await client.call_tool("get_company", {"symbol": "AAPL"})
    assert json.loads(result.content[0].text)["symbol"] == "AAPL"


async def test_gateway_does_not_proxy_resources_or_prompts() -> None:
    """The measured limitation, pinned as a test.

    agentgateway 1.4.1 answers these with empty arrays even though the server
    declares five resources and two prompts. If a future gateway starts
    forwarding them, this test fails — which is the signal to retire the
    `read_market_resource` bridge. See CLAUDE.md §9.
    """
    async with _client() as client:
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts = await client.list_prompts()

    if resources.resources or templates.resource_templates or prompts.prompts:
        pytest.fail(
            "The gateway now proxies resources/prompts — good news. Retire the "
            "bridge tools in modules/listings/bridge.py and update CLAUDE.md §9."
        )


async def test_gateway_rewrites_cache_hints() -> None:
    """Also measured: the server's ttlMs/cacheScope do not survive the hop."""
    async with _client() as client:
        listing = (await client.list_tools(cache_mode="skip")).model_dump(by_alias=True)
    assert listing["resultType"] == "complete"
    # Documented so a change in behaviour is noticed rather than assumed.
    assert listing["ttlMs"] == 0
    assert listing["cacheScope"] == "private"


async def test_resource_bridge_works_through_the_gateway() -> None:
    """The bridge exists precisely because the native surface does not survive."""
    import json

    async with _client() as client:
        result = await client.call_tool(
            "read_market_resource", {"uri": "market://companies/AAPL"}
        )
    assert json.loads(result.content[0].text)["symbol"] == "AAPL"


async def test_calls_through_the_gateway_are_attributed() -> None:
    """OBS-2.3 — the whole point: a host's identity reaches the audit log."""
    import httpx2

    backend = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
    async with _client(name="claude-desktop") as client:
        await client.call_tool("list_sectors")

    payload = httpx2.get(
        f"{backend}/observability/calls?source=claude-desktop&limit=1", timeout=10
    ).json()
    assert payload["total"] >= 1
    assert payload["calls"][0]["source"] == "claude-desktop"
