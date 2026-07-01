"use client";

/**
 * Conversation persistence — Claude-style saved chats, stored in localStorage.
 *
 * A single hook (`useConversations`) owns the list of conversations, the active
 * one, and CRUD helpers. Messages (including per-tool timing) live inside each
 * conversation so switching chats restores the full transcript and activity.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ToolCall } from "@/components/chat/ToolChip";

export interface Msg {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools: ToolCall[];
  error?: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Msg[];
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = "stkx.conversations.v1";
const uid = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

function load(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Conversation[]) : [];
  } catch {
    return [];
  }
}

function persist(convs: Conversation[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(convs));
  } catch {
    /* quota / privacy mode — ignore */
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
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const hydrated = useRef(false);

  // Hydrate once on mount (client only).
  useEffect(() => {
    const stored = load();
    if (stored.length) {
      setConversations(stored);
      setActiveId(stored[0].id);
    } else {
      const c = newConversation();
      setConversations([c]);
      setActiveId(c.id);
    }
    hydrated.current = true;
  }, []);

  // Persist whenever conversations change (after hydration).
  useEffect(() => {
    if (hydrated.current) persist(conversations);
  }, [conversations]);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  const createChat = useCallback(() => {
    const c = newConversation();
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
    return c.id;
  }, []);

  const deleteChat = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (next.length === 0) {
          const c = newConversation();
          setActiveId(c.id);
          return [c];
        }
        if (id === activeId) setActiveId(next[0].id);
        return next;
      });
    },
    [activeId],
  );

  /** Replace the active conversation's messages (used during streaming). */
  const setActiveMessages = useCallback(
    (updater: (msgs: Msg[]) => Msg[]) => {
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== activeId) return c;
          const messages = updater(c.messages);
          return { ...c, messages, title: titleFrom(messages), updatedAt: Date.now() };
        }),
      );
    },
    [activeId],
  );

  return {
    conversations,
    active,
    activeId,
    setActiveId,
    createChat,
    deleteChat,
    setActiveMessages,
  };
}
