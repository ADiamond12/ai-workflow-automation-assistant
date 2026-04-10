from typing import Protocol

from app.domain.schemas import IntakeSubmission, ProviderResponse


class AIProvider(Protocol):
    """Provider contract for workflow analysis backends."""

    name: str

    def analyze(self, submission: IntakeSubmission) -> ProviderResponse:
        """Return a structured workflow decision for the given submission."""
