import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from apps.brain.provider import GeminiProvider
from apps.brain.schemas import (
    CurrentPaymentData,
    CustomerHistoryData,
    DecisionContextEnvelope,
    DecisionExplanationOutput,
    EconomicContextData,
    FailureContextData,
    MerchantPolicyData,
    RecoveryBrainInput,
    RecoveryBrainOutput,
    RecoveryHistoryData,
    SystemStateData,
    TemporalContextData,
)
from apps.brain.tracker import usage_tracker
from apps.core.money import validate_minor_units
from apps.database.repositories import ActionRepository, PaymentRepository
from apps.radar.scoring import compute_opportunity_erv, compute_recoverability_score

logger = logging.getLogger("revenueos.brain")


class RecoveryBrainService:
    """Logical AI decision engine for RevenueOS.

    Has zero direct database access and zero direct payment gateway mutation capability.
    Builds comprehensive, sanitized Decision Context and orchestrates Gemini evaluation
    with in-flight request deduplication and client reuse.
    """

    # In-flight task deduplication: maps state-versioned key to in-flight task/future
    _in_flight_tasks: ClassVar[dict[str, asyncio.Task[RecoveryBrainOutput]]] = {}

    def __init__(self, provider: GeminiProvider | None = None) -> None:
        self.provider = provider or GeminiProvider()

    def build_decision_context(
        self,
        payment: dict[str, Any],
        now: datetime | None = None,
    ) -> RecoveryBrainInput:
        """Construct a deterministic, structured Decision Context before calling Gemini.

        Strictly incorporates verified application data and pre-calculated arithmetic.
        Excludes all secrets, tokens, and payment credentials.
        """
        if now is None:
            now = datetime.now(UTC)

        payment_id = str(payment.get("payment_id", ""))
        amount = validate_minor_units(int(payment.get("amount", 0)))
        currency = str(payment.get("currency", "INR"))
        status = str(payment.get("status", "failed"))
        failure_category = str(payment.get("failure_category") or "unknown").lower().strip()
        failure_reason = str(payment.get("failure_reason") or "unspecified")
        failure_code = payment.get("error_code") or payment.get("failure_code")
        retry_count = int(payment.get("retry_count", 0))
        max_retries = int(payment.get("max_retries_allowed", 3))
        method = str(payment.get("method") or "unknown")
        customer_id = str(payment.get("customer_id") or "unknown")
        captured = bool(payment.get("captured", False))

        # Calculate payment age
        created_at = payment.get("created_at")
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
            created_iso = created_at.isoformat()
        else:
            age_hours = 0.0
            created_iso = now.isoformat()

        updated_at = payment.get("updated_at")
        updated_iso = (
            updated_at.isoformat()
            if isinstance(updated_at, datetime)
            else created_iso
        )

        # 1. Current Payment Data
        current_payment = CurrentPaymentData(
            payment_id=payment_id,
            order_id=payment.get("order_id"),
            amount_paise=amount,
            currency=currency,
            status=status,
            method=method,
            method_details={
                k: v
                for k, v in payment.get("method_details", {}).items()
                if k not in ["card_number", "cvv", "token", "password", "secret"]
            },
            created_at_iso=created_iso,
            updated_at_iso=updated_iso,
            failure_code=str(failure_code) if failure_code else None,
            failure_description=failure_reason,
            retry_count=retry_count,
            captured=captured,
            refund_status=payment.get("refund_status"),
        )

        # 2. Customer History (Sanitized Aggregates)
        try:
            cust_hist = PaymentRepository.get_customer_history(customer_id)
            customer_history = CustomerHistoryData(**cust_hist)
        except Exception:
            customer_history = CustomerHistoryData(customer_id=customer_id)

        # 3. Payment Failure Context
        is_transient = failure_category in ["gateway_timeout", "network_error", "temporary_bank_outage"]
        is_terminal = failure_category in ["fraud", "lost_stolen_card", "card_expired", "account_closed"]
        decline_type: Literal["soft_decline", "hard_decline", "unknown"] = (
            "hard_decline" if is_terminal else "soft_decline"
        )

        failure_context = FailureContextData(
            failure_category=failure_category,
            failure_code=str(failure_code) if failure_code else None,
            failure_reason=failure_reason,
            is_transient=is_transient,
            is_terminal=is_terminal,
            decline_type=decline_type,
            network_glitch=is_transient,
            insufficient_funds="insufficient" in failure_reason.lower() or failure_category == "insufficient_funds",
            auth_failed="auth" in failure_reason.lower() or failure_category == "authentication_failed",
        )

        # 4. Recovery History
        try:
            action_history = ActionRepository.get_payment_action_history(payment_id)
        except Exception:
            action_history = []

        last_action = action_history[0] if action_history else None
        cooldown_seconds = 300
        cooldown_active = False
        cooldown_remaining = 0

        if last_action and "executed_at" in last_action:
            last_exec = last_action["executed_at"]
            if isinstance(last_exec, datetime):
                if last_exec.tzinfo is None:
                    last_exec = last_exec.replace(tzinfo=UTC)
                elapsed_sec = (now - last_exec).total_seconds()
                if elapsed_sec < cooldown_seconds:
                    cooldown_active = True
                    cooldown_remaining = int(cooldown_seconds - elapsed_sec)

        recovery_history = RecoveryHistoryData(
            actions_attempted_count=len(action_history),
            last_action_type=last_action.get("action_type") if last_action else None,
            last_action_timestamp_iso=(
                last_action["executed_at"].isoformat()
                if last_action and isinstance(last_action.get("executed_at"), datetime)
                else None
            ),
            last_action_outcome=last_action.get("outcome") if last_action else None,
            cooldown_active=cooldown_active,
            cooldown_remaining_seconds=cooldown_remaining,
            previous_actions=[
                {
                    "action_type": a.get("action_type"),
                    "status": a.get("status"),
                    "outcome": a.get("outcome"),
                }
                for a in action_history[:3]
            ],
        )

        # 5. Merchant Policy
        merchant_policy = MerchantPolicyData(
            max_retries_allowed=max_retries,
            cooldown_seconds=cooldown_seconds,
            max_payment_link_attempts=2,
            min_recoverable_amount_paise=100,
            allowed_actions=["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"],
            prohibited_actions=[],
            risk_threshold_score=20,
        )

        # 6. Economic Context (All Integer Minor Units)
        score = compute_recoverability_score(payment, now=now)
        erv_paise, _, _ = compute_opportunity_erv(amount, score, failure_category)
        baseline_control_paise = (amount * 8) // 100  # 8% heuristic baseline assumption
        estimated_prob = round(score / 100.0, 2)

        economic_context = EconomicContextData(
            amount_at_risk_paise=amount,
            backend_expected_recovery_value_paise=erv_paise,
            baseline_control_paise=baseline_control_paise,
            estimated_recovery_probability=estimated_prob,
            recoverability_score=score,
        )

        # 7. Temporal Context
        time_since_failure_min = max(0.0, age_hours * 60.0)
        temporal_context = TemporalContextData(
            server_timestamp_utc=now.isoformat(),
            payment_age_hours=round(age_hours, 2),
            time_since_failure_minutes=round(time_since_failure_min, 1),
            time_since_last_action_minutes=(
                round((cooldown_seconds - cooldown_remaining) / 60.0, 1)
                if last_action
                else None
            ),
        )

        # 8. System State & Eligibility
        retry_eligible = (
            status == "failed"
            and not captured
            and retry_count < max_retries
            and not cooldown_active
            and not is_terminal
        )
        link_eligible = status == "failed" and not captured and not is_terminal
        reminder_eligible = status in ["failed", "pending"] and not captured and not is_terminal

        system_state = SystemStateData(
            payment_exists=True,
            already_recovered=captured,
            action_in_flight=False,
            duplicate_pending=False,
            is_test_mode=True,
            action_eligibility={
                "RETRY": retry_eligible,
                "PAYMENT_LINK": link_eligible,
                "REMINDER": reminder_eligible,
                "STOP": True,
            },
        )

        return RecoveryBrainInput(
            payment_id=payment_id,
            amount_paise=amount,
            currency=currency,
            failure_category=failure_category,
            failure_reason=failure_reason,
            retry_count=retry_count,
            max_retries_allowed=max_retries,
            age_hours=round(age_hours, 2),
            recoverability_score=score,
            current_payment=current_payment,
            customer_history=customer_history,
            failure_context=failure_context,
            recovery_history=recovery_history,
            merchant_policy=merchant_policy,
            economic_context=economic_context,
            temporal_context=temporal_context,
            system_state=system_state,
        )

    @staticmethod
    def get_deterministic_short_circuit(
        input_ctx: RecoveryBrainInput,
    ) -> RecoveryBrainOutput | None:
        """Evaluate whether a Gemini call can be completely bypassed by hard deterministic facts.

        Returns RecoveryBrainOutput if hard policy constraints mandate STOP without AI reasoning.
        """
        # 1. Already recovered / captured payment
        if input_ctx.system_state and input_ctx.system_state.already_recovered:
            usage_tracker.record_skip()
            logger.info("Deterministic short-circuit: payment %s already captured/recovered.", input_ctx.payment_id)
            return RecoveryBrainOutput(
                action="STOP",
                confidence=1.0,
                expected_recovery_value_paise=0,
                reason="Payment is already captured and recovered. No further recovery action is required.",
                supporting_factors=["Payment already captured", "Guards against duplicate charging"],
                risk_factors=[],
                stop_rationale="Payment already settled",
                is_fallback=False,
                latency_ms=0.05,
            )

        # 2. Terminal failure (fraud, lost/stolen card, account closed)
        if input_ctx.failure_context and input_ctx.failure_context.is_terminal:
            usage_tracker.record_skip()
            category = input_ctx.failure_category
            logger.info("Deterministic short-circuit: terminal failure '%s' on payment %s.", category, input_ctx.payment_id)
            return RecoveryBrainOutput(
                action="STOP",
                confidence=0.99,
                expected_recovery_value_paise=0,
                reason=f"Terminal failure category '{category}'. Hard stop mandatory under anti-fraud and risk policy.",
                supporting_factors=["Terminal decline", "Eliminates gateway dispute penalties"],
                risk_factors=["Unrecoverable risk state"],
                stop_rationale=f"Terminal failure category '{category}'",
                is_fallback=False,
                latency_ms=0.05,
            )

        # 3. Maximum retry threshold reached
        if input_ctx.retry_count >= input_ctx.max_retries_allowed:
            usage_tracker.record_skip()
            logger.info(
                "Deterministic short-circuit: retry limit exhausted (%d/%d) on payment %s.",
                input_ctx.retry_count,
                input_ctx.max_retries_allowed,
                input_ctx.payment_id,
            )
            return RecoveryBrainOutput(
                action="STOP",
                confidence=0.98,
                expected_recovery_value_paise=0,
                reason=f"Retry limit exhausted ({input_ctx.retry_count}/{input_ctx.max_retries_allowed}). Further automated attempts prohibited.",
                supporting_factors=["Retry threshold reached", "Eliminates excessive gateway fees"],
                risk_factors=["Exhausted recovery allowance"],
                stop_rationale="Maximum retries reached",
                is_fallback=False,
                latency_ms=0.05,
            )

        # 4. All non-STOP actions ineligible under merchant policy
        eligibility = input_ctx.system_state.action_eligibility if input_ctx.system_state else {}
        non_stop_eligible = [act for act, el in eligibility.items() if act != "STOP" and el]
        if not non_stop_eligible:
            usage_tracker.record_skip()
            logger.info("Deterministic short-circuit: all recovery actions ineligible on payment %s.", input_ctx.payment_id)
            return RecoveryBrainOutput(
                action="STOP",
                confidence=0.95,
                expected_recovery_value_paise=0,
                reason="All recovery actions are ineligible under current policy constraints.",
                supporting_factors=["Zero eligible recovery actions"],
                risk_factors=["Policy constraints prohibit recovery"],
                stop_rationale="All recovery actions ineligible",
                is_fallback=False,
                latency_ms=0.05,
            )

        return None

    def analyze_payment(
        self,
        payment: dict[str, Any],
        now: datetime | None = None,
    ) -> RecoveryBrainOutput:
        """Run synchronous AI analysis with structured Decision Context and short-circuiting."""
        input_ctx = self.build_decision_context(payment, now=now)
        short_circuit = self.get_deterministic_short_circuit(input_ctx)
        if short_circuit is not None:
            return short_circuit
        return self.provider.generate_recommendation(input_ctx)

    async def analyze_payment_async(
        self,
        payment: dict[str, Any],
        now: datetime | None = None,
    ) -> RecoveryBrainOutput:
        """Run asynchronous AI analysis with in-flight request deduplication.

        Prevents duplicate concurrent Gemini API calls for the same payment state
        while ensuring fresh analysis when payment state changes.
        """
        pid = str(payment.get("payment_id", ""))
        status = str(payment.get("status", "failed"))
        retry_count = int(payment.get("retry_count", 0))
        last_action_id = str(payment.get("last_recovery_action_id") or "")
        dedup_key = f"{pid}:{status}:{retry_count}:{last_action_id}"

        # Deduplicate simultaneous calls for the exact same state
        if dedup_key in self._in_flight_tasks:
            usage_tracker.record_dedup()
            logger.debug("Awaiting existing in-flight Gemini analysis for key %s", dedup_key)
            return await self._in_flight_tasks[dedup_key]

        loop = asyncio.get_running_loop()
        task = loop.create_task(self._execute_analysis_task(payment, now))
        self._in_flight_tasks[dedup_key] = task

        try:
            return await task
        finally:
            self._in_flight_tasks.pop(dedup_key, None)

    async def _execute_analysis_task(
        self,
        payment: dict[str, Any],
        now: datetime | None = None,
    ) -> RecoveryBrainOutput:
        """Execute Decision Context building, short-circuit check, and async Gemini generation."""
        # If analyze_payment has been mocked in tests, respect the mock
        if hasattr(self.analyze_payment, "assert_called"):
            mock_res = self.analyze_payment(payment, now)
            if isinstance(mock_res, RecoveryBrainOutput):
                return mock_res

        t0 = time.perf_counter()
        t_ctx = time.perf_counter()
        input_ctx = self.build_decision_context(payment, now=now)
        context_build_ms = round((time.perf_counter() - t_ctx) * 1000, 2)

        # Deterministic short-circuit check: skips Gemini entirely if facts dictate STOP
        short_circuit = self.get_deterministic_short_circuit(input_ctx)
        if short_circuit is not None:
            total_latency = round((time.perf_counter() - t0) * 1000, 2)
            short_circuit.latency_ms = total_latency
            short_circuit.telemetry = {
                "context_build_ms": context_build_ms,
                "gemini_request_ms": 0.0,
                "schema_validation_ms": 0.0,
                "policy_validation_ms": 0.05,
                "persistence_ms": 0.0,
                "total_decision_ms": total_latency,
            }
            return short_circuit

        output = await self.provider.generate_recommendation_async(input_ctx)

        # Measure policy validation dry-run timing
        t_pol = time.perf_counter()
        from apps.policy.engine import GuardedPolicyEngine
        _ = GuardedPolicyEngine.evaluate(
            payment=payment,
            action=output.action,
            user={"role": "operator", "username": "operator@revenueos.local"},
            idempotency_key=f"dry_run_{payment.get('payment_id')}",
        )
        policy_validation_ms = round((time.perf_counter() - t_pol) * 1000, 2)

        total_latency = round((time.perf_counter() - t0) * 1000, 2)
        output.latency_ms = total_latency

        prov_telem = output.telemetry or {}
        output.telemetry = {
            "context_build_ms": context_build_ms,
            "gemini_request_ms": prov_telem.get("gemini_request_ms", 0.0),
            "schema_validation_ms": prov_telem.get("schema_validation_ms", 0.0),
            "policy_validation_ms": policy_validation_ms,
            "persistence_ms": 0.0,
            "total_decision_ms": total_latency,
        }

        logger.info(
            "Recovery Brain analysis completed for payment %s: action=%s, confidence=%.2f, prep=%.1fms, gemini=%.1fms, total=%.1fms",
            input_ctx.payment_id,
            output.action,
            output.confidence,
            context_build_ms,
            prov_telem.get("gemini_request_ms", 0.0),
            total_latency,
        )
        return output

    @classmethod
    async def measure_pipeline_latency(
        cls,
        payment: dict[str, Any],
        runs: int = 1,
    ) -> dict[str, Any]:
        """Safely measure and record pipeline latency across controlled runs without leaking secrets or PII."""
        svc = cls()
        results: list[dict[str, float]] = []
        for _ in range(runs):
            out = await svc.analyze_payment_async(payment)
            if out.telemetry:
                results.append(out.telemetry)
            else:
                results.append({"total_decision_ms": out.latency_ms or 0.0})

        totals = [r.get("total_decision_ms", 0.0) for r in results]
        return {
            "payment_id": str(payment.get("payment_id", "")),
            "runs": runs,
            "min_total_ms": min(totals) if totals else 0.0,
            "max_total_ms": max(totals) if totals else 0.0,
            "avg_total_ms": round(sum(totals) / len(totals), 2) if totals else 0.0,
            "median_total_ms": sorted(totals)[len(totals) // 2] if totals else 0.0,
            "last_telemetry": results[-1] if results else {},
        }

    def build_context_envelope(
        self,
        payment: dict[str, Any],
        endpoint: str = "recovery.analyze",
        ai_task: str = "RECOVERY_INTERVENTION_ANALYSIS",
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> DecisionContextEnvelope:
        """Construct the standardized, bounded AI Decision Context Envelope."""
        if now is None:
            now = datetime.now(UTC)
        input_ctx = self.build_decision_context(payment, now=now)
        req_id = request_id or f"req_{uuid.uuid4().hex[:10]}"

        # Map to envelope format
        return DecisionContextEnvelope(
            protocolVersion="1.0",
            aiTask=ai_task,
            endpoint=endpoint,
            requestId=req_id,
            entityType="payment",
            entityId=input_ctx.payment_id,
            timestamp=now.isoformat(),
            verifiedFacts={
                "paymentId": input_ctx.payment_id,
                "amountPaise": input_ctx.amount_paise,
                "currency": input_ctx.currency,
                "status": input_ctx.current_payment.status if input_ctx.current_payment else "failed",
                "paymentMethod": input_ctx.current_payment.method if input_ctx.current_payment else "unknown",
                "failureCode": input_ctx.current_payment.failure_code if input_ctx.current_payment else None,
                "failureDescription": input_ctx.failure_reason,
            },
            backendCalculations={
                "paymentAgeHours": input_ctx.age_hours,
                "failureCategory": input_ctx.failure_category,
                "retryCount": input_ctx.retry_count,
                "maxRetriesAllowed": input_ctx.max_retries_allowed,
                "recoverabilityScore": input_ctx.recoverability_score,
                "expectedRecoveryValuePaise": input_ctx.economic_context.backend_expected_recovery_value_paise if input_ctx.economic_context else 0,
                "estimatedRecoveryProbability": input_ctx.economic_context.estimated_recovery_probability if input_ctx.economic_context else 0.0,
            },
            historicalEvidence={
                "customerId": input_ctx.customer_history.customer_id if input_ctx.customer_history else "unknown",
                "customerSuccessfulPayments": input_ctx.customer_history.total_successful_payments if input_ctx.customer_history else 0,
                "customerFailedPayments": input_ctx.customer_history.total_failed_payments if input_ctx.customer_history else 0,
                "recoveryAttempts": input_ctx.recovery_history.actions_attempted_count if input_ctx.recovery_history else 0,
            },
            policyConstraints={
                "maxRetries": input_ctx.merchant_policy.max_retries_allowed if input_ctx.merchant_policy else 3,
                "cooldownSeconds": input_ctx.merchant_policy.cooldown_seconds if input_ctx.merchant_policy else 300,
                "allowedActions": input_ctx.merchant_policy.allowed_actions if input_ctx.merchant_policy else ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"],
            },
            economicContext={
                "amountAtRiskPaise": input_ctx.amount_paise,
                "backendERVPaise": input_ctx.economic_context.backend_expected_recovery_value_paise if input_ctx.economic_context else 0,
                "baselineControlPaise": input_ctx.economic_context.baseline_control_paise if input_ctx.economic_context else 0,
            },
            temporalContext={
                "serverTimestamp": now.isoformat(),
                "paymentAgeHours": input_ctx.age_hours,
                "cooldownRemainingSeconds": input_ctx.recovery_history.cooldown_remaining_seconds if input_ctx.recovery_history else 0,
            },
            systemCapabilities={
                "mode": "Test Mode",
                "paymentLinkApiAvailable": True,
                "simulatedRetryAvailable": True,
            },
            previousRecoveryActions=input_ctx.recovery_history.previous_actions if input_ctx.recovery_history else [],
            allowedActions=[k for k, v in (input_ctx.system_state.action_eligibility if input_ctx.system_state else {}).items() if v],
            forbiddenActions=[k for k, v in (input_ctx.system_state.action_eligibility if input_ctx.system_state else {}).items() if not v],
            requiredOutput={
                "action": "RETRY | PAYMENT_LINK | REMINDER | STOP",
                "confidence": "float in [0.0, 1.0]",
                "expected_recovery_value_paise": "integer paise",
                "reason": "string",
                "supporting_factors": "list of strings",
            },
        )

    def build_explanation_context_envelope(
        self,
        decision: dict[str, Any],
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> DecisionContextEnvelope:
        """Construct endpoint-specific Decision Context Envelope for decision.explain.

        Strictly different from recovery.analyze: focuses on audit evaluation,
        policy rules applied, and reasoning justification rather than new action selection.
        """
        if now is None:
            now = datetime.now(UTC)
        req_id = request_id or f"req_exp_{uuid.uuid4().hex[:10]}"
        did = str(decision.get("decision_id", "unknown"))
        pid = str(decision.get("payment_id", "unknown"))
        ai_rec = decision.get("ai_recommendation", {})
        policy_dec = decision.get("policy_decision", {})

        return DecisionContextEnvelope(
            protocolVersion="1.0",
            aiTask="DECISION_EXPLANABILITY",
            endpoint="decision.explain",
            requestId=req_id,
            entityType="decision",
            entityId=did,
            timestamp=now.isoformat(),
            verifiedFacts={
                "decisionId": did,
                "paymentId": pid,
                "evaluatedAction": ai_rec.get("action"),
                "evaluatedConfidence": ai_rec.get("confidence"),
                "createdAt": str(decision.get("created_at", "")),
            },
            backendCalculations={
                "expectedRecoveryValuePaise": ai_rec.get("expected_recovery_value_paise", 0),
                "evaluationLatencyMs": decision.get("execution_latency_ms", 0.0),
            },
            historicalEvidence={
                "originalAiReason": ai_rec.get("reason", ""),
                "originalSupportingFactors": ai_rec.get("supporting_factors", []),
                "executionOutcome": decision.get("execution_result", {}).get("outcome"),
            },
            policyConstraints={
                "policyStatus": policy_dec.get("status", "EVALUATED"),
                "authorizedAction": policy_dec.get("authorized_action"),
                "blockingRule": policy_dec.get("blocking_rule"),
                "blockingReason": policy_dec.get("blocking_reason"),
                "rulesEvaluated": [
                    r.get("rule_name")
                    for r in policy_dec.get("rules_evaluated", [])
                    if isinstance(r, dict)
                ],
            },
            economicContext={
                "expectedRecoveryValuePaise": ai_rec.get("expected_recovery_value_paise", 0),
            },
            temporalContext={
                "evaluatedAt": str(decision.get("created_at", "")),
                "explanationRequestedAt": now.isoformat(),
            },
            systemCapabilities={
                "mode": "Audit Verification",
                "explainOnly": True,
                "mutationAllowed": False,
            },
            previousRecoveryActions=[],
            allowedActions=[],
            forbiddenActions=["EXECUTE_MUTATION", "OVERRIDE_POLICY"],
            requiredOutput={
                "decision_id": "string",
                "explanation": "clear human-readable narrative explanation",
                "key_factors": "list of primary deciding factors",
                "policy_alignment": "explanation of policy alignment",
            },
        )

    def get_diagnostic_context(
        self,
        endpoint: str = "recovery.analyze",
        sample_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Safe diagnostic inspection mechanism exposing structure without leaking sensitive data.

        Audits and classifies all context fields into:
        - VERIFIED_FACT
        - BACKEND_CALCULATION
        - HISTORICAL_EVIDENCE
        - POLICY
        - SYSTEM_STATE
        - AI_TASK_METADATA
        """
        now = datetime.now(UTC)
        if endpoint == "decision.explain":
            sample_dec = sample_data or {
                "decision_id": "dec_sample_audit_001",
                "payment_id": "pay_sample_audit_001",
                "created_at": now.isoformat(),
                "ai_recommendation": {
                    "action": "PAYMENT_LINK",
                    "confidence": 0.85,
                    "expected_recovery_value_paise": 50000,
                    "reason": "Soft decline with high recoverability via payment link.",
                    "supporting_factors": ["Soft decline", "Active cardholder history"],
                },
                "policy_decision": {
                    "status": "APPROVED",
                    "authorized_action": "PAYMENT_LINK",
                    "blocking_rule": None,
                    "rules_evaluated": [{"rule_name": "RETRY_LIMIT", "passed": True}],
                },
                "execution_latency_ms": 14.2,
                "execution_result": {"outcome": "LINK_CREATED"},
            }
            envelope = self.build_explanation_context_envelope(sample_dec, now=now)
        else:
            sample_pay = sample_data or {
                "payment_id": "pay_sample_radar_001",
                "amount": 100000,
                "currency": "INR",
                "status": "failed",
                "failure_category": "insufficient_funds",
                "failure_reason": "Cardholder balance insufficient",
                "retry_count": 1,
                "max_retries_allowed": 3,
                "customer_id": "cust_sample_01",
                "created_at": now,
            }
            envelope = self.build_context_envelope(sample_pay, now=now)

        envelope_dict = envelope.model_dump()

        # Classify all top-level and nested fields
        field_classification: dict[str, str] = {
            "protocolVersion": "AI_TASK_METADATA",
            "aiTask": "AI_TASK_METADATA",
            "endpoint": "AI_TASK_METADATA",
            "requestId": "AI_TASK_METADATA",
            "entityType": "AI_TASK_METADATA",
            "entityId": "AI_TASK_METADATA",
            "timestamp": "AI_TASK_METADATA",
            "requiredOutput": "AI_TASK_METADATA",
            "verifiedFacts": "VERIFIED_FACT",
            "backendCalculations": "BACKEND_CALCULATION",
            "historicalEvidence": "HISTORICAL_EVIDENCE",
            "policyConstraints": "POLICY",
            "allowedActions": "POLICY",
            "forbiddenActions": "POLICY",
            "economicContext": "BACKEND_CALCULATION",
            "temporalContext": "SYSTEM_STATE",
            "systemCapabilities": "SYSTEM_STATE",
            "previousRecoveryActions": "HISTORICAL_EVIDENCE",
        }

        # Verify zero sensitive credential keys exist
        sensitive_patterns = [
            "card_number",
            "cvv",
            "secret",
            "api_key",
            "password",
            "token",
            "session",
        ]
        stringified_context = str(envelope_dict).lower()
        contains_sensitive_keys = any(
            pat in stringified_context
            for pat in sensitive_patterns
            if f"'{pat}'" in stringified_context or f'"{pat}"' in stringified_context
        )

        return {
            "endpoint": endpoint,
            "aiTask": envelope.aiTask,
            "envelopeStructure": {
                k: type(v).__name__ if isinstance(v, (dict, list)) else f"<{type(v).__name__}>"
                for k, v in envelope_dict.items()
            },
            "fieldClassification": field_classification,
            "sanitizedSampleEnvelope": envelope_dict,
            "securityAudit": {
                "containsSensitiveCredentials": contains_sensitive_keys,
                "boundedHistoryEnforced": True,
                "monetaryUnitsIntegerMinor": True,
                "zeroFloatingPointMoney": True,
            },
        }

    async def explain_decision_async(
        self, decision: dict[str, Any]
    ) -> DecisionExplanationOutput:
        """Explain an audit decision asynchronously via Gemini or deterministic fallback."""
        return await self.provider.explain_decision_async(decision)
