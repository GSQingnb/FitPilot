"use client"

import { useEffect } from "react"

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("FitPilot global error:", error)
  }, [error])

  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", background: "#fafafa" }}>
        <div style={{ textAlign: "center", maxWidth: 400, padding: 24 }}>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 600 }}>Something went wrong</h2>
          <p style={{ color: "#666", fontSize: "0.875rem", margin: "1rem 0" }}>
            {process.env.NODE_ENV === "development" ? error.message : "An unexpected error occurred. Please try again."}
          </p>
          <button
            onClick={reset}
            style={{ padding: "8px 16px", background: "#65a30d", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  )
}
