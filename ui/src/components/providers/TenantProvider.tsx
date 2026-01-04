"use client";

import { ReactNode } from "react";
import { TenantContext } from "@/lib/tenant-context";

type Props = {
  tenantId: string;
  children: ReactNode;
};

export default function TenantProvider({ tenantId, children }: Props) {
  return (
    <TenantContext.Provider value={tenantId}>
      {children}
    </TenantContext.Provider>
  );
}
