"use client"

import { useRouter } from "next/navigation"
import { LogOut, UserCircle } from "lucide-react"
import type { AuthUser } from "@/lib/api/auth"
import { useAuth } from "@/components/auth/auth-provider"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

export function getInitials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase()
}

export function UserMenu({
  user,
  compact = false,
}: {
  user: AuthUser
  compact?: boolean
}) {
  const router = useRouter()
  const { signOut } = useAuth()

  async function handleSignOut() {
    await signOut()
    router.replace("/login")
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
          compact ? "w-auto" : "w-full",
        )}
        aria-label="Open account menu"
      >
        <Avatar className="size-9">
          {false && <AvatarImage src="" alt="" />}
          <AvatarFallback>{getInitials(user.display_name)}</AvatarFallback>
        </Avatar>
        {!compact && (
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-sm font-medium">
              {user.display_name}
            </span>
            <span className="truncate text-xs text-muted-foreground">
              {user.email}
            </span>
          </div>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side="top" className="w-56">
        <DropdownMenuLabel>My account</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onClick={() => router.push("/profile")}>
            <UserCircle data-icon="inline-start" />
            Fitness Profile
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onClick={handleSignOut}>
            <LogOut data-icon="inline-start" />
            Log out
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
