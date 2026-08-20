"""SPECS TOOL-1, DATA-2 — tool behaviour, REST parity and the no-exec rule."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import data
from core.errors import DataError
from tests.conftest import GOLDEN_SYMBOLS, connected

BACKEND_ROOT = Path(__file__).resolve().parent.parent


async def _call(client, name: str, arguments: dict | None = None):
    result = await client.call_tool(name, arguments or {})
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict) and "result" in structured:
        return structured["result"]
    texts = [b.text for b in result.content if getattr(b, "text", None)]
    if len(texts) == 1:
        return json.loads(texts[0])
    return [json.loads(t) for t in texts]


@pytest.mark.parametrize("symbol", GOLDEN_SYMBOLS)
async def test_get_company_shape(mcp_server, symbol) -> None:
    """TOOL-1.1 — the pinned symbol set resolves and keeps its shape."""
    async with connected(mcp_server) as client:
        company = await _call(client, "get_company", {"symbol": symbol})
    assert company["symbol"] == symbol
    assert set(company) == {
        "symbol",
        "company_name",
        "sector",
        "industry",
        "market",
        "listing_date",
        "par_value",
        "shares_outstanding",
        "last_price",
        "market_cap",
        "pe_ratio",
        "pb_ratio",
        "dividend_yield",
        "is_active",
    }


async def test_every_tool_answers(mcp_server) -> None:
    """TOOL-1.1 — each of the nine tools returns a usable payload."""
    async with connected(mcp_server) as client:
        assert (await _call(client, "list_sectors"))[0]["company_count"] > 0
        assert len(await _call(client, "search_companies", {"sector": "Technology"})) > 0
        assert len(await _call(client, "get_filings", {"symbol": "AAPL"})) > 0
        assert (await _call(client, "get_latest_filing", {"symbol": "AAPL"}))["symbol"] == "AAPL"

        ratios = await _call(client, "calc_financial_ratios", {"symbol": "AAPL"})
        assert set(ratios) >= {"symbol", "profitability", "leverage", "valuation"}

        growth = await _call(client, "calc_revenue_growth", {"symbol": "AAPL"})
        assert growth["symbol"] == "AAPL"

        compared = await _call(client, "compare_companies", {"symbols": ["AAPL", "MSFT"]})
        assert len(compared["companies"]) == 2

        ranked = await _call(client, "sector_ranking", {"sector": "Technology", "top_n": 3})
        assert len(ranked["ranking"]) == 3


async def test_tool_matches_rest_endpoint(mcp_server, live_server) -> None:
    """TOOL-1.2 — decision D-2 must not change a single byte of output.

    Tools call repositories in-process now instead of looping back over HTTP.
    The REST endpoint is the reference: both paths serialise through the same
    Pydantic schema, so their JSON must be identical.
    """
    import httpx2

    async with connected(mcp_server) as client:
        for symbol in GOLDEN_SYMBOLS:
            tool = await _call(client, "get_company", {"symbol": symbol})
            rest = httpx2.get(f"{live_server}/listings/companies/{symbol}", timeout=10).json()
            assert tool == rest, symbol

        tool_sectors = await _call(client, "list_sectors")
        assert tool_sectors == httpx2.get(f"{live_server}/listings/sectors", timeout=10).json()

        tool_filings = await _call(client, "get_filings", {"symbol": "AAPL"})
        assert tool_filings == httpx2.get(f"{live_server}/filings/AAPL", timeout=10).json()


async def test_missing_data_returns_error_payload(mcp_server) -> None:
    """TOOL-1.5 — failures are answers, never unhandled exceptions."""
    async with connected(mcp_server) as client:
        assert "error" in await _call(client, "get_company", {"symbol": "ZZZZ"})
        assert "error" in await _call(client, "get_filings", {"symbol": "ZZZZ"})
        assert "error" in await _call(client, "calc_financial_ratios", {"symbol": "ZZZZ"})
        assert "error" in await _call(client, "sector_ranking", {"sector": "Nope"})
        assert "error" in await _call(
            client, "calc_financial_ratios", {"symbol": "AAPL", "fiscal_period": "1999Q9"}
        )


def test_data_layer_raises_data_error() -> None:
    """DATA-2 — the data layer signals absence with one exception type."""
    with pytest.raises(DataError):
        data.get_company("ZZZZ")
    with pytest.raises(DataError):
        data.get_filings("ZZZZ")


def test_no_exec_anywhere_in_the_backend() -> None:
    """TOOL-1.4 — tool generation must not use dynamic code evaluation.

    Parsed with the AST rather than grepped: the word "exec()" appears in prose
    explaining why it was removed, and a text search would flag the explanation
    as the offence.
    """
    import ast

    offenders = []
    for path in BACKEND_ROOT.rglob("*.py"):
        if ".venv" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("exec", "eval", "compile")
            ):
                offenders.append(f"{path.relative_to(BACKEND_ROOT)}:{node.lineno}")
    assert not offenders, f"dynamic code evaluation found: {offenders}"


def test_nothing_writes_to_stdout() -> None:
    """CLAUDE.md invariant #2 — stdout is the stdio JSON-RPC channel."""
    offenders = []
    for path in BACKEND_ROOT.rglob("*.py"):
        if ".venv" in path.parts or "tests" in path.parts:
            continue
        # CLI entrypoints print to a terminal by design and are never imported
        # by the server; the rule protects the stdio JSON-RPC channel.
        if path.name in ("seed.py", "cli_chat.py"):
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            stripped = line.strip()
            if stripped.startswith("print(") or stripped.startswith("sys.stdout"):
                offenders.append(f"{path.relative_to(BACKEND_ROOT)}:{lineno}")
    assert not offenders, f"stdout writes found: {offenders}"
