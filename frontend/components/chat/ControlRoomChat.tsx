"use client";

import { useEffect, useRef, useState } from "react";
import { AGUIMessage, runAgent } from "@/lib/agui";
import { AGENT_URL, Capabilities, getCapabilities } from "@/lib/api";
import { Msg, useConversations } from "@/lib/store";
import { Markdown } from "@/components/chat/Markdown";
import { renderToolCard, TOOL_LABEL } from "@/components/chat/toolCards";
import { ObservabilityRail } from "@/components/rail/ObservabilityRail";

const SUGGESTIONS = [
  "Show AAPL's company profile",
  "Compare JPM, BAC and WFC",
  "MSFT financial ratios",
  "NVDA revenue trend",
  "Top 5 Financials by market cap",
];

const uid = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

interface ProgressState {
  [toolCallId: string]: { progress: number; total: number | null };
}

/** Map a protocol error to copy that names the failing operation. */
function errorCopy(message: string): string {
  if (message.includes("-32020")) {
    return `Request rejected — header/body mismatch on the MCP call. ${message}`;
  }
  if (message.includes("-32022")) {
    return `Protocol mismatch — the server implements MCP 2026-07-28 only. ${message}`;
  }
  if (message.includes("-32602")) {
    return `Not found — the requested resource or argument is invalid. ${message}`;
  }
  if (message.includes("-32601")) {
    return `The server does not implement that method. ${message}`;
  }
  if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
    return `Can't reach the agent at ${AGENT_URL}. Is the backend running on :8000?`;
  }
  return message;
}

/**
 * Conversation workspace.
 *
 * Owns the streaming run and the two telemetry scopes: per-tool client-measured
 * timing, and the backend-measured usage event. Never conflate them — one is
 * wall-clock in this browser, the other is the backend's own accounting.
 */
export function ControlRoomChat() {
  const { conversations, active, activeId, setActiveId, createChat, deleteChat, setMessagesOf } =
    useConversations();

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<ProgressState>({});
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const messages = active?.messages ?? [];

  useEffect(() => {
    const controller = new AbortController();
    getCapabilities(controller.signal).then(setCapabilities).catch(() => undefined);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [messages]);

  async function send(text: string) {
    if (loading || !text.trim()) return;
    const conversationId = active?.id ?? createChat();

    const patch = (id: string, apply: (message: Msg) => void) =>
      setMessagesOf(conversationId, (previous) =>
        previous.map((message) => {
          if (message.id !== id) return message;
          const copy = { ...message, tools: [...message.tools] };
          apply(copy);
          return copy;
        }),
      );

    const userMessage: Msg = { id: uid(), role: "user", content: text.trim(), tools: [] };
    const assistantId = uid();
    const assistantMessage: Msg = { id: assistantId, role: "assistant", content: "", tools: [] };

    const history: AGUIMessage[] = [...messages, userMessage].map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
    }));

    setMessagesOf(conversationId, (previous) => [...previous, userMessage, assistantMessage]);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const event of runAgent({
        url: AGENT_URL,
        threadId: conversationId,
        runId: uid(),
        messages: history,
        signal: controller.signal,
      })) {
        switch (event.type) {
          case "TEXT_MESSAGE_CONTENT":
            patch(assistantId, (message) => {
              message.content += event.delta ?? "";
            });
            break;
          case "TOOL_CALL_START":
            patch(assistantId, (message) => {
              message.tools.push({
                id: event.toolCallId ?? uid(),
                name: event.toolCallName ?? "tool",
                args: "",
                status: "running",
                startedAt: performance.now(),
              });
            });
            break;
          case "TOOL_CALL_ARGS":
            patch(assistantId, (message) => {
              const tool = message.tools.find((t) => t.id === event.toolCallId);
              if (tool) tool.args += event.delta ?? "";
            });
            break;
          case "TOOL_CALL_RESULT":
            patch(assistantId, (message) => {
              const tool = message.tools.find((t) => t.id === event.toolCallId);
              if (tool) {
                tool.status = "done";
                tool.result = event.content;
                if (tool.startedAt != null) tool.ms = performance.now() - tool.startedAt;
              }
            });
            break;
          case "RUN_ERROR":
            patch(assistantId, (message) => {
              message.error = errorCopy(event.message ?? "Agent error");
            });
            break;
          case "CUSTOM":
            if (event.name === "usage") {
              patch(assistantId, (message) => {
                message.usage = event.value as Msg["usage"];
              });
            } else if (event.name === "progress") {
              const value = event.value as {
                toolCallId: string;
                progress: number;
                total: number | null;
              };
              setProgress((previous) => ({
                ...previous,
                [value.toolCallId]: { progress: value.progress, total: value.total },
              }));
            }
            break;
        }
      }
    } catch (error: unknown) {
      const raw = error instanceof Error ? error.message : String(error);
      patch(assistantId, (message) => {
        message.error = errorCopy(raw);
      });
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  const declared = capabilities?.declared;

  return (
    <div className="chat">
      <div className="chat__main">
        <header className="top">
          <div>
            <div className="top__title">MCP Assistant · Market Intelligence</div>
            <div className="top__sub">
              Single orchestrator with governed MCP access · synthetic dataset
            </div>
          </div>
          <div className="top__meta">
            <span className={`badge ${capabilities?.gateway_connected ? "badge--ok" : "badge--warn"}`}>
              {capabilities?.gateway_connected ? "● Gateway connected" : "● Gateway offline"}
            </span>
            <span className="badge">
              MCP {declared?.protocol_version ?? "…"}
            </span>
            <span className="badge">
              {declared?.server_name ?? "stock-exchange"} v{declared?.server_version ?? "—"}
            </span>
            <select
              aria-label="Conversation"
              className="badge"
              value={activeId ?? ""}
              onChange={(event) => setActiveId(event.target.value)}
            >
              {conversations.map((conversation) => (
                <option key={conversation.id} value={conversation.id}>
                  {conversation.title}
                </option>
              ))}
            </select>
            <button className="btn btn--secondary" onClick={() => createChat()}>
              New
            </button>
            {conversations.length > 1 && activeId && (
              <button
                className="btn btn--secondary"
                onClick={() => deleteChat(activeId)}
                title="Delete this conversation"
              >
                Delete
              </button>
            )}
          </div>
        </header>

        <section className="chat__scroll">
          <div className="chat__inner">
            {messages.length === 0 && (
              <div className="empty">
                <h2>Inspect the market dataset</h2>
                <p>
                  Every answer comes from MCP tool results. The data is synthetic
                  (Faker, fixed seed) and must not be read as real market data.
                </p>
                <div className="empty__grid">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      className="empty__item"
                      onClick={() => send(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
                {declared && declared.prompts.length > 0 && (
                  <>
                    <div className="rail__section">SERVER PROMPTS</div>
                    <div className="chips">
                      {declared.prompts.map((prompt) => (
                        <button
                          key={prompt}
                          className="chip chip--prompt"
                          onClick={() => {
                            setInput(
                              prompt === "compare-stocks"
                                ? "Run compare-stocks for JPM, BAC, WFC"
                                : "Run analyze-equity for AAPL",
                            );
                            inputRef.current?.focus();
                          }}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {messages.map((message) =>
              message.role === "user" ? (
                <div className="turn" key={message.id}>
                  <div className="msg-user">{message.content}</div>
                </div>
              ) : (
                <div className="turn" key={message.id}>
                  <div className="msg-assistant">
                    <div className="msg-assistant__head">
                      <div className="who">
                        <span className="dot" />
                        Orchestrator
                        {message.usage && <span className="badge">completed</span>}
                      </div>
                      {message.usage && (
                        <span className="time">
                          {(message.usage.elapsedMs / 1000).toFixed(1)}s · backend-measured
                        </span>
                      )}
                    </div>

                    {message.content ? (
                      <Markdown text={message.content} />
                    ) : (
                      !message.error && <span className="spinner" />
                    )}

                    {message.tools.length > 0 && (
                      <div className="chips">
                        {message.tools.map((tool, index) => (
                          <span
                            key={`${message.id}:${index}`}
                            className={`chip ${
                              tool.name === "read_market_resource"
                                ? "chip--resource"
                                : "chip--tool"
                            }`}
                          >
                            <span className="chip__state" />
                            {TOOL_LABEL[tool.name] ?? tool.name}
                            {tool.ms != null && ` · ${Math.round(tool.ms)} ms`}
                          </span>
                        ))}
                      </div>
                    )}

                    {message.tools.map((tool, index) => (
                      <div key={`card:${message.id}:${index}`}>
                        {renderToolCard(tool.name, tool.result)}
                      </div>
                    ))}

                    {message.error && (
                      <div className="err-row">
                        <b>Run failed.</b> {message.error}
                      </div>
                    )}
                  </div>
                </div>
              ),
            )}
            <div ref={bottomRef} />
          </div>
        </section>

        <footer className="composer">
          <div className="composer__inner">
            <div className="composer__box">
              <textarea
                ref={inputRef}
                aria-label="Message"
                placeholder="Ask the agent to inspect data, run tools, or explain a result…"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send(input);
                  }
                }}
              />
              <div className="composer__row">
                <span className="hint">
                  Enter to send · Shift+Enter for newline · tool calls are governed by
                  gateway policy
                </span>
                {loading ? (
                  <button
                    className="btn btn--stop"
                    onClick={() => {
                      abortRef.current?.abort();
                      setLoading(false);
                    }}
                  >
                    Stop
                  </button>
                ) : (
                  <button className="btn" onClick={() => send(input)} disabled={!input.trim()}>
                    Send
                  </button>
                )}
              </div>
            </div>
          </div>
        </footer>
      </div>

      <ObservabilityRail
        messages={messages}
        progress={progress}
        conversationId={activeId ?? undefined}
      />
    </div>
  );
}
