"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CallsPage,
  McpCall,
  Summary,
  fmtMs,
  fmtTime,
  getCalls,
  getSummary,
  subscribeToCalls,
} from "@/lib/api";

const PAGE_SIZE = 50;

/**
 * Audit Log — every MCP call, from every consumer, in one place.
 *
 * The conversation column is honest about its limits: MCP defines no
 * conversation identifier in any revision, so only this product's own client
 * can supply one. External hosts show "n/a" rather than an invented thread.
 */
export default function AuditPage() {
  const [page, setPage] = useState<CallsPage | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState({ source: "", status: "", tool: "" });

  const query = useCallback(() => {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (filters.source) params.set("source", filters.source);
    if (filters.status) params.set("status", filters.status);
    if (filters.tool) params.set("tool", filters.tool);
    return params.toString();
  }, [filters, offset]);

  const load = useCallback(() => {
    const controller = new AbortController();
    Promise.all([getCalls(query(), controller.signal), getSummary("", controller.signal)])
      .then(([calls, totals]) => {
        setPage(calls);
        setSummary(totals);
        setError(null);
      })
      .catch((cause: unknown) => {
        if ((cause as Error).name !== "AbortError") setError((cause as Error).message);
      });
    return () => controller.abort();
  }, [query]);

  useEffect(() => load(), [load]);

  // New calls arrive from any consumer; refresh the first page in place.
  useEffect(
    () =>
      subscribeToCalls(() => {
        if (offset === 0) load();
      }),
    [load, offset],
  );

  const calls = page?.calls ?? [];
  const total = page?.total ?? 0;

  return (
    <>
      <header className="top">
        <div>
          <div className="top__title">Audit Log</div>
          <div className="top__sub">
            Every MCP call through the gateway — tools, resources and prompts
          </div>
        </div>
        <div className="top__meta">
          <span className="badge">{total.toLocaleString()} calls</span>
          <span className="badge badge--ok">LIVE</span>
        </div>
      </header>

      <div className="page">
        {error && (
          <div className="notice">
            <b>Cannot reach the backend.</b> {error}
          </div>
        )}

        {summary && (
          <div className="panel">
            <p className="panel__title">SUMMARY</p>
            <div className="metrics">
              <div className="metric">
                <b>{summary.total_calls.toLocaleString()}</b>
                <span>total calls</span>
              </div>
              <div className="metric">
                <b>{summary.error_rate_pct}%</b>
                <span>error rate</span>
              </div>
              <div className="metric">
                <b>{summary.latency_p50_ms}</b>
                <span>p50 ms</span>
              </div>
              <div className="metric">
                <b>{summary.latency_p95_ms}</b>
                <span>p95 ms</span>
              </div>
              {Object.entries(summary.by_source).map(([source, count]) => (
                <div className="metric" key={source}>
                  <b>{count}</b>
                  <span>{source}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="filters">
          <select
            value={filters.source}
            onChange={(event) => {
              setOffset(0);
              setFilters({ ...filters, source: event.target.value });
            }}
          >
            <option value="">All sources</option>
            {(summary?.sources_seen ?? []).map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
          <select
            value={filters.status}
            onChange={(event) => {
              setOffset(0);
              setFilters({ ...filters, status: event.target.value });
            }}
          >
            <option value="">Any status</option>
            <option value="ok">ok</option>
            <option value="error">error</option>
          </select>
          <input
            placeholder="Filter by tool or resource…"
            value={filters.tool}
            onChange={(event) => {
              setOffset(0);
              setFilters({ ...filters, tool: event.target.value });
            }}
          />
          <button className="btn btn--secondary" onClick={() => load()}>
            Refresh
          </button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="mono">Time</th>
                <th>Source</th>
                <th>Conversation</th>
                <th className="mono">Method</th>
                <th className="mono">Tool / resource</th>
                <th>Args</th>
                <th>Status</th>
                <th className="mono">Latency</th>
              </tr>
            </thead>
            <tbody>
              {calls.length === 0 && (
                <tr>
                  <td colSpan={8} className="muted">
                    No calls recorded yet. Run a query in Chat, or call a tool from
                    Claude Desktop or an IDE — everything through the gateway lands
                    here.
                  </td>
                </tr>
              )}
              {calls.map((call: McpCall) => (
                <Row
                  key={call.id}
                  call={call}
                  expanded={expanded === call.id}
                  onToggle={() => setExpanded(expanded === call.id ? null : call.id)}
                />
              ))}
            </tbody>
          </table>
        </div>

        <div className="filters" style={{ marginTop: "var(--s-md)" }}>
          <button
            className="btn btn--secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <span className="muted" style={{ alignSelf: "center" }}>
            {total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <button
            className="btn btn--secondary"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </div>

        <p className="muted" style={{ marginTop: "var(--s-md)" }}>
          Episodes group calls from one source separated by an idle gap. They are
          inferred from timing and are a reading aid — not a conversation, thread
          or session.
        </p>
      </div>
    </>
  );
}

function Row({
  call,
  expanded,
  onToggle,
}: {
  call: McpCall;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className="clickable" onClick={onToggle}>
        <td className="mono">{fmtTime(call.ts)}</td>
        <td>
          <span
            className={`source-tag ${
              call.source === "unknown"
                ? "source-tag--unknown"
                : call.source === "control-room"
                  ? "source-tag--own"
                  : ""
            }`}
          >
            {call.source}
          </span>
        </td>
        <td className="mono">
          {call.conversation_id ? (
            call.conversation_id.slice(0, 8)
          ) : (
            <span className="muted">n/a · ep {call.episode}</span>
          )}
        </td>
        <td className="mono">{call.method}</td>
        <td className="mono">{call.resource_name ?? "—"}</td>
        <td className="mono" style={{ maxWidth: 220, overflow: "hidden" }}>
          {call.args_preview ?? "—"}
        </td>
        <td>
          <span className={`pill pill--${call.status}`}>
            {call.status}
            {call.error_code ? ` ${call.error_code}` : ""}
          </span>
        </td>
        <td className="mono">{fmtMs(call.latency_ms)}</td>
      </tr>
      {expanded && (
        <tr className="detail">
          <td colSpan={8}>
            <pre>
              {JSON.stringify(
                {
                  caller: `${call.caller_name ?? "unknown"} ${call.caller_version ?? ""}`.trim(),
                  protocol_version: call.protocol_version,
                  trace_id: call.trace_id,
                  observed_via: call.via,
                  episode: call.episode,
                  arguments: call.args_preview,
                  error: call.error_message,
                  extra_meta: call.extra_meta,
                },
                null,
                2,
              )}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}
