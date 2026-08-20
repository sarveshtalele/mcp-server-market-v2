import type { Metadata } from "next";
import { NavRail } from "@/components/shell/NavRail";
import "./globals.css";

export const metadata: Metadata = {
  title: "Enterprise MCP Control Room",
  description:
    "Operations console for an MCP 2026-07-28 market-intelligence agent, with cross-host call observability.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <NavRail />
          <main className="workspace">{children}</main>
        </div>
      </body>
    </html>
  );
}
