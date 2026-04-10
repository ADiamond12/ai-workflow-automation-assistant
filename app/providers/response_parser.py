from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.domain.enums import ReviewStatus
from app.domain.schemas import ProcessingMetadata, ProviderResponse, WorkflowDecision
from app.providers.openai_contracts import OpenAIWorkflowAnalysis


class OpenAIResponseParseError(ValueError):
    """Raised when a structured OpenAI response cannot be parsed safely."""


@dataclass(slots=True)
class OpenAIParsedOutput:
    analysis: OpenAIWorkflowAnalysis
    raw_text: str | None
    raw_payload: dict[str, Any]
    processing_metadata: ProcessingMetadata


def parse_openai_output(
    payload: Any,
    *,
    provider_name: str = "openai",
    model_name: str | None = None,
) -> OpenAIParsedOutput:
    raw_payload = _normalize_payload(payload)
    raw_text = extract_output_text(payload)
    parsed_payload = _extract_parsed_payload(payload)
    parsed_model = _parse_analysis_model(parsed_payload, raw_text=raw_text)
    processing_metadata = build_processing_metadata(
        payload,
        provider_name=provider_name,
        model_name=model_name,
    )
    return OpenAIParsedOutput(
        analysis=parsed_model,
        raw_text=raw_text,
        raw_payload=raw_payload,
        processing_metadata=processing_metadata,
    )


def build_workflow_decision(
    request_id: str,
    parsed: OpenAIParsedOutput,
    *,
    prompt_version: str | None = None,
) -> WorkflowDecision:
    return WorkflowDecision(
        request_id=request_id,
        category=parsed.analysis.category,
        priority=parsed.analysis.priority,
        summary=parsed.analysis.summary,
        recommended_team=parsed.analysis.recommended_team,
        recommended_action=parsed.analysis.recommended_action,
        missing_information=parsed.analysis.missing_information,
        confidence=parsed.analysis.confidence,
        explanation=parsed.analysis.explanation,
        review_status=ReviewStatus.PENDING,
        prompt_version=prompt_version,
        processing_metadata=parsed.processing_metadata,
    )


def build_provider_response(
    request_id: str,
    parsed: OpenAIParsedOutput,
    *,
    prompt_version: str | None = None,
) -> ProviderResponse:
    return ProviderResponse(
        decision=build_workflow_decision(
            request_id=request_id,
            parsed=parsed,
            prompt_version=prompt_version,
        ),
        raw_payload=parsed.raw_payload,
    )


def extract_output_text(payload: Any) -> str | None:
    if payload is None:
        return None
    if isinstance(payload, str):
        return payload
    if isinstance(payload, Mapping):
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        if isinstance(payload.get("text"), str):
            return payload["text"]
    output_text = getattr(payload, "output_text", None)
    if isinstance(output_text, str):
        return output_text
    text = getattr(payload, "text", None)
    if isinstance(text, str):
        return text

    output_items = getattr(payload, "output", None)
    if output_items is None and isinstance(payload, Mapping):
        output_items = payload.get("output")
    if not output_items:
        return None

    chunks: list[str] = []
    for item in output_items:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, Mapping):
            content = item.get("content")
        if not content:
            continue
        for part in content:
            part_text = getattr(part, "text", None)
            if part_text is None and isinstance(part, Mapping):
                part_text = part.get("text")
            if isinstance(part_text, str):
                chunks.append(part_text)
    joined = "".join(chunks).strip()
    return joined or None


def extract_refusal_text(payload: Any) -> str | None:
    refusal = getattr(payload, "refusal", None)
    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip()
    if isinstance(payload, Mapping):
        raw_refusal = payload.get("refusal")
        if isinstance(raw_refusal, str) and raw_refusal.strip():
            return raw_refusal.strip()

    output_items = getattr(payload, "output", None)
    if output_items is None and isinstance(payload, Mapping):
        output_items = payload.get("output")
    if not output_items:
        return None

    for item in output_items:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, Mapping):
            content = item.get("content")
        if not content:
            continue
        for part in content:
            part_refusal = getattr(part, "refusal", None)
            if part_refusal is None and isinstance(part, Mapping):
                part_refusal = part.get("refusal")
            if isinstance(part_refusal, str) and part_refusal.strip():
                return part_refusal.strip()
    return None


def build_processing_metadata(
    payload: Any,
    *,
    provider_name: str = "openai",
    model_name: str | None = None,
) -> ProcessingMetadata:
    usage = _extract_usage(payload)
    latency_ms = _extract_latency_ms(payload)
    response_model = model_name or _extract_model_name(payload)
    return ProcessingMetadata(
        provider_name=provider_name,
        model_name=response_model,
        latency_ms=latency_ms,
        token_usage=usage,
    )


def _parse_analysis_model(
    payload: dict[str, Any],
    *,
    raw_text: str | None,
) -> OpenAIWorkflowAnalysis:
    candidates: list[Any] = [payload]
    if raw_text:
        candidates.append(_json_from_text(raw_text))
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return OpenAIWorkflowAnalysis.model_validate(candidate)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise OpenAIResponseParseError(
        "Unable to parse OpenAI structured output into workflow analysis."
    ) from last_error


def _extract_parsed_payload(payload: Any) -> dict[str, Any]:
    output_parsed = getattr(payload, "output_parsed", None)
    if output_parsed is None and isinstance(payload, Mapping):
        output_parsed = payload.get("output_parsed")

    if output_parsed is None:
        if isinstance(payload, Mapping):
            return dict(payload)
        if hasattr(payload, "model_dump"):
            return payload.model_dump()
        if hasattr(payload, "dict"):
            return payload.dict()
        return {}

    if isinstance(output_parsed, Mapping):
        return dict(output_parsed)
    if hasattr(output_parsed, "model_dump"):
        return output_parsed.model_dump()
    if hasattr(output_parsed, "dict"):
        return output_parsed.dict()
    return {"value": output_parsed}


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if hasattr(payload, "dict"):
        return payload.dict()
    return {
        "value": payload,
    }


def _json_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseParseError("OpenAI response text is not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise OpenAIResponseParseError("OpenAI structured output must be a JSON object.")
    return parsed


def _extract_usage(payload: Any) -> dict[str, int]:
    usage = getattr(payload, "usage", None)
    if usage is None and isinstance(payload, Mapping):
        usage = payload.get("usage")
    if usage is None:
        return {}

    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    elif hasattr(usage, "dict"):
        usage = usage.dict()
    elif not isinstance(usage, Mapping):
        usage = {
            key: getattr(usage, key, None)
            for key in ("input_tokens", "output_tokens", "total_tokens")
        }

    if not isinstance(usage, Mapping):
        return {}

    normalized: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if value is None:
            continue
        try:
            normalized[key] = int(value)
        except (TypeError, ValueError):
            continue
    return normalized


def _extract_latency_ms(payload: Any) -> int | None:
    latency = getattr(payload, "latency_ms", None)
    if latency is None and isinstance(payload, Mapping):
        latency = payload.get("latency_ms")
    if latency is None:
        return None
    try:
        return max(int(latency), 0)
    except (TypeError, ValueError):
        return None


def _extract_model_name(payload: Any) -> str | None:
    model = getattr(payload, "model", None)
    if isinstance(model, str) and model.strip():
        return model.strip()
    if isinstance(payload, Mapping):
        raw_model = payload.get("model")
        if isinstance(raw_model, str) and raw_model.strip():
            return raw_model.strip()
    return None
