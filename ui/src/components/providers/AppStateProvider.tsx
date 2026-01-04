"use client";

import { ReactNode, useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import AppShell from "@/components/layout/AppShell";
import Header from "@/components/layout/Header";
import MainPanel from "@/components/app/MainPanel";

export default function AppStateProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [selectedConversationId, setSelectedConversationId] =
    useState<string | null>(null);

  return (
    <AppShell
      sidebar={
        <Sidebar
          selectedConversationId={selectedConversationId}
          onSelectConversation={setSelectedConversationId}
        />
      }
      header={<Header />}
    >
      <MainPanel selectedConversationId={selectedConversationId} />
    </AppShell>
  );
}
