"""
Unified asynchronous LLM client for FitPilot.

Supports Anthropic-compatible APIs (Claude, DeepSeek, etc.).
Handles multi-block responses (thinking → text), stop_reason truncation,
and configurable retry logic.

Environment variables:
  LLM_MODEL             — default model name (default: deepseek-v4-flash)
  LLM_THINKING          — JSON string for thinking param (default: {"type":"disabled"})
  LLM_MAX_TOKENS_PLAN   — plan generation (default: 4096)
  LLM_MAX_TOKENS_CHAT   — agent chat (default: 1024)
  LLM_MAX_TOKENS_REPORT — weekly report (default: 2048)
  ANTHROPIC_API_KEY
  ANTHROPIC_BASE_URL
  ANTHROPIC_MODEL        — fallback if LLM_MODEL not set

Retry policy:
  - 401, 402, 403 → do NOT retry
  - Timeout, 429, 5xx, JSON parse failure → retry (up to 2x)
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────

def _env_model() -> str:
    return os.getenv("LLM_MODEL") or os.getenv("ANTHROPIC_MODEL") or "deepseek-v4-flash"

def _env_thinking() -> Optional[Dict[str, Any]]:
    raw = os.getenv("LLM_THINKING", "")
    if raw:
        try:
            import json
            return json.loads(raw)
        except Exception:
            logger.warning(f"Invalid LLM_THINKING JSON: {raw}, using disabled default")
    # DeepSeek default: disable thinking for structured output
    return {"type": "disabled"}

def _env_max_tokens(env_var: str, default: int) -> int:
    try:
        return int(os.getenv(env_var, str(default)))
    except ValueError:
        return default


# ── Token budgets by context ─────────────────────────────────────────────────

PLAN_MAX_TOKENS = _env_max_tokens("LLM_MAX_TOKENS_PLAN", 4096)
CHAT_MAX_TOKENS = _env_max_tokens("LLM_MAX_TOKENS_CHAT", 1024)
REPORT_MAX_TOKENS = _env_max_tokens("LLM_MAX_TOKENS_REPORT", 2048)


# ── Response helper ───────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    text: str = ""
    stop_reason: Optional[str] = None
    truncated: bool = False


def _extract_text(response: Any) -> LLMResponse:
    """Safely extract text from a messages.create response.

    Iterates all content blocks, concatenating only type=='text' blocks.
    Does NOT assume content[0] is text (thinking blocks may come first).
    """
    result = LLMResponse()

    try:
        result.stop_reason = getattr(response, "stop_reason", None)
    except Exception:
        pass

    # Check for length truncation
    if result.stop_reason == "max_tokens":
        result.truncated = True

    content = getattr(response, "content", [])
    if not content:
        return result

    parts = []
    for block in content:
        try:
            if getattr(block, "type", None) == "text":
                t = getattr(block, "text", None)
                if t:
                    parts.append(str(t))
        except Exception:
            continue

    result.text = "".join(parts)
    return result


def _sanitize_error_message(exc: Exception) -> str:
    """Strip API keys, raw responses, and key suffixes from error messages."""
    msg = str(exc)
    # Truncate long messages
    if len(msg) > 500:
        msg = msg[:500] + "..."
    return msg


# ── Client class ─────────────────────────────────────────────────────────────

class LLMClient:
    """Unified async LLM client with retry logic and multi-block parsing."""

    # Status codes that should NOT be retried
    NO_RETRY_CODES = frozenset({401, 402, 403})

    # Status codes that DO trigger retry
    RETRY_CODES = frozenset({429, 500, 502, 503, 504})

    MAX_RETRIES = 2

    def __init__(
        self,
        api_key: str = "",
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL", "").strip() or None
        self.model = model or _env_model()

        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = AsyncAnthropic(**kwargs)

        self._thinking = _env_thinking()
        logger.info(
            "LLM client: model=%s base_url=%s thinking=%s",
            self.model,
            self.base_url or "(default)",
            self._thinking,
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        system: Optional[str] = None,
        max_tokens: int = CHAT_MAX_TOKENS,
        temperature: float = 0.3,
        timeout: float = 90.0,
    ) -> LLMResponse:
        """Chat-style completion with retry on transient errors."""
        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return await self._create(
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
            except Exception as e:
                last_error = e
                if not self._should_retry(e, attempt):
                    raise
                logger.warning(
                    "LLM chat attempt %d/%d failed (retrying): %s",
                    attempt + 1, self.MAX_RETRIES + 1, _sanitize_error_message(e),
                )
                time.sleep(min(2 ** attempt, 4))  # backoff

        # If we exhaust retries, return a safe error response
        # (in practice, the last exception is re-raised in _should_retry)
        raise last_error or RuntimeError("LLM request failed")

    async def generate_json(
        self,
        prompt: str,
        *,
        max_tokens: int = PLAN_MAX_TOKENS,
        temperature: float = 0.3,
        timeout: float = 120.0,
        retries: int = 2,
    ) -> LLMResponse:
        """Generate structured JSON output with retry on parse failure."""
        last_error = None

        for attempt in range(retries + 1):
            try:
                resp = await self._create(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
                if resp.truncated:
                    # Try with larger token budget once
                    if attempt == 0 and max_tokens < PLAN_MAX_TOKENS * 2:
                        logger.warning("Output truncated, retrying with larger max_tokens")
                        max_tokens = min(max_tokens * 2, 16384)
                        continue
                    raise RuntimeError("LLM output was truncated (max_tokens reached)")
                return resp
            except Exception as e:
                last_error = e
                if not self._should_retry(e, attempt):
                    raise
                logger.warning(
                    "LLM generate attempt %d/%d failed: %s",
                    attempt + 1, retries + 1, _sanitize_error_message(e),
                )
                time.sleep(min(2 ** attempt, 4))

        raise last_error or RuntimeError("LLM generate request failed")

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _create(
        self,
        messages: List[Dict[str, str]],
        *,
        system: Optional[str] = None,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> LLMResponse:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = self._clean(system)
        # Clean all user-facing messages to avoid encoding errors
        kwargs["messages"] = [
            {"role": m["role"], "content": self._clean(m["content"])}
            for m in messages
        ]
        if self._thinking:
            kwargs["thinking"] = self._thinking

        try:
            resp = await self._client.messages.create(**kwargs)
            result = _extract_text(resp)

            # Truncation handling
            if result.truncated and not result.text:
                result.text = "Model returned no final text response"

            return result
        except Exception as e:
            # Unwrap Anthropic API errors
            status = getattr(e, "status_code", 0)
            msg = _sanitize_error_message(e)
            if status:
                raise LLMAPIError(msg, status_code=status)
            raise

    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        if attempt >= self.MAX_RETRIES:
            return False

        status = getattr(exc, "status_code", 0)
        if status in self.NO_RETRY_CODES:
            logger.error("LLM authentication error (status=%d): not retrying", status)
            return False

        if status in self.RETRY_CODES:
            return True

        # Network errors, timeouts — retry
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return True

        # RuntimeError for truncation/parse — retry
        if isinstance(exc, RuntimeError) and "truncat" in str(exc).lower():
            return True

        return False

    @staticmethod
    def _clean(text: str) -> str:
        """Strip surrogate characters that break JSON encoding."""
        if not text:
            return ""
        return text.encode("utf-8", errors="ignore").decode("utf-8")


class LLMAPIError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
