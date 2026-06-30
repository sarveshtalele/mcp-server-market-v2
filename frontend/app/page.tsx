"use client";

import dynamic from "next/dynamic";

// Browser-only chat (streams from the AG-UI agent); skip during static build.
const ChatClaude = dynamic(
  () => import("@/components/chat/ChatClaude").then((m) => m.ChatClaude),
  { ssr: false, loading: () => <div className="chat-loading">Loading chat…</div> },
);

export default function Home() {
  return (
    <main className="app">
      <header className="chat-header">
        <div className="chat-header__brand">
          <span className="chat-header__mark">STK</span>
          <span className="chat-header__name">
            Market Copilot <span>· live tool calls + streaming</span>
          </span>
        </div>
        <div className="chat-header__status">
          <span className="chat-header__dot" /> AG-UI agent
        </div>
      </header>
      <div className="chat-body">
        <ChatClaude />
      </div>
    </main>
  );
}
