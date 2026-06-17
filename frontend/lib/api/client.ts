/**
 * Unified HTTP client for FitPilot FastAPI backend.
 * - Automatically attaches Bearer token
 * - Handles 401 → refresh → retry with dedup
 * - Parses FastAPI error format
 */
"use client"

type FetchOptions = RequestInit & { skipAuth?: boolean; skipRefresh?: boolean }

interface TokenState {
  accessToken: string | null
  refreshPromise: Promise<string | null> | null
}

const state: TokenState = {
  accessToken: null,
  refreshPromise: null,
}

export function setAccessToken(token: string | null) {
  state.accessToken = token
}

export function getAccessToken() {
  return state.accessToken
}

function getBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
}

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.detail = message
  }
}

async function refreshAccessToken(): Promise<string | null> {
  // Deduplicate concurrent refresh calls
  if (state.refreshPromise) return state.refreshPromise

  state.refreshPromise = (async () => {
    try {
      const res = await fetch(`${getBaseUrl()}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      })
      if (!res.ok) {
        setAccessToken(null)
        return null
      }
      const data = await res.json()
      const token = data.access_token
      setAccessToken(token)
      return token
    } catch {
      setAccessToken(null)
      return null
    } finally {
      state.refreshPromise = null
    }
  })()

  return state.refreshPromise
}

export async function apiFetch<T = unknown>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipAuth, skipRefresh, ...fetchOpts } = options
  const url = `${getBaseUrl()}${path}`

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOpts.headers as Record<string, string>),
  }

  if (!skipAuth && state.accessToken) {
    headers["Authorization"] = `Bearer ${state.accessToken}`
  }

  const res = await fetch(url, {
    ...fetchOpts,
    headers,
    credentials: "include",
  })

  if (res.status === 401 && !skipRefresh && state.accessToken) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`
      const retry = await fetch(url, {
        ...fetchOpts,
        headers,
        credentials: "include",
      })
      if (retry.ok) return retry.status !== 204 ? retry.json() : (undefined as T)
      const err = await retry.json().catch(() => ({}))
      throw new ApiError(err.detail || "Request failed", retry.status)
    }
    // Refresh failed — propagate the original 401
    throw new ApiError("Authentication required", 401)
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(err.detail || "Request failed", res.status)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}
