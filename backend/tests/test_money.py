"""Unit tests for integer minor currency units and ERV calculation."""

import pytest

from apps.core.money import (
    CurrencyError,
    calculate_expected_recovery_value,
    paise_to_formatted_inr,
    rupees_to_paise,
    validate_minor_units,
)


def test_validate_minor_units_valid() -> None:
    """Ensure non-negative integers pass validation."""
    assert validate_minor_units(100) == 100
    assert validate_minor_units(0) == 0


def test_validate_minor_units_invalid_type() -> None:
    """Ensure floating-point or non-integers are rejected."""
    with pytest.raises(CurrencyError, match="must be an integer"):
        validate_minor_units(10.5)  # type: ignore[arg-type]


def test_validate_minor_units_negative() -> None:
    """Ensure negative values raise CurrencyError."""
    with pytest.raises(CurrencyError, match="cannot be negative"):
        validate_minor_units(-50)


def test_rupees_to_paise() -> None:
    """Ensure accurate rupee-to-paise conversion without float issues."""
    assert rupees_to_paise(10) == 1000
    assert rupees_to_paise("49.99") == 4999
    assert rupees_to_paise("199.50") == 19950


def test_paise_to_formatted_inr() -> None:
    """Ensure accurate formatting of paise to INR string."""
    assert paise_to_formatted_inr(499900) == "₹4,999.00"
    assert paise_to_formatted_inr(50) == "₹0.50"
    assert paise_to_formatted_inr(10000000) == "₹100,000.00"


def test_calculate_expected_recovery_value() -> None:
    """Test Expected Recovery Value (ERV) = Amount * P_rec * P_act."""
    # ₹10,000 (1,000,000 paise), P_rec = 0.8, P_act = 0.5 -> ₹4,000 (400,000 paise)
    erv = calculate_expected_recovery_value(
        amount_paise=1_000_000,
        p_recovery=0.8,
        p_action_success=0.5,
    )
    assert erv == 400_000
    assert isinstance(erv, int)


def test_calculate_expected_recovery_value_bounds() -> None:
    """Ensure out-of-bound probabilities raise ValueError."""
    with pytest.raises(ValueError, match="p_recovery must be in"):
        calculate_expected_recovery_value(1000, -0.1, 0.5)
    with pytest.raises(ValueError, match="p_action_success must be in"):
        calculate_expected_recovery_value(1000, 0.5, 1.5)


def test_money_boundary_amounts_and_rounding() -> None:
    """Ensure boundary amounts (0 paise, 1 paisa, large amounts) and rounding are exact."""
    # Zero amount
    assert calculate_expected_recovery_value(0, 0.5, 0.5) == 0

    # Fractional rounding (ROUND_HALF_EVEN / Banker's rounding)
    assert calculate_expected_recovery_value(1, 0.5, 0.5) == 0  # 0.25 -> 0
    assert calculate_expected_recovery_value(2, 0.5, 0.5) == 0  # 0.50 -> 0 (nearest even integer)
    assert calculate_expected_recovery_value(6, 0.5, 0.5) == 2  # 1.50 -> 2 (nearest even integer)
    assert calculate_expected_recovery_value(10, 0.5, 0.5) == 2  # 2.50 -> 2 (nearest even integer)
    assert calculate_expected_recovery_value(14, 0.5, 0.5) == 4  # 3.50 -> 4 (nearest even integer)

