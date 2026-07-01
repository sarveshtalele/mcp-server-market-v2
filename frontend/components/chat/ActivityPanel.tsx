"use client";

import { Msg } from "@/lib/store";
import { ToolCall } from "./ToolChip";
import { TOOL_LABEL } from "./toolCards";

/** Flatten every tool call across the active conversation, newest first. */
function collectTools(messages: Msg[]): ToolCall[] {
  const all: ToolCall[] = [];
  for (const m of messages) if (m.role === "assistant") all.push(...m.tools);
  return all.reverse();
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

  return (
    <aside className="rail rail--right">
      <div className="rail__head">
        <span className="rail__brand">Tool activity</span>
      </div>

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
            <div key={t.id} className={`activity__row activity__row--${t.status}`}>
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
