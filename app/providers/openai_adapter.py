from __future__ import annotations

import logging
from hashlib import sha1
from time import perf_counter
from typing import Any

from app.core.config import get_settings
from app.domain.schemas import IntakeSubmission, ProviderResponse
from app.providers.base import AIProvider
from app.providers.errors import ProviderResponseError, ProviderUnavailableError
from app.providers.mock import LocalMockProvider
from app.providers.openai_contracts import OpenAIWorkflowAnalysis
from app.providers.prompt_builder import build_workflow_prompt
from app.providers.response_parser import (
    OpenAIResponseParseError,
    build_workflow_decision,
    extract_refusal_text,
    parse_openai_output,
)

try:  # pragma: no cover - import availability depends on the local environment
    from openai import OpenAI
except Exception:  # pragma: no cover - handled by fallback logic
    OpenAI = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI-backed provider with structured outputs and safe fallback handling."""

    name = "openai"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
        fallback_provider: AIProvider | None = None,
        allow_mock_fallback: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.openai_model
        self.timeout_seconds = settings.openai_timeout_seconds
        self.prompt_version = settings.openai_prompt_version
        self.allow_mock_fallback = (
            settings.openai_fallback_to_mock
            if allow_mock_fallback is None
            else allow_mock_fallback
        )
        self._fallback_provider = fallback_provider or LocalMockProvider()
        self._client: Any | None = None

        if client is not None:
            self._client = client
            return

        configured_api_key = api_key or settings.openai_api_key.strip()
        if not configured_api_key:
            return

        if OpenAI is None:
            logger.warning("OpenAI SDK is unavailable; provider will use fallback.")
            return

        try:
            self._client = OpenAI(
                api_key=configured_api_key,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - environment-specific
            logger.warning("OpenAI client initialization failed: %s", exc)

    def analyze(self, submission: IntakeSubmission) -> ProviderResponse:
        prompt = build_workflow_prompt(
            submission,
            prompt_version=self.prompt_version,
        )
        started_at = perf_counter()

        if self._client is None:
            return self._fallback_or_raise(
                submission,
                reason="openai_unavailable",
                prompt=prompt.messages,
            )

        try:
            response = self._client.responses.parse(
                model=self.model,
                input=prompt.messages,
                text_format=OpenAIWorkflowAnalysis,
                store=False,
            )
            refusal = extract_refusal_text(response)
            if refusal:
                return self._fallback_or_raise(
                    submission,
                    reason="model_refusal",
                    prompt=prompt.messages,
                    response=response,
                    error=ProviderResponseError(refusal),
                )

            parsed = parse_openai_output(
                response,
                provider_name=self.name,
                model_name=self.model,
            )
            decision = build_workflow_decision(
                request_id=self._build_request_id(submission),
                parsed=parsed,
                prompt_version=prompt.prompt_version,
            )
            metadata = decision.processing_metadata.model_copy(
                update={
                    "provider_name": self.name,
                    "model_name": parsed.processing_metadata.model_name or self.model,
                    "latency_ms": parsed.processing_metadata.latency_ms
                    or self._elapsed_ms(started_at),
                }
            )
            return ProviderResponse(
                decision=decision.model_copy(
                    update={"processing_metadata": metadata}
                ),
                raw_payload=self._build_success_payload(
                    prompt_version=prompt.prompt_version,
                    response=response,
                    parsed_output=parsed.analysis.model_dump(mode="json"),
                    token_usage=metadata.token_usage,
                    latency_ms=metadata.latency_ms,
                ),
            )
        except OpenAIResponseParseError as exc:
            logger.warning("OpenAI structured parsing failed; using fallback: %s", exc)
            return self._fallback_or_raise(
                submission,
                reason="malformed_output",
                prompt=prompt.messages,
                error=exc,
            )
        except (ProviderResponseError, ProviderUnavailableError):
            raise
        except Exception as exc:
            logger.warning("OpenAI request failed; using fallback: %s", exc)
            return self._fallback_or_raise(
                submission,
                reason="openai_request_failed",
                prompt=prompt.messages,
                error=exc,
            )

    def _fallback_or_raise(
        self,
        submission: IntakeSubmission,
        *,
        reason: str,
        prompt: list[dict[str, str]] | None,
        response: Any | None = None,
        error: Exception | None = None,
    ) -> ProviderResponse:
        if not self.allow_mock_fallback:
            exception_cls = (
                ProviderResponseError
                if reason in {"model_refusal", "malformed_output"}
                else ProviderUnavailableError
            )
            raise exception_cls(
                f"OpenAI provider failed without fallback: {reason}"
            ) from error

        fallback_response = self._fallback_provider.analyze(submission)
        fallback_provider_name = (
            fallback_response.decision.processing_metadata.provider_name
            or self._fallback_provider.name
        )
        fallback_metadata = fallback_response.decision.processing_metadata.model_copy(
            update={
                "provider_name": f"{self.name}->fallback:{fallback_provider_name}",
            }
        )
        return ProviderResponse(
            decision=fallback_response.decision.model_copy(
                update={"processing_metadata": fallback_metadata}
            ),
            raw_payload=self._build_fallback_payload(
                prompt=prompt,
                response=response,
                fallback_reason=reason,
                fallback_response=fallback_response,
                error=error,
            ),
        )

    def _build_success_payload(
        self,
        *,
        prompt_version: str,
        response: Any,
        parsed_output: dict[str, Any],
        token_usage: dict[str, int],
        latency_ms: int | None,
    ) -> dict[str, Any]:
        return self._prune_none(
            {
                "provider": self.name,
                "model": getattr(response, "model", self.model),
                "prompt_version": prompt_version,
                "response_id": getattr(response, "id", None),
                "parsed_output": parsed_output,
                "usage": token_usage,
                "latency_ms": latency_ms,
                "used_fallback": False,
            }
        )

    def _build_fallback_payload(
        self,
        *,
        prompt: list[dict[str, str]] | None,
        response: Any | None,
        fallback_reason: str,
        fallback_response: ProviderResponse,
        error: Exception | None,
    ) -> dict[str, Any]:
        return self._prune_none(
            {
                "provider": self.name,
                "model": self.model,
                "prompt_version": self.prompt_version,
                "prompt_count": len(prompt) if prompt else None,
                "response_id": getattr(response, "id", None) if response else None,
                "fallback_reason": fallback_reason,
                "fallback_provider": fallback_response.decision.processing_metadata.provider_name,
                "used_fallback": True,
                "error": str(error) if error else None,
            }
        )

    def _elapsed_ms(self, started_at: float) -> int:
        return max(int((perf_counter() - started_at) * 1000), 1)

    def _build_request_id(self, submission: IntakeSubmission) -> str:
        fingerprint = "|".join(
            [
                submission.message_text.strip().lower(),
                submission.sender_email.lower(),
                submission.company.strip().lower(),
                submission.received_at.isoformat(),
            ]
        )
        digest = sha1(fingerprint.encode("utf-8")).hexdigest()
        return f"openai-{digest[:12]}"

    def _prune_none(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}
