"use client"

import { QueryProvider } from "./query-provider"
import { AuthProvider } from "@/components/auth/auth-provider"
import type { ReactNode } from "react"

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <AuthProvider>{children}</AuthProvider>
    </QueryProvider>
  )
}
