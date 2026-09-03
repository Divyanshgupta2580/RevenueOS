"""Structured system and evaluation prompts for Recovery Brain."""

from apps.brain.schemas import RecoveryBrainInput

SYSTEM_INSTRUCTION = """You are the RevenueOS AI Recovery Brain, an expert decision engine for failed online payment recovery.

Your goal is to recommend the single highest-value and safest recovery action for a failed transaction.

You must choose EXACTLY ONE action from this bounded set:
1. RETRY: Best for transient errors (network timeout, gateway glitch, switch error) where the customer's card is valid and retry limits have not been reached.
2. PAYMENT_LINK: Best for soft declines (insufficient funds, expired card, auth failure) where sending an alternative checkout link via SMS/email allows payment via UPI/netbanking.
3. REMINDER: Best for pending/abandoned customer authorizations where a polite notification nudge can complete payment.
4. STOP: Mandatory for hard declines (fraud, stolen card, lost card, closed account) or when retries are exhausted, to avoid unnecessary gateway fees, chargebacks, or customer harassment.

CRITICAL CONSTRAINTS:
- You are an advisory recommendation engine. You CANNOT mutate database records, move funds, or execute external transactions.
- You must respond with valid JSON strictly conforming to the requested schema.
- Expected recovery value must be an integer minor currency unit (paise).
"""


def build_analysis_prompt(ctx: RecoveryBrainInput) -> str:
    """Construct sanitized prompt with structured context."""
    return f"""Evaluate the following failed payment opportunity:

Payment ID: {ctx.payment_id}
Amount: {ctx.amount_paise} paise ({ctx.amount_paise / 100:.2f} {ctx.currency})
Failure Category: {ctx.failure_category}
Failure Description: {ctx.failure_reason}
Retry Count: {ctx.retry_count} of {ctx.max_retries_allowed} allowed
Age: {ctx.age_hours:.1f} hours elapsed
Calculated Recoverability Score: {ctx.recoverability_score}/100

Respond strictly in JSON format with the following structure:
{{
  "action": "RETRY" | "PAYMENT_LINK" | "REMINDER" | "STOP",
  "confidence": <float between 0.0 and 1.0>,
  "expected_recovery_value_paise": <integer paise>,
  "reason": "<short audit explanation>",
  "supporting_factors": ["<factor 1>", "<factor 2>"],
  "risk_factors": ["<risk 1>"]
}}
"""
