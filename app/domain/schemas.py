from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.enums import (
    CustomerTier,
    IntakeChannel,
    PriorityLevel,
    RecommendedAction,
    RecommendedTeam,
    RequestCategory,
    ReviewStatus,
)
from app.domain.normalization import (
    clamp_float,
    normalize_optional_text,
    normalize_text_list,
    normalize_token_usage,
    normalize_whitespace,
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


class IntakeSubmission(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    message_text: str = Field(min_length=1, max_length=12000)
    sender_name: str = Field(min_length=1, max_length=200)
    sender_email: EmailStr
    company: str = Field(min_length=1, max_length=200)
    channel: IntakeChannel
    customer_tier: CustomerTier
    received_at: datetime
    urgency_hint: str | None = Field(default=None, max_length=300)

    @field_validator("message_text", "sender_name", "company")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = normalize_whitespace(value)
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized

    @field_validator("urgency_hint")
    @classmethod
    def _normalize_urgency_hint(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class ProcessingMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str | None = None
    model_name: str | None = None
    latency_ms: int | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)

    @field_validator("provider_name", "model_name")
    @classmethod
    def _normalize_optional_label(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("latency_ms")
    @classmethod
    def _validate_latency_ms(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 0:
            raise ValueError("latency_ms must be non-negative")
        return value

    @field_validator("token_usage")
    @classmethod
    def _normalize_token_usage(cls, value: dict[str, Any]) -> dict[str, int]:
        return normalize_token_usage(value)


class WorkflowDecision(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
        extra="forbid",
    )

    request_id: str
    category: RequestCategory
    priority: PriorityLevel
    summary: str = Field(min_length=1, max_length=2000)
    recommended_team: RecommendedTeam
    recommended_action: RecommendedAction
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=1, max_length=2000)
    review_status: ReviewStatus = ReviewStatus.PENDING
    prompt_version: str | None = None
    processing_metadata: ProcessingMetadata = Field(default_factory=ProcessingMetadata)

    @field_validator("summary", "explanation")
    @classmethod
    def _normalize_decision_text(cls, value: str) -> str:
        normalized = normalize_whitespace(value)
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized

    @field_validator("missing_information")
    @classmethod
    def _normalize_missing_information(cls, value: list[str]) -> list[str]:
        return normalize_text_list(value)

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return clamp_float(value)


class ReviewUpdate(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
        extra="forbid",
    )

    review_status: ReviewStatus
    category: RequestCategory | None = None
    priority: PriorityLevel | None = None
    recommended_team: RecommendedTeam | None = None
    recommended_action: RecommendedAction | None = None
    reviewer_name: str | None = Field(default=None, max_length=120)
    reviewer_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("reviewer_name")
    @classmethod
    def _normalize_reviewer_name(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("reviewer_notes")
    @classmethod
    def _normalize_reviewer_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class ProviderResponse(BaseModel):
    decision: WorkflowDecision
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class QueueItem(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    request_id: str
    sender_name: str
    company: str
    summary: str
    category: RequestCategory
    priority: PriorityLevel
    review_status: ReviewStatus
    confidence: float
    recommended_team: RecommendedTeam
    received_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QueueResponse(BaseModel):
    items: list[QueueItem] = Field(default_factory=list)
    total: int = 0


class ReviewEvent(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    review_status: ReviewStatus
    reviewer_name: str | None = None
    reviewer_notes: str | None = None
    edited_fields: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class RequestDetail(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    request_id: str
    submission: IntakeSubmission
    decision: WorkflowDecision | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime | None = None
    updated_at: datetime | None = None
    queue_position: int | None = None
    reviews: list[ReviewEvent] = Field(default_factory=list)
