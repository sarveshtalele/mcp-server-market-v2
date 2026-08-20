import type { Metadata } from "next";
import { Shell } from "@/components/shell/Shell";
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
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
