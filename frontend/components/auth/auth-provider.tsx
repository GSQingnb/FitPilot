"use client"

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { login as apiLogin, logout as apiLogout, register as apiRegister, restoreSession, type AuthUser } from "@/lib/api/auth"

export interface LoginPayload { email: string; password: string }
export interface RegisterPayload { displayName: string; email: string; password: string }

export interface AuthContextValue {
  user: AuthUser | null
  isInitializing: boolean
  signIn: (payload: LoginPayload) => Promise<void>
  signUp: (payload: RegisterPayload) => Promise<void>
  signOut: () => Promise<void>
  checkAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isInitializing, setIsInitializing] = useState(false)

  const checkAuth = useCallback(async () => {
    setIsInitializing(true)
    try {
      const u = await restoreSession()
      setUser(u)
    } catch {
      setUser(null)
    } finally {
      setIsInitializing(false)
    }
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
    try { await apiLogout() } catch { /* ignore */ }
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, isInitializing, signIn, signUp, signOut, checkAuth }),
    [user, isInitializing, signIn, signUp, signOut, checkAuth],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

export function useOptionalAuth(): AuthContextValue | null {
  return useContext(AuthContext) ?? null
}
