"""Strict Pydantic schemas for the Recovery Brain AI engine."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CurrentPaymentData(BaseModel):
    """Verified machine-readable facts about the payment."""

    payment_id: str
    order_id: str | None = None
    amount_paise: int
    currency: str = "INR"
    status: str = "failed"
    method: str = "unknown"
    method_details: dict[str, Any] = Field(default_factory=dict)
    created_at_iso: str = ""
    updated_at_iso: str = ""
    failure_code: str | None = None
    failure_description: str = "unknown"
    retry_count: int = 0
    captured: bool = False
    refund_status: str | None = None


class CustomerHistoryData(BaseModel):
    """Sanitized customer transaction history without any personal credentials."""

    customer_id: str = "unknown"
    total_successful_payments: int = 0
    total_failed_payments: int = 0
    recent_successful_payments_count: int = 0
    recent_failed_payments_count: int = 0
    historical_recovery_success_rate: float = 0.0
    time_since_last_success_hours: float | None = None


class FailureContextData(BaseModel):
    """Deterministic failure classification and gateway signals."""

    failure_category: str
    failure_code: str | None = None
    failure_reason: str = "unspecified"
    is_transient: bool = False
    is_terminal: bool = False
    decline_type: Literal["soft_decline", "hard_decline", "unknown"] = "unknown"
    network_glitch: bool = False
    insufficient_funds: bool = False
    auth_failed: bool = False


class RecoveryHistoryData(BaseModel):
    """History of recovery attempts already executed for this payment."""

    actions_attempted_count: int = 0
    last_action_type: str | None = None
    last_action_timestamp_iso: str | None = None
    last_action_outcome: str | None = None
    cooldown_active: bool = False
    cooldown_remaining_seconds: int = 0
    previous_actions: list[dict[str, Any]] = Field(default_factory=list)


class MerchantPolicyData(BaseModel):
    """Merchant business constraints and hard policy boundaries."""

    max_retries_allowed: int = 3
    cooldown_seconds: int = 300
    max_payment_link_attempts: int = 2
    min_recoverable_amount_paise: int = 100
    allowed_actions: list[str] = Field(
        default_factory=lambda: ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]
    )
    prohibited_actions: list[str] = Field(default_factory=list)
    risk_threshold_score: int = 20


class EconomicContextData(BaseModel):
    """Authoritative financial values pre-calculated by backend."""

    amount_at_risk_paise: int
    backend_expected_recovery_value_paise: int
    baseline_control_paise: int
    estimated_recovery_probability: float
    recoverability_score: int


class TemporalContextData(BaseModel):
    """Authoritative server-side timestamps and elapsed durations."""

    server_timestamp_utc: str
    payment_age_hours: float
    time_since_failure_minutes: float
    time_since_last_action_minutes: float | None = None


class SystemStateData(BaseModel):
    """Current operational state and action eligibility."""

    payment_exists: bool = True
    already_recovered: bool = False
    action_in_flight: bool = False
    duplicate_pending: bool = False
    is_test_mode: bool = True
    action_eligibility: dict[str, bool] = Field(default_factory=dict)


class RecoveryBrainInput(BaseModel):
    """Structured Decision Context provided to Gemini Recovery Brain.

    Maintains clean separation between verified facts, backend calculations,
    and policy constraints. Never contains secrets, tokens, or card numbers.
    """

    payment_id: str
    amount_paise: int
    currency: str = "INR"
    failure_category: str
    failure_reason: str = "unknown"
    retry_count: int = 0
    max_retries_allowed: int = 3
    age_hours: float = 0.0
    recoverability_score: int = 50

    # Structured Decision Context components
    current_payment: CurrentPaymentData | None = None
    customer_history: CustomerHistoryData | None = None
    failure_context: FailureContextData | None = None
    recovery_history: RecoveryHistoryData | None = None
    merchant_policy: MerchantPolicyData | None = None
    economic_context: EconomicContextData | None = None
    temporal_context: TemporalContextData | None = None
    system_state: SystemStateData | None = None


class GeminiBrainRecommendation(BaseModel):
    """Clean structured output schema for Gemini model (primitives only)."""

    action: Literal["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]
    confidence: float = Field(ge=0.0, le=1.0)
    expected_recovery_value_paise: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=500)
    supporting_factors: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    stop_rationale: str | None = None

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 4)


class RecoveryBrainOutput(GeminiBrainRecommendation):
    """Full logical AI decision output including backend telemetry and fallback status."""

    is_fallback: bool = False
    fallback_reason: str | None = None
    latency_ms: float | None = None
    telemetry: dict[str, Any] | None = None


class DecisionContextEnvelope(BaseModel):
    """Standardized, bounded AI Decision Context Envelope (Protocol v1.0).

    Guarantees that every AI request contains explicit task identification,
    verified facts, deterministic backend calculations, historical evidence,
    and policy boundaries, while strictly excluding secrets and raw credentials.
    """

    protocolVersion: str = "1.0"
    aiTask: str
    endpoint: str
    requestId: str
    entityType: str
    entityId: str
    timestamp: str
    verifiedFacts: dict[str, Any] = Field(default_factory=dict)
    backendCalculations: dict[str, Any] = Field(default_factory=dict)
    historicalEvidence: dict[str, Any] = Field(default_factory=dict)
    policyConstraints: dict[str, Any] = Field(default_factory=dict)
    economicContext: dict[str, Any] = Field(default_factory=dict)
    temporalContext: dict[str, Any] = Field(default_factory=dict)
    systemCapabilities: dict[str, Any] = Field(default_factory=dict)
    previousRecoveryActions: list[dict[str, Any]] = Field(default_factory=list)
    allowedActions: list[str] = Field(default_factory=list)
    forbiddenActions: list[str] = Field(default_factory=list)
    requiredOutput: dict[str, Any] = Field(default_factory=dict)


class DecisionExplanationOutput(BaseModel):
    """Structured explanation from Gemini for decision.explain endpoint."""

    decision_id: str
    explanation: str = Field(min_length=10, max_length=1000)
    key_factors: list[str] = Field(default_factory=list)
    policy_alignment: str = Field(default="Fully aligned with merchant policy.")
    counterfactual: str | None = Field(default=None)
    counterfactuals: list[str] = Field(default_factory=list)
    outcome_assessment: str | None = None
    latency_ms: float | None = None

