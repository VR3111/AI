"use client";

import { useTenant } from "@/lib/tenant-context";

type Props = {
  selectedConversationId: string | null;
};

export default function Header({ selectedConversationId }: Props) {
  const tenantId = useTenant();

  return (
    <div className="h-14 px-4 flex items-center justify-between text-sm">
      <div className="text-muted-foreground">
        Tenant: <span className="font-medium text-foreground">{tenantId}</span>
      </div>

      <div className="text-muted-foreground">
        {selectedConversationId ? "Conversation" : "Documents"}
      </div>
    </div>
  );
}
