"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";
import DocumentList from "@/components/app/DocumentList";
import { useTenant } from "@/lib/tenant-context";

type Props = {
  selectedConversationId: string | null;
  onQuerySuccess?: () => void;
};

type Item = {
  request_id: string;
  query: string;
  mode: "direct_answer" | "guided_fallback" | "hard_refusal";
  answer: string;
};

export default function MainPanel({
  selectedConversationId,
  onQuerySuccess,
}: Props) {
  const tenantId = useTenant();

  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);

  // Load conversation history (read-only)
  useEffect(() => {
    if (!selectedConversationId) return;

    let cancelled = false;
    setLoading(true);
    setItems([]);

    api
      .getConversation(selectedConversationId)
      .then((res) => {
        if (!cancelled) {
          setItems(
            res.items.map((i: any) => ({
              request_id: i.request_id,
              query: i.query,
              mode: i.mode,
              answer: i.answer,
            }))
          );
        }
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedConversationId]);

  // No conversation → Documents
  if (!selectedConversationId) {
    return <DocumentList tenantId={tenantId} />;
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {loading && (
          <div className="text-muted-foreground text-center mt-20">
            Loading conversation…
          </div>
        )}

        {!loading && items.length === 0 && (
          <div className="text-muted-foreground text-center mt-20">
            No messages yet in this conversation
          </div>
        )}

        {items.map((item) => (
          <div key={item.request_id} className="space-y-2">
            <div className="font-medium">{item.query}</div>

            <div
              className={[
                "rounded-lg border p-4",
                item.mode === "direct_answer" &&
                  "border-border/50 bg-muted",
                item.mode === "guided_fallback" &&
                  "border-amber-500/30 bg-amber-500/5",
                item.mode === "hard_refusal" &&
                  "border-red-500/30 bg-red-500/5",
              ].join(" ")}
            >
              {item.answer}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
