"""Centralized Gemini Model & Configuration Layer.

Serves as the single source of truth for the active Gemini model across RevenueOS.
Reads exclusively from Django settings (which sources GEMINI_MODEL from the environment).
"""

import logging

from django.conf import settings

logger = logging.getLogger("revenueos.brain")


def get_configured_gemini_model() -> str:
    """Return the single authoritative Gemini model identifier configured in settings.

    Guarantees that runtime components do not hardcode model names and that
    updating GEMINI_MODEL in the environment immediately propagates across the application.
    """
    model = getattr(settings, "GEMINI_MODEL", None)
    if not model or not str(model).strip():
        raise ValueError("GEMINI_MODEL is not configured in settings or environment.")
    return str(model).strip()


def get_configured_gemini_api_key() -> str:
    """Return the Gemini API key from settings (server-side only)."""
    return str(getattr(settings, "GEMINI_API_KEY", "") or "")
