"""Redis-based refresh token storage and revocation."""
import logging
import os

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Key prefix patterns
_REFRESH_KEY = "refresh_jti:{jti}"
_FAMILY_KEY = "refresh_family:{family_id}"
_LOGIN_ATTEMPTS_KEY = "login_attempts:{email}:{client}"


class TokenStore:
    """Manages refresh token lifecycle in Redis."""

    def __init__(self):
        try:
            self._redis = redis.from_url(REDIS_URL, decode_responses=True)
            self._redis.ping()
            self._available = True
        except Exception:
            logger.warning("Redis unavailable for token store")
            self._available = False
            self._redis = None

    @property
    def available(self) -> bool:
        return self._available

    def _require_redis(self):
        if not self._available:
            raise TokenStoreError("Token store unavailable — Redis is down", 503)

    # ── Refresh token operations ────────────────────────────────────────────

    def store_refresh(self, jti: str, family_id: str, user_id: str, ttl_days: int = 7) -> None:
        """Store a refresh token jti."""
        self._require_redis()
        key = _REFRESH_KEY.format(jti=jti)
        self._redis.setex(key, ttl_days * 86400, user_id)

    def is_valid(self, jti: str) -> bool:
        """Check if a refresh token jti is still valid."""
        self._require_redis()
        return bool(self._redis.exists(_REFRESH_KEY.format(jti=jti)))

    def revoke(self, jti: str) -> None:
        """Revoke a single refresh token."""
        self._require_redis()
        self._redis.delete(_REFRESH_KEY.format(jti=jti))

    def revoke_family(self, family_id: str) -> None:
        """Revoke an entire token family (rotation detected replay)."""
        self._require_redis()
        self._redis.setex(_FAMILY_KEY.format(family_id=family_id), 86400 * 7, "revoked")

    def is_family_revoked(self, family_id: str) -> bool:
        """Check if a token family has been revoked."""
        self._require_redis()
        return bool(self._redis.exists(_FAMILY_KEY.format(family_id=family_id)))

    def rotate(self, old_jti: str, new_jti: str, family_id: str, user_id: str, ttl_days: int = 7) -> None:
        """Rotate: revoke old, store new. If old is already revoked, revoke family."""
        self._require_redis()
        if self.is_family_revoked(family_id):
            raise TokenStoreError("Token family has been revoked", 401)
        if not self.is_valid(old_jti):
            # Possible replay attack — revoke entire family
            self.revoke_family(family_id)
            raise TokenStoreError("Refresh token has been reused — family revoked", 401)

        self.revoke(old_jti)
        self.store_refresh(new_jti, family_id, user_id, ttl_days)

    # ── Login rate limiting ──────────────────────────────────────────────────

    def record_login_failure(self, email: str, client: str = "unknown") -> int:
        """Record a failed login attempt. Returns current count."""
        if not self._available:
            return 0  # Degraded: allow login attempts
        key = _LOGIN_ATTEMPTS_KEY.format(email=email, client=client)
        count = self._redis.incr(key)
        self._redis.expire(key, 900)  # 15 min window
        return count

    def reset_login_failures(self, email: str, client: str = "unknown") -> None:
        """Reset login failure count on successful login."""
        if not self._available:
            return
        key = _LOGIN_ATTEMPTS_KEY.format(email=email, client=client)
        self._redis.delete(key)

    def get_login_failures(self, email: str, client: str = "unknown") -> int:
        if not self._available:
            return 0
        return int(self._redis.get(_LOGIN_ATTEMPTS_KEY.format(email=email, client=client)) or 0)


class TokenStoreError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
