"""Tests for Phase 3: Decision Ledger Authoritative Audit Layer & Razorpay Failure Ingestion."""

import json
from datetime import UTC, datetime
from unittest.mock import patch

from django.test import Client

from apps.brain.schemas import DecisionExplanationOutput
from apps.database.repositories import DecisionRepository, PaymentRepository
from apps.policy.service import GuardedAutopilotService


def test_record_payment_failure_view_success(mock_db, client: Client) -> None:

    """Authentic Razorpay payment failure is ingested and categorized correctly."""
    mock_rzp_payment = {
        "id": "pay_fail_test_001",
        "order_id": "order_test_001",
        "status": "failed",
        "amount": 150000,
        "currency": "INR",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Card was declined due to insufficient funds.",
        "error_reason": "insufficient_funds",
        "email": "customer@example.com",
        "method": "card",
    }

    with patch("apps.razorpay_adapter.views.RazorpayAdapter.fetch_payment", return_value=mock_rzp_payment):
        resp = client.post(
            "/api/record-failure",
            data=json.dumps({
                "payment_id": "pay_fail_test_001",
                "order_id": "order_test_001",
            }),
            content_type="application/json",
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["ingested"] is True
    assert data["payment_id"] == "pay_fail_test_001"
    assert data["payment_status"] == "failed"
    assert data["failure_category"] == "insufficient_funds"

    # Verify database persistence
    saved = PaymentRepository.get_by_id("pay_fail_test_001")
    assert saved is not None
    assert saved["status"] == "failed"
    assert saved["failure_category"] == "insufficient_funds"
    assert saved["amount"] == 150000
    assert saved["recovery_status"] == "at_risk"


def test_record_payment_failure_view_missing_payment_id(mock_db, client: Client) -> None:
    """Missing payment_id produces 400 error."""
    resp = client.post(
        "/api/record-failure",
        data=json.dumps({"order_id": "order_only"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "MISSING_PAYMENT_ID"


def test_record_payment_failure_view_rejects_non_post(mock_db, client: Client) -> None:
    """GET requests return 405 Method Not Allowed."""
    resp = client.get("/api/record-failure")
    assert resp.status_code == 405


def test_decision_repository_full_audit_lifecycle(mock_db) -> None:
    """DecisionRepository records full envelope, supports execution update and audit timeline."""
    now = datetime.now(UTC)
    dec_id = "dec_audit_001"
    pid = "pay_audit_001"

    PaymentRepository.create({
        "payment_id": pid,
        "amount": 250000,
        "status": "failed",
        "failure_category": "soft_decline",
    })

    doc = DecisionRepository.create({
        "decision_id": dec_id,
        "payment_id": pid,
        "model_version": "gemini-3.6-flash",
        "endpoint": "recovery.analyze",
        "request_id": "req_audit_001",
        "payment_snapshot": {"paymentId": pid, "amount": 250000},
        "evidence_summary": {"verifiedFacts": {"status": "FAILED"}},
        "ai_recommendation": {"action": "PAYMENT_LINK", "confidence": 0.85},
        "policy_decision": {"status": "APPROVED", "rules_evaluated": ["USER_AUTHORIZATION"]},
        "created_at": now,
    })

    assert doc["decision_id"] == dec_id
    assert doc["model_version"] == "gemini-3.6-flash"
    assert doc["execution_status"] == "PENDING"
    assert doc["outcome"] == "PENDING"

    # Update execution
    updated = DecisionRepository.update_execution(
        decision_id=dec_id,
        execution_status="EXECUTED",
        execution_result={"paymentLinkId": "plink_123"},
        execution_latency_ms=145.2,
        executed_at=datetime.now(UTC),
        outcome="PENDING",
    )
    assert updated is True

    retrieved = DecisionRepository.get_by_id(dec_id)
    assert retrieved is not None
    assert retrieved["execution_status"] == "EXECUTED"
    assert retrieved["execution_latency_ms"] == 145.2
    assert len(retrieved["audit_timeline"]) == 1
    assert retrieved["audit_timeline"][0]["stage"] == "EXECUTION"
    assert retrieved["audit_timeline"][0]["status"] == "EXECUTED"


def test_decision_repository_filtering(mock_db) -> None:
    """DecisionRepository.list_decisions filters by action, policy_status, execution_status, search."""
    # Create 3 decisions
    DecisionRepository.create({
        "decision_id": "dec_filter_1",
        "payment_id": "pay_alpha_1",
        "ai_recommendation": {"action": "PAYMENT_LINK"},
        "policy_decision": {"status": "APPROVED"},
        "execution_status": "EXECUTED",
    })
    DecisionRepository.create({
        "decision_id": "dec_filter_2",
        "payment_id": "pay_alpha_2",
        "ai_recommendation": {"action": "RETRY"},
        "policy_decision": {"status": "BLOCKED"},
        "execution_status": "BLOCKED",
    })
    DecisionRepository.create({
        "decision_id": "dec_filter_3",
        "payment_id": "pay_beta_1",
        "ai_recommendation": {"action": "STOP"},
        "policy_decision": {"status": "APPROVED"},
        "execution_status": "PENDING",
    })

    # Filter by action
    records, total = DecisionRepository.list_decisions(action="PAYMENT_LINK")
    assert total == 1
    assert records[0]["decision_id"] == "dec_filter_1"

    # Filter by policy_status
    records, total = DecisionRepository.list_decisions(policy_status="BLOCKED")
    assert total == 1
    assert records[0]["decision_id"] == "dec_filter_2"

    # Filter by search
    records, total = DecisionRepository.list_decisions(search="beta")
    assert total == 1
    assert records[0]["payment_id"] == "pay_beta_1"


def test_guarded_autopilot_service_audit_timeline(mock_db) -> None:
    """GuardedAutopilotService generates chronological audit timeline on evaluation."""
    pid = "pay_gap_001"
    PaymentRepository.create({
        "payment_id": pid,
        "amount": 100000,
        "status": "failed",
        "failure_category": "soft_decline",
        "retry_count": 0,
        "max_retries_allowed": 3,
    })

    verdict, dec_id = GuardedAutopilotService.evaluate_and_record(
        payment_id=pid,
        action="PAYMENT_LINK",
        user={"id": "op_1", "username": "operator", "role": "operator"},
        idempotency_key="idemp_gap_001",
        ai_recommendation={"action": "PAYMENT_LINK", "confidence": 0.8},
    )

    assert verdict.status == "APPROVED"
    assert dec_id.startswith("dec_")

    stored = DecisionRepository.get_by_id(dec_id)
    assert stored is not None
    assert stored["payment_id"] == pid
    assert stored["payment_snapshot"]["amount"] == 100000
    assert len(stored["audit_timeline"]) == 4
    stages = [entry["stage"] for entry in stored["audit_timeline"]]
    assert stages == ["FAILURE_DETECTED", "CONTEXT_CONSTRUCTED", "AI_RECOMMENDATION", "POLICY_EVALUATION"]


def test_decision_explanation_output_schema() -> None:
    """DecisionExplanationOutput supports counterfactual and key factors."""
    out = DecisionExplanationOutput(
        decision_id="dec_test_exp_01",
        explanation="Payment link was authorized because the customer had zero prior retries.",
        key_factors=["Zero retry count", "Soft decline"],
        policy_alignment="Complies with RETRY_THRESHOLD and RISK_POLICY rules.",
        counterfactual="If retries had exceeded 3, policy would block execution.",
        counterfactuals=["Retry limit exceeded", "Customer marked fraud"],
    )
    dump = out.model_dump()
    assert dump["decision_id"] == "dec_test_exp_01"
    assert dump["counterfactual"] is not None
    assert len(dump["counterfactuals"]) == 2
