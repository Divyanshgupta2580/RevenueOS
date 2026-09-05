"""Execute real live failover test through GeminiProvider.

KEY_1 is quota-exhausted (real 429).
GeminiKeyPool should catch 429 on KEY_1, mark it failed, and fail over to KEY_2.
KEY_2 will make a real call to Google Gemini 3.6 Flash and succeed!
"""

import asyncio
import os
import sys
import time
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "revenueos.settings")
import django

django.setup()

from apps.brain.key_pool import reset_key_pool
from apps.brain.provider import GeminiProvider
from apps.brain.schemas import RecoveryBrainInput


async def main():
    print("=" * 60)
    print("LIVE REAL-PROVIDER FAILOVER EXECUTION TEST")
    print("=" * 60)

    # Fresh pool with runtime keys from settings (.env)
    pool = reset_key_pool()
    provider = GeminiProvider(pool=pool)

    print("Initial Key Pool State:")
    for slot in pool.slots:
        print(f"  {slot.slot_id} | eligible={slot.is_eligible()} | quota_exhausted={slot.is_quota_exhausted}")

    ctx = RecoveryBrainInput(
        payment_id="pay_real_failover_test_01",
        amount_paise=150000,
        currency="INR",
        failure_category="insufficient_funds",
        failure_reason="Cardholder balance insufficient for debit",
        retry_count=0,
        max_retries_allowed=3,
        recoverability_score=75,
    )

    print("\nCalling provider.generate_recommendation_async(ctx) ...")
    t0 = time.perf_counter()
    out = await provider.generate_recommendation_async(ctx)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    print("\nREAL FAILOVER RESULT:")
    print(f"  Action: {out.action}")
    print(f"  Confidence: {out.confidence}")
    print(f"  Expected Recovery: {out.expected_recovery_value_paise} paise")
    print(f"  Is Fallback: {out.is_fallback}")
    print(f"  Reason: {out.reason}")
    print(f"  Telemetry: {out.telemetry}")
    print(f"  Total Wall-Clock Latency: {elapsed_ms}ms")

    print("\nKey Pool State AFTER Request:")
    for slot in pool.slots:
        print(f"  {slot.slot_id} | eligible={slot.is_eligible()} | quota_exhausted={slot.is_quota_exhausted} | failures={slot.consecutive_failures}")

    # Now make a SECOND request: KEY_1 is in cooldown, so it should go DIRECTLY to KEY_2 without attempting KEY_1!
    print("\nCalling second request (KEY_1 should be bypassed due to active cooldown) ...")
    t0 = time.perf_counter()
    out2 = await provider.generate_recommendation_async(ctx)
    elapsed2_ms = round((time.perf_counter() - t0) * 1000, 2)

    print("\nSECOND REQUEST RESULT:")
    print(f"  Action: {out2.action}")
    print(f"  Confidence: {out2.confidence}")
    print(f"  Is Fallback: {out2.is_fallback}")
    print(f"  Telemetry: {out2.telemetry}")
    print(f"  Total Wall-Clock Latency: {elapsed2_ms}ms")

    print("\nLive Failover Execution Complete.")


if __name__ == "__main__":
    asyncio.run(main())
