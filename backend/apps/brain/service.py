"""Recovery Brain Service: Coordinates input sanitization, inference, and audit packaging."""

from datetime import UTC, datetime
from typing import Any

from apps.brain.provider import GeminiProvider
from apps.brain.schemas import RecoveryBrainInput, RecoveryBrainOutput
from apps.core.money import validate_minor_units
from apps.radar.scoring import compute_recoverability_score


class RecoveryBrainService:
    """Logical AI decision engine for RevenueOS.

    Has zero direct database access and zero direct payment gateway mutation capability.
    """

    def __init__(self, provider: GeminiProvider | None = None) -> None:
        self.provider = provider or GeminiProvider()

    def analyze_payment(
        self,
        payment: dict[str, Any],
        now: datetime | None = None,
    ) -> RecoveryBrainOutput:
        """Run sanitized AI analysis for an eligible payment."""
        if now is None:
            now = datetime.now(UTC)

        payment_id = str(payment.get("payment_id", ""))
        amount = validate_minor_units(int(payment.get("amount", 0)))
        failure_category = str(payment.get("failure_category") or "unknown")
        failure_reason = str(payment.get("failure_reason") or "unspecified")
        retry_count = int(payment.get("retry_count", 0))
        max_retries = int(payment.get("max_retries_allowed", 3))

        created_at = payment.get("created_at")
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
        else:
            age_hours = 0.0

        score = compute_recoverability_score(payment, now=now)

        input_ctx = RecoveryBrainInput(
            payment_id=payment_id,
            amount_paise=amount,
            currency=str(payment.get("currency", "INR")),
            failure_category=failure_category,
            failure_reason=failure_reason,
            retry_count=retry_count,
            max_retries_allowed=max_retries,
            age_hours=round(age_hours, 2),
            recoverability_score=score,
        )

        return self.provider.generate_recommendation(input_ctx)
