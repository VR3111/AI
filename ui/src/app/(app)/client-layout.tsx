"use client";

import { useRef, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import MainPanel from "@/components/app/MainPanel";

export default function ClientLayout() {
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);

  // Will be connected to Sidebar in next step
  const refreshSidebarRef = useRef<() => void>(() => {});

  return (
    <AppShell
      sidebar={
        <Sidebar
          selectedConversationId={selectedConversationId}
          onSelectConversation={setSelectedConversationId}
          // wired in next step
          onRefreshReady={(fn) => {
            refreshSidebarRef.current = fn;
          }}
        />
      }
      header={<Header selectedConversationId={selectedConversationId} />}
    >
      <MainPanel
        selectedConversationId={selectedConversationId}
        onQuerySuccess={() => {
          refreshSidebarRef.current();
        }}
      />
    </AppShell>
  );
}
