"use client";

import { createContext, useContext } from "react";

export const TenantContext = createContext<string | null>(null);

export function useTenant() {
  return useContext(TenantContext);
}
