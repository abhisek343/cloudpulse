"""
CloudPulse AI - Cost Service
Circuit breaker for external API calls.

Prevents cascading failures when cloud provider APIs are unavailable.
After `failure_threshold` consecutive failures the circuit opens and
fast-fails for `recovery_timeout` seconds before allowing a probe.
"""
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing fast
    HALF_OPEN = "half_open"  # Probing with a single request


@dataclass
class CircuitBreaker:
    """Per-provider circuit breaker."""

    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        """Reset after a successful call."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self, exc: Exception | None = None) -> None:
        """Record a failure; open the circuit if threshold is reached."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker [%s] OPEN after %d failures (recovery in %ds)",
                self.name, self._failure_count, self.recovery_timeout,
            )

    def ensure_closed(self) -> None:
        """Raise if circuit is open; used before making an external call."""
        state = self.state
        if state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit breaker [{self.name}] is open — "
                f"retry after {self.recovery_timeout}s"
            )


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open."""


# Global registry — one breaker per provider
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(provider: str) -> CircuitBreaker:
    """Return (or create) the circuit breaker for a cloud provider."""
    if provider not in _breakers:
        _breakers[provider] = CircuitBreaker(name=provider)
    return _breakers[provider]


def breaker_status() -> dict[str, dict[str, Any]]:
    """Snapshot of all breaker states — useful for health endpoints."""
    return {
        name: {
            "state": cb.state,
            "failure_count": cb._failure_count,
        }
        for name, cb in _breakers.items()
    }
