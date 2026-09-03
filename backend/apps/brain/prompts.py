"""Structured system instructions and decision prompts for Recovery Brain."""

from apps.brain.schemas import RecoveryBrainInput

SYSTEM_INSTRUCTION = """You are the RevenueOS AI Recovery Brain, an expert decision engine for failed online payment recovery.

OPERATIONAL PRINCIPLES:
1. Grounded Reasoning: Reason strictly and exclusively from supplied VERIFIED_FACTS, FACTS_CALCULATED_BY_BACKEND, and HISTORICAL_EVIDENCE. Never invent missing facts. Missing information must remain unknown.
2. Determinism & Policy: Never attempt to override POLICY_CONSTRAINTS. Never recommend an action that is ineligible under current system state.
3. Bounded Action Space: You must select EXACTLY ONE action from:
   - PAYMENT_LINK: Dynamic checkout link via Razorpay Test Mode API. Safest for soft declines, auth errors, and alternative payment methods.
   - REMINDER: Non-intrusive notification for pending authorizations.
   - RETRY: Simulated Test Action for transient network faults where retries remain unexhausted and cooldown has elapsed.
   - STOP: Terminal policy action. Mandatory for fraud, stolen cards, hard declines, or exhausted retry limits.
4. Economic Prudence: Prefer the safest eligible action with the strongest expected recovery value. If recovery is unsafe, unethical, or economically unwarranted, select STOP.
5. Evidence Quality: Base confidence strictly on the freshness and strength of verified evidence, not certainty of wording.
6. Execution Truthfulness: You provide structured advisory recommendations. You do not charge cards, move balances, or execute transactions.
"""


def build_analysis_prompt(ctx: RecoveryBrainInput) -> str:
    """Construct structured decision context cleanly separating facts from inference."""
    # 1. Verified Facts
    cp = ctx.current_payment
    payment_id = cp.payment_id if cp else ctx.payment_id
    amount_paise = cp.amount_paise if cp else ctx.amount_paise
    currency = cp.currency if cp else ctx.currency
    status = cp.status if cp else "failed"
    method = cp.method if cp else "unknown"
    failure_code = (cp.failure_code if cp else None) or ctx.failure_reason
    failure_desc = (cp.failure_description if cp else None) or ctx.failure_reason
    captured = cp.captured if cp else False

    # 2. Calculated Facts
    fc = ctx.failure_context
    category = fc.failure_category if fc else ctx.failure_category
    retry_count = ctx.retry_count
    max_retries = ctx.max_retries_allowed
    score = ctx.recoverability_score
    age_hours = ctx.age_hours

    econ = ctx.economic_context
    erv_paise = econ.backend_expected_recovery_value_paise if econ else (amount_paise * score // 100)
    baseline_control = econ.baseline_control_paise if econ else (amount_paise * 8 // 100)
    est_prob = econ.estimated_recovery_probability if econ else round(score / 100.0, 2)

    rh = ctx.recovery_history
    cooldown_active = rh.cooldown_active if rh else False
    cooldown_secs = rh.cooldown_remaining_seconds if rh else 0
    actions_attempted = rh.actions_attempted_count if rh else 0
    last_action = rh.last_action_type if rh else None

    # 3. Policy Constraints
    mp = ctx.merchant_policy
    max_allowed = mp.max_retries_allowed if mp else max_retries
    cooldown_window = mp.cooldown_seconds if mp else 300
    allowed_actions = mp.allowed_actions if mp else ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]

    # 4. Historical Evidence
    ch = ctx.customer_history
    cust_id = ch.customer_id if ch else "unknown"
    cust_successes = ch.total_successful_payments if ch else 0
    cust_failures = ch.total_failed_payments if ch else 0
    cust_rate = ch.historical_recovery_success_rate if ch else 0.0

    # 5. System State & Eligibility
    ss = ctx.system_state
    eligibility = ss.action_eligibility if ss else {
        "RETRY": retry_count < max_allowed and not cooldown_active and category not in ["fraud", "lost_stolen_card"],
        "PAYMENT_LINK": category not in ["fraud", "lost_stolen_card"],
        "REMINDER": category not in ["fraud", "lost_stolen_card"],
        "STOP": True,
    }

    return f"""=== 1. VERIFIED_FACTS ===
Payment ID: {payment_id}
Amount: {amount_paise} paise ({amount_paise / 100:.2f} {currency})
Status: {status} (Captured: {captured})
Payment Method: {method}
Failure Code: {failure_code}
Failure Description: {failure_desc}

=== 2. FACTS_CALCULATED_BY_BACKEND ===
Payment Age: {age_hours:.1f} hours
Failure Category: {category}
Retry Count: {retry_count} of {max_allowed} allowed
Recoverability Score: {score}/100
Amount at Risk: {amount_paise} paise
Baseline Recovery Control (8% heuristic model): {baseline_control} paise
Backend Expected Recovery Value (ERV): {erv_paise} paise
Estimated Recovery Probability: {est_prob:.2f}
Cooldown Active: {cooldown_active} ({cooldown_secs}s remaining)
Current Action Eligibility: {eligibility}

=== 3. POLICY_CONSTRAINTS ===
Maximum Retry Limit: {max_allowed}
Cooldown Window: {cooldown_window}s
Allowed Recovery Actions: {allowed_actions}
Risk Rule: STOP mandatory on fraud, stolen cards, or closed accounts.

=== 4. HISTORICAL_EVIDENCE ===
Customer ID: {cust_id}
Customer Payment History: {cust_successes} successful, {cust_failures} failed (Success Rate: {cust_rate:.2f})
Recovery Attempts for this Payment: {actions_attempted} (Last Action: {last_action or 'None'})

=== 5. AI_TASK ===
Given the verified facts and deterministic constraints above, reason over the evidence and select the single safest and highest-value recovery action:
- PAYMENT_LINK: Dynamic checkout link via Razorpay Test Mode API. Safest for soft declines, auth errors, and alternative payment methods.
- REMINDER: Customer notification nudge for pending authorizations.
- RETRY: Automated gateway retry (Simulated Test Action) for transient network glitches with retries remaining.
- STOP: Terminate recovery. Mandatory for fraud, stolen cards, hard declines, or exhausted retry limits.

Respond strictly in JSON conforming to the schema with: action, confidence (0.0-1.0), expected_recovery_value_paise (integer), reason, supporting_factors, risk_factors, and stop_rationale (if action is STOP).
"""
