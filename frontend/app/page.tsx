"use client";

import dynamic from "next/dynamic";

// Browser-only app shell (streams from the AG-UI agent, uses localStorage).
const AppShell = dynamic(
  () => import("@/components/chat/AppShell").then((m) => m.AppShell),
  { ssr: false, loading: () => <div className="chat-loading">Loading…</div> },
);

export default function Home() {
  return (
    <main className="app">
      <AppShell />
    </main>
  );
}
