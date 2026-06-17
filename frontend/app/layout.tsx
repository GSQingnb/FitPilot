import type { ReactNode } from "react"
import { AppShell } from "@/components/layout/app-shell"

/**
 * Layout for all authenticated routes. AppShell guards access and renders the
 * sidebar/header chrome around each page.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>
}
