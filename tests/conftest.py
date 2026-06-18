"""Shared pytest fixtures for FitPilot test suite.

- Sets JWT secret for test environment
- Ensures DATABASE_URL uses the correct test database credentials
- Provides shared auth fixtures (test users, auth headers, token helpers)
"""
import os
import uuid
from typing import Optional

import pytest
import pytest_asyncio
import requests

# ── Environment setup ────────────────────────────────────────────────────────
# Always set test JWT secret before any imports
os.environ.setdefault("JWT_SECRET_KEY", "test_fitpilot_jwt_secret_key_2024_testing")

# Use the actual working PostgreSQL credentials for tests.
# The .env file may have wrong password; tests always use this.
_TEST_DB_URL = os.environ.get(
    "FITPILOT_TEST_DATABASE_URL",
    "postgresql+asyncpg://fitpilot:0000@localhost:5432/fitpilot",
)
os.environ["DATABASE_URL"] = _TEST_DB_URL

# Redirect Redis to local Docker for tests
os.environ.setdefault("REDIS_URL", "redis://:echomind123@localhost:6379/0")

# ── API Base URL ─────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"


# ── Auth fixtures ────────────────────────────────────────────────────────────

def _api(method: str, path: str, **kwargs) -> requests.Response:
    """Helper: call the running FitPilot API."""
    fn = requests.post if method == "POST" else requests.get if method == "GET" else requests.put
    return fn(f"{API_BASE}{path}", timeout=60, **kwargs)


def _register_and_get_token(email: str, display_name: str = "Test", password: str = "TestPass123!") -> str:
    """Register a user and return their access token."""
    r = _api("POST", "/auth/register", json={
        "email": email, "display_name": display_name, "password": password
    })
    if r.status_code not in (200, 201):
        # Maybe already registered — try login
        r2 = _api("POST", "/auth/login", json={"email": email, "password": password})
        if r2.status_code == 200:
            return r2.json()["access_token"]
        raise RuntimeError(f"Failed to register/login user {email}: {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def test_user():
    """Create a test user and return (user_id, email, access_token)."""
    email = f"test_{uuid.uuid4().hex[:8]}@fitpilot-test.local"
    token = _register_and_get_token(email, "Test User")
    # Get user info
    r = _api("GET", "/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_data = r.json()
    return {"id": user_data["id"], "email": email, "token": token}


@pytest.fixture(scope="session")
def second_test_user():
    """Create a second test user for cross-user access tests."""
    email = f"second_{uuid.uuid4().hex[:8]}@fitpilot-test.local"
    token = _register_and_get_token(email, "Second User")
    r = _api("GET", "/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_data = r.json()
    return {"id": user_data["id"], "email": email, "token": token}


@pytest.fixture(scope="session")
def auth_headers(test_user):
    """Authorization headers for the primary test user."""
    return {"Authorization": f"Bearer {test_user['token']}"}


@pytest.fixture(scope="session")
def second_auth_headers(second_test_user):
    """Authorization headers for the secondary test user."""
    return {"Authorization": f"Bearer {second_test_user['token']}"}
