"""SPECS CLI-1, AGENT-2 — the shipped MCP client: concurrency and progress."""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from core.config import PROTOCOL_VERSION
from mcp_client.session import MCPClientError, MCPToolClient, request_meta


def test_no_lock_serialises_tool_calls() -> None:
    """CLI-1.1 — the old client wrapped every call in an asyncio.Lock.

    The lock existed because one long-lived ClientSession was shared across
    concurrent web requests. Under 2026-07-28 there is no session to share, so
    the only lock left guards connection setup.
    """
    source = (
        __import__("pathlib").Path(__file__).resolve().parent.parent / "mcp_client" / "session.py"
    ).read_text()
    assert "_connect_lock" in source
    assert "async with self._lock" not in source


def test_request_meta_carries_a_conversation_id() -> None:
    """OBS-2a.1 — the W3C baggage key is the slot the spec reserves for this."""
    assert request_meta("conv-9") == {"baggage": "conversationId=conv-9"}
    assert request_meta(None) == {}


async def test_client_reports_a_useful_error_when_the_gateway_is_down() -> None:
    """A cold start must explain what to do, not raise a socket error."""
    client = MCPToolClient(url="http://127.0.0.1:9/mcp")
    with pytest.raises(MCPClientError) as excinfo:
        await client.connect()
    assert "agentgateway" in str(excinfo.value)
    assert "127.0.0.1:9" in str(excinfo.value)


async def test_client_talks_to_the_live_backend(live_server) -> None:
    """The client works end to end against the real endpoint."""
    client = MCPToolClient(url=f"{live_server}/mcp")
    try:
        await client.connect()
        assert client.protocol_version == PROTOCOL_VERSION
        assert len(client.tool_names) == 11

        payload = json.loads(await client.call_tool("get_company", {"symbol": "AAPL"}))
        assert payload["symbol"] == "AAPL"

        tools = client.openai_tools()
        assert tools[0]["type"] == "function"
        assert "parameters" in tools[0]["function"]

        caps = await client.capabilities()
        assert caps["protocol_version"] == PROTOCOL_VERSION
        assert len(caps["resource_templates"]) == 3
        assert caps["prompts"] == ["analyze-equity", "compare-stocks"]

        text = await client.read_resource("market://sectors")
        assert json.loads(text)

        prompt = await client.get_prompt("analyze-equity", {"symbol": "AAPL"})
        assert "AAPL" in prompt
    finally:
        await client.close()


async def test_concurrent_calls_are_not_serialised(live_server) -> None:
    """CLI-1.2 — the whole point of removing the lock.

    ``compare_companies`` is the slowest tool. Ten of them in parallel must
    finish in materially less than ten times one of them.
    """
    client = MCPToolClient(url=f"{live_server}/mcp")
    try:
        await client.connect()

        single_start = time.perf_counter()
        await client.call_tool("compare_companies", {"symbols": ["AAPL", "MSFT"]})
        single_ms = (time.perf_counter() - single_start) * 1000

        parallel_start = time.perf_counter()
        results = await asyncio.gather(
            *[
                client.call_tool("compare_companies", {"symbols": ["AAPL", "MSFT"]})
                for _ in range(10)
            ]
        )
        parallel_ms = (time.perf_counter() - parallel_start) * 1000

        assert len(results) == 10
        assert all(json.loads(r)["companies"] for r in results)
        assert parallel_ms < single_ms * 10, (
            f"10 parallel calls took {parallel_ms:.0f} ms; one takes {single_ms:.0f} ms "
            "— they are being serialised"
        )
    finally:
        await client.close()


async def test_progress_notifications_reach_the_caller(live_server) -> None:
    """AGENT-2.1 / AGENT-2.2 — progress flows on the request's own stream."""
    client = MCPToolClient(url=f"{live_server}/mcp")
    seen: list[tuple] = []

    async def on_progress(progress, total, message):
        seen.append((progress, total, message))

    try:
        await client.connect()
        await client.call_tool(
            "compare_companies",
            {"symbols": ["AAPL", "MSFT", "NVDA"]},
            progress_callback=on_progress,
        )
    finally:
        await client.close()

    assert len(seen) == 3
    assert [p for p, _, _ in seen] == [1.0, 2.0, 3.0]
    assert all(total == 3.0 for _, total, _ in seen)
    assert "AAPL" in seen[0][2]


async def test_conversation_id_is_recorded_for_our_own_client(live_server) -> None:
    """OBS-2a.1 / OBS-2a.3 — our calls link back to a specific conversation."""
    import httpx2

    client = MCPToolClient(url=f"{live_server}/mcp")
    try:
        await client.connect()
        await client.call_tool("get_company", {"symbol": "MSFT"}, conversation_id="thread-abc")
    finally:
        await client.close()

    payload = httpx2.get(
        f"{live_server}/observability/calls?conversation_id=thread-abc", timeout=10
    ).json()
    assert payload["total"] >= 1
    assert payload["calls"][0]["source"] == "control-room"
    assert payload["calls"][0]["conversation_id"] == "thread-abc"
