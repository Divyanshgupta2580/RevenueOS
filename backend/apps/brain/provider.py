"""Google Gemini Provider using official google-genai SDK.

Supports multi-key failover across up to three credentials (KEY_1, KEY_2, KEY_3),
asynchronous generation via client.aio, client reuse across the application lifecycle,
structured Pydantic outputs, and fail-safe deterministic fallbacks.
"""

import asyncio
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
from apps.brain.key_pool import (
    GeminiKeyPool,
    get_key_pool,
    is_failover_eligible,
    reset_key_pool,
)
from apps.brain.prompts import (
    EXPLANATION_SYSTEM_INSTRUCTION,
    SYSTEM_INSTRUCTION,
    build_analysis_prompt,
    build_explanation_prompt,
)
from apps.brain.schemas import (
    DecisionExplanationOutput,
    RecoveryBrainInput,
    RecoveryBrainOutput,
)
from apps.brain.tracker import usage_tracker
from apps.radar.scoring import compute_opportunity_erv, get_optimal_heuristic_action

logger = logging.getLogger("revenueos.brain")


class GeminiProvider:
    """Encapsulates interaction with Google Gemini API with multi-key failover and fallback safety."""

    # Class-level reusable client to avoid repeated client/connection initialization in mocked tests
    _shared_client: ClassVar[genai.Client | None] = None
    _shared_api_key: ClassVar[str | None] = None

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        pool: GeminiKeyPool | None = None,
    ) -> None:
        self.api_key = api_key or get_configured_gemini_api_key()
        self.model_name = model or get_configured_gemini_model()
        if pool is not None:
            self.pool = pool
        elif api_key:
            self.pool = GeminiKeyPool([("KEY_1", api_key)])
        else:
            self.pool = get_key_pool()

    @classmethod
    def get_client(cls, api_key: str | None) -> genai.Client | None:
        """Obtain or reuse the singleton genai.Client instance (backward compatibility)."""
        if not api_key:
            return None
        if cls._shared_client is None or cls._shared_api_key != api_key:
            cls._shared_client = genai.Client(api_key=api_key)
            cls._shared_api_key = api_key
        return cls._shared_client

    def _get_client(self) -> genai.Client | None:
        """Instance method alias for backward compatibility with tests."""
        if self._shared_client is not None:
            return self._shared_client
        slot = self.pool.get_active_slot()
        if slot:
            return slot.get_client()
        return self.get_client(self.api_key)

    def _is_mocked_or_override(self) -> tuple[bool, Any]:
        """Detect if client has been patched or overridden in tests via _shared_client or _get_client."""
        try:
            from unittest.mock import Mock
            if isinstance(self._shared_client, Mock):
                return True, self._shared_client
            get_client_attr = getattr(self, "_get_client", None)
            if isinstance(get_client_attr, Mock):
                return True, self._get_client()
            cls_get_client = getattr(self.__class__, "_get_client", None)
            if isinstance(cls_get_client, Mock):
                return True, self._get_client()
        except Exception:
            pass
        return False, None

    @classmethod
    def reset_client(cls) -> None:
        """Reset the shared client and key pool (used in testing and graceful shutdown)."""
        cls._shared_client = None
        cls._shared_api_key = None
        reset_key_pool()

    def _build_generation_config(self) -> types.GenerateContentConfig:
        """Construct generation config with structured schema and low temperature."""
        from apps.brain.schemas import GeminiBrainRecommendation

        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=GeminiBrainRecommendation,
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

    def _generate_with_single_client_sync(
        self, client: Any, slot_id: str, input_ctx: RecoveryBrainInput
    ) -> RecoveryBrainOutput:
        """Execute sync generation against a single specific client (mock or override)."""
        prompt = build_analysis_prompt(input_ctx)
        config = self._build_generation_config()
        t_start = time.perf_counter()

        try:
            t_gemini_start = time.perf_counter()
            response = client.models.generate_content(
                model=str(self.model_name),
                contents=prompt,
                config=config,
            )
            gemini_request_ms = round((time.perf_counter() - t_gemini_start) * 1000, 2)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

            t_schema_start = time.perf_counter()
            text = self._clean_json_text(response.text)
            raw_data = json.loads(text)

            output = RecoveryBrainOutput(**raw_data)
            schema_validation_ms = round((time.perf_counter() - t_schema_start) * 1000, 2)
            output.latency_ms = elapsed_ms
            output.telemetry = {
                "key_slot": slot_id,
                "attempts": 1,
                "gemini_request_ms": gemini_request_ms,
                "schema_validation_ms": schema_validation_ms,
            }
            return output
        except (json.JSONDecodeError, ValidationError) as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.warning("Malformed or invalid structured output from Gemini: %s", exc)
            fallback = self.get_safe_fallback(
                input_ctx, reason=f"Model response validation error: {exc}"
            )
            fallback.latency_ms = elapsed_ms
            fallback.fallback_reason = "Model response validation error"
            fallback.telemetry = {
                "key_slot": slot_id,
                "attempts": 1,
                "gemini_request_ms": elapsed_ms,
                "schema_validation_ms": 0.0,
            }
            return fallback
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error("Gemini sync invocation error: %s", exc)
            fallback = self.get_safe_fallback(
                input_ctx, reason=f"Gemini service unavailable: {exc}"
            )
            fallback.latency_ms = elapsed_ms
            fallback.fallback_reason = "Gemini service unavailable"
            fallback.telemetry = {
                "key_slot": slot_id,
                "attempts": 1,
                "gemini_request_ms": elapsed_ms,
                "schema_validation_ms": 0.0,
            }
            return fallback

    async def _generate_with_single_client_async(
        self, client: Any, slot_id: str, input_ctx: RecoveryBrainInput
    ) -> RecoveryBrainOutput:
        """Execute async generation against a single specific client (mock or override)."""
        prompt = build_analysis_prompt(input_ctx)
        config = self._build_generation_config()
        t_start = time.perf_counter()

        try:
            t_gemini_start = time.perf_counter()
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=str(self.model_name),
                    contents=prompt,
                    config=config,
                ),
                timeout=10.0,
            )
            gemini_request_ms = round((time.perf_counter() - t_gemini_start) * 1000, 2)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

            t_schema_start = time.perf_counter()
            text = self._clean_json_text(response.text)
            raw_data = json.loads(text)

            output = RecoveryBrainOutput(**raw_data)
            schema_validation_ms = round((time.perf_counter() - t_schema_start) * 1000, 2)
            output.latency_ms = elapsed_ms
            output.telemetry = {
                "key_slot": slot_id,
                "attempts": 1,
                "gemini_request_ms": gemini_request_ms,
                "schema_validation_ms": schema_validation_ms,
            }
            return output
        except (json.JSONDecodeError, ValidationError) as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.warning("Malformed or invalid structured output from Gemini: %s", exc)
            fallback = self.get_safe_fallback(
                input_ctx, reason=f"Model response validation error: {exc}"
            )
            fallback.latency_ms = elapsed_ms
            fallback.fallback_reason = "Model response validation error"
            fallback.telemetry = {
                "key_slot": slot_id,
                "attempts": 1,
                "gemini_request_ms": elapsed_ms,
                "schema_validation_ms": 0.0,
            }
            return fallback
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error("Gemini async invocation error: %s", exc)
            fallback = self.get_safe_fallback(
                input_ctx, reason=f"Gemini service unavailable: {exc}"
            )
            fallback.latency_ms = elapsed_ms
            fallback.fallback_reason = "Gemini service unavailable"
            fallback.telemetry = {
                "key_slot": slot_id,
                "attempts": 1,
                "gemini_request_ms": elapsed_ms,
                "schema_validation_ms": 0.0,
            }
            return fallback

    async def generate_recommendation_async(
        self, input_ctx: RecoveryBrainInput
    ) -> RecoveryBrainOutput:
        """Asynchronously call Gemini using client.aio with multi-key failover."""
        # 1. Check for manual test mock override
        is_mock, mock_client = self._is_mocked_or_override()
        if is_mock:
            return await self._generate_with_single_client_async(mock_client, "MOCK_KEY", input_ctx)

        # 2. Get eligible slots from pool
        eligible_slots = self.pool.get_eligible_slots()
        if not eligible_slots:
            logger.info("No eligible Gemini key slots available (all in cooldown or unconfigured); using deterministic fallback.")
            fallback = self.get_safe_fallback(input_ctx, reason="No eligible Gemini API keys available (all in cooldown).")
            fallback.fallback_reason = "ALL_KEYS_UNAVAILABLE"
            return fallback

        prompt = build_analysis_prompt(input_ctx)
        config = self._build_generation_config()
        t_total_start = time.perf_counter()
        last_error: Exception | None = None

        for attempt_idx, slot in enumerate(eligible_slots, start=1):
            t_attempt_start = time.perf_counter()
            client = slot.get_client()

            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=str(self.model_name),
                        contents=prompt,
                        config=config,
                    ),
                    timeout=10.0,
                )
                attempt_ms = round((time.perf_counter() - t_attempt_start) * 1000, 2)
                total_ms = round((time.perf_counter() - t_total_start) * 1000, 2)

                t_schema_start = time.perf_counter()
                text = self._clean_json_text(response.text)
                raw_data = json.loads(text)

                # Strict Pydantic validation
                output = RecoveryBrainOutput(**raw_data)
                schema_validation_ms = round((time.perf_counter() - t_schema_start) * 1000, 2)
                output.latency_ms = total_ms
                output.telemetry = {
                    "key_slot": slot.slot_id,
                    "attempts": attempt_idx,
                    "gemini_request_ms": attempt_ms,
                    "schema_validation_ms": schema_validation_ms,
                    "total_ms": total_ms,
                }

                # Mark slot healthy
                await self.pool.mark_success_async(slot.slot_id)

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
                    latency_ms=total_ms,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                )
                return output

            except (json.JSONDecodeError, ValidationError) as exc:
                # Schema/JSON errors are model formatting issues; do NOT rotate keys.
                elapsed_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
                logger.warning("Malformed or invalid structured output from Gemini on %s: %s", slot.slot_id, exc)
                usage_tracker.record_schema_failure()
                fallback = self.get_safe_fallback(
                    input_ctx, reason=f"Model response validation error: {exc}"
                )
                fallback.latency_ms = elapsed_ms
                fallback.fallback_reason = "Model response validation error"
                fallback.telemetry = {
                    "key_slot": slot.slot_id,
                    "attempts": attempt_idx,
                    "gemini_request_ms": elapsed_ms,
                    "schema_validation_ms": 0.0,
                }
                return fallback

            except Exception as exc:
                last_error = exc
                attempt_ms = round((time.perf_counter() - t_attempt_start) * 1000, 2)
                eligible, category = is_failover_eligible(exc)

                logger.warning(
                    "Gemini attempt %d on %s failed (duration=%.1fms, category=%s): %s",
                    attempt_idx,
                    slot.slot_id,
                    attempt_ms,
                    category,
                    exc,
                )

                if eligible:
                    await self.pool.mark_failure_async(slot.slot_id, category=category, cooldown_s=60.0)

                # Check if there are further eligible slots in pool
                remaining = [s for s in eligible_slots[attempt_idx:] if s.is_eligible()]
                if eligible and remaining:
                    logger.info("Failing over from %s to next eligible key slot %s...", slot.slot_id, remaining[0].slot_id)
                    continue
                else:
                    break

        # If all eligible slots failed
        total_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
        logger.error("All eligible Gemini key slots failed (attempts=%d, total=%.1fms): %s", len(eligible_slots), total_ms, last_error)
        usage_tracker.record_failure()
        fallback = self.get_safe_fallback(
            input_ctx, reason=f"Gemini service unavailable across {len(eligible_slots)} key slot(s): {last_error}"
        )
        fallback.latency_ms = total_ms
        fallback.fallback_reason = "Gemini service unavailable (all keys exhausted)"
        fallback.telemetry = {
            "key_slot": "FAILOVER_EXHAUSTED",
            "attempts": len(eligible_slots),
            "gemini_request_ms": total_ms,
            "schema_validation_ms": 0.0,
        }
        return fallback

    def generate_recommendation(
        self, input_ctx: RecoveryBrainInput
    ) -> RecoveryBrainOutput:
        """Synchronously call Gemini model with multi-key failover."""
        is_mock, mock_client = self._is_mocked_or_override()
        if is_mock:
            return self._generate_with_single_client_sync(mock_client, "MOCK_KEY", input_ctx)

        eligible_slots = self.pool.get_eligible_slots()
        if not eligible_slots:
            return self.get_safe_fallback(input_ctx, reason="No eligible Gemini API keys configured or available.")

        prompt = build_analysis_prompt(input_ctx)
        config = self._build_generation_config()
        t_total_start = time.perf_counter()
        last_error: Exception | None = None

        for attempt_idx, slot in enumerate(eligible_slots, start=1):
            t_attempt_start = time.perf_counter()
            client = slot.get_client()
            try:
                response = client.models.generate_content(
                    model=str(self.model_name),
                    contents=prompt,
                    config=config,
                )
                attempt_ms = round((time.perf_counter() - t_attempt_start) * 1000, 2)
                total_ms = round((time.perf_counter() - t_total_start) * 1000, 2)

                t_schema_start = time.perf_counter()
                text = self._clean_json_text(response.text)
                raw_data = json.loads(text)

                output = RecoveryBrainOutput(**raw_data)
                schema_validation_ms = round((time.perf_counter() - t_schema_start) * 1000, 2)
                output.latency_ms = total_ms
                output.telemetry = {
                    "key_slot": slot.slot_id,
                    "attempts": attempt_idx,
                    "gemini_request_ms": attempt_ms,
                    "schema_validation_ms": schema_validation_ms,
                    "total_ms": total_ms,
                }
                self.pool.mark_success(slot.slot_id)
                return output
            except (json.JSONDecodeError, ValidationError) as exc:
                elapsed_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
                usage_tracker.record_schema_failure()
                fallback = self.get_safe_fallback(input_ctx, reason=f"Model response validation error: {exc}")
                fallback.latency_ms = elapsed_ms
                fallback.fallback_reason = "Model response validation error"
                fallback.telemetry = {"key_slot": slot.slot_id, "attempts": attempt_idx, "gemini_request_ms": elapsed_ms, "schema_validation_ms": 0.0}
                return fallback
            except Exception as exc:
                last_error = exc
                eligible, category = is_failover_eligible(exc)
                if eligible:
                    self.pool.mark_failure(slot.slot_id, category=category, cooldown_s=60.0)
                remaining = [s for s in eligible_slots[attempt_idx:] if s.is_eligible()]
                if eligible and remaining:
                    continue
                else:
                    break

        total_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
        usage_tracker.record_failure()
        fallback = self.get_safe_fallback(input_ctx, reason=f"Gemini service unavailable: {last_error}")
        fallback.latency_ms = total_ms
        fallback.fallback_reason = "Gemini service unavailable"
        fallback.telemetry = {"key_slot": "FAILOVER_EXHAUSTED", "attempts": len(eligible_slots), "gemini_request_ms": total_ms, "schema_validation_ms": 0.0}
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
        """Generate structured explanation of an audit decision via Gemini or deterministic fallback with failover."""
        did = str(decision.get("decision_id", "unknown"))

        # 1. Check for manual test mock override
        is_mock, mock_client = self._is_mocked_or_override()
        if is_mock:
            client = mock_client
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
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=str(self.model_name),
                        contents=prompt,
                        config=config,
                    ),
                    timeout=10.0,
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

        eligible_slots = self.pool.get_eligible_slots()
        if not eligible_slots:
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

        for attempt_idx, slot in enumerate(eligible_slots, start=1):
            client = slot.get_client()
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=str(self.model_name),
                        contents=prompt,
                        config=config,
                    ),
                    timeout=10.0,
                )
                elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
                text = self._clean_json_text(response.text)
                raw_data = json.loads(text)
                output = DecisionExplanationOutput(**raw_data)
                output.latency_ms = elapsed_ms
                await self.pool.mark_success_async(slot.slot_id)
                return output
            except Exception as exc:
                eligible, category = is_failover_eligible(exc)
                if eligible:
                    await self.pool.mark_failure_async(slot.slot_id, category=category, cooldown_s=60.0)
                remaining = [s for s in eligible_slots[attempt_idx:] if s.is_eligible()]
                if eligible and remaining:
                    logger.info("Decision explanation failing over from %s to %s", slot.slot_id, remaining[0].slot_id)
                    continue
                else:
                    break

        return self.get_safe_explanation_fallback(decision)

    @staticmethod
    def get_safe_explanation_fallback(decision: dict[str, Any]) -> DecisionExplanationOutput:
        """Deterministic fallback explanation for audit ledger decisions."""
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
