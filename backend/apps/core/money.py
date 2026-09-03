"""Integer minor currency unit utilities for RevenueOS.

Never use floating point numbers for financial balance or arithmetic.
For INR: 1 Rupee = 100 paise.
"""

from decimal import ROUND_HALF_EVEN, Decimal


class CurrencyError(ValueError):
    """Raised when an invalid currency operation or amount is provided."""
    pass


def validate_minor_units(amount: int) -> int:
    """Validate that an amount is a non-negative integer minor unit."""
    if not isinstance(amount, int):
        raise CurrencyError(f"Amount must be an integer (paise), received {type(amount).__name__}")
    if amount < 0:
        raise CurrencyError(f"Amount cannot be negative: {amount}")
    return amount


def rupees_to_paise(rupee_amount: str | int | Decimal) -> int:
    """Convert rupee amount to integer paise using Decimal for precision."""
    try:
        dec = Decimal(str(rupee_amount))
        paise = int((dec * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
        if paise < 0:
            raise CurrencyError("Rupee amount cannot be negative.")
        return paise
    except Exception as exc:
        raise CurrencyError(f"Invalid rupee amount: {rupee_amount}") from exc


def paise_to_formatted_inr(paise: int) -> str:
    """Format paise as standard INR string without float conversion."""
    validate_minor_units(paise)
    rupees_part = paise // 100
    paise_part = paise % 100
    return f"₹{rupees_part:,}.{paise_part:02d}"


def calculate_expected_recovery_value(
    amount_paise: int,
    p_recovery: float,
    p_action_success: float,
) -> int:
    """Calculate Expected Recovery Value (ERV) in integer minor units (paise).

    ERV = floor(Amount * P_recovery * P_action_success)
    Probabilities must be bounded in [0.0, 1.0].
    """
    validate_minor_units(amount_paise)
    if not (0.0 <= p_recovery <= 1.0):
        raise ValueError(f"p_recovery must be in [0.0, 1.0], got {p_recovery}")
    if not (0.0 <= p_action_success <= 1.0):
        raise ValueError(f"p_action_success must be in [0.0, 1.0], got {p_action_success}")

    # Use Decimal for exact fractional multiplication
    dec_amount = Decimal(amount_paise)
    dec_p_rec = Decimal(str(p_recovery))
    dec_p_act = Decimal(str(p_action_success))

    erv_dec = (dec_amount * dec_p_rec * dec_p_act).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    return int(erv_dec)


calculate_erv = calculate_expected_recovery_value
format_paise_to_inr_string = paise_to_formatted_inr
