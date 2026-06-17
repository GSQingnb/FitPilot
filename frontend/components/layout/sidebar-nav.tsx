"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { NAV_ITEMS } from "@/lib/navigation"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

interface SidebarNavProps {
  /** Icon-only mode for the collapsed desktop sidebar. */
  collapsed?: boolean
  /** Called when a link is clicked (used to close the mobile drawer). */
  onNavigate?: () => void
}

export function SidebarNav({ collapsed = false, onNavigate }: SidebarNavProps) {
  const pathname = usePathname()

  return (
    <nav className="flex flex-col gap-1" aria-label="Primary">
      {NAV_ITEMS.map((item) => {
        const isActive =
          pathname === item.href || pathname.startsWith(`${item.href}/`)
        const Icon = item.icon

        const link = (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              "hover:bg-accent hover:text-accent-foreground",
              "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
              isActive
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground",
              collapsed && "justify-center px-0",
            )}
          >
            <Icon className="size-5 shrink-0" aria-hidden="true" />
            {!collapsed && (
              <>
                <span className="flex-1 truncate">{item.label}</span>
                {item && (
                  <Badge variant="secondary" className="shrink-0 text-[10px]">
                    Soon
                  </Badge>
                )}
              </>
            )}
          </Link>
        )

        if (collapsed) {
          return (
            <Tooltip key={item.href}>
              <TooltipTrigger render={link} />
              <TooltipContent side="right">
                {item.label}
                {item ? " (coming soon)" : ""}
              </TooltipContent>
            </Tooltip>
          )
        }

        return link
      })}
    </nav>
  )
}
