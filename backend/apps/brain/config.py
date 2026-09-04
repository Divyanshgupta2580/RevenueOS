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


def get_configured_gemini_api_key() -> str:
    """Return the Gemini API key from settings (server-side only)."""
    return str(getattr(settings, "GEMINI_API_KEY", "") or "")
