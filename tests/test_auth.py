"""FitPilot authentication tests — passwords, JWT, registration, login, refresh.

Uses Python standard library JWT + PBKDF2 implementation.
Tests run without external services.
"""
import os
import time
import uuid

import pytest

# Ensure JWT secret is set for tests
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


# ── Password hashing tests ───────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_not_plaintext(self):
        from core.security import hash_password
        pw = "MySecurePass123!"
        hashed = hash_password(pw)
        assert pw not in hashed
        assert hashed.startswith("$pbkdf2-sha256$")

    def test_verify_correct_password(self):
        from core.security import hash_password, verify_password
        pw = "CorrectHorseBatteryStaple"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_wrong_password(self):
        from core.security import hash_password, verify_password
        hashed = hash_password("RealPassword123!")
        assert verify_password("WrongPassword123!", hashed) is False

    def test_same_password_different_hash(self):
        from core.security import hash_password
        pw = "SamePassword123!"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2  # Different salts

    def test_empty_password_still_hashes(self):
        from core.security import hash_password, verify_password
        h = hash_password("")
        assert h.startswith("$pbkdf2-sha256$")

    def test_short_password_validation(self):
        from core.security import validate_password_strength
        assert validate_password_strength("short") is not None  # too short
        assert validate_password_strength("LongEnough1!") is None  # OK

    def test_long_password_validation(self):
        from core.security import validate_password_strength
        assert validate_password_strength("x" * 129) is not None  # too long


# ── JWT tests ────────────────────────────────────────────────────────────────

class TestJWT:
    def test_create_and_decode_access_token(self):
        from core.security import create_access_token, decode_token
        token = create_access_token(str(uuid.uuid4()))
        payload = decode_token(token, verify_type="access")
        assert payload["type"] == "access"
        assert "sub" in payload
        assert "exp" in payload
        assert "jti" in payload

    def test_create_and_decode_refresh_token(self):
        from core.security import create_refresh_token
        token, jti, family_id = create_refresh_token(str(uuid.uuid4()))
        from core.security import decode_token
        payload = decode_token(token, verify_type="refresh")
        assert payload["type"] == "refresh"
        assert payload["family_id"] == family_id
        assert payload["jti"] == jti

    def test_expired_token(self):
        from core.security import create_token, decode_token
        # Create token that expired 1 second ago
        token = create_token(str(uuid.uuid4()), "access", -1)
        with pytest.raises(ValueError, match="expired"):
            decode_token(token, verify_type="access")

    def test_wrong_type_rejected(self):
        from core.security import create_access_token, decode_token
        token = create_access_token(str(uuid.uuid4()))
        with pytest.raises(ValueError, match="type"):
            decode_token(token, verify_type="refresh")

    def test_tampered_signature(self):
        from core.security import create_access_token, decode_token
        token = create_access_token(str(uuid.uuid4()))
        parts = token.split(".")
        # Change last char of signature
        sig = list(parts[2])
        sig[-1] = 'A' if sig[-1] != 'A' else 'B'
        tampered = parts[0] + "." + parts[1] + "." + "".join(sig)
        with pytest.raises(ValueError, match="signature"):
            decode_token(tampered, verify_type="access")

    def test_refresh_cannot_access_business_api(self):
        from core.security import create_refresh_token, decode_token
        token, _, _ = create_refresh_token(str(uuid.uuid4()))
        # It should decode as refresh type
        decode_token(token, verify_type="refresh")  # OK
        # But not as access type
        with pytest.raises(ValueError, match="type"):
            decode_token(token, verify_type="access")


# ── Email normalization tests ────────────────────────────────────────────────

class TestEmailNormalization:
    def test_lowercase(self):
        from core.security import normalize_email
        assert normalize_email("User@Example.COM") == "user@example.com"

    def test_trim_whitespace(self):
        from core.security import normalize_email
        assert normalize_email("  user@test.com  ") == "user@test.com"


# ── Token store mock tests ──────────────────────────────────────────────────

class TestTokenStore:
    def test_token_store_import(self):
        from services.token_store import TokenStore
        store = TokenStore()
        # Store may or may not have Redis — just verify import works
        assert store is not None


# ── Schema tests ─────────────────────────────────────────────────────────────

class TestAuthSchemas:
    def test_register_request_validation(self):
        from api.schemas import RegisterRequest
        r = RegisterRequest(email="test@example.com", display_name="Test", password="Abc12345!")
        assert r.email == "test@example.com"

    def test_register_short_password_fails(self):
        from api.schemas import RegisterRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(email="t@t.com", display_name="T", password="short")

    def test_login_request(self):
        from api.schemas import LoginRequest
        r = LoginRequest(email="test@example.com", password="ValidPass1!")
        assert r.email == "test@example.com"


# ── Security module tests ────────────────────────────────────────────────────

class TestSecurityConfig:
    def test_jwt_secret_required(self):
        """Verify JWT_SECRET_KEY is set in test environment."""
        from core.security import JWT_SECRET_KEY
        assert len(JWT_SECRET_KEY) > 10, "JWT_SECRET_KEY should be set for tests"

    def test_access_token_expiry(self):
        from core.security import ACCESS_TOKEN_EXPIRE_MINUTES
        assert ACCESS_TOKEN_EXPIRE_MINUTES > 0

    def test_refresh_token_expiry(self):
        from core.security import REFRESH_TOKEN_EXPIRE_DAYS
        assert REFRESH_TOKEN_EXPIRE_DAYS > 0
