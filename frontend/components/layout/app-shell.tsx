"use client"

import { useState, type ReactNode } from "react"
import { useAuth } from "@/components/auth/auth-provider"
import { AppHeader } from "@/components/layout/app-header"
import { AppSidebar } from "@/components/layout/app-sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"

/** Authenticated layout shell. AuthGuard above ensures user is non-null. */
export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [collapsed, setCollapsed] = useState(false)

  if (!user) return null

  return (
    <TooltipProvider delay={200}>
      <div className="flex min-h-svh bg-background">
        <AppSidebar user={user} collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader user={user} />
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </TooltipProvider>
  )
}
