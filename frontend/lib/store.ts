"use client";

/**
 * Conversation persistence — Claude-style saved chats, stored in localStorage.
 *
 * `useConversations` owns the list of conversations, the active one, and CRUD
 * helpers. Messages (including per-tool timing) live inside each conversation so
 * switching chats restores the full transcript and activity.
 *
 * Design notes:
 * - State is lazily initialised from localStorage on the first client render
 *   (this component only mounts client-side via `ssr:false`), so `active` is
 *   never null and there is no empty hydration window.
 * - Persistence is DEBOUNCED: streaming appends many small updates per second;
 *   writing to localStorage on every one would jank the UI, so writes are
 *   coalesced (~400 ms).
 * - `setMessagesOf(id, …)` targets a specific conversation, so streaming keeps
 *   writing to the right chat even if the user switches conversations mid-run.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ToolCall } from "@/components/chat/ToolChip";

export interface MsgUsage {
  /** Backend-measured end-to-end run time (LLM turns + tool calls), ms. */
  elapsedMs: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  toolCalls: number;
}

export interface Msg {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools: ToolCall[];
  error?: string;
  /** Set from the backend's "usage" CUSTOM event once the run finishes. */
  usage?: MsgUsage;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Msg[];
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = "stkx.conversations.v1";
const PERSIST_DEBOUNCE_MS = 400;

const uid = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

function load(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Conversation[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persist(convs: Conversation[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(convs));
  } catch {
    /* quota exceeded / privacy mode — ignore, chats stay in memory */
  }
}

export function newConversation(): Conversation {
  const now = Date.now();
  return { id: uid(), title: "New chat", messages: [], createdAt: now, updatedAt: now };
}

/** Derive a short title from the first user message. */
export function titleFrom(messages: Msg[]): string {
  const first = messages.find((m) => m.role === "user");
  if (!first) return "New chat";
  const t = first.content.trim().replace(/\s+/g, " ");
  return t.length > 42 ? t.slice(0, 42) + "…" : t;
}

export function useConversations() {
  // Lazy init: read localStorage once, synchronously, on first client render.
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const stored = load();
    return stored.length ? stored : [newConversation()];
  });
  const [activeId, setActiveId] = useState<string>(() => "");

  // Pick the first conversation as active on mount (state initialisers can't
  // reference each other, so this one-time effect wires it up).
  useEffect(() => {
    setActiveId((cur) => cur || conversations[0]?.id || "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Debounced persistence — coalesce rapid streaming updates into one write.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => persist(conversations), PERSIST_DEBOUNCE_MS);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [conversations]);

  const active =
    conversations.find((c) => c.id === activeId) ?? conversations[0] ?? null;

  const createChat = useCallback(() => {
    const c = newConversation();
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
    return c.id;
  }, []);

  const deleteChat = useCallback(
    (id: string) => {
      // Both updates are computed here rather than inside the setConversations
      // updater: React runs updater functions during the render phase, and
      // calling another setState from there warns ("Cannot update a component
      // while rendering a different component") now that the store sits above
      // both the nav rail and the workspace.
      const remaining = conversations.filter((c) => c.id !== id);
      if (remaining.length === 0) {
        const replacement = newConversation();
        setConversations([replacement]);
        setActiveId(replacement.id);
        return;
      }
      setConversations(remaining);
      if (id === activeId) setActiveId(remaining[0].id);
    },
    [conversations, activeId],
  );

  /** Update the messages of a specific conversation by id. */
  const setMessagesOf = useCallback(
    (id: string, updater: (msgs: Msg[]) => Msg[]) => {
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== id) return c;
          const messages = updater(c.messages);
          return { ...c, messages, title: titleFrom(messages), updatedAt: Date.now() };
        }),
      );
    },
    [],
  );

  return {
    conversations,
    active,
    activeId: active?.id ?? "",
    setActiveId,
    createChat,
    deleteChat,
    setMessagesOf,
  };
}
