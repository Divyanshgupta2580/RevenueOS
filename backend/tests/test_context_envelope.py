"""Unit tests validating the Bounded AI Decision Context Envelope (Protocol v1.0).

Verifies that:
- Every context envelope contains endpoint, task, protocolVersion, entityId.
- Verified facts, backend calculations, policy constraints, and economic context are populated.
- Integer minor units (paise) are strictly preserved.
- Sensitive credentials (card numbers, secrets, keys) are strictly excluded.
"""

from apps.brain.schemas import DecisionContextEnvelope, DecisionExplanationOutput
from apps.brain.service import RecoveryBrainService


def test_build_context_envelope_structure():
    service = RecoveryBrainService()
    payment = {
        "payment_id": "pay_test_context_001",
        "order_id": "order_test_ctx_001",
        "amount": 499900,
        "currency": "INR",
        "status": "failed",
        "failure_category": "insufficient_funds",
        "failure_reason": "Payment failed due to insufficient balance",
        "customer_id": "cust_test_99",
        "customer_email": "operator@revenueos.local",
        "retry_count": 1,
        "max_retries_allowed": 3,
        "method": "card",
    }

    envelope = service.build_context_envelope(
        payment=payment,
        endpoint="recovery.analyze",
        ai_task="RECOVERY_INTERVENTION_ANALYSIS",
        request_id="req_ctx_test_01",
    )

    assert isinstance(envelope, DecisionContextEnvelope)
    assert envelope.protocolVersion == "1.0"
    assert envelope.aiTask == "RECOVERY_INTERVENTION_ANALYSIS"
    assert envelope.endpoint == "recovery.analyze"
    assert envelope.requestId == "req_ctx_test_01"
    assert envelope.entityType == "payment"
    assert envelope.entityId == "pay_test_context_001"

    # Verified facts
    assert envelope.verifiedFacts["paymentId"] == "pay_test_context_001"
    assert envelope.verifiedFacts["amountPaise"] == 499900
    assert envelope.verifiedFacts["currency"] == "INR"
    assert envelope.verifiedFacts["status"] == "failed"

    # Backend calculations
    assert envelope.backendCalculations["failureCategory"] == "insufficient_funds"
    assert envelope.backendCalculations["retryCount"] == 1
    assert "recoverabilityScore" in envelope.backendCalculations
    assert "expectedRecoveryValuePaise" in envelope.backendCalculations

    # Economic context
    assert envelope.economicContext["amountAtRiskPaise"] == 499900
    assert isinstance(envelope.economicContext["backendERVPaise"], int)

    # Allowed and forbidden actions
    assert "STOP" in envelope.allowedActions
    assert "PAYMENT_LINK" in envelope.allowedActions

    # Zero secrets in serialized JSON
    envelope_json = envelope.model_dump_json()
    assert "KEY_SECRET" not in envelope_json
    assert "secret" not in envelope_json.lower()
    assert "password" not in envelope_json.lower()


def test_context_envelope_contains_all_required_sections():
    """Verify that every AI decision context contains all 10 required prompt/envelope sections."""
    service = RecoveryBrainService()
    payment = {
        "payment_id": "pay_test_context_full",
        "order_id": "order_test_ctx_full",
        "amount": 250000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "network_timeout",
        "failure_reason": "Gateway timed out waiting for response",
        "customer_id": "cust_test_42",
        "customer_email": "customer@example.com",
        "retry_count": 0,
        "max_retries_allowed": 3,
        "method": "upi",
    }

    envelope = service.build_context_envelope(
        payment=payment,
        endpoint="recovery.analyze",
        ai_task="RECOVERY_INTERVENTION_ANALYSIS",
        request_id="req_full_ctx_01",
    )

    # 3. AI context contains endpoint
    assert envelope.endpoint == "recovery.analyze"
    # 4. AI context contains task
    assert envelope.aiTask == "RECOVERY_INTERVENTION_ANALYSIS"
    # 5. AI context contains verified facts
    assert bool(envelope.verifiedFacts)
    assert envelope.verifiedFacts["paymentId"] == "pay_test_context_full"
    # 6. AI context contains backend calculations
    assert bool(envelope.backendCalculations)
    assert "recoverabilityScore" in envelope.backendCalculations
    # 7. AI context contains historical evidence
    assert isinstance(envelope.historicalEvidence, dict)
    assert "recoveryAttempts" in envelope.historicalEvidence
    # 8. AI context contains policy constraints
    assert bool(envelope.policyConstraints)
    assert "maxRetries" in envelope.policyConstraints
    # 9. AI context contains economic context
    assert bool(envelope.economicContext)
    assert envelope.economicContext["amountAtRiskPaise"] == 250000
    # 10. AI context contains temporal context
    assert bool(envelope.temporalContext)
    assert "serverTimestamp" in envelope.temporalContext
    # 11. AI context contains allowed actions
    assert isinstance(envelope.allowedActions, list)
    assert len(envelope.allowedActions) > 0
    assert "STOP" in envelope.allowedActions
    # 12. AI context does not contain secrets
    envelope_str = envelope.model_dump_json()
    for forbidden in ["KEY_SECRET", "api_key", "secret_key", "password", "private_key"]:
        assert forbidden not in envelope_str


def test_decision_explanation_output_schema():
    explanation = DecisionExplanationOutput(
        decision_id="dec_test_expl_01",
        explanation="Payment link was authorized because the failure was transient and within merchant retry limits.",
        key_factors=["Transient decline", "0 prior retries"],
        policy_alignment="Fully aligned with merchant retry policy.",
    )
    assert explanation.decision_id == "dec_test_expl_01"
    assert "Payment link was authorized" in explanation.explanation
    assert len(explanation.key_factors) == 2


def test_endpoint_specific_context_separation():
    """Explicit proof that recovery.analyze and decision.explain use endpoint-specific contexts."""
    service = RecoveryBrainService()

    # 1. recovery.analyze envelope
    payment = {
        "payment_id": "pay_sep_test_001",
        "amount": 75000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "soft_decline",
        "failure_reason": "Card balance check declined",
        "retry_count": 0,
        "max_retries_allowed": 3,
    }
    analyze_env = service.build_context_envelope(payment)

    # 2. decision.explain envelope
    decision = {
        "decision_id": "dec_sep_test_001",
        "payment_id": "pay_sep_test_001",
        "ai_recommendation": {
            "action": "PAYMENT_LINK",
            "confidence": 0.88,
            "expected_recovery_value_paise": 60000,
            "reason": "High probability soft decline recovery via checkout link.",
            "supporting_factors": ["Soft decline", "Zero prior retries"],
        },
        "policy_decision": {
            "status": "APPROVED",
            "authorized_action": "PAYMENT_LINK",
            "blocking_rule": None,
            "rules_evaluated": [{"rule_name": "RETRY_LIMIT", "passed": True}],
        },
        "execution_latency_ms": 11.5,
        "execution_result": {"outcome": "LINK_SENT"},
    }
    explain_env = service.build_explanation_context_envelope(decision)

    # Proof of distinct tasks and endpoints
    assert analyze_env.endpoint == "recovery.analyze"
    assert explain_env.endpoint == "decision.explain"

    assert analyze_env.aiTask == "RECOVERY_INTERVENTION_ANALYSIS"
    assert explain_env.aiTask == "DECISION_EXPLANABILITY"

    assert analyze_env.entityType == "payment"
    assert explain_env.entityType == "decision"

    assert analyze_env.entityId == "pay_sep_test_001"
    assert explain_env.entityId == "dec_sep_test_001"

    # Analyze requires action choice; explain requires audit narrative
    assert "action" in analyze_env.requiredOutput
    assert "explanation" in explain_env.requiredOutput
    assert "policy_alignment" in explain_env.requiredOutput

    # Analyze has allowed actions; explain has strictly forbidden mutation
    assert len(analyze_env.allowedActions) > 0
    assert "EXECUTE_MUTATION" in explain_env.forbiddenActions


def test_diagnostic_context_mechanism_and_field_classification():
    """Diagnostic tool records structure and verifies field classifications without sensitive data."""
    service = RecoveryBrainService()

    diag_analyze = service.get_diagnostic_context("recovery.analyze")
    diag_explain = service.get_diagnostic_context("decision.explain")

    assert diag_analyze["endpoint"] == "recovery.analyze"
    assert diag_explain["endpoint"] == "decision.explain"

    # Verify field classifications exist
    cls_map = diag_analyze["fieldClassification"]
    assert cls_map["verifiedFacts"] == "VERIFIED_FACT"
    assert cls_map["backendCalculations"] == "BACKEND_CALCULATION"
    assert cls_map["historicalEvidence"] == "HISTORICAL_EVIDENCE"
    assert cls_map["policyConstraints"] == "POLICY"
    assert cls_map["temporalContext"] == "SYSTEM_STATE"
    assert cls_map["systemCapabilities"] == "SYSTEM_STATE"
    assert cls_map["protocolVersion"] == "AI_TASK_METADATA"

    # Verify security audit guarantees
    assert diag_analyze["securityAudit"]["containsSensitiveCredentials"] is False
    assert diag_analyze["securityAudit"]["boundedHistoryEnforced"] is True
    assert diag_analyze["securityAudit"]["monetaryUnitsIntegerMinor"] is True
    assert diag_analyze["securityAudit"]["zeroFloatingPointMoney"] is True

    assert diag_explain["securityAudit"]["containsSensitiveCredentials"] is False

