"use client";

import { ReactNode } from "react";
import { ConversationsProvider } from "@/lib/conversations";
import { TopBar } from "@/components/shell/TopBar";

/**
 * App shell: the menu bar across the top, routed content beneath it.
 *
 * The conversation store lives here, above both the chat sidebar and the
 * workspace, so the two never hold divergent copies of localStorage state.
 */
export function Shell({ children }: { children: ReactNode }) {
  return (
    <ConversationsProvider>
      <div className="app">
        <TopBar />
        <main className="body">{children}</main>
      </div>
    </ConversationsProvider>
  );
}
