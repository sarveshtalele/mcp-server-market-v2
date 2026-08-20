"""Queries over the audit log."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from core.config import settings
from modules.observability.models import McpCall


def query_calls(
    db: Session,
    *,
    source: str | None = None,
    tool: str | None = None,
    status: str | None = None,
    method: str | None = None,
    conversation_id: str | None = None,
    since_minutes: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[McpCall], int]:
    """Filtered, paginated call history, newest first. Returns (rows, total)."""
    stmt = select(McpCall)
    count_stmt = select(func.count(McpCall.id))

    def apply(statement):
        if source:
            statement = statement.where(McpCall.source == source)
        if tool:
            statement = statement.where(McpCall.resource_name == tool)
        if status:
            statement = statement.where(McpCall.status == status)
        if method:
            statement = statement.where(McpCall.method == method)
        if conversation_id:
            statement = statement.where(McpCall.conversation_id == conversation_id)
        if since_minutes:
            cutoff = _now() - timedelta(minutes=since_minutes)
            statement = statement.where(McpCall.ts >= cutoff)
        return statement

    total = db.scalar(apply(count_stmt)) or 0
    rows = list(
        db.scalars(
            apply(stmt)
            .order_by(McpCall.ts.desc(), McpCall.id.desc())
            .offset(max(offset, 0))
            .limit(max(1, min(limit, 500)))
        )
    )
    return rows, total


def summary(db: Session, *, since_minutes: int | None = None) -> dict:
    """Counts by source and tool, error rate, and latency percentiles."""
    stmt = select(McpCall)
    if since_minutes:
        stmt = stmt.where(McpCall.ts >= _now() - timedelta(minutes=since_minutes))
    rows = list(db.scalars(stmt))

    by_source: dict[str, int] = {}
    by_tool: dict[str, int] = {}
    latencies: list[float] = []
    errors = 0
    for row in rows:
        by_source[row.source] = by_source.get(row.source, 0) + 1
        if row.resource_name:
            by_tool[row.resource_name] = by_tool.get(row.resource_name, 0) + 1
        if row.status == "error":
            errors += 1
        latencies.append(row.latency_ms)

    total = len(rows)
    return {
        "total_calls": total,
        "error_count": errors,
        "error_rate_pct": round(errors / total * 100, 2) if total else 0.0,
        "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        "by_tool": dict(sorted(by_tool.items(), key=lambda kv: -kv[1])),
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "sources_seen": sorted(by_source),
    }


def callers_seen(db: Session, *, since_minutes: int = 60) -> list[dict]:
    """Distinct callers observed recently, for the MCP Servers page."""
    cutoff = _now() - timedelta(minutes=since_minutes)
    stmt = (
        select(
            McpCall.source,
            McpCall.caller_name,
            McpCall.caller_version,
            func.count(McpCall.id),
            func.max(McpCall.ts),
        )
        .where(McpCall.ts >= cutoff)
        .group_by(McpCall.source, McpCall.caller_name, McpCall.caller_version)
        .order_by(func.count(McpCall.id).desc())
    )
    return [
        {
            "source": source,
            "caller_name": name,
            "caller_version": version,
            "calls": calls,
            "last_seen": last.isoformat(timespec="seconds") + "Z",
        }
        for source, name, version, calls, last in db.execute(stmt)
    ]


def prune(db: Session) -> int:
    """Apply the retention cap. Returns the number of rows removed."""
    removed = 0

    cutoff = _now() - timedelta(days=settings.audit_max_age_days)
    result = db.execute(delete(McpCall).where(McpCall.ts < cutoff))
    removed += result.rowcount or 0

    total = db.scalar(select(func.count(McpCall.id))) or 0
    excess = total - settings.audit_max_rows
    if excess > 0:
        oldest = db.scalars(
            select(McpCall.id).order_by(McpCall.ts.asc(), McpCall.id.asc()).limit(excess)
        ).all()
        if oldest:
            result = db.execute(delete(McpCall).where(McpCall.id.in_(list(oldest))))
            removed += result.rowcount or 0

    db.commit()
    return removed


def _percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return round(ordered[index], 1)


def _now() -> datetime:
    """Naive UTC, matching how rows are stored."""
    return datetime.now(UTC).replace(tzinfo=None)
