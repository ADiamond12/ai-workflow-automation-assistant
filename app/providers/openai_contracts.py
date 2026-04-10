from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    PriorityLevel,
    RecommendedAction,
    RecommendedTeam,
    RequestCategory,
)


class OpenAIWorkflowAnalysis(BaseModel):
    """Structured output schema expected from the OpenAI model."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    category: RequestCategory
    priority: PriorityLevel
    summary: str = Field(min_length=1, max_length=2000)
    recommended_team: RecommendedTeam
    recommended_action: RecommendedAction
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=1, max_length=2000)
