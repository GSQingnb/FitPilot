"use client"

import { useEffect, useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/auth/auth-provider"
import { AppHeader } from "@/components/layout/app-header"
import { AppSidebar } from "@/components/layout/app-sidebar"
import { Logo } from "@/components/brand/logo"
import { TooltipProvider } from "@/components/ui/tooltip"

/**
 * Authenticated application shell.
 *
 * Guards its children: while the (mock) session is restoring it shows a
 * splash, and if there is no user it redirects to /login. Replace the auth
 * check with the result of `GET /auth/me` when wiring the FastAPI backend.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter()
  const { user, isInitializing } = useAuth()
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    if (!isInitializing && !user) {
      router.replace("/login")
    }
  }, [isInitializing, user, router])

  if (isInitializing || !user) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Logo />
          <p className="text-sm text-muted-foreground">Loading your workspace…</p>
        </div>
      </div>
    )
  }

  return (
    <TooltipProvider delay={200}>
      <div className="flex min-h-svh bg-background">
        <AppSidebar
          user={user}
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader user={user} />
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </TooltipProvider>
  )
}
