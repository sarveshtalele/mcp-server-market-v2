"use client";

import { TOOL_LABEL } from "./toolCards";

export interface ToolCall {
  id: string;
  name: string;
  args: string;
  status: "running" | "done" | "error";
  result?: string;
}

/** A Claude-style "using a tool" pill that shows live status. */
export function ToolChip({ tool }: { tool: ToolCall }) {
  const label = TOOL_LABEL[tool.name] ?? tool.name;
  let argHint = "";
  try {
    const a = tool.args ? JSON.parse(tool.args) : {};
    argHint = Object.values(a).filter(Boolean).join(", ");
  } catch {
    /* args may still be streaming */
  }
  return (
    <div className={`tool-chip tool-chip--${tool.status}`}>
      <span className="tool-chip__icon">
        {tool.status === "running" ? (
          <span className="spinner" />
        ) : tool.status === "error" ? (
          "!"
        ) : (
          "✓"
        )}
      </span>
      <span className="tool-chip__text">
        {label}
        {argHint && <span className="tool-chip__arg"> · {argHint}</span>}
      </span>
      <span className="tool-chip__name">{tool.name}</span>
    </div>
  );
}
