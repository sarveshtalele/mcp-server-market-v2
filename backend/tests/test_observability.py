"""SPECS OBS-1..OBS-5 — the centralized, cross-host audit log."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx2
import pytest

from core.config import PROTOCOL_VERSION, settings
from modules.observability import attribution as attr
from modules.observability import repository as repo
from modules.observability.ingester import parse_line
from modules.observability.models import McpCall
from modules.observability.recorder import record

# --- attribution -----------------------------------------------------------


@pytest.mark.parametrize(
    ("client_name", "expected"),
    [
        ("control-room", "control-room"),
        ("Claude Code", "claude-code"),
        ("claude-desktop", "claude-desktop"),
        ("Visual Studio Code - Copilot Chat", "vscode-copilot"),
        ("Antigravity", "antigravity"),
        ("mcp-remote", "mcp-remote-bridge"),
    ],
)
def test_known_clients_resolve_to_a_source(client_name, expected) -> None:
    """OBS-2.1 / OBS-2.3."""
    assert attr.source_for(client_name) == expected


def test_unknown_client_is_never_guessed() -> None:
    """OBS-2.5 — an unattributed call must look unattributed."""
    assert attr.source_for(None) == "unknown"
    assert attr.source_for("") == "unknown"
    assert attr.source_for("Some Unreleased Host 4.2") == "unknown"


def test_route_hint_is_the_fallback() -> None:
    """OBS-2.4 — for hosts whose bridge strips clientInfo."""
    assert attr.source_for(None, route_hint="antigravity") == "antigravity"
    assert attr.source_for("Unknown Host", route_hint="claude-desktop") == "claude-desktop"


def test_client_info_extraction() -> None:
    meta = {"io.modelcontextprotocol/clientInfo": {"name": "control-room", "version": "2.0.0"}}
    assert attr.client_info_from_meta(meta) == ("control-room", "2.0.0")
    assert attr.client_info_from_meta({}) == (None, None)
    assert attr.client_info_from_meta(None) == (None, None)


def test_conversation_id_from_baggage() -> None:
    """OBS-2a.1 — only a client we control can supply one."""
    assert attr.conversation_from_meta({"baggage": "conversationId=abc-123"}) == "abc-123"
    assert attr.conversation_from_meta({"baggage": "x=1,conversationId=c9,y=2"}) == "c9"
    assert attr.conversation_from_meta({"baggage": "other=1"}) is None
    assert attr.conversation_from_meta({}) is None


def test_conversation_id_from_a_vendor_meta_key() -> None:
    """OBS-2b.2 — a host that starts sending one is picked up with no code change."""
    meta = {"com.example.mcp/conversationId": "thread-77"}
    assert attr.conversation_from_meta(meta) == "thread-77"


def test_trace_id_from_traceparent() -> None:
    """OBS-5.3."""
    traceparent = "00-0af7651916cd43dd8448eb211c80319c-00f067aa0ba902b7-01"
    assert attr.trace_id_from_meta({"traceparent": traceparent}) == (
        "0af7651916cd43dd8448eb211c80319c"
    )
    assert attr.trace_id_from_meta({"traceparent": "garbage"}) is None


def test_unrecognised_meta_is_preserved_and_capped() -> None:
    """OBS-2b.1 / OBS-2b.3."""
    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "com.vendor/custom": "keep-me",
    }
    extra = attr.extra_meta(meta, limit=1000)
    assert extra is not None
    assert json.loads(extra) == {"com.vendor/custom": "keep-me"}
    # Reserved protocol keys are not duplicated into the blob.
    assert "protocolVersion" not in extra

    long_meta = {"com.vendor/big": "x" * 5000}
    assert len(attr.extra_meta(long_meta, limit=100)) == 100


# --- recording -------------------------------------------------------------


def _meta(name="control-room", version="2.0.0", **extra):
    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": name, "version": version},
    }
    meta.update(extra)
    return meta


def test_record_writes_one_row_with_full_detail(obs_db) -> None:
    """OBS-1.1 / OBS-1.2."""
    row = record(
        method="tools/call",
        params={
            "name": "get_company",
            "arguments": {"symbol": "AAPL"},
            "_meta": _meta(baggage="conversationId=conv-1"),
        },
        latency_ms=12.5,
    )
    assert row["source"] == "control-room"
    assert row["caller_name"] == "control-room"
    assert row["method"] == "tools/call"
    assert row["resource_type"] == "tool"
    assert row["resource_name"] == "get_company"
    assert row["conversation_id"] == "conv-1"
    assert row["status"] == "ok"
    assert row["latency_ms"] == 12.5
    assert row["protocol_version"] == PROTOCOL_VERSION
    assert json.loads(row["args_preview"]) == {"symbol": "AAPL"}

    assert obs_db.query(McpCall).count() == 1


def test_arguments_are_truncated(obs_db) -> None:
    """OBS-1.3 — the audit DB stores previews, never whole payloads."""
    row = record(
        method="tools/call",
        params={
            "name": "compare_companies",
            "arguments": {"symbols": ["AAA"] * 500},
            "_meta": _meta(),
        },
    )
    assert len(row["args_preview"]) <= settings.audit_args_max_chars + 40
    assert "chars]" in row["args_preview"]


def test_resource_and_prompt_calls_are_classified(obs_db) -> None:
    """OBS-1.6 — not just tools/call."""
    resource = record(
        method="resources/read",
        params={"uri": "market://companies/AAPL", "_meta": _meta()},
    )
    assert resource["resource_type"] == "resource"
    assert resource["resource_name"] == "market://companies/AAPL"

    prompt = record(method="prompts/get", params={"name": "analyze-equity", "_meta": _meta()})
    assert prompt["resource_type"] == "prompt"
    assert prompt["resource_name"] == "analyze-equity"


def test_unknown_caller_is_recorded_as_unknown(obs_db) -> None:
    """OBS-2.5."""
    row = record(method="tools/list", params={"_meta": {}})
    assert row["source"] == "unknown"
    assert row["caller_name"] is None


def test_episodes_group_by_idle_gap(obs_db) -> None:
    """OBS-2c.1 — an inferred reading aid, never an identity."""
    now = datetime(2026, 8, 20, 12, 0, 0)
    first = record(method="tools/list", params={"_meta": _meta()}, ts=now)
    close = record(
        method="tools/list",
        params={"_meta": _meta()},
        ts=now + timedelta(seconds=settings.episode_idle_gap_s - 5),
    )
    far = record(
        method="tools/list",
        params={"_meta": _meta()},
        ts=now + timedelta(seconds=settings.episode_idle_gap_s * 3),
    )
    assert close["episode"] == first["episode"]
    assert far["episode"] == first["episode"] + 1


def test_episodes_are_per_source(obs_db) -> None:
    now = datetime(2026, 8, 20, 12, 0, 0)
    record(method="tools/list", params={"_meta": _meta("control-room")}, ts=now)
    other = record(method="tools/list", params={"_meta": _meta("Claude Code")}, ts=now)
    assert other["source"] == "claude-code"
    assert other["episode"] == 1


# --- queries ---------------------------------------------------------------


def _seed_rows() -> None:
    record(
        method="tools/call",
        params={"name": "get_company", "arguments": {"symbol": "AAPL"}, "_meta": _meta()},
        latency_ms=10.0,
    )
    record(
        method="tools/call",
        params={"name": "get_company", "_meta": _meta("Claude Code")},
        latency_ms=30.0,
    )
    record(
        method="tools/call",
        params={"name": "sector_ranking", "_meta": _meta("Antigravity")},
        status="error",
        error_code=-32602,
        error_message="nope",
        latency_ms=50.0,
    )


def test_query_filters(obs_db) -> None:
    """OBS-4.1."""
    _seed_rows()
    rows, total = repo.query_calls(obs_db, source="claude-code")
    assert total == 1 and rows[0].source == "claude-code"

    rows, total = repo.query_calls(obs_db, tool="get_company")
    assert total == 2

    rows, total = repo.query_calls(obs_db, status="error")
    assert total == 1 and rows[0].error_code == -32602


def test_query_is_newest_first_and_paginates(obs_db) -> None:
    _seed_rows()
    page_one, total = repo.query_calls(obs_db, limit=2, offset=0)
    page_two, _ = repo.query_calls(obs_db, limit=2, offset=2)
    assert total == 3
    assert len(page_one) == 2 and len(page_two) == 1
    assert page_one[0].ts >= page_one[1].ts


def test_summary_matches_the_rows(obs_db) -> None:
    """OBS-4.2."""
    _seed_rows()
    summary = repo.summary(obs_db)
    assert summary["total_calls"] == 3
    assert summary["error_count"] == 1
    assert summary["error_rate_pct"] == pytest.approx(33.33, abs=0.1)
    assert summary["by_source"] == {
        "control-room": 1,
        "claude-code": 1,
        "antigravity": 1,
    }
    assert summary["by_tool"]["get_company"] == 2
    assert summary["latency_p95_ms"] >= summary["latency_p50_ms"]


def test_callers_seen(obs_db) -> None:
    _seed_rows()
    callers = repo.callers_seen(obs_db, since_minutes=60)
    assert {c["source"] for c in callers} == {
        "control-room",
        "claude-code",
        "antigravity",
    }


def test_retention_prunes_by_age(obs_db) -> None:
    """OBS-3.3."""
    old = datetime.utcnow() - timedelta(days=settings.audit_max_age_days + 1)
    record(method="tools/list", params={"_meta": _meta()}, ts=old)
    record(method="tools/list", params={"_meta": _meta()})
    assert obs_db.query(McpCall).count() == 2

    removed = repo.prune(obs_db)
    assert removed == 1
    assert obs_db.query(McpCall).count() == 1


# --- the ingester ----------------------------------------------------------


def test_ingester_parses_a_gateway_line() -> None:
    """OBS-1 — field mapping for agentgateway's documented log schema."""
    line = json.dumps(
        {
            "timestamp": "2026-08-20T12:00:00Z",
            "mcp.method.name": "tools/call",
            "gen_ai.tool.name": "get_company",
            "mcp.tool.error": "tool not allowed by policy",
            "duration_ms": 3,
            "mcp.client.name": "claude-desktop",
        }
    )
    parsed = parse_line(line)
    assert parsed is not None
    assert parsed["method"] == "tools/call"
    assert parsed["status"] == "error"
    assert parsed["via"] == "gateway"
    assert parsed["params"]["name"] == "get_company"
    assert parsed["ts"] == datetime(2026, 8, 20, 12, 0, 0)


def test_ingester_skips_unparseable_lines() -> None:
    assert parse_line("") is None
    assert parse_line("not json") is None
    assert parse_line('{"unrelated": true}') is None


def test_ingester_records_only_denials(obs_db, tmp_path) -> None:
    """The backend recorder already saw everything it served.

    A gateway denial never reaches the backend, so that is the one thing worth
    ingesting — otherwise every call would be counted twice.
    """
    from modules.observability.ingester import GatewayLogIngester

    log_file = tmp_path / "access.log"
    log_file.write_text(
        "\n".join(
            [
                json.dumps({"mcp.method.name": "tools/call", "gen_ai.tool.name": "ok_tool"}),
                json.dumps(
                    {
                        "mcp.method.name": "tools/call",
                        "gen_ai.tool.name": "blocked_tool",
                        "mcp.tool.error": "denied by policy",
                        "mcp.client.name": "antigravity",
                    }
                ),
            ]
        )
        + "\n"
    )
    ingester = GatewayLogIngester(path=log_file)
    assert ingester.poll_once() == 1
    assert ingester.poll_once() == 0  # OBS-3.2: no double ingest

    rows, total = repo.query_calls(obs_db, status="error")
    assert total == 1
    assert rows[0].resource_name == "blocked_tool"
    assert rows[0].source == "antigravity"
    assert rows[0].via == "gateway"


def test_ingester_handles_a_missing_file(tmp_path) -> None:
    from modules.observability.ingester import GatewayLogIngester

    assert GatewayLogIngester(path=tmp_path / "nope.log").poll_once() == 0


# --- the HTTP surface ------------------------------------------------------


def test_calls_api_records_real_traffic(live_server) -> None:
    """OBS-1.1 / OBS-4.1 — a real MCP call over HTTP lands in the log."""
    before = httpx2.get(f"{live_server}/observability/calls", timeout=10).json()["total"]

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_company",
            "arguments": {"symbol": "AAPL"},
            "_meta": {
                **_meta(baggage="conversationId=web-1"),
                # Required on every request by the 2026-07-28 spec; the server
                # rejects a request without it with -32602.
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    response = httpx2.post(
        f"{live_server}/mcp",
        json=body,
        headers={
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "Mcp-Method": "tools/call",
            "Mcp-Name": "get_company",
        },
        timeout=10,
    )
    assert response.status_code == 200

    payload = httpx2.get(
        f"{live_server}/observability/calls?tool=get_company&limit=5", timeout=10
    ).json()
    assert payload["total"] > before - 1
    latest = payload["calls"][0]
    assert latest["source"] == "control-room"
    assert latest["conversation_id"] == "web-1"
    assert latest["method"] == "tools/call"
    assert latest["latency_ms"] >= 0


def test_summary_and_servers_endpoints(live_server) -> None:
    """OBS-4.2 / UI-5.5."""
    summary = httpx2.get(f"{live_server}/observability/summary", timeout=10).json()
    assert "by_source" in summary and "latency_p95_ms" in summary

    servers = httpx2.get(f"{live_server}/observability/servers", timeout=10).json()
    assert servers["server"]["protocol_version"] == PROTOCOL_VERSION
    assert len(servers["server"]["tools"]) == 11
    assert servers["gateway"]["url"].endswith("/mcp")
    # The gateway config ships with all nine tools allowlisted.
    assert servers["gateway"]["allowlist_matches_tools"] in (True, None)


def test_gateway_logs_raw_is_still_available(live_server) -> None:
    """OBS-4.4 — the escape hatch survives."""
    response = httpx2.get(f"{live_server}/observability/gateway-logs/raw", timeout=10)
    assert response.status_code == 200
    assert "stdout" in response.text
