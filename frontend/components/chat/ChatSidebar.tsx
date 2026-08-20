"use client";

import { useEffect, useState } from "react";
import { useConversationsContext } from "@/lib/conversations";

const COLLAPSE_KEY = "controlRoom.chatsCollapsed";

/**
 * Conversation sidebar — the chatbot pattern: new chat on top, saved chats
 * below, newest first.
 *
 * The list renders only after mount: the store reads localStorage in its state
 * initialiser, so the server has no conversations while the browser may have
 * several, and rendering it during SSR is a guaranteed hydration mismatch.
 */
export function ChatSidebar() {
  const { conversations, activeId, setActiveId, createChat, deleteChat } =
    useConversationsContext();
  const [collapsed, setCollapsed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
    setReady(true);
  }, []);

  function toggle() {
    // The persist happens here, not inside a state updater: React may defer or
    // double-invoke updaters, so they have to stay pure. Writing localStorage
    // from one made the preference unreliable.
    const next = !collapsed;
    setCollapsed(next);
    window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
  }

  return (
    <aside className={`chats ${collapsed ? "chats--collapsed" : ""}`}>
      <div className="chats__head">
        <span className="chats__title">Conversations</span>
        <button
          className="chats__collapse"
          onClick={toggle}
          title={collapsed ? "Expand conversations" : "Collapse conversations"}
          aria-label={collapsed ? "Expand conversations" : "Collapse conversations"}
          aria-expanded={!collapsed}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      <button className="chats__new" onClick={() => createChat()} title="New chat">
        <span className="chats__newlabel">+ New chat</span>
        <span className="chats__newicon">+</span>
      </button>

      {ready && (
        <div className="chats__list">
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`chats__item ${
                conversation.id === activeId ? "chats__item--active" : ""
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
      )}

      <div className="chats__foot">
        {ready ? `${conversations.length} saved locally` : ""}
      </div>
    </aside>
  );
}
