"use client";

import { ReactNode } from "react";

type Props = {
  sidebar: ReactNode;
  header?: ReactNode;
  children: ReactNode;
};

export default function AppShell({ sidebar, header, children }: Props) {
  return (
    <div className="h-screen flex bg-background text-foreground">
      <aside className="w-80 border-r border-border/50 bg-card">
        {sidebar}
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        {header && (
          <header className="border-b border-border/50 bg-card">
            {header}
          </header>
        )}

        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
