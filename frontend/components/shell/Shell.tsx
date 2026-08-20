"use client";

import { ReactNode, useEffect, useState } from "react";
import { ConversationsProvider } from "@/lib/conversations";
import { NavRail } from "@/components/shell/NavRail";

const COLLAPSE_KEY = "controlRoom.navCollapsed";

/**
 * App shell: the ink navigation rail plus the routed workspace.
 *
 * Client-side because both the conversation store and the collapse preference
 * live in localStorage.
 */
export function Shell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [ready, setReady] = useState(false);

  // Read the preference after mount: reading localStorage during render would
  // make the server and client markup disagree.
  useEffect(() => {
    setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
    setReady(true);
  }, []);

  function toggle() {
    setCollapsed((previous) => {
      const next = !previous;
      window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <ConversationsProvider>
      <div
        className={`shell ${collapsed ? "shell--collapsed" : ""}`}
        data-ready={ready ? "1" : "0"}
      >
        <NavRail collapsed={collapsed} onToggle={toggle} ready={ready} />
        <main className="workspace">{children}</main>
      </div>
    </ConversationsProvider>
  );
}
