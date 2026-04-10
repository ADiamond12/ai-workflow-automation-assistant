from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.enums import (
    PriorityLevel,
    RecommendedAction,
    RecommendedTeam,
    RequestCategory,
)
from app.providers.openai_contracts import OpenAIWorkflowAnalysis
from app.providers.response_parser import (
    OpenAIResponseParseError,
    build_provider_response,
    build_workflow_decision,
    extract_refusal_text,
    parse_openai_output,
)


def test_parse_openai_output_handles_output_parsed_payload() -> None:
    payload = SimpleNamespace(
        output_parsed=OpenAIWorkflowAnalysis(
            category=RequestCategory.BILLING_ISSUE,
            priority=PriorityLevel.URGENT,
            summary="Invoice review required.",
            recommended_team=RecommendedTeam.BILLING,
            recommended_action=RecommendedAction.ROUTE_TO_TEAM,
            missing_information=["invoice_id"],
            confidence=0.91,
            explanation="Billing and urgency signals are strong.",
        ),
        usage=SimpleNamespace(input_tokens=84, output_tokens=22, total_tokens=106),
        model="gpt-4.1-mini",
    )

    parsed = parse_openai_output(payload, model_name="gpt-4.1-mini")

    assert parsed.analysis.category == RequestCategory.BILLING_ISSUE
    assert parsed.analysis.priority == PriorityLevel.URGENT
    assert parsed.analysis.recommended_team == RecommendedTeam.BILLING
    assert parsed.analysis.recommended_action == RecommendedAction.ROUTE_TO_TEAM
    assert parsed.processing_metadata.provider_name == "openai"
    assert parsed.processing_metadata.model_name == "gpt-4.1-mini"
    assert parsed.processing_metadata.token_usage == {
        "input_tokens": 84,
        "output_tokens": 22,
        "total_tokens": 106,
    }

    decision = build_workflow_decision(
        "request-1",
        parsed,
        prompt_version="openai-workflow-v1",
    )
    provider_response = build_provider_response(
        "request-1",
        parsed,
        prompt_version="openai-workflow-v1",
    )

    assert decision.request_id == "request-1"
    assert provider_response.decision.request_id == "request-1"


def test_parse_openai_output_handles_structured_json_text() -> None:
    payload = {
        "output_text": (
            "```json\n"
            "{\n"
            '  "category": "billing_issue",\n'
            '  "priority": "urgent",\n'
            '  "summary": "Invoice review required.",\n'
            '  "recommended_team": "billing",\n'
            '  "recommended_action": "route_to_team",\n'
            '  "missing_information": ["invoice_id"],\n'
            '  "confidence": 0.91,\n'
            '  "explanation": "Billing and urgency signals are strong."\n'
            "}\n"
            "```"
        ),
        "usage": {
            "input_tokens": 84,
            "output_tokens": 22,
            "total_tokens": 106,
        },
        "model": "gpt-4.1-mini",
        "latency_ms": 17,
    }

    parsed = parse_openai_output(payload, model_name="gpt-4.1-mini")

    assert parsed.raw_text.startswith("```json")
    assert parsed.raw_payload["model"] == "gpt-4.1-mini"
    assert parsed.analysis.category == RequestCategory.BILLING_ISSUE
    assert parsed.analysis.priority == PriorityLevel.URGENT
    assert parsed.processing_metadata.latency_ms == 17


def test_parse_openai_output_raises_for_malformed_json_text() -> None:
    payload = {
        "output_text": "{not-json}",
        "usage": {"input_tokens": 10, "output_tokens": 0},
        "model": "gpt-4.1-mini",
    }

    with pytest.raises(OpenAIResponseParseError):
        parse_openai_output(payload)


def test_parse_openai_output_raises_for_invalid_schema_payload() -> None:
    payload = {
        "output_text": (
            '{"category":"billing_issue","priority":"urgent","summary":"ok",'
            '"recommended_team":"billing","recommended_action":"route_to_team",'
            '"missing_information":[],"confidence":2.0,"explanation":"too high"}'
        ),
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "model": "gpt-4.1-mini",
    }

    with pytest.raises(OpenAIResponseParseError):
        parse_openai_output(payload)


def test_extract_refusal_text_reads_nested_response_shape() -> None:
    payload = SimpleNamespace(
        output=[
            SimpleNamespace(
                content=[SimpleNamespace(refusal="policy refusal")],
            )
        ]
    )

    assert extract_refusal_text(payload) == "policy refusal"
