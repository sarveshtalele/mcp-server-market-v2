import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Exchange Copilot",
  description: "Streaming AG-UI chatbot for a stock exchange",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
