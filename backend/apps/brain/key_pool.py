"""Gemini Multi-Key Failover Pool & Lifecycle Manager.

Manages an ordered pool of up to three Gemini credentials (KEY_1, KEY_2, KEY_3)
with intelligent failure classification, per-key cooldowns, client reuse,
concurrency safety, and zero secret leakage.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from google import genai
from pydantic import ValidationError

from apps.brain.config import (
    get_configured_gemini_api_keys,
    mask_api_key,
)

logger = logging.getLogger("revenueos.brain.key_pool")

DEFAULT_COOLDOWN_SECONDS = 60.0
MAX_KEY_SLOTS = 3


@dataclass
class GeminiKeySlot:
    """Represents a single Gemini API credential slot with runtime health tracking."""

    slot_id: str
    _api_key: str = field(repr=False)  # Never expose raw key in repr
    is_active: bool = True
    cooldown_until: float = 0.0
    consecutive_failures: int = 0
    last_failure_time: float | None = None
    failure_category: str | None = None
    is_quota_exhausted: bool = False
    is_temporarily_unavailable: bool = False
    project_id: str | None = None
    _client: genai.Client | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        masked = mask_api_key(self._api_key)
        return (
            f"<GeminiKeySlot slot_id={self.slot_id} key={masked} "
            f"active={self.is_active} cooldown_until={self.cooldown_until:.1f} "
            f"failures={self.consecutive_failures} quota_exhausted={self.is_quota_exhausted}>"
        )

    def __str__(self) -> str:
        return f"{self.slot_id} ({mask_api_key(self._api_key)})"

    @property
    def api_key(self) -> str:
        """Return the raw API key for SDK invocation (internal use only)."""
        return self._api_key

    def get_client(self) -> genai.Client:
        """Obtain or reuse the singleton genai.Client for this credential slot."""
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def is_eligible(self, now: float | None = None) -> bool:
        """Check if slot is active and not currently in cooldown."""
        current_time = now if now is not None else time.perf_counter()
        if not self.is_active:
            return False
        return current_time >= self.cooldown_until

    def reset_client(self) -> None:
        """Reset the cached client instance."""
        self._client = None


def is_failover_eligible(exc: Exception) -> tuple[bool, str]:
    """Determine whether an exception is a key/project-specific failure justifying failover.

    Returns:
        (is_eligible, failure_category)

    Failover Eligible:
    - 429 / RESOURCE_EXHAUSTED / Quota limit / Rate limit
    - 401 / 403 / API_KEY_INVALID / UNAUTHENTICATED / PERMISSION_DENIED
    - 503 / 502 / UNAVAILABLE / Service unavailable
    - Timeout connecting to Gemini provider

    Non-Eligible (Application / Schema / Logic issues):
    - Pydantic ValidationError (model schema formatting error)
    - JSONDecodeError (invalid JSON response)
    - Local application logic errors / ValueError / KeyError
    """
    if isinstance(exc, (ValidationError, ValueError, KeyError)):
        return False, "NON_RETRYABLE_APPLICATION_ERROR"

    err_str = str(exc).lower()
    err_cls = exc.__class__.__name__.lower()

    # 1. 429 Quota / Rate Limit
    if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str or "rate limit" in err_str:
        return True, "QUOTA_EXHAUSTED"

    # 2. 401/403 Invalid or Rejected Credentials
    if "401" in err_str or "403" in err_str or "unauthenticated" in err_str or "permission_denied" in err_str or "api_key_invalid" in err_str:
        return True, "CREDENTIAL_REJECTED"

    # 3. 503 / Service Unavailable
    if "503" in err_str or "502" in err_str or "unavailable" in err_str or "overloaded" in err_str:
        return True, "SERVICE_UNAVAILABLE"

    # 4. Timeout to Google Provider
    if "timeout" in err_str or "timed out" in err_str or "timeouterror" in err_cls:
        return True, "PROVIDER_TIMEOUT"

    # Generic unhandled provider errors
    if "genai" in err_cls or "google" in err_cls:
        return True, "PROVIDER_ERROR"

    return False, "NON_RETRYABLE_ERROR"


class GeminiKeyPool:
    """Concurrency-safe, ordered pool of Gemini API keys with health tracking and failover."""

    def __init__(self, key_tuples: list[tuple[str, str]] | None = None) -> None:
        self._lock = asyncio.Lock()
        self.slots: list[GeminiKeySlot] = []

        raw_keys = key_tuples if key_tuples is not None else get_configured_gemini_api_keys()
        for idx, (slot_id, key) in enumerate(raw_keys[:MAX_KEY_SLOTS]):
            self.slots.append(
                GeminiKeySlot(
                    slot_id=slot_id or f"KEY_{idx + 1}",
                    _api_key=key,
                )
            )

        logger.info(
            "Initialized GeminiKeyPool with %d configured key slot(s): %s",
            len(self.slots),
            ", ".join(str(s) for s in self.slots),
        )

    def __len__(self) -> int:
        return len(self.slots)

    @property
    def size(self) -> int:
        return len(self.slots)

    def get_slot_by_id(self, slot_id: str) -> GeminiKeySlot | None:
        """Find slot by its identifier (e.g. 'KEY_1')."""
        for s in self.slots:
            if s.slot_id == slot_id:
                return s
        return None

    def get_active_slot(self, now: float | None = None) -> GeminiKeySlot | None:
        """Return the preferred healthy key slot (Slot 1 preferred, then Slot 2, then Slot 3)."""
        current_time = now if now is not None else time.perf_counter()
        for slot in self.slots:
            if slot.is_eligible(current_time):
                return slot
        return None

    def get_eligible_slots(self, now: float | None = None) -> list[GeminiKeySlot]:
        """Return all eligible key slots in priority order."""
        current_time = now if now is not None else time.perf_counter()
        return [s for s in self.slots if s.is_eligible(current_time)]

    async def mark_failure_async(
        self,
        slot_id: str,
        category: str,
        cooldown_s: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        """Thread-safe update of slot health following an eligible failure."""
        async with self._lock:
            self.mark_failure(slot_id, category, cooldown_s)

    def mark_failure(
        self,
        slot_id: str,
        category: str,
        cooldown_s: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        """Record a failure for a key slot and set its cooldown window."""
        slot = self.get_slot_by_id(slot_id)
        if not slot:
            return

        now = time.perf_counter()
        slot.consecutive_failures += 1
        slot.last_failure_time = now
        slot.failure_category = category
        slot.cooldown_until = now + cooldown_s
        slot.is_temporarily_unavailable = True

        if category == "QUOTA_EXHAUSTED":
            slot.is_quota_exhausted = True

        logger.warning(
            "Gemini key slot %s marked failed (category=%s, failures=%d). Cooldown for %.1fs until %.2f",
            slot_id,
            category,
            slot.consecutive_failures,
            cooldown_s,
            slot.cooldown_until,
        )

    async def mark_success_async(self, slot_id: str) -> None:
        """Thread-safe update of slot health following a successful call."""
        async with self._lock:
            self.mark_success(slot_id)

    def mark_success(self, slot_id: str) -> None:
        """Record a success for a key slot, clearing transient failure flags."""
        slot = self.get_slot_by_id(slot_id)
        if not slot:
            return

        if slot.consecutive_failures > 0 or slot.is_temporarily_unavailable:
            logger.info("Gemini key slot %s restored to healthy status.", slot_id)

        slot.consecutive_failures = 0
        slot.cooldown_until = 0.0
        slot.failure_category = None
        slot.is_quota_exhausted = False
        slot.is_temporarily_unavailable = False

    def detect_project_distribution(self) -> dict[str, Any]:
        """Analyze configured keys to determine project distribution and quota implications.

        Google AI Studio and Cloud Console enforce API quotas (e.g. 20 req/day free-tier on gemini-3.6-flash)
        at the PROJECT level, not per key. If multiple keys are from the same project,
        they share the exact same quota.
        """
        key_count = len(self.slots)
        if key_count == 0:
            return {
                "key_count": 0,
                "project_distribution": "NO_KEYS_CONFIGURED",
                "shared_quota": True,
                "summary": "No Gemini API keys configured.",
            }

        # Check unique key values
        unique_keys = {s.api_key for s in self.slots}
        distinct_key_count = len(unique_keys)

        # Detect identical keys configured in multiple slots
        is_duplicate = distinct_key_count < key_count

        # Google Cloud project inference:
        # Standard Studio keys format: AQ.Ab8... or AIzaSy...
        if is_duplicate:
            distribution = "IDENTICAL_KEY_DUPLICATION"
            shared_quota = True
            summary = (
                f"Configured {key_count} slot(s) with only {distinct_key_count} distinct key string(s). "
                "Keys share identical project-level quota. Failover does not provide independent quota capacity."
            )
        elif key_count == 1:
            distribution = "SINGLE_PROJECT"
            shared_quota = False
            summary = "Single Gemini API key configured in Key Pool."
        else:
            # When distinct keys are configured without project metadata:
            distribution = "MULTIPLE_KEYS_POTENTIALLY_SHARED_PROJECT"
            shared_quota = True  # Conservative default: assume shared unless verified from different projects
            summary = (
                f"{key_count} distinct Gemini API key(s) configured. "
                "Note: If these keys originate from the same Google Cloud / AI Studio project, "
                "they share the same project-level rate limit and daily quota (e.g. 20 req/day on gemini-3.6-flash free tier). "
                "Failover provides protection against key invalidation, transient network drops, or distinct project quotas."
            )

        return {
            "key_count": key_count,
            "distinct_key_count": distinct_key_count,
            "project_distribution": distribution,
            "shared_quota": shared_quota,
            "summary": summary,
        }

    def close_all(self) -> None:
        """Reset all client connections in the pool."""
        for slot in self.slots:
            slot.reset_client()


# Singleton Key Pool Instance
_shared_pool: GeminiKeyPool | None = None


def get_key_pool() -> GeminiKeyPool:
    """Obtain or lazily initialize the shared GeminiKeyPool instance."""
    global _shared_pool
    if _shared_pool is None:
        _shared_pool = GeminiKeyPool()
    return _shared_pool


def reset_key_pool(custom_keys: list[tuple[str, str]] | None = None) -> GeminiKeyPool:
    """Reset the shared GeminiKeyPool instance (for tests and dynamic reconfiguration)."""
    global _shared_pool
    if _shared_pool is not None:
        _shared_pool.close_all()
    _shared_pool = GeminiKeyPool(custom_keys)
    return _shared_pool
