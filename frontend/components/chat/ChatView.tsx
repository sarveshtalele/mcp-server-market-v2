"use client";

import { KeyboardEvent, RefObject, useEffect } from "react";
import { Msg } from "@/lib/store";
import { Markdown } from "./Markdown";
import { ToolChip } from "./ToolChip";
import { renderToolCard } from "./toolCards";

interface ChatViewProps {
  messages: Msg[];
  loading: boolean;
  input: string;
  suggestions: string[];
  inputRef: RefObject<HTMLTextAreaElement>;
  bottomRef: RefObject<HTMLDivElement>;
  onInput: (v: string) => void;
  onSend: (text: string) => void;
  onStop: () => void;
}

/**
 * The centre column: the message transcript (streamed text, tool chips + cards)
 * and the composer. Purely presentational — all state lives in AppShell.
 */
export function ChatView({
  messages,
  loading,
  input,
  suggestions,
  inputRef,
  bottomRef,
  onInput,
  onSend,
  onStop,
}: ChatViewProps) {
  const empty = messages.length === 0;

  // Auto-grow the composer to fit its content (up to a max), like Claude.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [input, inputRef]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend(input);
    }
  };

  return (
    <div className="cc">
      <div className="cc__scroll">
        <div className="cc__col">
          {empty && (
            <div className="cc__welcome">
              <div className="cc__logo">◆</div>
              <h2>Stock Exchange Analyst</h2>
              <p>
                Ask about listed companies — profiles, filings, ratios, growth,
                comparisons and sector rankings. Watch the tools run on the right.
              </p>
              <div className="cc__suggest">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => onSend(s)} className="cc__chip">
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
                      {loading && isLast && !m.error && <span className="cc__caret" />}
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
            ref={inputRef}
            className="cc__input"
            value={input}
            placeholder="Ask about a company…"
            rows={1}
            onChange={(e) => onInput(e.target.value)}
            onKeyDown={onKeyDown}
          />
          {loading ? (
            <button className="cc__send cc__send--stop" onClick={onStop} title="Stop">
              ■
            </button>
          ) : (
            <button
              className="cc__send"
              onClick={() => onSend(input)}
              disabled={!input.trim()}
              title="Send"
            >
              ↑
            </button>
          )}
        </div>
        <div className="cc__hint">Streams live · shows tool calls + timing · synthetic data</div>
      </div>
    </div>
  );
}
