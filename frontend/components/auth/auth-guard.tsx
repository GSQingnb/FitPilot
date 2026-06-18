"use client"

import { useEffect, useRef, type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/auth/auth-provider"
import { Logo } from "@/components/brand/logo"

export function AuthGuard({ children }: { children: ReactNode }) {
  const { user, isInitializing, checkAuth } = useAuth()
  const router = useRouter()
  const checked = useRef(false)

  useEffect(() => {
    if (!checked.current) {
      checked.current = true
      void checkAuth()
    }
  }, [checkAuth])

  useEffect(() => {
    if (!isInitializing && checked.current && !user) {
      router.replace("/login")
    }
  }, [isInitializing, user, router])

  if (isInitializing || !user) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Logo />
          <p className="text-sm text-muted-foreground">Loading your workspace...</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
