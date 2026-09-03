"""Safe Observability & Usage Tracking for Gemini Recovery Brain.

Tracks request counts, deterministic skips, deduplicated calls, failures,
latencies, and token consumption metrics (when returned by the SDK).
Does NOT log or store API keys, customer PII, card numbers, or authorization secrets.
"""

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeminiUsageMetrics:
    """Thread-safe aggregate metrics for Gemini API usage."""

    gemini_requests: int = 0
    gemini_skipped_deterministic: int = 0
    gemini_deduplicated: int = 0
    gemini_failures: int = 0
    gemini_schema_failures: int = 0
    gemini_input_tokens: int = 0
    gemini_output_tokens: int = 0
    gemini_total_tokens: int = 0
    last_latency_ms: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def record_request(
        self,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        with self._lock:
            self.gemini_requests += 1
            self.last_latency_ms = latency_ms
            if isinstance(input_tokens, (int, float)) and input_tokens > 0:
                self.gemini_input_tokens += int(input_tokens)
            if isinstance(output_tokens, (int, float)) and output_tokens > 0:
                self.gemini_output_tokens += int(output_tokens)
            self.gemini_total_tokens = self.gemini_input_tokens + self.gemini_output_tokens

    def record_skip(self) -> None:
        with self._lock:
            self.gemini_skipped_deterministic += 1

    def record_dedup(self) -> None:
        with self._lock:
            self.gemini_deduplicated += 1

    def record_failure(self) -> None:
        with self._lock:
            self.gemini_failures += 1

    def record_schema_failure(self) -> None:
        with self._lock:
            self.gemini_schema_failures += 1

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "gemini_requests": self.gemini_requests,
                "gemini_skipped_deterministic": self.gemini_skipped_deterministic,
                "gemini_deduplicated": self.gemini_deduplicated,
                "gemini_failures": self.gemini_failures,
                "gemini_schema_failures": self.gemini_schema_failures,
                "gemini_input_tokens": self.gemini_input_tokens,
                "gemini_output_tokens": self.gemini_output_tokens,
                "gemini_total_tokens": self.gemini_total_tokens,
                "gemini_latency": self.last_latency_ms,
            }

    def reset(self) -> None:
        with self._lock:
            self.gemini_requests = 0
            self.gemini_skipped_deterministic = 0
            self.gemini_deduplicated = 0
            self.gemini_failures = 0
            self.gemini_schema_failures = 0
            self.gemini_input_tokens = 0
            self.gemini_output_tokens = 0
            self.gemini_total_tokens = 0
            self.last_latency_ms = 0.0


# Global singleton instance
usage_tracker = GeminiUsageMetrics()
