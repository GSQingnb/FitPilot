import { apiFetch, setAccessToken } from "./client"

export interface AuthUser {
  id: string
  email: string
  display_name: string
  is_active: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const data = await apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    skipAuth: true,
    skipRefresh: true,
  })
  setAccessToken(data.access_token)
  return data
}

export async function register(email: string, display_name: string, password: string): Promise<AuthResponse> {
  const data = await apiFetch<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, display_name, password }),
    skipAuth: true,
    skipRefresh: true,
  })
  setAccessToken(data.access_token)
  return data
}

export async function getMe(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/auth/me")
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/auth/logout", { method: "POST" })
  } finally {
    setAccessToken(null)
  }
}

/** Attempt to restore session via refresh token cookie.
 *  Returns null for ANY failure — MUST NOT throw.
 *  Callers treat null as "not logged in" and proceed to show login. */
export async function restoreSession(): Promise<AuthUser | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const res = await fetch(`${baseUrl}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
    if (!res.ok) {
      setAccessToken(null)
      return null
    }
    const data = await res.json()
    const token = data?.access_token
    if (!token) {
      setAccessToken(null)
      return null
    }
    setAccessToken(token)
    return await getMe()
  } catch {
    setAccessToken(null)
    return null
  }
}
