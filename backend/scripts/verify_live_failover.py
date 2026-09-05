"""Verification script for Gemini Multi-Key Failover Pool in RevenueOS.

Runs:
1. Configuration check & key masking verification.
2. GCP Project distribution analysis.
3. LIVE Gemini call against Google Gemini API with GEMINI_API_KEY_1.
4. CONTROLLED SIMULATION of Key 1 (429) -> Key 2 failover.
5. Overhead benchmark comparing single-key direct lookup vs multi-key pool selection.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "revenueos.settings")
import django

django.setup()

from apps.brain.config import (
    get_configured_gemini_api_keys,
    get_configured_gemini_model,
    mask_api_key,
    validate_gemini_configuration,
)
from apps.brain.key_pool import GeminiKeyPool, reset_key_pool
from apps.brain.provider import GeminiProvider
from apps.brain.schemas import RecoveryBrainInput


async def main() -> None:
    print("=" * 60)
    print("REVENUEOS MULTI-KEY GEMINI FAILOVER VERIFICATION")
    print("=" * 60)

    # 1. Config Validation
    validate_gemini_configuration()
    keys = get_configured_gemini_api_keys()
    print("\n[1] CONFIGURATION VALIDATION:")
    print(f"Total configured keys: {len(keys)}")
    for slot_id, key in keys:
        print(f"  Slot: {slot_id} -> Key: {mask_api_key(key)}")

    # 2. Project Distribution
    pool = reset_key_pool()
    dist = pool.detect_project_distribution()
    print("\n[2] PROJECT DISTRIBUTION DETECTION:")
    print(f"Key Count: {dist['key_count']}")
    print(f"Distinct Key Count: {dist['distinct_key_count']}")
    print(f"Project Distribution: {dist['project_distribution']}")
    print(f"Shared Project Quota: {dist['shared_quota']}")
    print(f"Summary: {dist['summary']}")

    # 3. Overhead Benchmark: Key Selection & Client Lookup
    print("\n[3] PERFORMANCE / OVERHEAD MEASUREMENT:")
    trials = 10000
    t0 = time.perf_counter()
    for _ in range(trials):
        _ = pool.get_eligible_slots()
    t_pool = (time.perf_counter() - t0) / trials * 1_000_000

    t0 = time.perf_counter()
    for _ in range(trials):
        _ = pool.get_active_slot()
    t_active = (time.perf_counter() - t0) / trials * 1_000_000

    print(f"Key selection overhead (get_eligible_slots): {t_pool:.3f} microseconds per request")
    print(f"Active key lookup overhead (get_active_slot): {t_active:.3f} microseconds per request")

    # 4. LIVE GEMINI INFERENCE (Controlled single request)
    print("\n[4] LIVE GEMINI API INFERENCE (Using GEMINI_API_KEY_1):")
    model_name = get_configured_gemini_model()
    print(f"Configured Model: {model_name}")

    provider = GeminiProvider()
    input_ctx = RecoveryBrainInput(
        payment_id="pay_live_audit_001",
        amount_paise=450000,
        currency="INR",
        failure_category="insufficient_funds",
        failure_reason="Cardholder balance insufficient for debit",
        retry_count=0,
        max_retries_allowed=3,
        recoverability_score=78,
    )

    t_start = time.perf_counter()
    result = await provider.generate_recommendation_async(input_ctx)
    t_live_total = (time.perf_counter() - t_start) * 1000

    print("LIVE GEMINI RESULT:")
    print(f"  Action: {result.action}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Expected Recovery Value: {result.expected_recovery_value_paise} paise")
    print(f"  Reason: {result.reason}")
    print(f"  Is Fallback: {result.is_fallback}")
    print(f"  Total Wall Clock: {t_live_total:.1f}ms")
    print(f"  Telemetry: {result.telemetry}")

    # 5. CONTROLLED SIMULATION: Failover Path Timing
    print("\n[5] CONTROLLED SIMULATION: FAILOVER PATH TIMINGS")
    # Simulate Key 1 returning 429 in 50ms, Key 2 succeeding in 600ms
    from unittest.mock import AsyncMock, MagicMock
    m_client1 = MagicMock()
    m_client1.aio.models.generate_content = AsyncMock(side_effect=Exception("429 RESOURCE_EXHAUSTED"))

    m_client2 = MagicMock()
    m_resp2 = MagicMock()
    m_resp2.text = (
        '{"action": "PAYMENT_LINK", "confidence": 0.88, "expected_recovery_value_paise": 400000, '
        '"reason": "Simulated failover to Key 2 succeeded.", "supporting_factors": ["Key 2 healthy"], '
        '"risk_factors": [], "stop_rationale": null}'
    )
    m_resp2.usage_metadata.prompt_token_count = 120
    m_resp2.usage_metadata.candidates_token_count = 35
    m_client2.aio.models.generate_content = AsyncMock(return_value=m_resp2)

    sim_pool = GeminiKeyPool([("KEY_1", "key1_sim"), ("KEY_2", "key2_sim")])
    sim_pool.slots[0]._client = m_client1
    sim_pool.slots[1]._client = m_client2
    sim_provider = GeminiProvider(pool=sim_pool)

    t_sim_start = time.perf_counter()
    sim_out = await sim_provider.generate_recommendation_async(input_ctx)
    t_sim_total = (time.perf_counter() - t_sim_start) * 1000

    print("CONTROLLED SIMULATION RESULT (Key 1 -> Key 2):")
    print(f"  Action: {sim_out.action}")
    print(f"  Confidence: {sim_out.confidence}")
    print(f"  Key Slot: {sim_out.telemetry.get('key_slot')}")
    print(f"  Attempts: {sim_out.telemetry.get('attempts')}")
    print(f"  Total Sim Duration: {t_sim_total:.2f}ms")

    # 6. All Keys Exhausted Simulation
    m_client3 = MagicMock()
    m_client3.aio.models.generate_content = AsyncMock(side_effect=Exception("429 RESOURCE_EXHAUSTED"))
    exhaust_pool = GeminiKeyPool([("KEY_1", "k1"), ("KEY_2", "k2"), ("KEY_3", "k3")])
    exhaust_pool.slots[0]._client = m_client1
    exhaust_pool.slots[1]._client = m_client3
    exhaust_pool.slots[2]._client = m_client3
    exhaust_provider = GeminiProvider(pool=exhaust_pool)

    t_ex_start = time.perf_counter()
    ex_out = await exhaust_provider.generate_recommendation_async(input_ctx)
    t_ex_total = (time.perf_counter() - t_ex_start) * 1000

    print("\nCONTROLLED SIMULATION RESULT (All 3 Keys Exhausted -> Deterministic Fallback):")
    print(f"  Action: {ex_out.action}")
    print(f"  Confidence: {ex_out.confidence}")
    print(f"  Is Fallback: {ex_out.is_fallback}")
    print(f"  Fallback Reason: {ex_out.fallback_reason}")
    print(f"  Key Slot: {ex_out.telemetry.get('key_slot')}")
    print(f"  Attempts: {ex_out.telemetry.get('attempts')}")
    print(f"  Total Timing: {t_ex_total:.2f}ms")

    print("\nVerification Complete.")


if __name__ == "__main__":
    asyncio.run(main())
