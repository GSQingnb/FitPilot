"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { login as apiLogin, logout as apiLogout, register as apiRegister, restoreSession, type AuthUser } from "@/lib/api/auth"

export interface LoginPayload { email: string; password: string }
export interface RegisterPayload { displayName: string; email: string; password: string }

interface AuthContextValue {
  user: AuthUser | null
  isInitializing: boolean
  signIn: (payload: LoginPayload) => Promise<void>
  signUp: (payload: RegisterPayload) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)
  const [initError, setInitError] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function init() {
      try {
        const u = await restoreSession()
        if (!cancelled) {
          setUser(u)
        }
      } catch {
        if (!cancelled) {
          setInitError(true)
        }
      } finally {
        if (!cancelled) {
          setIsInitializing(false)
        }
      }
    }
    init()
    return () => { cancelled = true }
  }, [])

  const signIn = useCallback(async (payload: LoginPayload) => {
    const res = await apiLogin(payload.email, payload.password)
    setUser(res.user)
  }, [])

  const signUp = useCallback(async (payload: RegisterPayload) => {
    const res = await apiRegister(payload.email, payload.displayName, payload.password)
    setUser(res.user)
  }, [])

  const signOut = useCallback(async () => {
    try {
      await apiLogout()
    } catch {
      // Even if logout API fails, clear local state
    }
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, isInitializing, signIn, signUp, signOut }),
    [user, isInitializing, signIn, signUp, signOut],
  )

  // If initialization failed (network error, not 401), show a minimal loading state
  // that doesn't crash — the login page will still render
  if (initError) {
    // Still render children — let the login page handle it
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    // SSR or context-not-yet-mounted: return safe defaults
    // This prevents crashes during SSR and early hydration
    return {
      user: null,
      isInitializing: true,
      signIn: async () => {},
      signUp: async () => {},
      signOut: async () => {},
    }
  }
  return ctx
}
