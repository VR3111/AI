"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";

type Conversation = {
  conversation_id: string;
  created_at: string;
  last_activity_at: string;
};

type Props = {
  selectedConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onRefreshReady?: (fn: () => void) => void;
};

export default function Sidebar({
  selectedConversationId,
  onSelectConversation,
  onRefreshReady,
}: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  function loadConversations() {
    setLoading(true);
    api
      .listConversations()
      .then((res) => {
        setConversations(res.conversations);
      })
      .catch((err) => {
        console.error("Failed to load conversations:", err);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadConversations();
    onRefreshReady?.(loadConversations);
  }, []);

  function handleNewConversation() {
    const id = crypto.randomUUID();
    onSelectConversation(id);
  }

  return (
    <div className="h-full flex flex-col bg-background text-foreground">
      {/* Top brand */}
      <div className="px-4 py-3 border-b border-border/50">
        <div className="text-sm font-semibold">P1</div>
        <div className="text-xs text-muted-foreground">
          Document-faithful response system
        </div>
      </div>

      {/* Actions */}
      <div className="px-4 py-4 space-y-2">
        <button
          onClick={handleNewConversation}
          className="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:opacity-90"
        >
          + New Conversation
        </button>

        <input
          disabled
          placeholder="Search Conversations"
          className="w-full rounded-md border border-border/50 bg-muted px-3 py-2 text-sm text-muted-foreground placeholder:text-muted-foreground cursor-not-allowed"
        />
      </div>

      {/* Section */}
      <div className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Conversations
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {loading && (
          <div className="text-xs text-muted-foreground">Loading…</div>
        )}

        {!loading && conversations.length === 0 && (
          <div className="text-xs text-muted-foreground">
            No conversations yet
          </div>
        )}

        {!loading && conversations.length > 0 && (
          <ul className="space-y-1">
            {conversations.map((c) => {
              const active = c.conversation_id === selectedConversationId;

              return (
                <li
                  key={c.conversation_id}
                  onClick={() => onSelectConversation(c.conversation_id)}
                  className={[
                    "truncate rounded px-2 py-1 text-sm cursor-pointer transition",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-foreground hover:bg-muted",
                  ].join(" ")}
                  title={c.conversation_id}
                >
                  {c.conversation_id}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-border/50 px-4 py-3">
        <div className="text-sm font-medium">John Doe</div>
        <div className="text-xs text-muted-foreground">
          john.doe@company.com
        </div>
      </div>
    </div>
  );
}
