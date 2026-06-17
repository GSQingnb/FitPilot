#!/usr/bin/env python3
"""FitPilot End-to-End Smoke Test — Docker same-origin deployment.

Uses httpx.Client for proper HttpOnly cookie handling across requests.
Validates full auth flow: register → cookie → refresh → logout → denied.
"""
import sys, uuid

try:
    import httpx
except ImportError:
    print("ERROR: httpx required.  pip install httpx")
    sys.exit(1)

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost"
API = f"{BASE}/api"

PASS = 0
FAIL = 0

def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} {detail}")

print(f"FitPilot Smoke Test — {BASE}\n")

# ── Shared HTTP client with cookie jar ──────────────────────────────────────
client = httpx.Client(base_url=BASE, follow_redirects=True, timeout=30)

try:
    # 1. Nginx health
    r = client.get("/nginx-health")
    check("Nginx health", r.status_code == 200, f"got {r.status_code}")

    # 2. Frontend serves login page
    r = client.get("/login")
    check("Frontend login page", r.status_code == 200 and "text/html" in r.headers.get("content-type", ""), f"got {r.status_code}")

    # 3. Backend health
    r = client.get("/api/health")
    check("Backend health", r.status_code == 200 and r.json().get("status") == "ok")

    # 4. Database health
    r = client.get("/api/health/database")
    check("Database health", r.status_code == 200 and r.json().get("status") == "ok")

    # 5. Exercises API (public)
    r = client.get("/api/exercises", params={"limit": 1})
    check("Exercises API", r.status_code == 200 and r.json().get("total", 0) > 0)

    # ── Auth flow (shared client = shared cookies) ──────────────────────────
    email = f"smoke.{uuid.uuid4().hex[:8]}@test.local"
    password = "SmokeTest123!"

    # 6. Register
    r = client.post("/api/auth/register", json={
        "email": email, "display_name": "SmokeTest", "password": password,
    })
    ok = r.status_code in (200, 201)
    access_token = r.json().get("access_token", "") if ok else ""
    check("Register user", ok, f"got {r.status_code}")

    if not ok:
        print(f"\nERROR: Registration failed, cannot continue auth tests.")
    else:
        # 7. Refresh Cookie set with correct Path
        refresh_cookie = client.cookies.get("fitpilot_refresh_token")
        cookie_ok = refresh_cookie is not None and len(refresh_cookie) > 0
        check("Refresh Cookie set", cookie_ok, "missing or empty")
        # Verify Set-Cookie header contains Path=/api/auth (best effort)
        set_cookie = r.headers.get("set-cookie", "")
        path_ok = "Path=/api/auth" in set_cookie or "Path=/auth" in set_cookie
        check("Cookie Path correct", path_ok, set_cookie[:80] if not path_ok else "")

        # 8. Auth me (access token from register response)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        check("Auth me", r.status_code == 200 and r.json().get("email") == email,
              f"got {r.status_code}")

        # 9. Refresh (same client = sends the cookie)
        r = client.post("/api/auth/refresh")
        refresh_ok = r.status_code == 200
        new_token = r.json().get("access_token", "") if refresh_ok else ""
        check("Refresh returns 200 + new token",
              refresh_ok and len(new_token) > 10,
              f"got {r.status_code}")

        # 10. Logout (same client)
        r = client.post("/api/auth/logout",
                         headers={"Authorization": f"Bearer {access_token}"})
        check("Logout", r.status_code in (200, 204), f"got {r.status_code}")

        # 11. Post-logout refresh must be denied
        r = client.post("/api/auth/refresh")
        check("Post-logout refresh denied",
              r.status_code == 401,
              f"got {r.status_code}")

finally:
    client.close()

print(f"\nResults: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
