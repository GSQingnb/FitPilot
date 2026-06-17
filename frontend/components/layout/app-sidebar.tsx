"use client"

import { PanelLeftClose, PanelLeftOpen } from "lucide-react"
import type { AuthUser } from "@/lib/api/auth"
import { Logo } from "@/components/brand/logo"
import { SidebarNav } from "@/components/layout/sidebar-nav"
import { UserMenu } from "@/components/layout/user-menu"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

interface AppSidebarProps {
  user: AuthUser
  collapsed: boolean
  onToggle: () => void
}

export function AppSidebar({ user, collapsed, onToggle }: AppSidebarProps) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-svh shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground transition-[width] duration-200 lg:flex",
        collapsed ? "w-[76px]" : "w-64",
      )}
    >
      <div
        className={cn(
          "flex h-16 items-center px-4",
          collapsed ? "justify-center" : "justify-between",
        )}
      >
        {collapsed ? <Logo iconOnly /> : <Logo />}
      </div>

      <Separator />

      <div className="flex-1 overflow-y-auto px-3 py-4">
        <SidebarNav collapsed={collapsed} />
      </div>

      <div className="px-3 pb-2">
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "default"}
          onClick={onToggle}
          className={cn("text-muted-foreground", !collapsed && "w-full justify-start")}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen />
          ) : (
            <>
              <PanelLeftClose data-icon="inline-start" />
              Collapse
            </>
          )}
        </Button>
      </div>

      <Separator />

      <div className="p-3">
        {collapsed ? (
          <div className="flex justify-center">
            <UserMenu user={user} compact />
          </div>
        ) : (
          <UserMenu user={user} />
        )}
      </div>
    </aside>
  )
}
