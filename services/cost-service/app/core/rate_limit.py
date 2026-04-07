"""
CloudPulse AI - Cost Service
Simple auth-focused rate limiting helpers.
"""
from typing import Any
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import Depends, HTTPException, Request, status

from app.core.cache import RedisCache, get_cache
from app.core.config import get_settings

settings = get_settings()


@dataclass(frozen=True)
class RateLimitPolicy:
    name: str
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """A process-local rate limiter used for auth endpoints."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[str, deque[datetime]] = defaultdict(deque)

    async def hit(
        self,
        bucket: str,
        policy: RateLimitPolicy,
        cache: RedisCache | Any | None = None,
    ) -> None:
        """Record a request or raise if the bucket is currently limited."""
        cache_key = f"rate_limit:{bucket}"
        if cache is not None and hasattr(cache, "increment"):
            try:
                request_count = await cache.increment(cache_key, ttl=policy.window_seconds)
            except Exception:
                request_count = None
            else:
                if request_count > policy.max_requests:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=(
                            f"Too many {policy.name} attempts. "
                            f"Try again in {policy.window_seconds} seconds."
                        ),
                    )
                return

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=policy.window_seconds)

        with self._lock:
            events = self._events[bucket]
            while events and events[0] < window_start:
                events.popleft()

            if len(events) >= policy.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Too many {policy.name} attempts. "
                        f"Try again in {policy.window_seconds} seconds."
                    ),
                )

            events.append(now)

    def reset(self) -> None:
        """Clear all tracked rate-limit buckets."""
        with self._lock:
            self._events.clear()


rate_limiter = InMemoryRateLimiter()


def _request_ip(request: Request) -> str:
    """Resolve the best-effort client identifier for rate limiting."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else "unknown"


def auth_rate_limit(policy_name: str) -> Callable[[Request], None]:
    """Build a dependency that rate limits auth-sensitive endpoints."""
    policy = RateLimitPolicy(
        name=policy_name,
        max_requests=settings.auth_rate_limit_requests,
        window_seconds=settings.auth_rate_limit_window_seconds,
    )

    async def dependency(
        request: Request,
        cache: RedisCache = Depends(get_cache),
    ) -> None:
        bucket = f"{policy.name}:{_request_ip(request)}"
        await rate_limiter.hit(bucket, policy, cache)

    return dependency
