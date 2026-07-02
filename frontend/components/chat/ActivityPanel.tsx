"use client";

import { Msg } from "@/lib/store";
import { ToolCall } from "./ToolChip";
import { TOOL_LABEL } from "./toolCards";

/**
 * Flatten every tool call across the active conversation, newest first.
 *
 * `ToolCall.id` comes straight from the LLM proxy's tool_call id, which is
 * NOT guaranteed unique across the whole conversation (some proxies emit
 * turn-scoped ids like "functions.get_company:0" that reset every turn) — so
 * a synthetic `key` (message id + position) is attached for React instead of
 * reusing `t.id` directly.
 */
function collectTools(messages: Msg[]): (ToolCall & { key: string })[] {
  const all: (ToolCall & { key: string })[] = [];
  for (const m of messages) {
    if (m.role !== "assistant") continue;
    m.tools.forEach((t, i) => all.push({ ...t, key: `${m.id}:${i}` }));
  }
  return all.reverse();
}

/** The most recent assistant message that has finished (usage arrives at RUN_FINISHED). */
function lastUsage(messages: Msg[]) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role === "assistant" && m.usage) return m.usage;
  }
  return null;
}

/**
 * Right rail: live tool-call activity for the current chat — which tools ran,
 * their arguments, status, and how long each took. Updates in real time as the
 * agent streams TOOL_CALL_* events.
 */
export function ActivityPanel({ messages }: { messages: Msg[] }) {
  const tools = collectTools(messages);
  const done = tools.filter((t) => t.status === "done" && t.ms != null);
  const totalMs = done.reduce((s, t) => s + (t.ms ?? 0), 0);
  const avgMs = done.length ? totalMs / done.length : 0;
  const usage = lastUsage(messages);

  return (
    <aside className="rail rail--right">
      <div className="rail__head">
        <span className="rail__brand">Tool activity</span>
      </div>

      {usage && (
        <>
          <div className="activity__subhead">Last response</div>
          <div className="activity__stats">
            <div className="activity__stat">
              <span className="activity__num">{(usage.elapsedMs / 1000).toFixed(1)}s</span>
              <span className="activity__cap">response time</span>
            </div>
            <div className="activity__stat">
              <span className="activity__num">{usage.totalTokens.toLocaleString()}</span>
              <span className="activity__cap">tokens</span>
            </div>
            <div className="activity__stat">
              <span className="activity__num">
                {usage.promptTokens.toLocaleString()}/{usage.completionTokens.toLocaleString()}
              </span>
              <span className="activity__cap">in / out</span>
            </div>
          </div>
          <div className="activity__subhead">Tool calls</div>
        </>
      )}

      <div className="activity__stats">
        <div className="activity__stat">
          <span className="activity__num">{tools.length}</span>
          <span className="activity__cap">calls</span>
        </div>
        <div className="activity__stat">
          <span className="activity__num">{Math.round(totalMs)}</span>
          <span className="activity__cap">total ms</span>
        </div>
        <div className="activity__stat">
          <span className="activity__num">{Math.round(avgMs)}</span>
          <span className="activity__cap">avg ms</span>
        </div>
      </div>

      <div className="activity__list">
        {tools.length === 0 && (
          <div className="activity__empty">
            Tool calls will appear here with their execution time.
          </div>
        )}
        {tools.map((t) => {
          let arg = "";
          try {
            arg = Object.values(t.args ? JSON.parse(t.args) : {})
              .filter(Boolean)
              .join(", ");
          } catch {
            /* streaming args */
          }
          return (
            <div key={t.key} className={`activity__row activity__row--${t.status}`}>
              <span className="activity__dot" />
              <span className="activity__info">
                <span className="activity__name">{TOOL_LABEL[t.name] ?? t.name}</span>
                <span className="activity__tool">{t.name}</span>
                {arg && <span className="activity__arg">{arg}</span>}
              </span>
              <span className="activity__ms">
                {t.status === "running" ? (
                  <span className="spinner" />
                ) : t.ms != null ? (
                  `${Math.round(t.ms)} ms`
                ) : (
                  "—"
                )}
              </span>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
