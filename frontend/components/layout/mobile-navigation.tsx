"use client"

import { useState } from "react"
import { Menu } from "lucide-react"
import type { AuthUser } from "@/lib/api/auth"
import { Logo } from "@/components/brand/logo"
import { SidebarNav } from "@/components/layout/sidebar-nav"
import { UserMenu } from "@/components/layout/user-menu"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"

/** Slide-out navigation drawer for mobile / tablet viewports. */
export function MobileNavigation({ user }: { user: AuthUser }) {
  const [open, setOpen] = useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button variant="ghost" size="icon" aria-label="Open navigation menu">
            <Menu />
          </Button>
        }
      />
      <SheetContent side="left" className="flex w-72 flex-col gap-0 p-0">
        <SheetHeader className="h-16 justify-center px-4">
          <SheetTitle className="flex items-center">
            <Logo />
            <span className="sr-only">FitPilot navigation</span>
          </SheetTitle>
        </SheetHeader>
        <Separator />
        <div className="flex-1 overflow-y-auto px-3 py-4">
          <SidebarNav onNavigate={() => setOpen(false)} />
        </div>
        <Separator />
        <div className="p-3">
          <UserMenu user={user} />
        </div>
      </SheetContent>
    </Sheet>
  )
}
