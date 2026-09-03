"""Deterministic Recoverability Scoring and Expected Recovery Value (ERV) Engine.

All probabilities, weights, and scoring matrices are deterministic heuristic assumptions
based on payment decline taxonomy and retry limits.
All monetary calculations strictly use integer minor currency units (paise).
"""

from datetime import UTC, datetime
from typing import Any

from apps.core.money import calculate_erv, validate_minor_units

# Heuristic weights summing to 1.00
WEIGHT_FAILURE_CATEGORY = 0.40
WEIGHT_RETRY_DECAY = 0.30
WEIGHT_AGE_DECAY = 0.20
WEIGHT_CUSTOMER_HISTORY = 0.10

# Failure Category Multipliers: M_cat in [0.0, 1.0]
# Transients have high recoverability; hard declines/fraud have minimal recoverability.
CATEGORY_MULTIPLIERS: dict[str, float] = {
    "network_timeout": 1.00,
    "gateway_error": 0.95,
    "system_error": 0.90,
    "soft_decline": 0.75,
    "insufficient_funds": 0.70,
    "authentication_failed": 0.45,
    "expired_card": 0.35,
    "invalid_card": 0.10,
    "lost_stolen_card": 0.05,
    "fraud": 0.00,
    "hard_decline": 0.05,
    "unknown": 0.40,
}

# Heuristic Action Success Matrix: P(action | category) in [0.0, 1.0]
ACTION_SUCCESS_MATRIX: dict[str, dict[str, float]] = {
    "network_timeout": {"RETRY": 0.85, "PAYMENT_LINK": 0.60, "REMINDER": 0.40, "STOP": 0.00},
    "gateway_error": {"RETRY": 0.80, "PAYMENT_LINK": 0.60, "REMINDER": 0.40, "STOP": 0.00},
    "system_error": {"RETRY": 0.80, "PAYMENT_LINK": 0.55, "REMINDER": 0.35, "STOP": 0.00},
    "soft_decline": {"RETRY": 0.50, "PAYMENT_LINK": 0.75, "REMINDER": 0.50, "STOP": 0.00},
    "insufficient_funds": {"RETRY": 0.35, "PAYMENT_LINK": 0.75, "REMINDER": 0.60, "STOP": 0.00},
    "authentication_failed": {"RETRY": 0.25, "PAYMENT_LINK": 0.70, "REMINDER": 0.50, "STOP": 0.00},
    "expired_card": {"RETRY": 0.05, "PAYMENT_LINK": 0.80, "REMINDER": 0.50, "STOP": 0.00},
    "invalid_card": {"RETRY": 0.00, "PAYMENT_LINK": 0.60, "REMINDER": 0.30, "STOP": 0.00},
    "lost_stolen_card": {"RETRY": 0.00, "PAYMENT_LINK": 0.10, "REMINDER": 0.05, "STOP": 1.00},
    "fraud": {"RETRY": 0.00, "PAYMENT_LINK": 0.00, "REMINDER": 0.00, "STOP": 1.00},
    "hard_decline": {"RETRY": 0.00, "PAYMENT_LINK": 0.10, "REMINDER": 0.05, "STOP": 1.00},
    "unknown": {"RETRY": 0.40, "PAYMENT_LINK": 0.50, "REMINDER": 0.30, "STOP": 0.10},
}


def compute_failure_multiplier(category: str) -> float:
    """Normalize and look up category multiplier."""
    normalized = category.lower().strip().replace(" ", "_")
    return CATEGORY_MULTIPLIERS.get(normalized, CATEGORY_MULTIPLIERS["unknown"])


def compute_retry_multiplier(retry_count: int, max_retries: int = 3) -> float:
    """Deterministic linear retry penalty decay: each retry reduces score by 33%."""
    if retry_count <= 0:
        return 1.00
    decay_rate = 1.0 / max(1, max_retries)
    return max(0.00, round(1.00 - (retry_count * decay_rate), 4))


def compute_age_multiplier(created_at: datetime | str | None, now: datetime | None = None) -> float:
    """Deterministic age decay based on hours since failure."""
    if not created_at:
        return 0.50  # Default heuristic when timestamp missing

    if isinstance(created_at, str):
        try:
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return 0.50
    else:
        created_dt = created_at

    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=UTC)

    if now is None:
        now = datetime.now(UTC)

    hours_elapsed = max(0.0, (now - created_dt).total_seconds() / 3600.0)

    if hours_elapsed <= 1.0:
        return 1.00
    if hours_elapsed <= 6.0:
        return 0.85
    if hours_elapsed <= 24.0:
        return 0.60
    if hours_elapsed <= 72.0:
        return 0.35
    return 0.10


def compute_customer_history_multiplier(history_score: float | None = None) -> float:
    """Return customer trust factor in [0.0, 1.0], default neutral 0.50."""
    if history_score is None:
        return 0.50
    return max(0.00, min(1.00, float(history_score)))


def compute_recoverability_score(payment: dict[str, Any], now: datetime | None = None) -> int:
    """Compute deterministic Recoverability Score S_i in [0, 100]."""
    category = payment.get("failure_category") or payment.get("failure_reason") or "unknown"
    m_cat = compute_failure_multiplier(str(category))

    retry_count = int(payment.get("retry_count", 0))
    max_retries = int(payment.get("max_retries_allowed", 3))
    m_retry = compute_retry_multiplier(retry_count, max_retries)

    created_at = payment.get("created_at")
    m_age = compute_age_multiplier(created_at, now=now)

    customer_history = payment.get("customer_history_score")
    m_history = compute_customer_history_multiplier(customer_history)

    raw_score = (
        (WEIGHT_FAILURE_CATEGORY * m_cat)
        + (WEIGHT_RETRY_DECAY * m_retry)
        + (WEIGHT_AGE_DECAY * m_age)
        + (WEIGHT_CUSTOMER_HISTORY * m_history)
    ) * 100.0

    return int(round(max(0.0, min(100.0, raw_score))))


def get_optimal_heuristic_action(category: str) -> tuple[str, float]:
    """Find the highest-probability heuristic recovery action for a failure category."""
    normalized = category.lower().strip().replace(" ", "_")
    actions = ACTION_SUCCESS_MATRIX.get(normalized, ACTION_SUCCESS_MATRIX["unknown"])
    # Return highest action that is not STOP (unless all non-stop are 0.0)
    best_action = "STOP"
    best_prob = 0.0

    for action, prob in actions.items():
        if action == "STOP":
            continue
        if prob > best_prob:
            best_prob = prob
            best_action = action

    if best_prob == 0.0:
        return "STOP", actions.get("STOP", 1.00)

    return best_action, best_prob


def get_action_probability(category: str, action: str) -> float:
    """Return the heuristic probability for a specific action and failure category."""
    normalized_cat = category.lower().strip().replace(" ", "_")
    normalized_act = action.upper().strip()
    actions = ACTION_SUCCESS_MATRIX.get(normalized_cat, ACTION_SUCCESS_MATRIX["unknown"])
    return actions.get(normalized_act, 0.10)


def compute_opportunity_erv(
    amount_paise: int,
    score: int,
    category: str,
    action: str | None = None,
) -> tuple[int, str, float]:
    """Compute deterministic Expected Recovery Value (ERV) in integer minor currency units (paise).

    Formula:
    ERV = floor(Amount * P_rec * P_act)
    where P_rec = Score / 100.0
    """
    validated_amount = validate_minor_units(amount_paise)
    p_rec = max(0.0, min(1.0, score / 100.0))

    if action is not None:
        p_act = get_action_probability(category, action)
        chosen_action = action.upper()
    else:
        chosen_action, p_act = get_optimal_heuristic_action(category)

    erv_paise = calculate_erv(validated_amount, p_rec, p_act)
    return erv_paise, chosen_action, p_act
