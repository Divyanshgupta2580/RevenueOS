"""Audit script for the newly configured 3-key Gemini runtime.

1. Safe runtime configuration check (masked identifiers).
2. Live provider tests for each key individually (KEY_1, KEY_2, KEY_3).
3. Project distribution detection and shared quota analysis.
4. Controlled failover simulations (429, timeout, 401/403).
5. Concurrency & in-flight deduplication tests.
6. Performance & latency benchmarks.
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

from google import genai
from google.genai import types

from apps.brain.config import (
    APPROVED_GEMINI_MODEL,
    get_configured_gemini_api_keys,
    get_configured_gemini_model,
    mask_api_key,
    validate_gemini_configuration,
)
from apps.brain.key_pool import GeminiKeyPool, reset_key_pool
from apps.brain.provider import GeminiProvider
from apps.brain.schemas import GeminiBrainRecommendation, RecoveryBrainInput
from apps.brain.service import RecoveryBrainService


async def test_single_real_key(slot_id: str, raw_key: str, model_name: str) -> dict:
    """Safely test a single real key with a minimal prompt without exposing secrets."""
    print(f"\n--- Testing real API access for {slot_id} ({mask_api_key(raw_key)}) ---")
    t0 = time.perf_counter()
    try:
        client = genai.Client(api_key=raw_key)
        # Minimal prompt to minimize quota consumption
        prompt = (
            "Analyze payment decline: category=insufficient_funds, amount=100000 paise. "
            "Return JSON matching schema: action, confidence, expected_recovery_value_paise, reason, supporting_factors, risk_factors."
        )
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiBrainRecommendation,
            temperature=0.1,
            max_output_tokens=300,
        )
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            ),
            timeout=10.0,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        print(f"[{slot_id}] SUCCESS in {elapsed_ms}ms! Response: {response.text[:120]}...")
        return {
            "slot_id": slot_id,
            "status": "SUCCESS",
            "latency_ms": elapsed_ms,
            "error": None,
            "quota_violation": None,
            "response_snippet": response.text[:100] if response.text else None,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        err_str = str(exc)
        print(f"[{slot_id}] FAILED in {elapsed_ms}ms: {err_str[:200]}")
        # Parse quota details if 429
        quota_details = None
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            quota_details = "RESOURCE_EXHAUSTED (Quota limit reached)"
            if "GenerateRequestsPerDayPerProjectPerModel-FreeTier" in err_str:
                quota_details += " [Project-level Free Tier 20 req/day limit]"
        return {
            "slot_id": slot_id,
            "status": "QUOTA_EXHAUSTED" if "429" in err_str else "ERROR",
            "latency_ms": elapsed_ms,
            "error": err_str[:300],
            "quota_violation": quota_details,
        }


async def main() -> None:
    print("=" * 65)
    print("REVENUEOS 3-KEY GEMINI RUNTIME AUDIT")
    print("=" * 65)

    # 1. Configuration Validation
    validate_gemini_configuration()
    keys = get_configured_gemini_api_keys()
    print("\n1. REAL RUNTIME CONFIGURATION:")
    print(f"Number of configured keys: {len(keys)}")
    key_dict = dict(keys)
    for slot in ["KEY_1", "KEY_2", "KEY_3"]:
        is_cfg = slot in key_dict and bool(key_dict[slot])
        masked = mask_api_key(key_dict.get(slot)) if is_cfg else "[NOT CONFIGURED]"
        print(f"  {slot} configured: {'YES' if is_cfg else 'NO'} ({masked})")

    # 2. Model Governance
    model_name = get_configured_gemini_model()
    print("\n2. RUNTIME MODEL:")
    print(f"  Configured model: {model_name}")
    print(f"  Approved model constant: {APPROVED_GEMINI_MODEL}")
    assert model_name == "gemini-3.6-flash", f"Expected gemini-3.6-flash, got {model_name}"

    # 3. Active Key Pool Inspection
    pool = reset_key_pool()
    print("\n3. ACTIVE KEY POOL:")
    print(f"  Total slots loaded: {len(pool.slots)}")
    for i, slot in enumerate(pool.slots):
        print(f"  Slot {i+1}: {slot.slot_id} | active={slot.is_active} | eligible={slot.is_eligible()}")
    active_slot = pool.get_active_slot()
    print(f"  Preferred active slot: {active_slot.slot_id if active_slot else 'None'}")
    assert active_slot is not None and active_slot.slot_id == "KEY_1", "Expected KEY_1 to be preferred active slot"

    # 4. Project Distribution Detection
    dist = pool.detect_project_distribution()
    print("\n4. PROJECT DISTRIBUTION DETECTION:")
    print(f"  Key count: {dist['key_count']}")
    print(f"  Distinct key count: {dist['distinct_key_count']}")
    print(f"  Project distribution classification: {dist['project_distribution']}")
    print(f"  Shared project quota: {dist['shared_quota']}")
    print(f"  Summary: {dist['summary']}")

    # 5. Safe Real-Provider Tests for each configured key
    print("\n5. REAL LIVE PROVIDER KEY TESTS:")
    live_results = {}
    for slot_id, raw_key in keys:
        res = await test_single_real_key(slot_id, raw_key, model_name)
        live_results[slot_id] = res

    # 6. Overhead Benchmark
    print("\n6. HEALTHY-PATH PERFORMANCE & OVERHEAD:")
    trials = 20000
    t0 = time.perf_counter()
    for _ in range(trials):
        _ = pool.get_eligible_slots()
    t_eligible = (time.perf_counter() - t0) / trials * 1_000_000

    t0 = time.perf_counter()
    for _ in range(trials):
        _ = pool.get_active_slot()
    t_active = (time.perf_counter() - t0) / trials * 1_000_000

    print(f"  Slot eligibility selection overhead: {t_eligible:.3f} microseconds per request")
    print(f"  Active preferred slot lookup overhead: {t_active:.3f} microseconds per request")

    # 7. Controlled Failover Simulations
    print("\n7. CONTROLLED FAILOVER SIMULATIONS:")
    from unittest.mock import AsyncMock, MagicMock

    ctx = RecoveryBrainInput(
        payment_id="pay_sim_audit_01",
        amount_paise=300000,
        failure_category="insufficient_funds",
        retry_count=0,
    )

    # Simulation A: KEY_1 (429) -> KEY_2 (SUCCESS)
    c1_429 = MagicMock()
    c1_429.aio.models.generate_content = AsyncMock(side_effect=Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded"))
    c2_ok = MagicMock()
    r2 = MagicMock()
    r2.text = '{"action": "PAYMENT_LINK", "confidence": 0.90, "expected_recovery_value_paise": 270000, "reason": "Simulated failover to Key 2 succeeded.", "supporting_factors": ["Key 2 healthy"], "risk_factors": []}'
    c2_ok.aio.models.generate_content = AsyncMock(return_value=r2)
    c3_ok = MagicMock()

    pool_a = GeminiKeyPool([("KEY_1", "k1"), ("KEY_2", "k2"), ("KEY_3", "k3")])
    pool_a.slots[0]._client = c1_429
    pool_a.slots[1]._client = c2_ok
    pool_a.slots[2]._client = c3_ok
    prov_a = GeminiProvider(pool=pool_a)

    t0 = time.perf_counter()
    out_a = await prov_a.generate_recommendation_async(ctx)
    t_a_ms = round((time.perf_counter() - t0) * 1000, 2)
    print("  Simulation A [KEY_1 (429) -> KEY_2 (SUCCESS)]:")
    print(f"    Outcome: {out_a.action} (conf={out_a.confidence}) | Slot: {out_a.telemetry.get('key_slot')} | Attempts: {out_a.telemetry.get('attempts')} | Duration: {t_a_ms}ms")
    assert out_a.telemetry.get("key_slot") == "KEY_2"
    assert out_a.telemetry.get("attempts") == 2
    c3_ok.aio.models.generate_content.assert_not_called()

    # Simulation B: KEY_1 (429) -> KEY_2 (429) -> KEY_3 (SUCCESS)
    c2_429 = MagicMock()
    c2_429.aio.models.generate_content = AsyncMock(side_effect=Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded"))
    c3_ok = MagicMock()
    r3 = MagicMock()
    r3.text = '{"action": "PAYMENT_LINK", "confidence": 0.88, "expected_recovery_value_paise": 260000, "reason": "Simulated failover to Key 3 succeeded.", "supporting_factors": ["Key 3 healthy"], "risk_factors": []}'
    c3_ok.aio.models.generate_content = AsyncMock(return_value=r3)

    pool_b = GeminiKeyPool([("KEY_1", "k1"), ("KEY_2", "k2"), ("KEY_3", "k3")])
    pool_b.slots[0]._client = c1_429
    pool_b.slots[1]._client = c2_429
    pool_b.slots[2]._client = c3_ok
    prov_b = GeminiProvider(pool=pool_b)

    t0 = time.perf_counter()
    out_b = await prov_b.generate_recommendation_async(ctx)
    t_b_ms = round((time.perf_counter() - t0) * 1000, 2)
    print("  Simulation B [KEY_1 (429) -> KEY_2 (429) -> KEY_3 (SUCCESS)]:")
    print(f"    Outcome: {out_b.action} (conf={out_b.confidence}) | Slot: {out_b.telemetry.get('key_slot')} | Attempts: {out_b.telemetry.get('attempts')} | Duration: {t_b_ms}ms")
    assert out_b.telemetry.get("key_slot") == "KEY_3"
    assert out_b.telemetry.get("attempts") == 3

    # Simulation C: KEY_1 (timeout) -> KEY_2 (SUCCESS)
    c1_timeout = MagicMock()
    c1_timeout.aio.models.generate_content = AsyncMock(side_effect=TimeoutError("Request timed out after 10.0s"))
    pool_c = GeminiKeyPool([("KEY_1", "k1"), ("KEY_2", "k2")])
    pool_c.slots[0]._client = c1_timeout
    pool_c.slots[1]._client = c2_ok
    prov_c = GeminiProvider(pool=pool_c)

    t0 = time.perf_counter()
    out_c = await prov_c.generate_recommendation_async(ctx)
    t_c_ms = round((time.perf_counter() - t0) * 1000, 2)
    print("  Simulation C [KEY_1 (timeout) -> KEY_2 (SUCCESS)]:")
    print(f"    Outcome: {out_c.action} | Slot: {out_c.telemetry.get('key_slot')} | Attempts: {out_c.telemetry.get('attempts')} | Duration: {t_c_ms}ms")
    assert out_c.telemetry.get("key_slot") == "KEY_2"

    # Simulation D: KEY_1 (401/403) -> KEY_2 (SUCCESS)
    c1_auth = MagicMock()
    c1_auth.aio.models.generate_content = AsyncMock(side_effect=Exception("401 API_KEY_INVALID: User API key not valid"))
    pool_d = GeminiKeyPool([("KEY_1", "k1"), ("KEY_2", "k2")])
    pool_d.slots[0]._client = c1_auth
    pool_d.slots[1]._client = c2_ok
    prov_d = GeminiProvider(pool=pool_d)

    t0 = time.perf_counter()
    out_d = await prov_d.generate_recommendation_async(ctx)
    t_d_ms = round((time.perf_counter() - t0) * 1000, 2)
    print("  Simulation D [KEY_1 (401/403) -> KEY_2 (SUCCESS)]:")
    print(f"    Outcome: {out_d.action} | Slot: {out_d.telemetry.get('key_slot')} | Attempts: {out_d.telemetry.get('attempts')} | Duration: {t_d_ms}ms")
    assert out_d.telemetry.get("key_slot") == "KEY_2"

    # Simulation E: Non-retryable Schema Error -> Immediate Fallback, NO key rotation
    c1_schema = MagicMock()
    r_schema = MagicMock()
    r_schema.text = "NOT_JSON_AT_ALL{broken"
    c1_schema.aio.models.generate_content = AsyncMock(return_value=r_schema)
    c2_unused = MagicMock()
    pool_e = GeminiKeyPool([("KEY_1", "k1"), ("KEY_2", "k2")])
    pool_e.slots[0]._client = c1_schema
    pool_e.slots[1]._client = c2_unused
    prov_e = GeminiProvider(pool=pool_e)

    t0 = time.perf_counter()
    out_e = await prov_e.generate_recommendation_async(ctx)
    t_e_ms = round((time.perf_counter() - t0) * 1000, 2)
    print("  Simulation E [KEY_1 (Schema Error) -> Immediate Fallback (NO ROTATION)]:")
    print(f"    Outcome: {out_e.action} | Is Fallback: {out_e.is_fallback} | Slot: {out_e.telemetry.get('key_slot')} | Attempts: {out_e.telemetry.get('attempts')} | Duration: {t_e_ms}ms")
    assert out_e.is_fallback is True
    assert out_e.telemetry.get("key_slot") == "KEY_1"
    assert out_e.telemetry.get("attempts") == 1
    c2_unused.aio.models.generate_content.assert_not_called()

    # 8. Concurrency Test
    print("\n8. CONCURRENCY VERIFICATION:")
    c1_fail = MagicMock()
    c1_fail.aio.models.generate_content = AsyncMock(side_effect=Exception("429 RESOURCE_EXHAUSTED"))
    c2_shared = MagicMock()
    c2_shared.aio.models.generate_content = AsyncMock(return_value=r2)
    pool_conc = GeminiKeyPool([("KEY_1", "k1"), ("KEY_2", "k2")])
    pool_conc.slots[0]._client = c1_fail
    pool_conc.slots[1]._client = c2_shared
    prov_conc = GeminiProvider(pool=pool_conc)

    # Launch 5 concurrent tasks with distinct payment IDs
    async def _req(pid: str):
        c = RecoveryBrainInput(payment_id=pid, amount_paise=200000, failure_category="insufficient_funds")
        return await prov_conc.generate_recommendation_async(c)

    t0 = time.perf_counter()
    results = await asyncio.gather(*[_req(f"pay_c_{i}") for i in range(5)])
    t_conc_ms = round((time.perf_counter() - t0) * 1000, 2)
    print(f"  5 concurrent requests completed in {t_conc_ms}ms")
    for r in results:
        assert r.telemetry.get("key_slot") == "KEY_2"
    assert pool_conc.slots[0].is_quota_exhausted is True
    print("  All 5 requests successfully completed on KEY_2 without race conditions.")

    # 9. In-Flight Deduplication Test
    print("\n9. IN-FLIGHT DEDUPLICATION VERIFICATION:")
    c_single = MagicMock()
    c_single.aio.models.generate_content = AsyncMock(return_value=r2)
    pool_dedup = GeminiKeyPool([("KEY_1", "k1")])
    pool_dedup.slots[0]._client = c_single
    svc = RecoveryBrainService(provider=GeminiProvider(pool=pool_dedup))

    payment = {
        "payment_id": "pay_dedup_audit_999",
        "amount": 250000,
        "status": "failed",
        "failure_category": "insufficient_funds",
        "retry_count": 0,
    }
    t0 = time.perf_counter()
    t1 = asyncio.create_task(svc.analyze_payment_async(payment))
    t2 = asyncio.create_task(svc.analyze_payment_async(payment))
    res1, res2 = await asyncio.gather(t1, t2)
    t_dedup_ms = round((time.perf_counter() - t0) * 1000, 2)
    assert res1.action == res2.action
    assert c_single.aio.models.generate_content.call_count == 1
    print(f"  2 simultaneous duplicate requests completed in {t_dedup_ms}ms.")
    print(f"  Underlying Gemini provider calls: {c_single.aio.models.generate_content.call_count} (EXACTLY 1).")

    print("\n" + "=" * 65)
    print("ALL RUNTIME AUDIT CHECKS COMPLETED SUCCESSFULLY")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
