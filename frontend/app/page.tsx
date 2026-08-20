"use client";

import dynamic from "next/dynamic";

// Browser-only: streams from the AG-UI agent and persists conversations in
// localStorage, neither of which exists during server rendering.
const ControlRoomChat = dynamic(
  () => import("@/components/chat/ControlRoomChat").then((m) => m.ControlRoomChat),
  { ssr: false, loading: () => <div className="chat-loading">Loading Control Room…</div> },
);

export default function ChatPage() {
  return <ControlRoomChat />;
}
