"use client";

import { useEffect, useRef, useState } from "react";
import { runAgent, AGUIMessage } from "@/lib/agui";
import { Markdown } from "./Markdown";
import { ToolChip, ToolCall } from "./ToolChip";
import { renderToolCard } from "./toolCards";

const AGENT_URL =
  process.env.NEXT_PUBLIC_AGUI_URL || "http://127.0.0.1:8001/agui";

interface Msg {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools: ToolCall[];
  error?: string;
}

const SUGGESTIONS = [
  "Show PTT's company profile",
  "Compare KBANK, SCB and BBL",
  "PTTEP financial ratios",
  "ADVANC revenue trend",
  "Top 5 Financials by market cap",
];

export function ChatClaude() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const threadId = useRef(crypto.randomUUID());
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const patchAssistant = (id: string, fn: (m: Msg) => void) =>
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== id) return m;
        const copy = { ...m, tools: [...m.tools] };
        fn(copy);
        return copy;
      }),
    );

  async function send(text: string) {
    if (loading || !text.trim()) return;
    const userMsg: Msg = {
      id: crypto.randomUUID(),
      role: "user",
      content: text.trim(),
      tools: [],
    };
    const assistantId = crypto.randomUUID();
    const assistantMsg: Msg = {
      id: assistantId,
      role: "assistant",
      content: "",
      tools: [],
    };

    const history: AGUIMessage[] = [...messages, userMsg].map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const ev of runAgent({
        url: AGENT_URL,
        threadId: threadId.current,
        runId: crypto.randomUUID(),
        messages: history,
        signal: controller.signal,
      })) {
        switch (ev.type) {
          case "TEXT_MESSAGE_CONTENT":
            patchAssistant(assistantId, (m) => {
              m.content += ev.delta ?? "";
            });
            break;
          case "TOOL_CALL_START":
            patchAssistant(assistantId, (m) => {
              m.tools.push({
                id: ev.toolCallId ?? crypto.randomUUID(),
                name: ev.toolCallName ?? "tool",
                args: "",
                status: "running",
              });
            });
            break;
          case "TOOL_CALL_ARGS":
            patchAssistant(assistantId, (m) => {
              const t = m.tools.find((x) => x.id === ev.toolCallId);
              if (t) t.args += ev.delta ?? "";
            });
            break;
          case "TOOL_CALL_RESULT":
            patchAssistant(assistantId, (m) => {
              const t = m.tools.find((x) => x.id === ev.toolCallId);
              if (t) {
                t.status = "done";
                t.result = ev.content;
              }
            });
            break;
          case "RUN_ERROR":
            patchAssistant(assistantId, (m) => {
              m.error = ev.message ?? "Agent error";
            });
            break;
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      patchAssistant(assistantId, (m) => {
        m.error =
          msg.includes("Failed to fetch") || msg.includes("NetworkError")
            ? "Can't reach the agent at " + AGENT_URL + ". Is it running on :8001?"
            : msg;
      });
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
    setLoading(false);
  }

  const empty = messages.length === 0;

  return (
    <div className="cc">
      <div className="cc__scroll">
        <div className="cc__col">
          {empty && (
            <div className="cc__welcome">
              <div className="cc__logo">◆</div>
              <h2>SET Market Analyst</h2>
              <p>
                Ask about companies on the Stock Exchange of Thailand — profiles,
                filings, ratios, growth, comparisons and sector rankings.
              </p>
              <div className="cc__suggest">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)} className="cc__chip">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, idx) => {
            const isLast = idx === messages.length - 1;
            return (
              <div key={m.id} className={`cc__msg cc__msg--${m.role}`}>
                <div className="cc__avatar">{m.role === "user" ? "You" : "◆"}</div>
                <div className="cc__bubble">
                  {m.role === "user" ? (
                    <div className="cc__usertext">{m.content}</div>
                  ) : (
                    <>
                      {m.tools.map((t) => (
                        <div key={t.id} className="cc__tool">
                          <ToolChip tool={t} />
                          {t.status === "done" && (
                            <div className="cc__card">
                              {renderToolCard(t.name, t.result)}
                            </div>
                          )}
                        </div>
                      ))}
                      {m.content && <Markdown text={m.content} />}
                      {loading && isLast && !m.error && (
                        <span className="cc__caret" />
                      )}
                      {!m.content && !m.tools.length && loading && isLast && (
                        <div className="cc__thinking">
                          <span className="spinner" /> Thinking…
                        </div>
                      )}
                      {m.error && <div className="cc__error">{m.error}</div>}
                    </>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="cc__inputbar">
        <div className="cc__inputwrap">
          <textarea
            className="cc__input"
            value={input}
            placeholder="Ask about a SET company…"
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
          />
          {loading ? (
            <button className="cc__send cc__send--stop" onClick={stop} title="Stop">
              ■
            </button>
          ) : (
            <button
              className="cc__send"
              onClick={() => send(input)}
              disabled={!input.trim()}
              title="Send"
            >
              ↑
            </button>
          )}
        </div>
        <div className="cc__hint">
          Streams live · shows tool calls · synthetic SET data
        </div>
      </div>
    </div>
  );
}
