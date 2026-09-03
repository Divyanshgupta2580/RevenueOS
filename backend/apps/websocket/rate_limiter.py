"""In-memory rate limiter for WebSocket RPC commands.

Enforces per-session rate limits to protect backend resources and external APIs.
"""

import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    capacity: float
    rate: float  # tokens added per second
    tokens: float
    last_updated: float


class WebSocketRateLimiter:
    """Token-bucket rate limiter per session and command type."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def is_allowed(
        self,
        session_id: str,
        command_type: str,
        capacity: float = 60.0,
        rate: float = 1.0,
    ) -> bool:
        """Check if request is allowed under the token bucket policy.

        Default: 60 tokens burst capacity, replenishing at 1 token/sec (60/min).
        For sensitive actions (e.g. recovery.execute): capacity=10, rate=0.2 (12/min).
        """
        now = time.monotonic()
        key = f"{session_id}:{command_type}"

        if len(self._buckets) > 500:
            self.prune_stale()

        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                capacity=capacity,
                rate=rate,
                tokens=capacity - 1.0,
                last_updated=now,
            )
            return True

        bucket = self._buckets[key]
        elapsed = now - bucket.last_updated
        bucket.last_updated = now

        # Add newly accrued tokens up to capacity
        bucket.tokens = min(bucket.capacity, bucket.tokens + (elapsed * bucket.rate))

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True

        return False

    def prune_stale(self, max_idle_seconds: float = 3600.0) -> None:
        """Clean up buckets that have been inactive."""
        now = time.monotonic()
        stale_keys = [
            k for k, b in self._buckets.items() if (now - b.last_updated) > max_idle_seconds
        ]
        for k in stale_keys:
            del self._buckets[k]


rate_limiter = WebSocketRateLimiter()
