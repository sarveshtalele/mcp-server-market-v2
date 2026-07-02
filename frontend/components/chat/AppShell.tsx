"use client";

import { useEffect, useRef, useState } from "react";
import { runAgent, AGUIMessage } from "@/lib/agui";
import { useConversations, Msg } from "@/lib/store";
import { AgentPreset, agentPrompt } from "@/lib/agents";
import { ChatSidebar } from "./ChatSidebar";
import { ChatView } from "./ChatView";
import { ActivityPanel } from "./ActivityPanel";

const AGENT_URL =
  process.env.NEXT_PUBLIC_AGUI_URL || "http://127.0.0.1:8001/agui";

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

/**
 * Top-level chat application shell.
 *
 * Owns all state: the conversation store (left rail), the streaming engine
 * (centre) and the derived tool-activity view (right rail). Runs one AG-UI
 * stream per user message, measuring each tool's wall-clock time on the client
 * and writing it into the message so it persists and shows in both the chip and
 * the activity panel.
 */
export function AppShell() {
  const {
    conversations,
    active,
    activeId,
    setActiveId,
    createChat,
    deleteChat,
    setMessagesOf,
  } = useConversations();

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const messages = active?.messages ?? [];

  // Keep the newest message in view. Use "auto" (not "smooth") so rapid token
  // updates don't queue a backlog of animated scrolls.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [messages]);

  async function send(text: string) {
    if (loading || !text.trim()) return;
    // Ensure a conversation exists (defensive; there is always one).
    const convId = active?.id ?? createChat();

    /** Patch one assistant message inside THIS conversation (survives switching). */
    const patch = (id: string, fn: (m: Msg) => void) =>
      setMessagesOf(convId, (prev) =>
        prev.map((m) => {
          if (m.id !== id) return m;
          const copy = { ...m, tools: [...m.tools] };
          fn(copy);
          return copy;
        }),
      );

    const userMsg: Msg = { id: uid(), role: "user", content: text.trim(), tools: [] };
    const assistantId = uid();
    const assistantMsg: Msg = { id: assistantId, role: "assistant", content: "", tools: [] };

    const history: AGUIMessage[] = [...messages, userMsg].map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
    }));

    setMessagesOf(convId, (prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const ev of runAgent({
        url: AGENT_URL,
        threadId: convId,
        runId: uid(),
        messages: history,
        signal: controller.signal,
      })) {
        switch (ev.type) {
          case "TEXT_MESSAGE_CONTENT":
            patch(assistantId, (m) => {
              m.content += ev.delta ?? "";
            });
            break;
          case "TOOL_CALL_START":
            patch(assistantId, (m) => {
              m.tools.push({
                id: ev.toolCallId ?? uid(),
                name: ev.toolCallName ?? "tool",
                args: "",
                status: "running",
                startedAt: performance.now(),
              });
            });
            break;
          case "TOOL_CALL_ARGS":
            patch(assistantId, (m) => {
              const t = m.tools.find((x) => x.id === ev.toolCallId);
              if (t) t.args += ev.delta ?? "";
            });
            break;
          case "TOOL_CALL_RESULT":
            patch(assistantId, (m) => {
              const t = m.tools.find((x) => x.id === ev.toolCallId);
              if (t) {
                t.status = "done";
                t.result = ev.content;
                if (t.startedAt != null) t.ms = performance.now() - t.startedAt;
              }
            });
            break;
          case "RUN_ERROR":
            patch(assistantId, (m) => {
              m.error = ev.message ?? "Agent error";
            });
            break;
          case "CUSTOM":
            if (ev.name === "usage") {
              patch(assistantId, (m) => {
                m.usage = ev.value as Msg["usage"];
              });
            }
            break;
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      patch(assistantId, (m) => {
        m.error =
          msg.includes("Failed to fetch") || msg.includes("NetworkError")
            ? `Can't reach the agent at ${AGENT_URL}. Is it running on :8001?`
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

  /** Fill the composer with an agent's template for the user to complete. */
  function useAgent(agent: AgentPreset) {
    setInput(agentPrompt(agent, `[${agent.placeholder}]`));
    inputRef.current?.focus();
  }

  return (
    <div className="shell">
      <ChatSidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={createChat}
        onDelete={deleteChat}
        onAgent={useAgent}
      />
      <ChatView
        messages={messages}
        loading={loading}
        input={input}
        suggestions={SUGGESTIONS}
        inputRef={inputRef}
        bottomRef={bottomRef}
        onInput={setInput}
        onSend={send}
        onStop={stop}
      />
      <ActivityPanel messages={messages} />
    </div>
  );
}
