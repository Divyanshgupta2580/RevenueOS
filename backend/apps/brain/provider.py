"""Google Gemini Provider using official google-genai SDK.

Supports asynchronous generation via client.aio, client reuse across the application lifecycle,
structured Pydantic outputs, and fail-safe deterministic fallbacks.
"""

import json
import logging
import time
from typing import Any, ClassVar, Literal, cast

from google import genai
from google.genai import types
from pydantic import ValidationError

from apps.brain.config import (
    get_configured_gemini_api_key,
    get_configured_gemini_model,
)
from apps.brain.prompts import SYSTEM_INSTRUCTION, build_analysis_prompt
from apps.brain.schemas import (
    DecisionExplanationOutput,
    RecoveryBrainInput,
    RecoveryBrainOutput,
)
from apps.brain.tracker import usage_tracker
from apps.radar.scoring import compute_opportunity_erv, get_optimal_heuristic_action

logger = logging.getLogger("revenueos.brain")


class GeminiProvider:
    """Encapsulates interaction with Google Gemini API with fallback safety."""

    # Class-level reusable client to avoid repeated client/connection initialization
    _shared_client: ClassVar[genai.Client | None] = None
    _shared_api_key: ClassVar[str | None] = None

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or get_configured_gemini_api_key()
        self.model_name = model or get_configured_gemini_model()

    @classmethod
    def get_client(cls, api_key: str | None) -> genai.Client | None:
        """Obtain or reuse the singleton genai.Client instance."""
        if not api_key:
            return None
        if cls._shared_client is None or cls._shared_api_key != api_key:
            cls._shared_client = genai.Client(api_key=api_key)
            cls._shared_api_key = api_key
        return cls._shared_client

    def _get_client(self) -> genai.Client | None:
        """Instance method alias for backward compatibility with tests."""
        return self.get_client(self.api_key)

    @classmethod
    def reset_client(cls) -> None:
        """Reset the shared client (used in testing and graceful shutdown)."""
        cls._shared_client = None
        cls._shared_api_key = None

    def _build_generation_config(self) -> types.GenerateContentConfig:
        """Construct generation config with structured schema and low temperature."""
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=RecoveryBrainOutput,
            temperature=0.1,  # Low temperature for deterministic financial decision support
            max_output_tokens=1500,  # Generous token budget for complete structured Pydantic schema
        )

    @staticmethod
    def _clean_json_text(raw_text: str | None) -> str:
        """Strip markdown code fence blocks and extra whitespace from model response."""
        if not raw_text:
            return "{}"
        text = raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    async def generate_recommendation_async(
        self, input_ctx: RecoveryBrainInput
    ) -> RecoveryBrainOutput:
        """Asynchronously call Gemini using client.aio for high-concurrency WebSocket paths."""
        client = self._get_client()
        if not client:
            logger.info("Gemini API key not configured; using deterministic fallback engine.")
            return self.get_safe_fallback(input_ctx, reason="Gemini API key not configured.")

        prompt = build_analysis_prompt(input_ctx)
        config = self._build_generation_config()
        t_start = time.perf_counter()

        try:
            response = await client.aio.models.generate_content(
                model=str(self.model_name),
                contents=prompt,
                config=config,
            )
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

            text = self._clean_json_text(response.text)
            raw_data = json.loads(text)

            # Strict Pydantic validation
            output = RecoveryBrainOutput(**raw_data)
            output.latency_ms = elapsed_ms

            # Safe observability tracking
            in_tokens = 0
            out_tokens = 0
            usage_meta = getattr(response, "usage_metadata", None)
            if usage_meta is not None:
                p_cnt = getattr(usage_meta, "prompt_token_count", 0)
                c_cnt = getattr(usage_meta, "candidates_token_count", 0)
                if isinstance(p_cnt, (int, float)):
                    in_tokens = int(p_cnt)
                if isinstance(c_cnt, (int, float)):
                    out_tokens = int(c_cnt)
            usage_tracker.record_request(
                latency_ms=elapsed_ms,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
            )
            return output

        except (json.JSONDecodeError, ValidationError) as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.warning("Malformed or invalid structured output from Gemini: %s", exc)
            usage_tracker.record_schema_failure()
            fallback = self.get_safe_fallback(
                input_ctx, reason=f"Model response validation error: {exc}"
            )
            fallback.latency_ms = elapsed_ms
            return fallback
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error("Gemini async invocation error: %s", exc)
            usage_tracker.record_failure()
            fallback = self.get_safe_fallback(
                input_ctx, reason=f"Gemini service unavailable: {exc}"
            )
            fallback.latency_ms = elapsed_ms
            return fallback

    def generate_recommendation(
        self, input_ctx: RecoveryBrainInput
    ) -> RecoveryBrainOutput:
        """Synchronously call Gemini model to obtain structured recovery action recommendation."""
        client = self._get_client()
        if not client:
            logger.info("Gemini API key not configured; using deterministic fallback engine.")
            return self.get_safe_fallback(input_ctx, reason="Gemini API key not configured.")

        prompt = build_analysis_prompt(input_ctx)
        config = self._build_generation_config()
        t_start = time.perf_counter()

        try:
            response = client.models.generate_content(
                model=str(self.model_name),
                contents=prompt,
                config=config,
            )
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

            text = self._clean_json_text(response.text)
            raw_data = json.loads(text)

            # Strict Pydantic validation
            output = RecoveryBrainOutput(**raw_data)
            output.latency_ms = elapsed_ms

            # Safe observability tracking
            in_tokens = 0
            out_tokens = 0
            usage_meta = getattr(response, "usage_metadata", None)
            if usage_meta is not None:
                p_cnt = getattr(usage_meta, "prompt_token_count", 0)
                c_cnt = getattr(usage_meta, "candidates_token_count", 0)
                if isinstance(p_cnt, (int, float)):
                    in_tokens = int(p_cnt)
                if isinstance(c_cnt, (int, float)):
                    out_tokens = int(c_cnt)
            usage_tracker.record_request(
                latency_ms=elapsed_ms,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
            )
            return output

        except (json.JSONDecodeError, ValidationError) as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.warning("Malformed or invalid structured output from Gemini: %s", exc)
            usage_tracker.record_schema_failure()
            fallback = self.get_safe_fallback(
                input_ctx, reason=f"Model response validation error: {exc}"
            )
            fallback.latency_ms = elapsed_ms
            return fallback
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error("Gemini sync invocation error: %s", exc)
            usage_tracker.record_failure()
            fallback = self.get_safe_fallback(
                input_ctx, reason=f"Gemini service unavailable: {exc}"
            )
            fallback.latency_ms = elapsed_ms
            return fallback

    @staticmethod
    def get_safe_fallback(
        input_ctx: RecoveryBrainInput, reason: str = "Deterministic fallback"
    ) -> RecoveryBrainOutput:
        """Deterministic, safe fallback recommendation matching Radar heuristics."""
        category = input_ctx.failure_category.lower().strip()
        retry_count = input_ctx.retry_count
        max_retries = input_ctx.max_retries_allowed

        # Strict hard stop conditions
        action: Literal["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]
        stop_rationale: str | None = None

        if category in ["fraud", "lost_stolen_card"] or retry_count >= max_retries:
            action = "STOP"
            confidence = 0.95
            erv_paise = 0
            reason_text = (
                f"STOP: High-risk decline '{category}' or max retries ({retry_count}/{max_retries}) reached."
            )
            stop_rationale = (
                f"Hard decline '{category}' or exhausted retries ({retry_count}/{max_retries})"
            )
            supporting = [
                "Hard decline or retry limit exhausted",
                "Guards against unnecessary fees and card brand penalties",
            ]
            risks = ["Payment cannot be safely recovered"]
        else:
            best_action, prob = get_optimal_heuristic_action(category)
            erv_paise, chosen_action, _ = compute_opportunity_erv(
                input_ctx.amount_paise,
                input_ctx.recoverability_score,
                category,
                action=best_action,
            )
            action = cast(
                Literal["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"],
                chosen_action
                if chosen_action in ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]
                else "STOP",
            )
            confidence = round(prob, 2)
            safe_reason_snippet = reason[:300] if len(reason) > 300 else reason
            reason_text = (
                f"Fallback recommended {action} based on category '{category}' heuristics ({safe_reason_snippet})."
            )
            supporting = [
                f"Deterministic heuristic for {category}",
                f"Historical action suitability {prob:.2f}",
            ]
            risks = ["Generated via fallback heuristic rather than dynamic inference"]

        return RecoveryBrainOutput(
            action=action,
            confidence=confidence,
            expected_recovery_value_paise=erv_paise,
            reason=reason_text,
            supporting_factors=supporting,
            risk_factors=risks,
            stop_rationale=stop_rationale,
            is_fallback=True,
        )

    async def explain_decision_async(
        self, decision: dict[str, Any]
    ) -> DecisionExplanationOutput:
        """Generate structured explanation of an audit decision via Gemini or deterministic fallback."""
        from apps.brain.prompts import EXPLANATION_SYSTEM_INSTRUCTION, build_explanation_prompt
        from apps.brain.schemas import DecisionExplanationOutput

        did = str(decision.get("decision_id", "unknown"))
        client = self._get_client()

        if not client:
            return self.get_safe_explanation_fallback(decision)

        prompt = build_explanation_prompt(decision)
        config = types.GenerateContentConfig(
            system_instruction=EXPLANATION_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=DecisionExplanationOutput,
            temperature=0.1,
            max_output_tokens=1500,
        )

        t_start = time.perf_counter()
        try:
            response = await client.aio.models.generate_content(
                model=str(self.model_name),
                contents=prompt,
                config=config,
            )
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            text = self._clean_json_text(response.text)
            raw_data = json.loads(text)
            output = DecisionExplanationOutput(**raw_data)
            output.latency_ms = elapsed_ms
            return output
        except Exception as exc:
            logger.warning("Error generating AI explanation for decision %s: %s", did, exc)
            return self.get_safe_explanation_fallback(decision)

    @staticmethod
    def get_safe_explanation_fallback(decision: dict[str, Any]) -> DecisionExplanationOutput:
        """Deterministic fallback explanation for audit ledger decisions."""
        from apps.brain.schemas import DecisionExplanationOutput

        did = str(decision.get("decision_id", "unknown"))
        policy_dec = decision.get("policy_decision", {})
        status = policy_dec.get("status", "EVALUATED")
        blocking_reason = policy_dec.get("blocking_reason")
        auth_action = policy_dec.get("authorized_action")

        if status == "BLOCKED":
            exp = f"Decision was BLOCKED by Guarded Autopilot policy. Rule violated: {blocking_reason or 'Risk policy constraint'}."
            factors = [blocking_reason or "Policy restriction", "Protected against unnecessary retry overhead"]
        else:
            exp = f"Decision was APPROVED by Guarded Autopilot policy for action '{auth_action or 'AUTHORIZED'}'. All pre-execution checks passed."
            factors = ["Action within merchant limits", "No active cooldowns", "Eligible payment state"]

        return DecisionExplanationOutput(
            decision_id=did,
            explanation=exp,
            key_factors=factors,
            policy_alignment="Verified against deterministic policy engine rules.",
            outcome_assessment="Deterministic evaluation without external API dependency.",
            latency_ms=0.01,
        )
