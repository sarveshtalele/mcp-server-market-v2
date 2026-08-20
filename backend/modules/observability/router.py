"""Query API over the audit log — what the Control Room UI reads."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from core.config import PROTOCOL_VERSION, settings
from modules.observability import repository as repo
from modules.observability.hub import hub
from modules.observability.store import get_obs_db

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/calls")
def get_calls(
    source: str | None = Query(None, description="Filter by source label"),
    tool: str | None = Query(None, description="Filter by tool / resource name"),
    status: str | None = Query(None, pattern="^(ok|error)$"),
    method: str | None = Query(None, description="e.g. tools/call"),
    conversation_id: str | None = Query(None),
    since_minutes: int | None = Query(None, ge=1, le=60 * 24 * 30),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_obs_db),
) -> dict:
    """Filtered, paginated call history across every MCP consumer."""
    rows, total = repo.query_calls(
        db,
        source=source,
        tool=tool,
        status=status,
        method=method,
        conversation_id=conversation_id,
        since_minutes=since_minutes,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "calls": [r.as_dict() for r in rows],
    }


@router.get("/summary")
def get_summary(
    since_minutes: int | None = Query(None, ge=1, le=60 * 24 * 30),
    db: Session = Depends(get_obs_db),
) -> dict:
    """Counts by source and tool, error rate, p50/p95 latency."""
    return repo.summary(db, since_minutes=since_minutes)


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    """Server-Sent Events: one event per new MCP call, from any consumer."""

    async def events():
        with hub.subscribe() as queue:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    return
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    # Keep-alive comment so proxies and idle timeouts don't
                    # close a quiet stream.
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/servers")
def servers(db: Session = Depends(get_obs_db)) -> dict:
    """Status surface for the MCP Servers page."""
    from mcp_server.server import mcp

    tools = sorted(t.name for t in mcp._tool_manager.list_tools())  # noqa: SLF001
    allowlist = _gateway_allowlist()
    return {
        "server": {
            "name": mcp.name,
            "version": mcp.version,
            "protocol_version": PROTOCOL_VERSION,
            "endpoint": settings.backend_mcp_url,
            "transport": "streamable-http",
            "tools": tools,
        },
        "gateway": {
            "url": settings.mcp_gateway_url,
            "configured": bool(allowlist),
            "allowlist": allowlist,
            "allowlist_matches_tools": sorted(allowlist) == tools if allowlist else None,
        },
        "callers_seen": repo.callers_seen(db, since_minutes=60),
        "live_listeners": hub.listener_count,
    }


@router.get("/gateway-logs/raw", response_class=PlainTextResponse)
def gateway_logs_raw(lines: int = Query(300, ge=1, le=5000)) -> str:
    """Raw tail of the gateway's own log files — the escape hatch.

    The structured view at /observability/calls is the normal way in; this stays
    for the cases where you need to see exactly what the gateway printed.
    """
    parts = []
    for label, relative in (
        ("stdout", settings.gateway_stdout_log),
        ("stderr", settings.gateway_stderr_log),
        ("access", settings.gateway_log_path),
    ):
        parts.append(f"=== {label} ({relative}) ===")
        parts.append(_tail(settings.resolve(relative), lines))
        parts.append("")
    return "\n".join(parts)


def _tail(path: Path, count: int) -> str:
    if not path.exists():
        return f"(no file at {path} — is the gateway running with logging enabled?)"
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"(cannot read {path}: {exc})"
    return "\n".join(content[-count:]) or "(empty)"


_ALLOWLIST_RULE = re.compile(r'mcp\.tool\.name\s*==\s*"([^"]+)"')


def _gateway_allowlist() -> list[str]:
    """Tool names the gateway is configured to permit.

    Parsed with a regex rather than a YAML dependency: the file is ours, the
    rule shape is fixed, and this keeps the backend dependency-light.
    """
    config = settings.resolve("mcp_server/gateway/config.yaml")
    if not config.exists():
        return []
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return sorted(set(_ALLOWLIST_RULE.findall(text)))
