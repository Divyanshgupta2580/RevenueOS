"""Acceptance tests for Phase 7: Guarded Autopilot Deterministic Policy Engine."""

import json

import pytest

from apps.database.repositories import ActionRepository, DecisionRepository, PaymentRepository
from apps.policy.engine import GuardedPolicyEngine
from apps.policy.service import GuardedAutopilotService
from apps.websocket.consumer import RevenueOSConsumer
from tests.test_websocket import WebsocketTestCommunicator


@pytest.fixture
def valid_payment(mock_db) -> dict:
    """Fixture providing a standard eligible failed payment."""
    return PaymentRepository.create({
        "payment_id": "pay_policy_001",
        "amount": 250000,
        "status": "failed",
        "failure_category": "insufficient_funds",
        "retry_count": 1,
        "max_retries_allowed": 3,
        "recovery_status": "pending",
    })


def test_approved_action_passes_all_rules(valid_payment) -> None:
    """Acceptance Test: Valid failed payment under retry limit with authorized operator is APPROVED."""
    user = {"id": "usr_operator", "username": "operator@test.com", "role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=valid_payment,
        action="PAYMENT_LINK",
        user=user,
        idempotency_key="idemp_policy_001_plink",
    )
    assert verdict.status == "APPROVED"
    assert verdict.authorized_action == "PAYMENT_LINK"
    assert verdict.blocking_rule is None


def test_blocked_already_captured_payment(mock_db) -> None:
    """Acceptance Test: Captured or paid payments are strictly BLOCKED from recovery actions."""
    captured_payment = PaymentRepository.create({
        "payment_id": "pay_captured_001",
        "amount": 100000,
        "status": "captured",
    })
    user = {"role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=captured_payment,
        action="PAYMENT_LINK",
        user=user,
        idempotency_key="idemp_cap_1",
    )
    assert verdict.status == "BLOCKED"
    assert verdict.blocking_rule == "PAYMENT_ELIGIBILITY"


def test_blocked_already_recovered(mock_db) -> None:
    """Acceptance Test: Already recovered opportunity is strictly BLOCKED."""
    recovered_payment = PaymentRepository.create({
        "payment_id": "pay_recovered_001",
        "amount": 100000,
        "status": "failed",
        "recovery_status": "recovered",
    })
    user = {"role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=recovered_payment,
        action="PAYMENT_LINK",
        user=user,
        idempotency_key="idemp_rec_1",
    )
    assert verdict.status == "BLOCKED"
    assert verdict.blocking_rule == "ALREADY_RECOVERED"


def test_blocked_retry_threshold_exceeded(mock_db) -> None:
    """Acceptance Test: RETRY action exceeding max_retries_allowed is strictly BLOCKED."""
    maxed_payment = PaymentRepository.create({
        "payment_id": "pay_maxed_retries",
        "amount": 100000,
        "status": "failed",
        "retry_count": 3,
        "max_retries_allowed": 3,
    })
    user = {"role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=maxed_payment,
        action="RETRY",
        user=user,
        idempotency_key="idemp_maxed_1",
    )
    assert verdict.status == "BLOCKED"
    assert verdict.blocking_rule == "RETRY_THRESHOLD"


def test_blocked_risk_policy_on_hard_decline(mock_db) -> None:
    """Acceptance Test: Retrying fraud or lost/stolen card is strictly BLOCKED by risk policy."""
    fraud_payment = PaymentRepository.create({
        "payment_id": "pay_fraud_policy",
        "amount": 100000,
        "status": "failed",
        "failure_category": "fraud",
        "retry_count": 0,
    })
    user = {"role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=fraud_payment,
        action="RETRY",
        user=user,
        idempotency_key="idemp_fraud_1",
    )
    assert verdict.status == "BLOCKED"
    assert verdict.blocking_rule == "RISK_POLICY"


def test_blocked_duplicate_execution(mock_db, valid_payment) -> None:
    """Acceptance Test: Duplicate action idempotency key is strictly BLOCKED."""
    ActionRepository.create({
        "action_id": "act_dup_001",
        "payment_id": valid_payment["payment_id"],
        "idempotency_key": "idemp_already_executed",
        "action_type": "PAYMENT_LINK",
    })
    user = {"role": "operator"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=valid_payment,
        action="PAYMENT_LINK",
        user=user,
        idempotency_key="idemp_already_executed",
    )
    assert verdict.status == "BLOCKED"
    assert verdict.blocking_rule == "DUPLICATE_EXECUTION"


def test_blocked_unauthorized_user(valid_payment) -> None:
    """Acceptance Test: Missing user or viewer role cannot authorize execution."""
    unauthorized_user = {"role": "viewer"}
    verdict = GuardedPolicyEngine.evaluate(
        payment=valid_payment,
        action="PAYMENT_LINK",
        user=unauthorized_user,
        idempotency_key="idemp_unauth_1",
    )
    assert verdict.status == "BLOCKED"
    assert verdict.blocking_rule == "USER_AUTHORIZATION"


def test_all_policy_decisions_persisted_for_audit(mock_db, valid_payment) -> None:
    """Acceptance Test: Every policy evaluation is persisted with auditable rules evaluated."""
    user = {"role": "operator", "username": "auditor"}
    verdict, decision_id = GuardedAutopilotService.evaluate_and_record(
        payment_id=valid_payment["payment_id"],
        action="PAYMENT_LINK",
        user=user,
        idempotency_key="idemp_audit_test",
        ai_recommendation={"action": "PAYMENT_LINK", "confidence": 0.9},
    )
    assert verdict.status == "APPROVED"
    assert decision_id.startswith("dec_")

    stored = DecisionRepository.get_by_id(decision_id)
    assert stored is not None
    assert stored["payment_id"] == valid_payment["payment_id"]
    assert stored["policy_decision"]["status"] == "APPROVED"
    assert len(stored["policy_decision"]["rulesEvaluated"]) > 0


@pytest.mark.asyncio
async def test_websocket_recovery_execute_blocked_flow(mock_db) -> None:
    """Acceptance Test: Blocked policy verdict emits recovery.blocked without execution."""
    PaymentRepository.create({
        "payment_id": "pay_ws_blocked_001",
        "amount": 100000,
        "status": "failed",
        "failure_category": "fraud",  # Will be blocked by RISK_POLICY if retried
    })

    user = {"id": "usr_test", "username": "operator", "role": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    execute_frame = {
        "protocolVersion": "v1",
        "requestId": "req_exec_risk",
        "type": "recovery.execute",
        "payload": {
            "paymentId": "pay_ws_blocked_001",
            "action": "RETRY",
            "idempotencyKey": "idemp_ws_blocked_1",
        },
    }
    await communicator.send_to(text_data=json.dumps(execute_frame))

    res = json.loads(await communicator.receive_from())
    assert res["type"] == "recovery.blocked"
    assert res["payload"]["blockingRule"] == "RISK_POLICY"
    assert "decisionId" in res["payload"]

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_websocket_recovery_execute_approved_flow(mock_db, valid_payment) -> None:
    """Acceptance Test: Approved policy verdict emits recovery.approved and recovery.executed."""
    user = {"id": "usr_test", "username": "operator", "role": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    execute_frame = {
        "protocolVersion": "v1",
        "requestId": "req_exec_approved",
        "type": "recovery.execute",
        "payload": {
            "paymentId": valid_payment["payment_id"],
            "action": "PAYMENT_LINK",
            "idempotencyKey": "idemp_ws_approved_1",
        },
    }
    await communicator.send_to(text_data=json.dumps(execute_frame))

    # Event 1: recovery.approved
    msg1 = json.loads(await communicator.receive_from())
    assert msg1["type"] == "recovery.approved"
    assert msg1["payload"]["action"] == "PAYMENT_LINK"

    # Event 2: recovery.executed
    msg2 = json.loads(await communicator.receive_from())
    assert msg2["type"] == "recovery.executed"
    assert msg2["payload"]["status"] in ["EXECUTED", "QUEUED"]

    await communicator.disconnect()
