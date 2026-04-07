"""
CloudPulse AI - Cost Service
Tests for circuit breaker, rate limiter, logging, and cost sync hardening.
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    get_breaker,
    breaker_status,
)
from app.core.logging import sanitize_error, JSONFormatter
from app.core.rate_limit import InMemoryRateLimiter, RateLimitPolicy
from fastapi import HTTPException


# === Circuit Breaker Tests ===


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_ensure_closed_raises_when_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()
        with pytest.raises(CircuitOpenError):
            cb.ensure_closed()

    def test_success_resets(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED  # reset, so only 1 failure

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_get_breaker_returns_same_instance(self):
        b1 = get_breaker("aws-test")
        b2 = get_breaker("aws-test")
        assert b1 is b2

    def test_breaker_status_reports_state(self):
        cb = get_breaker("status-test")
        cb.record_failure()
        status = breaker_status()
        assert "status-test" in status
        assert status["status-test"]["failure_count"] == 1


# === Rate Limiter Tests ===


class TestInMemoryRateLimiter:
    def test_allows_under_limit(self):
        limiter = InMemoryRateLimiter()
        policy = RateLimitPolicy(name="test", max_requests=5, window_seconds=60)
        loop = asyncio.new_event_loop()
        for _ in range(5):
            loop.run_until_complete(limiter.hit("bucket1", policy))
        loop.close()

    def test_blocks_over_limit(self):
        limiter = InMemoryRateLimiter()
        policy = RateLimitPolicy(name="test", max_requests=2, window_seconds=60)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(limiter.hit("bucket2", policy))
        loop.run_until_complete(limiter.hit("bucket2", policy))
        with pytest.raises(HTTPException) as exc_info:
            loop.run_until_complete(limiter.hit("bucket2", policy))
        assert exc_info.value.status_code == 429
        loop.close()

    def test_window_expires(self):
        limiter = InMemoryRateLimiter()
        policy = RateLimitPolicy(name="test", max_requests=1, window_seconds=0)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(limiter.hit("bucket3", policy))
        loop.run_until_complete(limiter.hit("bucket3", policy))
        loop.close()

    def test_reset_clears_all(self):
        limiter = InMemoryRateLimiter()
        policy = RateLimitPolicy(name="test", max_requests=1, window_seconds=60)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(limiter.hit("bucket4", policy))
        limiter.reset()
        loop.run_until_complete(limiter.hit("bucket4", policy))
        loop.close()

    def test_redis_fallback_on_error(self):
        """When Redis raises, falls back to in-memory limiter."""
        limiter = InMemoryRateLimiter()
        policy = RateLimitPolicy(name="test", max_requests=5, window_seconds=60)
        broken_cache = MagicMock()
        broken_cache.increment = AsyncMock(side_effect=ConnectionError("Redis down"))
        loop = asyncio.new_event_loop()
        loop.run_until_complete(limiter.hit("bucket5", policy, cache=broken_cache))
        loop.close()


# === Sanitize Error Tests ===


class TestSanitizeError:
    def test_basic_message(self):
        result = sanitize_error(ValueError("connection refused"))
        assert result == "connection refused"

    def test_redacts_aws_key(self):
        result = sanitize_error(ValueError("Invalid key AKIAIOSFODNN7EXAMPLE in request"))
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED]" in result

    def test_redacts_bearer_token(self):
        result = sanitize_error(ValueError("Authorization: Bearer eyJhbGciOiJI..."))
        assert "eyJhbGciOiJI" not in result
        assert "[REDACTED]" in result

    def test_redacts_password_in_url(self):
        result = sanitize_error(ValueError("password=s3cr3t in config"))
        assert "s3cr3t" not in result

    def test_truncation(self):
        long_msg = "x" * 1000
        result = sanitize_error(ValueError(long_msg), max_length=100)
        assert len(result) == 101  # 100 + "…"
        assert result.endswith("…")

    def test_empty_exception(self):
        result = sanitize_error(ValueError(""))
        assert result == ""


class TestJSONFormatter:
    def test_format_basic(self):
        import logging
        import json

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["msg"] == "hello world"
        assert parsed["level"] == "INFO"
        assert "ts" in parsed


# === Cost Sync Transaction Tests ===


class TestCostSyncTransactionIsolation:
    """Verify that cost sync uses begin_nested for atomic delete+insert."""

    def test_sync_uses_nested_transaction(self):
        """The sync method should use begin_nested() for the delete+insert block."""
        import inspect
        from app.services.cost_sync import CostSyncService
        source = inspect.getsource(CostSyncService.sync_account_costs)
        assert "begin_nested" in source, "sync_account_costs should use begin_nested for atomicity"

    def test_sync_uses_sanitize_error(self):
        """Error messages stored in DB should be sanitized."""
        import inspect
        from app.services.cost_sync import CostSyncService
        source = inspect.getsource(CostSyncService.sync_account_costs)
        assert "sanitize_error" in source, "sync should use sanitize_error, not raw str(exc)"
        assert "str(exc)" not in source, "str(exc) should be replaced with sanitize_error"

    def test_sync_uses_circuit_breaker(self):
        """Sync should check circuit breaker before calling cloud API."""
        import inspect
        from app.services.cost_sync import CostSyncService
        source = inspect.getsource(CostSyncService.sync_account_costs)
        assert "ensure_closed" in source
        assert "record_success" in source
        assert "record_failure" in source
