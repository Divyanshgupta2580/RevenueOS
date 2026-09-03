"""Strict Pydantic schemas for the Recovery Brain AI engine."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RecoveryBrainInput(BaseModel):
    """Sanitized payment context provided to the Gemini model."""
    payment_id: str
    amount_paise: int
    currency: str = "INR"
    failure_category: str
    failure_reason: str = "unknown"
    retry_count: int = 0
    max_retries_allowed: int = 3
    age_hours: float = 0.0
    recoverability_score: int = 50


class RecoveryBrainOutput(BaseModel):
    """Strictly validated structured output from the Recovery Brain."""
    action: Literal["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]
    confidence: float = Field(ge=0.0, le=1.0)
    expected_recovery_value_paise: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=500)
    supporting_factors: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    is_fallback: bool = False

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 4)
