"use client"

import Link from "next/link"
import { Bell, Bot } from "lucide-react"
import type { AuthUser } from "@/lib/api/auth"
import { Logo } from "@/components/brand/logo"
import { MobileNavigation } from "@/components/layout/mobile-navigation"
import { Button } from "@/components/ui/button"

export function AppHeader({ user }: { user: AuthUser }) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur sm:px-6">
      {/* Mobile: drawer trigger + compact logo */}
      <div className="flex items-center gap-2 lg:hidden">
        <MobileNavigation user={user} />
        <Logo iconOnly />
      </div>

      <div className="flex flex-1 items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          render={
            <Link href="/coach">
              <Bot data-icon="inline-start" />
              <span className="hidden sm:inline">Ask AI Coach</span>
              <span className="sm:hidden">Coach</span>
            </Link>
          }
        />
        <Button
          variant="ghost"
          size="icon"
          aria-label="Notifications"
          className="text-muted-foreground"
        >
          <Bell />
        </Button>
      </div>
    </header>
  )
}
