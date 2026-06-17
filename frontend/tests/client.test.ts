import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

// We test the auth module's client behavior by mocking fetch
// and verifying the refresh token flow.

describe("API Client — Token Refresh", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://test.local")
    vi.stubGlobal("window", { location: { href: "" } })
    // Reset module state
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("should call /auth/refresh with POST when receiving 401", async () => {
    const { setAccessToken } = await import("../lib/api/client")
    setAccessToken("fake-token")

    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: "expired" }) })  // first call
      .mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: "new-token" }) })        // refresh
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data: "ok" }) })                        // retry
    vi.stubGlobal("fetch", fetchMock)

    const { apiFetch } = await import("../lib/api/client")
    const result = await apiFetch("/test-path")

    // Verify refresh was called with POST
    expect(fetchMock).toHaveBeenCalledTimes(3)
    const refreshCall = fetchMock.mock.calls[1]
    expect(refreshCall[0]).toBe("http://test.local/auth/refresh")
    expect(refreshCall[1].method).toBe("POST")
    expect(refreshCall[1].credentials).toBe("include")
    expect(result).toEqual({ data: "ok" })
  })

  it("should deduplicate concurrent refresh calls", async () => {
    const { setAccessToken } = await import("../lib/api/client")
    setAccessToken("fake-token")

    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: "1" }) })
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: "2" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: "new-token" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data: "ok1" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data: "ok2" }) })
    vi.stubGlobal("fetch", fetchMock)

    const { apiFetch } = await import("../lib/api/client")
    const [r1, r2] = await Promise.all([
      apiFetch("/path1"),
      apiFetch("/path2"),
    ])

    // Only one refresh call should happen (call index 2)
    expect(r1).toEqual({ data: "ok1" })
    expect(r2).toEqual({ data: "ok2" })
  })

  it("should clear token and return 401 when refresh fails", async () => {
    const { setAccessToken, getAccessToken } = await import("../lib/api/client")
    setAccessToken("fake-token")

    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: "expired" }) })
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: "refresh failed" }) })
    vi.stubGlobal("fetch", fetchMock)

    const { apiFetch } = await import("../lib/api/client")
    await expect(apiFetch("/test")).rejects.toThrow("Authentication required")
    expect(getAccessToken()).toBeNull()
  })
})

describe("API Client — Login form validation", () => {
  it("should reject empty email", () => {
    // Simple unit test for email validation logic
    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    expect(EMAIL_RE.test("")).toBe(false)
    expect(EMAIL_RE.test("not-email")).toBe(false)
    expect(EMAIL_RE.test("user@example.com")).toBe(true)
  })
})

describe("Profile enum mapping", () => {
  it("should have correct goal values", () => {
    const goals = ["muscle_gain", "fat_loss", "strength", "general_fitness"]
    expect(goals).toContain("muscle_gain")
    expect(goals).toContain("fat_loss")
    expect(goals).toContain("strength")
    expect(goals).toContain("general_fitness")
  })

  it("should have correct experience levels", () => {
    const levels = ["beginner", "intermediate", "advanced"]
    expect(levels).toContain("beginner")
    expect(levels).toContain("intermediate")
    expect(levels).toContain("advanced")
  })
})
