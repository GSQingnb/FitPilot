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

/**
 * Returns the normalized API base URL.
 *
 * Docker: "/api"  → same-origin (browser → nginx → backend)
 * Dev:    "http://localhost:8000" → direct backend access
 *
 * Rejects values contaminated by MSYS/Git Bash path conversion
 * (e.g. "C:/Program Files/Git/api") which would produce file:// URLs.
 */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "/api"

  // Block common contamination patterns from MSYS2/Git Bash path conversion
  if (typeof window !== "undefined") {
    const invalid =
      /^file:|^[A-Za-z]:[\\/]|\\\\|Program Files|Program Files \(x86\)/.test(raw)
    if (invalid) {
      console.error(
        "FitPilot: NEXT_PUBLIC_API_BASE_URL is contaminated (MSYS path conversion?):",
        raw,
        "— falling back to /api"
      )
      return "/api"
    }
  }

  return raw.replace(/\/+$/, "") // strip trailing slashes
}

/**
 * Build a full API URL from a path like "/auth/register".
 * Handles both relative ("/api") and absolute ("http://...") base URLs.
 */
export function buildApiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`
  const base = getApiBaseUrl()

  if (base.startsWith("http")) {
    return `${base}${normalized}`
  }

  // Relative base like "/api"
  return `${base}${normalized}`
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
  if (state.refreshPromise) return state.refreshPromise

  state.refreshPromise = (async () => {
    try {
      const res = await fetch(buildApiUrl("/auth/refresh"), {
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
  const url = buildApiUrl(path)

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
    throw new ApiError("Authentication required", 401)
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(err.detail || "Request failed", res.status)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}
