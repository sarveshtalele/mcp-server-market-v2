"""SPECS MCP-2, MCP-4, RES-1, PROMPT-1 — protocol conformance for 2026-07-28."""

from __future__ import annotations

import json

import pytest
from mcp import Implementation
from mcp.shared.exceptions import MCPError

from core.config import PROTOCOL_VERSION
from tests.conftest import connected

EXPECTED_TOOLS = {
    "get_company",
    "search_companies",
    "list_sectors",
    "get_filings",
    "get_latest_filing",
    "calc_financial_ratios",
    "calc_revenue_growth",
    "compare_companies",
    "sector_ranking",
    "list_market_resources",
    "read_market_resource",
}


async def test_protocol_version_is_2026_07_28(mcp_server) -> None:
    """MCP-2.2 — the negotiated revision is the one this project targets."""
    async with connected(mcp_server) as client:
        assert client.protocol_version == PROTOCOL_VERSION


async def test_server_identity_and_instructions(mcp_server) -> None:
    """MCP-2.4 / MCP-2.5."""
    async with connected(mcp_server) as client:
        assert client.server_info.name == "mcp-market-mcp-server"
        assert "ONLY source of truth" in client.instructions
        assert "synthetic" in client.instructions


async def test_capabilities_cover_all_three_surfaces(mcp_server) -> None:
    """MCP-2.3."""
    async with connected(mcp_server) as client:
        caps = client.server_capabilities
        assert caps.tools is not None
        assert caps.resources is not None
        assert caps.prompts is not None


async def test_tools_list_contents(mcp_server) -> None:
    """TOOL-1.1 — all nine tools are exposed."""
    async with connected(mcp_server) as client:
        listing = await client.list_tools()
    assert {t.name for t in listing.tools} == EXPECTED_TOOLS


async def test_tools_list_ordering_is_deterministic(mcp_server) -> None:
    """MCP-4.2 — ordering is stable across calls and across fresh servers.

    Order comes from the registry (priority, then module name) and then
    declaration order within a module, which is reproducible. That is what lets
    a client cache the list and keeps LLM prompt-cache hit rates up.
    """
    from mcp_server.server import build_server

    async with connected(mcp_server) as client:
        first = [t.name for t in (await client.list_tools()).tools]
        second = [t.name for t in (await client.list_tools(cache_mode="skip")).tools]
    assert first == second

    async with connected(build_server()) as other:
        assert [t.name for t in (await other.list_tools()).tools] == first


async def test_cacheable_results_carry_ttl_and_scope(mcp_server) -> None:
    """MCP-4.3 / MCP-4.4 — CacheableResult fields are required in this revision."""
    async with connected(mcp_server) as client:
        results = {
            "tools/list": await client.list_tools(cache_mode="skip"),
            "resources/list": await client.list_resources(cache_mode="skip"),
            "resources/templates/list": await client.list_resource_templates(cache_mode="skip"),
            "prompts/list": await client.list_prompts(),
            "resources/read": await client.read_resource("market://sectors", cache_mode="skip"),
        }
    for method, result in results.items():
        dumped = result.model_dump(by_alias=True)
        assert dumped["ttlMs"] == 3_600_000, method
        assert dumped["cacheScope"] == "public", method


async def test_results_declare_result_type(mcp_server) -> None:
    """MCP-4.1 — every result carries resultType."""
    async with connected(mcp_server) as client:
        listing = await client.list_tools(cache_mode="skip")
        called = await client.call_tool("list_sectors")
    assert listing.model_dump(by_alias=True)["resultType"] == "complete"
    assert called.model_dump(by_alias=True)["resultType"] == "complete"


async def test_tool_schemas_are_json_schema(mcp_server) -> None:
    """TOOL-1.3 — schemas are real JSON Schema derived from typed signatures."""
    async with connected(mcp_server) as client:
        listing = await client.list_tools()
    by_name = {t.name: t for t in listing.tools}

    company = by_name["get_company"].input_schema
    assert company["type"] == "object"
    assert "symbol" in company["properties"]
    assert company["required"] == ["symbol"]

    compare = by_name["compare_companies"].input_schema
    assert compare["properties"]["symbols"]["type"] == "array"
    # The Context parameter is injected by the SDK and must never leak into the
    # schema the model sees.
    assert "ctx" not in compare["properties"]

    # Optional arguments must not be marked required.
    assert by_name["get_filings"].input_schema["required"] == ["symbol"]


# --- resources -------------------------------------------------------------


async def test_static_resources(mcp_server) -> None:
    """RES-1.1."""
    async with connected(mcp_server) as client:
        listing = await client.list_resources()
    assert {str(r.uri) for r in listing.resources} == {
        "market://companies",
        "market://sectors",
    }


async def test_resource_templates(mcp_server) -> None:
    """RES-1.1."""
    async with connected(mcp_server) as client:
        listing = await client.list_resource_templates()
    assert {t.uri_template for t in listing.resource_templates} == {
        "market://companies/{symbol}",
        "market://filings/{symbol}/latest",
        "market://filings/{symbol}/{period}",
    }


async def test_resource_matches_tool_payload(mcp_server) -> None:
    """RES-1.2 — the two surfaces must never drift apart."""
    async with connected(mcp_server) as client:
        resource = await client.read_resource("market://companies/AAPL")
        tool = await client.call_tool("get_company", {"symbol": "AAPL"})
    assert json.loads(resource.contents[0].text) == json.loads(tool.content[0].text)


async def test_unknown_resource_is_invalid_params(mcp_server) -> None:
    """RES-1.4 / MCP-4.5 — resource-not-found moved from -32002 to -32602."""
    async with connected(mcp_server) as client:
        with pytest.raises(MCPError) as excinfo:
            await client.read_resource("market://companies/NOPE")
    assert excinfo.value.error.code == -32602


async def test_resource_rejects_path_traversal(mcp_server) -> None:
    """RES-1.3 — RFC 6570 templates must not resolve outside their space."""
    async with connected(mcp_server) as client:
        with pytest.raises(MCPError) as excinfo:
            await client.read_resource("market://companies/../../etc/passwd")
    assert excinfo.value.error.code == -32602


async def test_filing_period_resource(mcp_server) -> None:
    """RES-1 — the two-parameter template resolves a specific fiscal period."""
    async with connected(mcp_server) as client:
        listing = await client.call_tool(
            "get_filings", {"symbol": "AAPL", "filing_type": "Quarterly"}
        )
        period = json.loads(listing.content[0].text)["fiscal_period"]
        resource = await client.read_resource(f"market://filings/AAPL/{period}")
    assert json.loads(resource.contents[0].text)["fiscal_period"] == period


async def test_unknown_filing_period_is_invalid_params(mcp_server) -> None:
    async with connected(mcp_server) as client:
        with pytest.raises(MCPError) as excinfo:
            await client.read_resource("market://filings/AAPL/1999Q1")
    assert excinfo.value.error.code == -32602


# --- prompts ---------------------------------------------------------------


async def test_prompts_are_declared(mcp_server) -> None:
    """PROMPT-1.1."""
    async with connected(mcp_server) as client:
        listing = await client.list_prompts()
    by_name = {p.name: p for p in listing.prompts}
    assert set(by_name) == {"analyze-equity", "compare-stocks"}
    assert [a.name for a in by_name["analyze-equity"].arguments] == ["symbol"]


async def test_prompt_renders_its_argument(mcp_server) -> None:
    """PROMPT-1.2."""
    async with connected(mcp_server) as client:
        result = await client.get_prompt("analyze-equity", {"symbol": "aapl"})
    text = result.messages[0].content.text
    assert "AAPL" in text
    assert "market://companies/AAPL" in text
    assert "synthetic" in text


async def test_prompt_missing_argument_is_an_error(mcp_server) -> None:
    """PROMPT-1.3 — with a documented deviation.

    The spec calls for -32602 (Invalid params). The SDK validates prompt
    arguments before the handler runs and reports the failure as -32603
    (Internal error). That is SDK behaviour, not something this server chooses,
    so the assertion records what actually happens rather than pretending.
    See CLAUDE.md §9.
    """
    async with connected(mcp_server) as client:
        with pytest.raises(MCPError) as excinfo:
            await client.get_prompt("analyze-equity", {})
    assert excinfo.value.error.code in (-32602, -32603)
    assert "symbol" in str(excinfo.value.error.message)


# --- tools -----------------------------------------------------------------


async def test_unknown_tool_reports_is_error(mcp_server) -> None:
    """An unknown tool is a tool-level failure, not a transport failure."""
    async with connected(mcp_server) as client:
        result = await client.call_tool("no_such_tool", {})
    assert result.is_error is True


async def test_missing_symbol_is_a_normal_result(mcp_server) -> None:
    """TOOL-1.5 — a missing ticker is an answer, not a protocol error."""
    async with connected(mcp_server) as client:
        result = await client.call_tool("get_company", {"symbol": "NOPE"})
    assert result.is_error is False
    assert json.loads(result.content[0].text) == {"error": "Company 'NOPE' not found"}


async def test_client_info_is_carried_per_request(mcp_server) -> None:
    """MCP-2 — identity travels on every request, not just at a handshake."""
    async with connected(
        mcp_server, client_info=Implementation(name="probe", version="9.9")
    ) as client:
        assert client.client_info.name == "probe"
        assert (await client.list_tools()).tools
