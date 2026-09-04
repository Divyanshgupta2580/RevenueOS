"""Acceptance & regression tests for Phase 2: Opportunity Intelligence + AI Decision Command Center."""

from datetime import UTC, datetime

import pytest

from apps.brain.config import get_configured_gemini_model
from apps.brain.service import RecoveryBrainService
from apps.database.repositories import DecisionRepository, PaymentRepository
from apps.policy.engine import GuardedPolicyEngine
from apps.policy.service import GuardedAutopilotService
from apps.radar.service import RevenueRadarService


@pytest.fixture
def clean_test_payment(mock_db) -> dict:
    """Fixture providing a standard test payment."""
    return PaymentRepository.create({
        "payment_id": "pay_phase2_valid_01",
        "order_id": "order_phase2_01",
        "amount": 250000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "insufficient_funds",
        "failure_reason": "Cardholder account balance insufficient",
        "retry_count": 1,
        "max_retries_allowed": 3,
        "recovery_status": "pending",
        "method": "card",
        "customer_id": "cust_phase2_01",
        "created_at": datetime.now(UTC),
    })


def test_radar_evaluate_opportunity_provides_complete_phase2_command_center_fields(clean_test_payment) -> None:
    """Test that evaluate_opportunity enriches the opportunity with all required Phase 2 structures."""
    opp = RevenueRadarService.evaluate_opportunity(clean_test_payment)
    assert opp is not None
    assert opp["paymentId"] == "pay_phase2_valid_01"
    assert opp["amountPaise"] == 250000
    assert opp["policyStatus"] == "APPROVED"
    assert opp["policyReason"] is not None

    # Verify evaluated rules contain all 8 standard policy rules
    rules = opp.get("rulesEvaluated", [])
    assert len(rules) == 8
    rule_names = {r["ruleName"] for r in rules}
    expected_rules = {
        "USER_AUTHORIZATION",
        "SUPPORTED_ACTION",
        "PAYMENT_ELIGIBILITY",
        "ALREADY_RECOVERED",
        "AMOUNT_VALIDITY",
        "RETRY_THRESHOLD",
        "RISK_POLICY",
        "DUPLICATE_EXECUTION",
    }
    assert rule_names == expected_rules

    # Verify evidence summary structure
    evidence = opp.get("evidenceSummary", {})
    assert "verifiedFacts" in evidence
    assert "backendCalculations" in evidence
    assert "historicalEvidence" in evidence
    assert "policyConstraints" in evidence
    assert "systemState" in evidence

    # Verify zero secrets in evidence
    stringified = str(evidence).lower()
    for secret_word in ["api_key", "secret", "cvv", "password", "token"]:
        assert f"'{secret_word}'" not in stringified


def test_guarded_policy_engine_all_eight_rules_evaluated_on_approved(clean_test_payment) -> None:
    """Test that all 8 rules evaluate to PASS on an authorized eligible recovery."""
    user = {"id": "usr_op", "username": "operator@test.com", "role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=clean_test_payment,
        action="PAYMENT_LINK",
        user=user,
        idempotency_key="idemp_p2_approved",
    )
    assert verdict.status == "APPROVED"
    assert verdict.blocking_rule is None
    assert len(verdict.rules_evaluated) == 8
    for rule in verdict.rules_evaluated:
        assert rule["passed"] is True, f"Rule {rule['ruleName']} unexpectedly failed: {rule['reason']}"


def test_policy_negative_case_hard_decline_strictly_blocked_regardless_of_ai(mock_db) -> None:
    """Negative Test: Fraud/hard decline payment is strictly BLOCKED by policy, AI recommendation cannot override."""
    fraud_payment = PaymentRepository.create({
        "payment_id": "pay_phase2_fraud_01",
        "amount": 500000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "fraud",
        "failure_reason": "High risk transaction flagged by bank fraud monitoring",
        "retry_count": 0,
        "max_retries_allowed": 3,
        "recovery_status": "pending",
    })

    user = {"role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=fraud_payment,
        action="RETRY",
        user=user,
        idempotency_key="idemp_fraud_neg_01",
    )

    # Must be strictly BLOCKED
    assert verdict.status == "BLOCKED"
    assert verdict.blocking_rule == "RISK_POLICY"
    assert "prohibited on high-risk decline" in verdict.blocking_reason.lower()

    # Verify rule statuses: RISK_POLICY must have passed == False
    risk_rule = next(r for r in verdict.rules_evaluated if r["ruleName"] == "RISK_POLICY")
    assert risk_rule["passed"] is False

    # Verify GuardedAutopilotService records the blocked verdict
    verdict_rec, dec_id = GuardedAutopilotService.evaluate_and_record(
        payment_id=fraud_payment["payment_id"],
        action="RETRY",
        user=user,
        idempotency_key="idemp_fraud_neg_01_rec",
        ai_recommendation={"action": "RETRY", "confidence": 0.99, "reason": "AI wrongly suggested retry"},
    )
    assert verdict_rec.status == "BLOCKED"
    stored_dec = DecisionRepository.get_by_id(dec_id)
    assert stored_dec is not None
    assert stored_dec["policy_decision"]["status"] == "BLOCKED"
    assert stored_dec["policy_decision"]["blockingRule"] == "RISK_POLICY"


def test_policy_negative_case_retry_ceiling_strictly_blocked(mock_db) -> None:
    """Negative Test: Retry count reaching max retries is strictly BLOCKED for RETRY action."""
    maxed_payment = PaymentRepository.create({
        "payment_id": "pay_phase2_maxed_01",
        "amount": 100000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "gateway_timeout",
        "retry_count": 3,
        "max_retries_allowed": 3,
        "recovery_status": "pending",
    })

    user = {"role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=maxed_payment,
        action="RETRY",
        user=user,
        idempotency_key="idemp_maxed_neg_01",
    )
    assert verdict.status == "BLOCKED"
    assert verdict.blocking_rule == "RETRY_THRESHOLD"


def test_gemini_model_governance_for_phase2() -> None:
    """Verify authoritative gemini-3.6-flash governance in Phase 2."""
    model = get_configured_gemini_model()
    assert model == "gemini-3.6-flash"


def test_decision_evidence_and_context_envelope_sanitization(clean_test_payment) -> None:
    """Verify Recovery Brain context building produces sanitized Decision Context without credential exposure."""
    brain = RecoveryBrainService()
    ctx = brain.build_decision_context(clean_test_payment)
    envelope = brain.build_context_envelope(clean_test_payment)

    assert envelope.entityId == clean_test_payment["payment_id"]
    assert envelope.verifiedFacts["amountPaise"] == clean_test_payment["amount"]
    assert envelope.backendCalculations["recoverabilityScore"] == ctx.recoverability_score

    # Check diagnostic context classification
    diag = brain.get_diagnostic_context("recovery.analyze", clean_test_payment)
    assert diag["securityAudit"]["containsSensitiveCredentials"] is False
    assert diag["securityAudit"]["monetaryUnitsIntegerMinor"] is True
