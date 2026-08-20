"use client";

import { ReactNode, createContext, useContext } from "react";
import { useConversations } from "@/lib/store";

/**
 * One conversation store shared by the nav rail and the chat workspace.
 *
 * `useConversations` owns localStorage-backed state, so calling the hook twice
 * would give the sidebar and the chat two copies that drift apart. The provider
 * calls it once, above both.
 */
type ConversationsValue = ReturnType<typeof useConversations>;

const ConversationsContext = createContext<ConversationsValue | null>(null);

export function ConversationsProvider({ children }: { children: ReactNode }) {
  const value = useConversations();
  return (
    <ConversationsContext.Provider value={value}>{children}</ConversationsContext.Provider>
  );
}

export function useConversationsContext(): ConversationsValue {
  const value = useContext(ConversationsContext);
  if (value === null) {
    throw new Error("useConversationsContext must be used inside ConversationsProvider");
  }
  return value;
}
