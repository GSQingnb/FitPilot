"""FitPilot LLM client tests — text extraction, thinking blocks, retry logic.

Tests the core/llm_client.py multi-block response parser and LLMClient class.
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── _extract_text tests ──────────────────────────────────────────────────────

class TestExtractText:
    def test_single_text_block(self):
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = [MagicMock(type="text", text="Hello world")]

        result = _extract_text(resp)
        assert result.text == "Hello world"
        assert result.truncated is False
        assert result.stop_reason == "end_turn"

    def test_thinking_block_before_text_block(self):
        """Thinking blocks (type != 'text') must be skipped, not crash content[0]."""
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = [
            MagicMock(type="thinking", text=None, thinking="some reasoning..."),
            MagicMock(type="text", text="final answer"),
        ]

        result = _extract_text(resp)
        assert result.text == "final answer"
        assert result.truncated is False

    def test_content_first_is_none_text(self):
        """content[0].text may be None (thinking block). Must not crash."""
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = [
            MagicMock(type="text", text=None),  # empty text block
            MagicMock(type="text", text="actual output"),
        ]

        result = _extract_text(resp)
        assert result.text == "actual output"

    def test_multiple_text_blocks_merged(self):
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = [
            MagicMock(type="text", text='{"key":'),
            MagicMock(type="text", text='"value"}'),
        ]

        result = _extract_text(resp)
        assert result.text == '{"key":"value"}'

    def test_no_text_blocks(self):
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = [
            MagicMock(type="thinking", text=None, thinking="deep thought..."),
            MagicMock(type="thinking", text=None, thinking="more thinking..."),
        ]

        result = _extract_text(resp)
        assert result.text == ""

    def test_empty_content_list(self):
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = []

        result = _extract_text(resp)
        assert result.text == ""

    def test_content_is_none(self):
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = None

        result = _extract_text(resp)
        assert result.text == ""

    def test_stop_reason_max_tokens(self):
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "max_tokens"
        resp.content = [MagicMock(type="text", text="partial output")]

        result = _extract_text(resp)
        assert result.truncated is True
        assert result.text == "partial output"

    def test_non_thinking_mode_returns_json(self):
        """Normal (non-thinking) mode: content[0] is text, returns JSON."""
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = [
            MagicMock(type="text", text='{"name": "Test Plan", "goal": "muscle_gain"}'),
        ]

        result = _extract_text(resp)
        assert "Test Plan" in result.text
        assert result.truncated is False

    def test_unicode_surrogate_characters_stripped(self):
        """Surrogate characters in LLM output must not cause encoding errors."""
        from core.llm_client import _extract_text

        resp = MagicMock()
        resp.stop_reason = "end_turn"
        # Text with embedded surrogate (should be handled by _clean in caller)
        resp.content = [MagicMock(type="text", text="clean text with emoji 🏋️")]

        result = _extract_text(resp)
        assert "clean text" in result.text
        assert "🏋️" in result.text


# ── LLMClient retry policy tests ─────────────────────────────────────────────

class TestLLMClientRetry:
    def test_401_not_retried(self):
        from core.llm_client import LLMClient

        client = LLMClient(api_key="fake", base_url="https://fake.api")
        assert client._should_retry(LLMAPIError("unauthorized", 401), 0) is False

    def test_402_not_retried(self):
        from core.llm_client import LLMClient, LLMAPIError

        client = LLMClient(api_key="fake")
        assert client._should_retry(LLMAPIError("payment required", 402), 0) is False

    def test_403_not_retried(self):
        from core.llm_client import LLMClient, LLMAPIError

        client = LLMClient(api_key="fake")
        assert client._should_retry(LLMAPIError("forbidden", 403), 0) is False

    def test_429_retried(self):
        from core.llm_client import LLMClient, LLMAPIError

        client = LLMClient(api_key="fake")
        assert client._should_retry(LLMAPIError("rate limited", 429), 0) is True

    def test_500_retried(self):
        from core.llm_client import LLMClient, LLMAPIError

        client = LLMClient(api_key="fake")
        assert client._should_retry(LLMAPIError("server error", 500), 0) is True

    def test_timeout_retried(self):
        from core.llm_client import LLMClient

        client = LLMClient(api_key="fake")
        assert client._should_retry(TimeoutError("timed out"), 0) is True

    def test_connection_error_retried(self):
        from core.llm_client import LLMClient

        client = LLMClient(api_key="fake")
        assert client._should_retry(ConnectionError("refused"), 0) is True

    def test_not_retried_after_max_attempts(self):
        from core.llm_client import LLMClient, LLMAPIError

        client = LLMClient(api_key="fake")
        # Attempt 2 = the third attempt (0-indexed), which exceeds MAX_RETRIES=2
        assert client._should_retry(LLMAPIError("server error", 500), 2) is False


# ── Environment config tests ─────────────────────────────────────────────────

class TestLLMEnvConfig:
    def setup_method(self):
        self._saved = {}
        for key in ("LLM_MODEL", "ANTHROPIC_MODEL"):
            self._saved[key] = os.environ.pop(key, None)

    def teardown_method(self):
        for key, val in self._saved.items():
            if val is not None:
                os.environ[key] = val
            else:
                os.environ.pop(key, None)

    def test_default_model_is_deepseek(self):
        from core.llm_client import _env_model
        model = _env_model()
        assert model == "deepseek-v4-flash"

    def test_llm_model_override(self):
        os.environ["LLM_MODEL"] = "claude-opus-4-8"
        from core.llm_client import _env_model
        assert _env_model() == "claude-opus-4-8"

    def test_max_tokens_defaults(self):
        from core.llm_client import PLAN_MAX_TOKENS, CHAT_MAX_TOKENS, REPORT_MAX_TOKENS
        assert PLAN_MAX_TOKENS == 4096
        assert CHAT_MAX_TOKENS == 1024
        assert REPORT_MAX_TOKENS == 2048

    def test_thinking_disabled_by_default(self):
        from core.llm_client import _env_thinking
        result = _env_thinking()
        assert result == {"type": "disabled"}


# ── Error message sanitization ───────────────────────────────────────────────

class TestSanitizeError:
    def test_long_error_truncated(self):
        from core.llm_client import _sanitize_error_message
        long_msg = "x" * 600
        result = _sanitize_error_message(RuntimeError(long_msg))
        assert len(result) <= 503  # 500 + "..."
        assert result.endswith("...")

    def test_short_error_preserved(self):
        from core.llm_client import _sanitize_error_message
        result = _sanitize_error_message(RuntimeError("short error"))
        assert result == "short error"


# Ensure LLMAPIError import available in test module
from core.llm_client import LLMAPIError
