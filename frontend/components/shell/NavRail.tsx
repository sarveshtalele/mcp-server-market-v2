"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const ROUTES = [
  { href: "/", label: "Chat" },
  { href: "/servers", label: "MCP Servers" },
  { href: "/audit", label: "Audit Log" },
];

/**
 * Global navigation. Every entry resolves to a real view — a dead link in a
 * console whose whole premise is auditability is worse than no link at all.
 */
export function NavRail({ children }: { children?: ReactNode }) {
  const pathname = usePathname();

  return (
    <aside className="nav">
      <div className="nav__brand">
        <div className="nav__mark">M</div>
        <div>
          <b>Control Room</b>
          <span>MCP 2026-07-28</span>
        </div>
      </div>

      <div className="nav__env">DEMO · SYNTHETIC DATA</div>

      <div className="nav__heading">WORKSPACE</div>
      {ROUTES.map((route) => (
        <Link
          key={route.href}
          href={route.href}
          className={`nav__link ${pathname === route.href ? "nav__link--active" : ""}`}
        >
          {route.label}
        </Link>
      ))}

      {children}

      <div className="nav__profile">
        <div className="nav__avatar">ST</div>
        <div>
          <div>Operator</div>
          <div className="nav__role">AI Platform Engineer</div>
        </div>
      </div>
    </aside>
  );
}
