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
import { ApiError } from "@/lib/api/client"

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

  useEffect(() => {
    restoreSession()
      .then((u) => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setIsInitializing(false))
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
    await apiLogout()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, isInitializing, signIn, signUp, signOut }),
    [user, isInitializing, signIn, signUp, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    // SSR / static generation: return safe defaults
    if (typeof window === "undefined") {
      return { user: null, isInitializing: true, signIn: async () => {}, signUp: async () => {}, signOut: async () => {} } as AuthContextValue
    }
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return ctx
}
