"use client";

import { useEffect, useState } from "react";
import {
  Capabilities,
  McpCall,
  fmtMs,
  fmtTime,
  getCapabilities,
  subscribeToCalls,
} from "@/lib/api";
import { Msg } from "@/lib/store";
import { ToolCall } from "@/components/chat/ToolChip";
import { TOOL_LABEL } from "@/components/chat/toolCards";

/** Newest-first tool calls belonging to the active conversation. */
function conversationTools(messages: Msg[]): (ToolCall & { key: string })[] {
  const all: (ToolCall & { key: string })[] = [];
  for (const message of messages) {
    if (message.role !== "assistant") continue;
    // Tool-call ids are not unique across a conversation — some proxies emit
    // turn-scoped ids that reset every turn — so the React key is synthetic.
    message.tools.forEach((tool, index) =>
      all.push({ ...tool, key: `${message.id}:${index}` }),
    );
  }
  return all.reverse();
}

function lastUsage(messages: Msg[]) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message.role === "assistant" && message.usage) return message.usage;
  }
  return null;
}

function argPreview(args: string | undefined): string {
  try {
    return Object.values(args ? JSON.parse(args) : {})
      .filter(Boolean)
      .join(", ");
  } catch {
    return ""; // arguments may still be streaming
  }
}

/**
 * Right rail. Two scopes that must never be blurred together:
 *   - this conversation's tool calls (what the last question cost)
 *   - the fleet's calls, from every MCP consumer (who is using the server)
 */
export function ObservabilityRail({
  messages,
  progress,
  conversationId,
}: {
  messages: Msg[];
  progress: Record<string, { progress: number; total: number | null }>;
  conversationId?: string;
}) {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [fleet, setFleet] = useState<McpCall[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    getCapabilities(controller.signal)
      .then(setCapabilities)
      .catch(() => setCapabilities(null));
    return () => controller.abort();
  }, []);

  useEffect(() => subscribeToCalls((call) => {
    setFleet((previous) => [call, ...previous].slice(0, 12));
  }), []);

  const tools = conversationTools(messages);
  const done = tools.filter((t) => t.status === "done" && t.ms != null);
  const totalMs = done.reduce((sum, t) => sum + (t.ms ?? 0), 0);
  const usage = lastUsage(messages);
  const declared = capabilities?.declared;

  return (
    <aside className="rail">
      <div className="rail__head">
        <h3>Runtime observability</h3>
        <span className="badge badge--ok">LIVE</span>
      </div>

      <div className="rail__body">
        {usage && (
          <>
            <div className="rail__section">LAST RESPONSE</div>
            <div className="usage">
              <div className="usage__top">
                <b>{usage.totalTokens.toLocaleString()}</b>
                <span>tokens · {(usage.elapsedMs / 1000).toFixed(1)}s end to end</span>
              </div>
              <div className="usage__grid">
                <div className="usage__cell">
                  <b>{usage.promptTokens.toLocaleString()}</b>
                  <span>input</span>
                </div>
                <div className="usage__cell">
                  <b>{usage.completionTokens.toLocaleString()}</b>
                  <span>output</span>
                </div>
                <div className="usage__cell">
                  <b>{usage.toolCalls}</b>
                  <span>tool calls</span>
                </div>
              </div>
            </div>
            {/* No cached-token cell and no context-limit bar: this backend does
                not report either, and inventing them would be fabrication. */}
          </>
        )}

        <div className="rail__section">THIS CONVERSATION</div>
        <div className="metrics">
          <div className="metric">
            <b>{tools.length}</b>
            <span>calls</span>
          </div>
          <div className="metric">
            <b>{Math.round(totalMs)}</b>
            <span>total ms</span>
          </div>
          <div className="metric">
            <b>{done.length ? Math.round(totalMs / done.length) : 0}</b>
            <span>avg ms</span>
          </div>
        </div>

        <div className="rows" style={{ marginTop: "var(--s-sm)" }}>
          {tools.length === 0 && (
            <div className="muted">Tool calls appear here with their timing.</div>
          )}
          {tools.map((tool) => {
            const live = progress[tool.id];
            const argument = argPreview(tool.args);
            return (
              <div key={tool.key} className={`row row--${tool.status}`}>
                <span className="row__bullet" />
                <span>
                  <b>{TOOL_LABEL[tool.name] ?? tool.name}</b>
                  <span className="row__sub">
                    mcp-market-mcp-server{argument ? ` · ${argument}` : ""}
                  </span>
                  {tool.status === "running" && live && live.total ? (
                    <span className="progress">
                      <span
                        className="progress__fill"
                        style={{ width: `${(live.progress / live.total) * 100}%` }}
                      />
                    </span>
                  ) : null}
                </span>
                <span className="row__ms">
                  {tool.status === "running" ? (
                    live && live.total ? (
                      `${live.progress}/${live.total}`
                    ) : (
                      <span className="spinner" />
                    )
                  ) : tool.ms != null ? (
                    fmtMs(tool.ms)
                  ) : (
                    "—"
                  )}
                </span>
              </div>
            );
          })}
        </div>

        <div className="divider" />

        <div className="rail__section">FLEET ACTIVITY · ALL CONSUMERS</div>
        <div className="rows">
          {fleet.length === 0 && (
            <div className="muted">
              Calls from every MCP consumer — this UI, Claude Desktop, an IDE —
              stream here as they happen.
            </div>
          )}
          {fleet.map((call) => {
            const own =
              call.source === "control-room" &&
              (!conversationId || call.conversation_id === conversationId);
            return (
              <div
                key={call.id}
                className={`row ${own ? "row--own" : ""} ${
                  call.status === "error" ? "row--error" : ""
                } ${call.resource_type === "resource" ? "row--resource" : ""}`}
              >
                <span className="row__bullet" />
                <span>
                  <b>{call.resource_name ?? call.method}</b>
                  <span className="row__sub">
                    <span
                      className={`source-tag ${
                        call.source === "unknown"
                          ? "source-tag--unknown"
                          : own
                            ? "source-tag--own"
                            : ""
                      }`}
                    >
                      {call.source}
                    </span>{" "}
                    {call.method} · {fmtTime(call.ts)}
                  </span>
                </span>
                <span className="row__ms">{fmtMs(call.latency_ms)}</span>
              </div>
            );
          })}
        </div>

        <div className="divider" />

        <div className="rail__section">MCP CAPABILITY SURFACE</div>
        {declared ? (
          <>
            <div className="metrics">
              <div className="metric">
                <b>{declared.tools.length}</b>
                <span>tools</span>
              </div>
              <div className="metric">
                <b>{declared.resources.length + declared.resource_templates.length}</b>
                <span>resources</span>
              </div>
              <div className="metric">
                <b>{declared.prompts.length}</b>
                <span>prompts</span>
              </div>
            </div>
            <div className="meta-block" style={{ marginTop: "var(--s-sm)" }}>
              tools/list cache · {Math.round(declared.cache_ttl_ms / 60000)} min · public
            </div>
            {capabilities && capabilities.reachable &&
              capabilities.reachable.resources.length === 0 &&
              declared.resources.length > 0 && (
                <div className="notice" style={{ marginTop: "var(--s-sm)" }}>
                  <b>Gateway note.</b> The server declares resources and prompts, but
                  agentgateway does not proxy them — use the{" "}
                  <span className="mono">read_market_resource</span> tool, which does
                  pass through and stays audited.
                </div>
              )}
          </>
        ) : (
          <div className="muted">Capability surface unavailable.</div>
        )}

        <div className="divider" />

        <div className="rail__section">REQUEST METADATA</div>
        <div className="meta-block">
          gateway&nbsp;&nbsp; = <b>{capabilities?.gateway_url ?? "—"}</b>
          <br />
          endpoint&nbsp; = <b>/mcp</b>
          <br />
          transport = <b>streamable-http</b>
          <br />
          protocol&nbsp; = <b>{declared?.protocol_version ?? "—"}</b>
          <br />
          policy&nbsp;&nbsp;&nbsp; = <b>mcp-market-mcp-server-allowlist</b>
          <br />
          data&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; = <b>synthetic</b>
        </div>
        {/* No session id: sessions were removed from the transport in this
            revision, so the field would be actively misleading. */}
      </div>
    </aside>
  );
}
