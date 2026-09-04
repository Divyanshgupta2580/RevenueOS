"""Automated test suite verifying single Gemini model governance.

Ensures that:
1. GEMINI_MODEL runtime source of truth returns 'gemini-3.6-flash'.
2. Missing or alternate models fail safely with ValueError.
3. No forbidden Gemini model strings exist anywhere in the active codebase.
"""

from pathlib import Path

import pytest
from django.conf import settings

from apps.brain.config import (
    APPROVED_GEMINI_MODEL,
    REQUIRED_GEMINI_MODEL,
    get_configured_gemini_model,
)

FORBIDDEN_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-3-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
]


def test_configured_gemini_model_is_gemini_3_6_flash(monkeypatch):
    """Runtime model source of truth must strictly return approved gemini-3.6-flash."""
    assert APPROVED_GEMINI_MODEL == "gemini-3.6-flash"
    assert REQUIRED_GEMINI_MODEL == "gemini-3.6-flash"
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-3.6-flash")
    assert get_configured_gemini_model() == "gemini-3.6-flash"


def test_missing_gemini_model_raises_value_error(monkeypatch):
    """Missing model in settings/environment must fail safely."""
    monkeypatch.setattr(settings, "GEMINI_MODEL", None)
    with pytest.raises(ValueError, match="GEMINI_MODEL is missing"):
        get_configured_gemini_model()


def test_empty_gemini_model_raises_value_error(monkeypatch):
    """Empty or blank model must raise ValueError rather than falling back silently."""
    monkeypatch.setattr(settings, "GEMINI_MODEL", "")
    with pytest.raises(ValueError, match="GEMINI_MODEL is empty"):
        get_configured_gemini_model()

    monkeypatch.setattr(settings, "GEMINI_MODEL", "   ")
    with pytest.raises(ValueError, match="GEMINI_MODEL is empty"):
        get_configured_gemini_model()


def test_unauthorized_gemini_model_raises_value_error(monkeypatch):
    """Setting an alternate or unauthorized model must fail safely and immediately."""
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")
    with pytest.raises(ValueError, match="Unauthorized GEMINI_MODEL 'gemini-3.8-flash'"):
        get_configured_gemini_model()

    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    with pytest.raises(ValueError, match="Unauthorized GEMINI_MODEL 'gemini-2.0-flash'"):
        get_configured_gemini_model()


def test_no_forbidden_models_in_codebase():
    """Scan all active code and config files to assert zero occurrences of unauthorized models."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    allowed_extensions = {".py", ".ts", ".tsx", ".yaml", ".yml", ".json", ".md"}
    excluded_dirs = {".git", ".venv", "node_modules", ".next", "__pycache__", ".pytest_cache", ".system_generated"}

    violations = []

    for file_path in root_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in excluded_dirs for part in file_path.parts):
            continue
        if file_path.suffix not in allowed_extensions:
            continue
        # Skip this test file itself since it defines FORBIDDEN_MODELS
        if file_path.name == "test_gemini_model_governance.py":
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for forbidden in FORBIDDEN_MODELS:
            if forbidden in content:
                violations.append(f"{file_path.relative_to(root_dir)}: contains '{forbidden}'")

    assert not violations, "Forbidden Gemini model strings found in codebase:\n" + "\n".join(violations)
