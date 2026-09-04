"""Structured system instructions and decision prompts for Recovery Brain."""

import json
from typing import Any

from apps.brain.schemas import DecisionContextEnvelope, RecoveryBrainInput

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
5. Evidence Quality: Base confidence strictly on the freshness and strength of verified evidence, not certainty of wording. If evidence is insufficient, select STOP with low confidence.
6. Execution Truthfulness: You provide structured advisory recommendations. You do not charge cards, move balances, or execute transactions.
"""

EXPLANATION_SYSTEM_INSTRUCTION = """You are the RevenueOS Decision Explainability Engine.
Your role is to explain concisely and transparently to merchant operators WHY a specific recovery decision was made or blocked, referencing verified facts, backend calculations, and deterministic policy rules.
Do not invent facts. State clearly which rules governed the outcome.
"""


def build_envelope_prompt(env: DecisionContextEnvelope) -> str:
    """Construct structured decision context prompt from standardized DecisionContextEnvelope."""
    return f"""=== SYSTEM_ROLE ===
RevenueOS Advisory Engine — Task: {env.aiTask} (Endpoint: {env.endpoint}, Request: {env.requestId})

=== TASK ===
Evaluate entity {env.entityType} '{env.entityId}' at {env.timestamp}.
Select the bounded optimal recovery action, assess confidence from evidence quality, and output structured JSON.

=== VERIFIED_FACTS ===
{json.dumps(env.verifiedFacts, indent=2)}

=== FACTS_CALCULATED_BY_BACKEND ===
{json.dumps(env.backendCalculations, indent=2)}

=== HISTORICAL_EVIDENCE ===
{json.dumps(env.historicalEvidence, indent=2)}

=== POLICY_CONSTRAINTS ===
{json.dumps(env.policyConstraints, indent=2)}

=== ECONOMIC_CONTEXT ===
{json.dumps(env.economicContext, indent=2)}

=== TEMPORAL_CONTEXT ===
{json.dumps(env.temporalContext, indent=2)}

=== SYSTEM_CAPABILITIES ===
{json.dumps(env.systemCapabilities, indent=2)}

=== ALLOWED_ACTIONS ===
{json.dumps(env.allowedActions)}

=== FORBIDDEN_ACTIONS ===
{json.dumps(env.forbiddenActions)}

=== OUTPUT_SCHEMA ===
{json.dumps(env.requiredOutput, indent=2)}
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

    forbidden_actions = [k for k, v in eligibility.items() if not v]

    return f"""=== SYSTEM_ROLE ===
You are the RevenueOS AI Recovery Brain. Evaluate the verified facts and policy constraints below.

=== TASK ===
Select the optimal recovery action from eligible actions ({', '.join(k for k, v in eligibility.items() if v)}), assess confidence based on evidence quality, and identify key supporting and risk factors.

=== VERIFIED_FACTS ===
Payment ID: {payment_id}
Amount: {amount_paise} paise ({amount_paise / 100:.2f} {currency})
Status: {status} (Captured: {captured})
Payment Method: {method}
Failure Code: {failure_code}
Failure Description: {failure_desc}

=== FACTS_CALCULATED_BY_BACKEND ===
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

=== POLICY_CONSTRAINTS ===
Maximum Retry Limit: {max_allowed}
Cooldown Window: {cooldown_window}s
Allowed Recovery Actions: {allowed_actions}
Risk Rule: STOP mandatory on fraud, stolen cards, or closed accounts.

=== HISTORICAL_EVIDENCE ===
Customer ID: {cust_id}
Customer Payment History: {cust_successes} successful, {cust_failures} failed (Success Rate: {cust_rate:.2f})
Recovery Attempts for this Payment: {actions_attempted} (Last Action: {last_action or 'None'})

=== ECONOMIC_CONTEXT ===
Amount at Risk: {amount_paise} paise
Expected Recovery Value: {erv_paise} paise
Baseline Control: {baseline_control} paise

=== TEMPORAL_CONTEXT ===
Elapsed Duration: {age_hours:.1f} hours
Cooldown Status: {'Active' if cooldown_active else 'Elapsed'}

=== SYSTEM_CAPABILITIES ===
Mode: Test Mode (Simulated retries, dynamic Razorpay Test payment links)

=== ALLOWED_ACTIONS ===
{[k for k, v in eligibility.items() if v]}

=== FORBIDDEN_ACTIONS ===
{forbidden_actions}

=== OUTPUT_SCHEMA ===
action: RETRY | PAYMENT_LINK | REMINDER | STOP
confidence: float in [0.0, 1.0]
expected_recovery_value_paise: integer paise
reason: string explanation
supporting_factors: list of strings
risk_factors: list of strings
"""


def build_explanation_prompt(decision: dict[str, Any]) -> str:
    """Construct prompt to explain an existing audit decision."""
    did = decision.get("decision_id", "unknown")
    pid = decision.get("payment_id", "unknown")
    ai_rec = decision.get("ai_recommendation", {})
    policy_dec = decision.get("policy_decision", {})

    return f"""=== SYSTEM_ROLE ===
RevenueOS Decision Explainability Engine

=== TASK ===
Explain why decision '{did}' for payment '{pid}' was evaluated as {policy_dec.get('status', 'EVALUATED')}.

=== VERIFIED_FACTS ===
Decision ID: {did}
Payment ID: {pid}
Created At: {decision.get('created_at')}

=== AI_RECOMMENDATION ===
Recommended Action: {ai_rec.get('action')}
Confidence: {ai_rec.get('confidence')}
Reason: {ai_rec.get('reason')}
Supporting Factors: {ai_rec.get('supporting_factors', [])}

=== POLICY_DECISION ===
Status: {policy_dec.get('status')}
Authorized Action: {policy_dec.get('authorized_action') or 'None'}
Blocking Rule: {policy_dec.get('blocking_rule') or 'None'}
Blocking Reason: {policy_dec.get('blocking_reason') or 'None'}
Rules Evaluated: {policy_dec.get('rules_evaluated', [])}

=== OUTPUT_SCHEMA ===
decision_id: string
explanation: clear human-readable narrative explanation
key_factors: list of primary deciding factors
policy_alignment: explanation of how policy rules governed the outcome
"""
