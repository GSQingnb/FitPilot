"""Core security module — password hashing (PBKDF2) and JWT tokens.

Uses Python standard library only (hashlib, hmac, base64).
For production, consider upgrading to argon2-cffi / PyJWT when network allows.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

# ── Configuration ────────────────────────────────────────────────────────────

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def _get_secret() -> bytes:
    """Return JWT secret as bytes. Warns if using default."""
    key = JWT_SECRET_KEY
    if not key or key in ("change_me", "change_this_in_production", ""):
        raise RuntimeError(
            "JWT_SECRET_KEY is not set or using a default value. "
            "Set a strong random secret in .env before running."
        )
    return key.encode("utf-8")


# ── Password hashing (PBKDF2) ───────────────────────────────────────────────

_PBKDF2_ITERATIONS = 600_000
_PBKDF2_HASH = "sha256"
_SALT_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256. Returns a storage string."""
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_PBKDF2_HASH, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    # Format: $pbkdf2-sha256$600000$base64_salt$base64_dk
    return f"$pbkdf2-sha256${_PBKDF2_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    try:
        parts = stored.split("$")
        if len(parts) != 5 or parts[1] != "pbkdf2-sha256":
            return False
        iterations = int(parts[2])
        salt = base64.urlsafe_b64decode(parts[3])
        expected = base64.urlsafe_b64decode(parts[4])
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(subject: str, token_type: str, expires_in: int,
                 extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """Create a signed JWT token.

    Args:
        subject: user UUID string
        token_type: "access" or "refresh"
        expires_in: lifetime in seconds
        extra_claims: optional dict of additional claims
    """
    secret = _get_secret()
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": secrets.token_hex(16),
        "iat": now,
        "exp": now + expires_in,
    }
    if extra_claims:
        for k, v in extra_claims.items():
            if k not in ("sub", "type", "jti", "iat", "exp", "alg"):
                payload[k] = v

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"

    sig = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{signing_input}.{sig_b64}"


def decode_token(token: str, *, verify_type: Optional[str] = None) -> Dict[str, Any]:
    """Decode and verify a JWT token. Returns the payload dict.

    Raises ValueError for any validation failure.
    """
    secret = _get_secret()

    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"

        # Verify signature
        expected_sig = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid token signature")

        # Parse payload
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))

        # Check type
        if verify_type and payload.get("type") != verify_type:
            raise ValueError(f"Expected token type '{verify_type}', got '{payload.get('type')}'")

        # Check expiry
        now = int(time.time())
        if payload.get("exp", 0) < now:
            raise ValueError("Token has expired")

        # Check subject
        if not payload.get("sub"):
            raise ValueError("Token missing subject")

        return payload
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"Invalid token encoding: {e}")


def create_access_token(user_id: str) -> str:
    expires = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return create_token(subject=user_id, token_type="access", expires_in=expires)


def create_refresh_token(user_id: str, family_id: Optional[str] = None) -> Tuple[str, str, str]:
    """Create a refresh token. Returns (token, jti, family_id)."""
    expires = REFRESH_TOKEN_EXPIRE_DAYS * 86400
    fid = family_id or secrets.token_hex(8)
    extra = {"family_id": fid}
    token = create_token(subject=user_id, token_type="refresh", expires_in=expires, extra_claims=extra)
    payload = decode_token(token, verify_type="refresh")
    return token, payload["jti"], fid


# ── Validation helpers ───────────────────────────────────────────────────────

def validate_password_strength(password: str) -> Optional[str]:
    """Return error message if password is too weak, None if acceptable."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 128:
        return "Password must be at most 128 characters"
    return None


def normalize_email(email: str) -> str:
    """Trim and lowercase email for storage and comparison."""
    return email.strip().lower()
