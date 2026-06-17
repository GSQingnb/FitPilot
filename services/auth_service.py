"""Authentication service — register, login, refresh, logout."""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_password_strength,
    normalize_email,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from database.models.user import User
from database.repositories.user_repository import UserRepository
from services.token_store import TokenStore, TokenStoreError

logger = logging.getLogger(__name__)

COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "fitpilot_refresh_token")
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "") or None
COOKIE_PATH = os.getenv("AUTH_COOKIE_PATH", "/auth")
MAX_LOGIN_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))


class AuthService:
    """Orchestrates authentication workflows."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._user_repo = UserRepository(db)
        self._token_store = TokenStore()

    # ── Register ────────────────────────────────────────────────────────────

    async def register(self, email: str, display_name: str, password: str) -> Tuple[dict, str]:
        """Register a new user. Returns (user_data, refresh_token_cookie_value)."""
        email = normalize_email(email)
        pw_error = validate_password_strength(password)
        if pw_error:
            raise AuthError(pw_error, 400)

        if await self._user_repo.email_exists(email):
            raise AuthError("Email already registered", 409)

        pw_hash = hash_password(password)
        user = User(email=email, display_name=display_name, password_hash=pw_hash)
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)

        return await self._login_response(user)

    # ── Login ────────────────────────────────────────────────────────────────

    async def login(self, email: str, password: str, client_ip: str = "unknown") -> Tuple[dict, str]:
        """Authenticate user. Returns (response_data, refresh_cookie_value)."""
        email = normalize_email(email)
        user = await self._user_repo.get_by_email(email)

        # Rate limit check
        attempts = self._token_store.get_login_failures(email, client_ip)
        if attempts >= MAX_LOGIN_ATTEMPTS:
            raise AuthError("Too many login attempts. Try again later.", 429)

        # Constant-time-ish: hash even if user doesn't exist
        if user and user.password_hash:
            valid = verify_password(password, user.password_hash)
        else:
            # Simulate hash verification to avoid timing difference
            verify_password(password, "$pbkdf2-sha256$600000$invalid$hash")
            valid = False

        if not valid or not user:
            self._token_store.record_login_failure(email, client_ip)
            raise AuthError("Invalid email or password", 401)

        if not user.is_active:
            raise AuthError("Account is disabled", 403)

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self._db.commit()

        self._token_store.reset_login_failures(email, client_ip)
        return await self._login_response(user)

    async def _login_response(self, user: User) -> Tuple[dict, str]:
        """Generate tokens and return auth response + cookie value."""
        uid = str(user.id)
        access_token = create_access_token(uid)
        refresh_token, jti, family_id = create_refresh_token(uid)

        self._token_store.store_refresh(jti, family_id, uid, REFRESH_TOKEN_EXPIRE_DAYS)

        response = {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": uid,
                "email": user.email,
                "display_name": user.display_name,
                "is_active": user.is_active,
            },
        }
        return response, refresh_token

    # ── Refresh ──────────────────────────────────────────────────────────────

    async def refresh(self, refresh_token: str) -> Tuple[dict, str]:
        """Validate refresh token, rotate, and return new tokens."""
        payload = decode_token(refresh_token, verify_type="refresh")
        jti = payload["jti"]
        family_id = payload.get("family_id", "")
        uid = payload["sub"]

        # Check user still exists
        user = await self._user_repo.get_by_id(uuid.UUID(uid))
        if not user or not user.is_active:
            raise AuthError("User not found or inactive", 403)

        # Rotate
        new_refresh, new_jti, _ = create_refresh_token(uid, family_id=family_id)
        self._token_store.rotate(jti, new_jti, family_id, uid, REFRESH_TOKEN_EXPIRE_DAYS)

        access_token = create_access_token(uid)
        response = {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": uid,
                "email": user.email,
                "display_name": user.display_name,
                "is_active": user.is_active,
            },
        }
        return response, new_refresh

    # ── Logout ───────────────────────────────────────────────────────────────

    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token."""
        try:
            payload = decode_token(refresh_token, verify_type="refresh")
            self._token_store.revoke(payload["jti"])
        except ValueError:
            pass  # Already invalid — idempotent

    # ── Current user ─────────────────────────────────────────────────────────

    async def get_current_user_from_token(self, access_token: str) -> User:
        """Validate access token and return user."""
        payload = decode_token(access_token, verify_type="access")
        uid = payload["sub"]
        user = await self._user_repo.get_by_id(uuid.UUID(uid))
        if not user:
            raise AuthError("User not found", 404)
        if not user.is_active:
            raise AuthError("Account is disabled", 403)
        return user

    # ── Cookie helpers ───────────────────────────────────────────────────────

    @staticmethod
    def make_refresh_cookie(token: str) -> dict:
        """Build a cookie dict for FastAPI response."""
        return {
            "key": COOKIE_NAME,
            "value": token,
            "httponly": True,
            "secure": COOKIE_SECURE,
            "samesite": COOKIE_SAMESITE,
            "domain": COOKIE_DOMAIN,
            "path": COOKIE_PATH,
            "max_age": REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        }

    @staticmethod
    def make_clear_cookie() -> dict:
        """Build a cookie-clearing dict."""
        return {
            "key": COOKIE_NAME,
            "value": "",
            "httponly": True,
            "secure": COOKIE_SECURE,
            "samesite": COOKIE_SAMESITE,
            "domain": COOKIE_DOMAIN,
            "path": COOKIE_PATH,
            "max_age": 0,
        }


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
