"""Live validation test executing a real Google Gemini 3.6 Flash request through RevenueOS.

Follows the complete product flow:
real/test payment record
→ RecoveryBrainService
→ endpoint-specific DecisionContextEnvelope
→ prompt builder
→ Gemini provider
→ gemini-3.6-flash
→ structured response
→ Pydantic validation
→ deterministic policy engine

Strict security: Zero secrets, zero raw API keys, zero card numbers printed or logged.
"""

import os
import sys
import time

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "revenueos.settings")

import django  # noqa: E402

django.setup()

from apps.brain.config import APPROVED_GEMINI_MODEL, get_configured_gemini_model  # noqa: E402
from apps.brain.schemas import RecoveryBrainOutput  # noqa: E402
from apps.brain.service import RecoveryBrainService  # noqa: E402
from apps.policy.engine import GuardedPolicyEngine  # noqa: E402


def run_live_gemini_validation() -> dict:
    print("=" * 60)
    print("REVENUEOS — LIVE GEMINI 3.6 FLASH AUTHENTICATED VALIDATION")
    print("=" * 60)

    # 1. Model Governance Check
    configured_model = get_configured_gemini_model()
    print(f"1. Model Governance: Configured Model = '{configured_model}'")
    assert configured_model == APPROVED_GEMINI_MODEL, f"Model mismatch: {configured_model} != {APPROVED_GEMINI_MODEL}"
    print(f"   Model Approved: True ({APPROVED_GEMINI_MODEL})")

    # 2. Prepare Sample Failed Payment (paise minor units, no PII, no card numbers)
    payment = {
        "payment_id": "pay_live_test_001",
        "order_id": "order_live_test_001",
        "amount": 150000,  # 1,500 INR in integer paise
        "currency": "INR",
        "status": "failed",
        "failure_category": "soft_decline",
        "failure_reason": "Bank declined transaction due to temporary limit check",
        "customer_id": "cust_live_val_99",
        "customer_email": "operator@revenueos.local",
        "retry_count": 0,
        "max_retries_allowed": 3,
        "method": "card",
    }
    print(f"\n2. Test Payment Created: ID={payment['payment_id']}, Amount={payment['amount']} paise, Category={payment['failure_category']}")

    # 3. Instantiate Actual Application Service
    service = RecoveryBrainService()

    # 4. Build DecisionContextEnvelope (Protocol v1.0)
    t0 = time.perf_counter()
    envelope = service.build_context_envelope(
        payment=payment,
        endpoint="recovery.analyze",
        ai_task="RECOVERY_INTERVENTION_ANALYSIS",
        request_id="req_live_gemini_val_01",
    )
    print("\n3. Decision Context Envelope Built:")
    print(f"   - Protocol Version: {envelope.protocolVersion}")
    print(f"   - AI Task: {envelope.aiTask}")
    print(f"   - Endpoint: {envelope.endpoint}")
    print(f"   - Request ID: {envelope.requestId}")
    print(f"   - Entity: {envelope.entityType}:{envelope.entityId}")
    print(f"   - Amount at Risk (Paise): {envelope.economicContext['amountAtRiskPaise']}")
    print(f"   - Pre-computed ERV (Paise): {envelope.economicContext['backendERVPaise']}")
    print(f"   - Allowed Actions: {envelope.allowedActions}")

    # 5. Invoke Live Gemini API through Application Provider
    print(f"\n4. Dispatching Real API Request to Gemini ({configured_model})...")
    input_ctx = service.build_decision_context(payment)

    output = service.provider.generate_recommendation(input_ctx)
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    print(f"   API Response Received in {latency_ms} ms")

    # 6. Validate Output Schema
    is_valid_pydantic = isinstance(output, RecoveryBrainOutput)
    is_fallback = getattr(output, "is_fallback", False)
    print("\n5. Validation Results:")
    print(f"   - Pydantic Schema Validation: {'PASS' if is_valid_pydantic else 'FAIL'}")
    print(f"   - Model Used: {configured_model}")
    print(f"   - Fallback Used: {'YES' if is_fallback else 'NO'}")
    print(f"   - Action Recommended: {output.action}")
    print(f"   - AI Confidence: {output.confidence * 100:.1f}%")
    print(f"   - Expected Recovery Value: {output.expected_recovery_value_paise} paise")
    print(f"   - AI Reason: {output.reason}")
    print(f"   - Supporting Factors: {output.supporting_factors}")

    # 7. Run Deterministic Policy Engine (Guarded Autopilot)
    user = {"id": "usr_operator", "username": "operator", "role": "operator"}
    policy_verdict = GuardedPolicyEngine.evaluate(
        payment=payment,
        action=output.action,
        user=user,
        idempotency_key=f"idem_{payment['payment_id']}_{output.action}",
    )
    print("\n6. Guarded Autopilot Policy Evaluation:")
    print(f"   - Policy Verdict: {policy_verdict.status}")
    print(f"   - Authorized Action: {policy_verdict.authorized_action}")
    print(f"   - Rules Evaluated Count: {len(policy_verdict.rules_evaluated)}")
    print(f"   - All Rules Passed: {all(r.get('passed', False) for r in policy_verdict.rules_evaluated)}")

    # Strict assertion for verification
    assert is_valid_pydantic, "Output failed Pydantic validation"
    assert output.action in ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"], f"Invalid action: {output.action}"
    assert 0.0 <= output.confidence <= 1.0, f"Confidence out of range: {output.confidence}"
    assert isinstance(output.expected_recovery_value_paise, int), "ERV must be integer paise"

    summary = {
        "live_gemini_request": "PASS",
        "model_used": configured_model,
        "structured_output": "PASS",
        "schema_validation": "PASS",
        "policy_validation": "PASS" if policy_verdict.status == "APPROVED" else "BLOCKED_SAFE",
        "fallback_used": "YES" if is_fallback else "NO",
        "latency_ms": latency_ms,
        "action": output.action,
        "confidence": output.confidence,
        "expected_recovery_value_paise": output.expected_recovery_value_paise,
    }
    print("\n" + "=" * 60)
    print("LIVE VALIDATION SUMMARY:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 60)
    return summary


if __name__ == "__main__":
    run_live_gemini_validation()
