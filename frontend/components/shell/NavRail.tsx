"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useConversationsContext } from "@/lib/conversations";

const ROUTES = [
  { href: "/", label: "Chat", short: "C" },
  { href: "/servers", label: "MCP Servers", short: "S" },
  { href: "/audit", label: "Audit Log", short: "A" },
];

/**
 * Global navigation: routes, the conversation list, and a collapse control.
 *
 * Every entry resolves to a real view — a dead link in a console whose whole
 * premise is auditability is worse than no link at all.
 */
export function NavRail({
  collapsed,
  onToggle,
  ready,
}: {
  collapsed: boolean;
  onToggle: () => void;
  /** True once mounted in the browser. See the conversation block below. */
  ready: boolean;
}) {
  const pathname = usePathname();
  const { conversations, activeId, setActiveId, createChat, deleteChat } =
    useConversationsContext();
  const onChat = pathname === "/";

  return (
    <aside className="nav">
      <div className="nav__top">
        <div className="nav__brand">
          <div className="nav__mark">M</div>
          <div className="nav__brandtext">
            <b>Control Room</b>
            <span>MCP 2026-07-28</span>
          </div>
        </div>
        <button
          className="nav__collapse"
          onClick={onToggle}
          title={collapsed ? "Expand navigation" : "Collapse navigation"}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          aria-expanded={!collapsed}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      <div className="nav__env">DEMO · SYNTHETIC DATA</div>

      <div className="nav__heading">WORKSPACE</div>
      {ROUTES.map((route) => (
        <Link
          key={route.href}
          href={route.href}
          className={`nav__link ${pathname === route.href ? "nav__link--active" : ""}`}
          title={route.label}
        >
          <span className="nav__linklabel">{route.label}</span>
          <span className="nav__linkshort">{route.short}</span>
        </Link>
      ))}

      {/* Rendered only after mount. The conversation store reads localStorage
          in its state initialiser, so the server has no conversations while the
          browser may have several — rendering it during SSR is a guaranteed
          hydration mismatch. */}
      {onChat && ready && (
        <>
          <div className="nav__heading">CONVERSATIONS</div>
          <button className="nav__new" onClick={() => createChat()} title="New chat">
            <span className="nav__linklabel">+ New chat</span>
            <span className="nav__linkshort">+</span>
          </button>
          <div className="nav__scroll">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`nav__chat ${
                  conversation.id === activeId ? "nav__chat--active" : ""
                }`}
                onClick={() => setActiveId(conversation.id)}
                title={conversation.title}
              >
                <span>{conversation.title}</span>
                {conversations.length > 1 && (
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      deleteChat(conversation.id);
                    }}
                    title="Delete conversation"
                    aria-label={`Delete ${conversation.title}`}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      <div className="nav__profile">
        <div className="nav__avatar">ST</div>
        <div className="nav__brandtext">
          <div>Operator</div>
          <div className="nav__role">AI Platform Engineer</div>
        </div>
      </div>
    </aside>
  );
}
