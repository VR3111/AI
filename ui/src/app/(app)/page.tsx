"use client";

import { useState } from "react";
import { useTenant } from "@/lib/tenant-context";
import DocumentList from "@/components/app/DocumentList";

function ConversationPlaceholder({ conversationId }: { conversationId: string }) {
  return (
    <div className="h-full flex items-center justify-center text-muted-foreground">
      Conversation selected: {conversationId}
    </div>
  );
}

export default function HomePage() {
  const tenantId = useTenant();
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);

  if (!selectedConversationId) {
    return <DocumentList tenantId={tenantId} />;
  }

  return <ConversationPlaceholder conversationId={selectedConversationId} />;
}
