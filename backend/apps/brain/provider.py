"""Google Gemini Provider using official google-genai SDK."""

import json
import logging
from typing import Literal

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import ValidationError

from apps.brain.prompts import SYSTEM_INSTRUCTION, build_analysis_prompt
from apps.brain.schemas import RecoveryBrainInput, RecoveryBrainOutput
from apps.radar.scoring import compute_opportunity_erv, get_optimal_heuristic_action

logger = logging.getLogger("revenueos.brain")


class GeminiProvider:
    """Encapsulates interaction with Google Gemini API with fallback safety."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model_name = model or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client | None:
        if not self.api_key:
            return None
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_recommendation(self, input_ctx: RecoveryBrainInput) -> RecoveryBrainOutput:
        """Call Gemini model to obtain structured recovery action recommendation.

        Returns safe fallback on timeout, network error, or invalid schema.
        """
        client = self._get_client()
        if not client:
            logger.info("Gemini API key not configured; using deterministic fallback engine.")
            return self.get_safe_fallback(input_ctx, reason="Gemini API key not configured.")

        prompt = build_analysis_prompt(input_ctx)

        try:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,  # Low temperature for deterministic output
            )

            response = client.models.generate_content(
                model=str(self.model_name),
                contents=prompt,
                config=config,
            )

            text = response.text or "{}"
            raw_data = json.loads(text)

            # Strict Pydantic validation
            output = RecoveryBrainOutput(**raw_data)
            return output

        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(f"Malformed Gemini output: {exc}. Activating safe fallback.")
            return self.get_safe_fallback(input_ctx, reason=f"Model response validation error: {exc}")
        except Exception as exc:
            logger.error(f"Gemini API invocation error: {exc}. Activating safe fallback.")
            return self.get_safe_fallback(input_ctx, reason=f"Gemini service unavailable: {exc}")

    @staticmethod
    def get_safe_fallback(input_ctx: RecoveryBrainInput, reason: str = "Deterministic fallback") -> RecoveryBrainOutput:
        """Deterministic, safe fallback recommendation matching Radar heuristics."""
        category = input_ctx.failure_category.lower().strip()
        retry_count = input_ctx.retry_count
        max_retries = input_ctx.max_retries_allowed

        # Strict hard stop conditions
        action: Literal["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]
        if category in ["fraud", "lost_stolen_card"] or retry_count >= max_retries:
            action = "STOP"
            confidence = 0.95
            erv_paise = 0
            reason_text = (
                f"STOP: High-risk decline '{category}' or max retries ({retry_count}/{max_retries}) reached."
            )
            supporting = ["Hard decline or retry limit exhausted", "Guards against unnecessary fees"]
            risks = ["Payment cannot be safely recovered"]
        else:
            best_action, prob = get_optimal_heuristic_action(category)
            erv_paise, chosen_action, _ = compute_opportunity_erv(
                input_ctx.amount_paise,
                input_ctx.recoverability_score,
                category,
                action=best_action,
            )
            action = chosen_action if chosen_action in ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"] else "STOP"  # type: ignore[assignment]
            confidence = round(prob, 2)
            safe_reason_snippet = reason[:300] if len(reason) > 300 else reason
            reason_text = f"Fallback recommended {action} based on category '{category}' heuristics ({safe_reason_snippet})."
            supporting = [f"Deterministic heuristic for {category}", f"Historical action suitability {prob:.2f}"]
            risks = ["Generated via fallback heuristic rather than dynamic inference"]

        return RecoveryBrainOutput(
            action=action,
            confidence=confidence,
            expected_recovery_value_paise=erv_paise,
            reason=reason_text,
            supporting_factors=supporting,
            risk_factors=risks,
            is_fallback=True,
        )
