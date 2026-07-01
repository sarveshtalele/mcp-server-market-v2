"use client";

import { Conversation } from "@/lib/store";
import { AGENTS, AgentPreset } from "@/lib/agents";

interface ChatSidebarProps {
  conversations: Conversation[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onAgent: (agent: AgentPreset) => void;
}

/**
 * Left rail (Claude-style): "New chat", the saved-conversation list, and the
 * predefined Agents. Conversations persist in localStorage (see lib/store).
 */
export function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onAgent,
}: ChatSidebarProps) {
  return (
    <aside className="rail rail--left">
      <div className="rail__head">
        <span className="rail__brand">
          <span className="rail__mark">STK</span> Copilot
        </span>
      </div>

      <button className="rail__new" onClick={onNew}>
        <span className="rail__plus">+</span> New chat
      </button>

      <div className="rail__section">
        <div className="rail__label">Chats</div>
        <div className="rail__list">
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`rail__item ${c.id === activeId ? "rail__item--active" : ""}`}
              onClick={() => onSelect(c.id)}
            >
              <span className="rail__item-title">{c.title || "New chat"}</span>
              <button
                className="rail__del"
                title="Delete chat"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(c.id);
                }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="rail__section">
        <div className="rail__label">Agents</div>
        <div className="rail__agents">
          {AGENTS.map((a) => (
            <button key={a.id} className="agent-card" onClick={() => onAgent(a)}>
              <span className="agent-card__icon">{a.icon}</span>
              <span className="agent-card__body">
                <span className="agent-card__name">{a.name}</span>
                <span className="agent-card__tag">{a.tagline}</span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
