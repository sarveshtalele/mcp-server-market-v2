"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ROUTES = [
  { href: "/", label: "Chat" },
  { href: "/servers", label: "MCP Servers" },
  { href: "/audit", label: "Audit Log" },
];

/**
 * Global menu bar: product identity, the three routes, and the environment.
 *
 * Every entry resolves to a real view — a dead link in a console whose whole
 * premise is auditability is worse than no link at all.
 */
export function TopBar() {
  const pathname = usePathname();

  return (
    <header className="topbar">
      <div className="topbar__brand">
        <div className="topbar__mark">M</div>
        <div>
          <b>Control Room</b>
          <span>MCP 2026-07-28</span>
        </div>
      </div>

      <nav className="topbar__nav" aria-label="Primary">
        {ROUTES.map((route) => (
          <Link
            key={route.href}
            href={route.href}
            className={`topbar__tab ${
              pathname === route.href ? "topbar__tab--active" : ""
            }`}
            aria-current={pathname === route.href ? "page" : undefined}
          >
            {route.label}
          </Link>
        ))}
      </nav>

      <div className="topbar__meta">
        <span className="topbar__env">DEMO · SYNTHETIC DATA</span>
        <span className="topbar__avatar" title="Operator">
          ST
        </span>
      </div>
    </header>
  );
}
