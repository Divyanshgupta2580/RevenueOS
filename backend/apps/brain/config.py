"""Centralized Gemini Model & Configuration Layer.

Serves as the single source of truth for the active Gemini model across RevenueOS.
Reads exclusively from Django settings (which sources GEMINI_MODEL from the environment).
"""

import logging

from django.conf import settings

logger = logging.getLogger("revenueos.brain")


# Application Governance: Only the approved model may execute
APPROVED_GEMINI_MODEL: str = "gemini-3.6-flash"
REQUIRED_GEMINI_MODEL: str = APPROVED_GEMINI_MODEL


def get_configured_gemini_model() -> str:
    """Return the authoritative Gemini model identifier configured in settings.

    Architecture:
    - Environment: GEMINI_MODEL selects the requested runtime model.
    - Application Governance: APPROVED_GEMINI_MODEL validates that only the
      approved model (gemini-3.6-flash) may execute.

    Fails safely and explicitly if missing, empty, or unapproved.
    """
    model = getattr(settings, "GEMINI_MODEL", None)
    if model is None:
        raise ValueError("GEMINI_MODEL is missing from configuration.")
    model_str = str(model).strip()
    if not model_str:
        raise ValueError("GEMINI_MODEL is empty in configuration.")
    if model_str != APPROVED_GEMINI_MODEL:
        raise ValueError(
            f"Unauthorized GEMINI_MODEL '{model_str}'. "
            f"RevenueOS strictly requires approved model '{APPROVED_GEMINI_MODEL}'."
        )
    return model_str


def mask_api_key(key: str | None) -> str:
    """Mask an API key for safe logging and telemetry (never reveals raw secret)."""
    if not key or not isinstance(key, str):
        return "[UNSET]"
    k = key.strip()
    if len(k) <= 8:
        return "[MASKED]"
    return f"{k[:6]}...{k[-4:]}"


def get_configured_gemini_api_keys() -> list[tuple[str, str]]:
    """Return ordered list of configured (slot_id, api_key) pairs (server-side only).

    Checks GEMINI_API_KEY_1, GEMINI_API_KEY_2, and GEMINI_API_KEY_3 in order.
    Maintains backward compatibility if only GEMINI_API_KEY is configured.
    """
    slots: list[tuple[str, str]] = []

    k_compat = str(getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    k1 = str(getattr(settings, "GEMINI_API_KEY_1", "") or "").strip()
    if k_compat and k_compat != getattr(settings, "GEMINI_API_KEY_1", ""):
        k1 = k_compat
    elif not k1 and k_compat:
        k1 = k_compat

    k2 = str(getattr(settings, "GEMINI_API_KEY_2", "") or "").strip()
    k3 = str(getattr(settings, "GEMINI_API_KEY_3", "") or "").strip()

    if k1:
        slots.append(("KEY_1", k1))
    if k2:
        slots.append(("KEY_2", k2))
    if k3:
        slots.append(("KEY_3", k3))

    return slots


def get_configured_gemini_api_key() -> str:
    """Return the primary Gemini API key from settings (server-side only, backward compatible)."""
    keys = get_configured_gemini_api_keys()
    return keys[0][1] if keys else ""


def validate_gemini_configuration() -> None:
    """Validate that approved model and at least one valid Gemini key are configured.

    Raises ValueError if configuration is invalid or missing.
    """
    get_configured_gemini_model()
    keys = get_configured_gemini_api_keys()
    if not keys:
        raise ValueError(
            "No valid Gemini API key configured. "
            "Please configure GEMINI_API_KEY_1 (or GEMINI_API_KEY) in environment settings."
        )
