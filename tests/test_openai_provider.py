from __future__ import annotations

from types import SimpleNamespace

from app.domain.enums import (
    PriorityLevel,
    RecommendedAction,
    RecommendedTeam,
    RequestCategory,
)
from app.domain.schemas import (
    IntakeSubmission,
    ProcessingMetadata,
    ProviderResponse,
    WorkflowDecision,
)
from app.providers.factory import get_provider
from app.providers.openai_adapter import OpenAIProvider
from app.providers.openai_contracts import OpenAIWorkflowAnalysis


def _build_submission() -> IntakeSubmission:
    return IntakeSubmission(
        message_text="The enterprise invoice was charged twice and needs review.",
        sender_name="Alex Morgan",
        sender_email="alex@example.com",
        company="Northwind Labs",
        channel="email",
        customer_tier="enterprise",
        received_at="2026-03-26T10:00:00Z",
        urgency_hint="urgent follow-up requested",
    )


def _build_analysis() -> OpenAIWorkflowAnalysis:
    return OpenAIWorkflowAnalysis(
        category=RequestCategory.BILLING_ISSUE,
        priority=PriorityLevel.URGENT,
        summary="Billing issue triaged with high confidence.",
        recommended_team=RecommendedTeam.BILLING,
        recommended_action=RecommendedAction.ROUTE_TO_TEAM,
        missing_information=[],
        confidence=0.93,
        explanation="Matched billing and urgency signals from the request body.",
    )


def _build_fallback_response() -> ProviderResponse:
    return ProviderResponse(
        decision=WorkflowDecision(
            request_id="fallback-1",
            category=RequestCategory.BILLING_ISSUE,
            priority=PriorityLevel.HIGH,
            summary="Fallback triage summary",
            recommended_team=RecommendedTeam.BILLING,
            recommended_action=RecommendedAction.ROUTE_TO_TEAM,
            missing_information=[],
            confidence=0.74,
            explanation="Fallback provider handled malformed or refused output.",
            prompt_version="fallback-test",
            processing_metadata=ProcessingMetadata(
                provider_name="mock-local",
                model_name="rule-based-mock",
                latency_ms=7,
                token_usage={"input": 0, "output": 0},
            ),
        ),
        raw_payload={"fallback": True},
    )


class _FakeResponses:
    def __init__(self, response: object):
        self.response = response
        self.calls: list[dict[str, object]] = []

    def parse(self, *args: object, **kwargs: object) -> object:
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.response


class _FakeOpenAIClient:
    def __init__(self, response: object) -> None:
        self.responses = _FakeResponses(response)


class _FakeFallbackProvider:
    name = "mock-local"

    def analyze(self, submission: IntakeSubmission) -> ProviderResponse:
        return _build_fallback_response()


def test_get_provider_openai_mode_returns_openai_provider() -> None:
    provider = get_provider("openai")

    assert isinstance(provider, OpenAIProvider)


def test_openai_provider_uses_structured_output_and_prompt_bundle() -> None:
    fake_response = SimpleNamespace(
        output_parsed=_build_analysis(),
        output_text=None,
        output=[],
        usage=SimpleNamespace(input_tokens=128, output_tokens=42, total_tokens=170),
        model="gpt-4.1-mini",
        id="resp-1",
    )
    fake_client = _FakeOpenAIClient(response=fake_response)

    provider = OpenAIProvider(
        client=fake_client,
        fallback_provider=_FakeFallbackProvider(),
        allow_mock_fallback=True,
    )
    result = provider.analyze(_build_submission())

    assert result.decision.category == RequestCategory.BILLING_ISSUE
    assert result.decision.priority == PriorityLevel.URGENT
    assert result.decision.recommended_team == RecommendedTeam.BILLING
    assert result.decision.recommended_action == RecommendedAction.ROUTE_TO_TEAM
    assert result.decision.processing_metadata.provider_name == "openai"
    assert result.decision.processing_metadata.model_name == "gpt-4.1-mini"
    assert result.decision.prompt_version == "openai-workflow-v1"
    assert result.raw_payload["provider"] == "openai"
    assert result.raw_payload["used_fallback"] is False
    assert result.raw_payload["response_id"] == "resp-1"
    assert result.raw_payload["parsed_output"]["recommended_action"] == "route_to_team"
    assert "prompt" not in result.raw_payload

    call = fake_client.responses.calls[0]
    assert call["kwargs"]["text_format"] is OpenAIWorkflowAnalysis
    prompt = call["kwargs"]["input"]
    assert prompt[0]["role"] == "system"
    assert prompt[1]["role"] == "user"
    assert "The enterprise invoice was charged twice and needs review." in prompt[1]["content"]
    assert "urgent follow-up requested" in prompt[1]["content"]
    assert call["kwargs"]["model"] == "gpt-4.1-mini"
    assert call["kwargs"]["store"] is False


def test_openai_provider_falls_back_when_output_is_malformed() -> None:
    fake_response = SimpleNamespace(
        output_parsed=None,
        output_text="{not-json}",
        output=[],
        usage=SimpleNamespace(input_tokens=64, output_tokens=0, total_tokens=64),
        model="gpt-4.1-mini",
        id="resp-malformed",
    )
    fake_client = _FakeOpenAIClient(response=fake_response)

    provider = OpenAIProvider(
        client=fake_client,
        fallback_provider=_FakeFallbackProvider(),
        allow_mock_fallback=True,
    )
    result = provider.analyze(_build_submission())

    assert result.decision.summary == "Fallback triage summary"
    assert result.decision.processing_metadata.provider_name == "openai->fallback:mock-local"
    assert result.raw_payload["provider"] == "openai"
    assert result.raw_payload["used_fallback"] is True
    assert result.raw_payload["fallback_reason"] == "malformed_output"
    assert result.raw_payload["fallback_provider"] == "mock-local"
    assert "fallback_payload" not in result.raw_payload


def test_openai_provider_falls_back_when_model_refuses() -> None:
    fake_response = SimpleNamespace(
        output_parsed=None,
        output_text="I cannot comply with this request.",
        output=[
            SimpleNamespace(
                content=[SimpleNamespace(refusal="safety refusal")],
            )
        ],
        usage=SimpleNamespace(input_tokens=64, output_tokens=0, total_tokens=64),
        model="gpt-4.1-mini",
        id="resp-refusal",
    )
    fake_client = _FakeOpenAIClient(response=fake_response)

    provider = OpenAIProvider(
        client=fake_client,
        fallback_provider=_FakeFallbackProvider(),
        allow_mock_fallback=True,
    )
    result = provider.analyze(_build_submission())

    assert result.decision.category == RequestCategory.BILLING_ISSUE
    assert result.decision.priority == PriorityLevel.HIGH
    assert result.decision.processing_metadata.provider_name == "openai->fallback:mock-local"
    assert result.raw_payload["provider"] == "openai"
    assert result.raw_payload["used_fallback"] is True
    assert result.raw_payload["fallback_reason"] == "model_refusal"
