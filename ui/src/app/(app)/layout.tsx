import { headers } from "next/headers";
import AppShell from "@/components/layout/AppShell";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import TenantProvider from "@/components/providers/TenantProvider";
import MainPanel from "@/components/app/MainPanel";
import ClientLayout from "./client-layout";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const h = await headers();
  const tenantId = h.get("x-tenant-id");

  if (!tenantId) return null;

  return (
    <TenantProvider tenantId={tenantId}>
      <ClientLayout />
    </TenantProvider>
  );
}
