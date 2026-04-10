from __future__ import annotations

from hashlib import sha1
from time import perf_counter

from app.domain.enums import (
    CustomerTier,
    PriorityLevel,
    RecommendedAction,
    RecommendedTeam,
    RequestCategory,
    ReviewStatus,
)
from app.domain.schemas import (
    IntakeSubmission,
    ProcessingMetadata,
    ProviderResponse,
    WorkflowDecision,
)
from app.providers.base import AIProvider


class LocalMockProvider(AIProvider):
    """Deterministic local provider used for development and tests."""

    name = "mock-local"

    _BILLING_KEYWORDS = (
        "billing",
        "invoice",
        "charge",
        "charged",
        "refund",
        "payment",
        "subscription",
    )
    _ACCESS_KEYWORDS = (
        "login",
        "log in",
        "password",
        "locked",
        "mfa",
        "2fa",
        "access",
        "sign in",
    )
    _INCIDENT_KEYWORDS = (
        "incident",
        "outage",
        "down",
        "broken",
        "error",
        "failing",
        "bug",
        "degraded",
    )
    _FEATURE_KEYWORDS = (
        "feature",
        "enhancement",
        "roadmap",
        "request",
        "add",
        "would like",
    )
    _VENDOR_KEYWORDS = (
        "vendor",
        "procurement",
        "quote",
        "pricing",
        "contract",
        "nda",
        "security review",
    )
    _URGENT_KEYWORDS = (
        "urgent",
        "asap",
        "immediately",
        "critical",
        "sev",
        "severe",
        "production down",
    )

    def analyze(self, submission: IntakeSubmission) -> ProviderResponse:
        started_at = perf_counter()
        customer_tier = self._coerce_customer_tier(submission.customer_tier)
        normalized_text = self._normalize_text(submission)
        category = self._detect_category(normalized_text)
        priority = self._detect_priority(normalized_text, category, customer_tier)
        team = self._detect_team(category)
        action = self._detect_action(category, priority, normalized_text)
        missing_information = self._detect_missing_information(submission, category)
        confidence = self._score_confidence(
            category, priority, missing_information, normalized_text
        )
        request_id = self._build_request_id(submission)
        summary = self._build_summary(
            submission,
            category,
            priority,
            missing_information,
        )
        explanation = self._build_explanation(category, priority, team, action, confidence)

        decision = WorkflowDecision(
            request_id=request_id,
            category=category,
            priority=priority,
            summary=summary,
            recommended_team=team,
            recommended_action=action,
            missing_information=missing_information,
            confidence=confidence,
            explanation=explanation,
            review_status=ReviewStatus.PENDING,
            prompt_version="mock-local-v1",
            processing_metadata=ProcessingMetadata(
                provider_name=self.name,
                model_name="rule-based-mock",
                latency_ms=self._elapsed_ms(started_at),
                token_usage={"input": 0, "output": 0},
            ),
        )
        return ProviderResponse(
            decision=decision,
            raw_payload={
                "provider": self.name,
                "normalized_text": normalized_text,
                "signals": self._collect_signals(normalized_text),
                "category": category.value,
                "priority": priority.value,
                "team": team.value,
                "action": action.value,
                "confidence": confidence,
            },
        )

    def _normalize_text(self, submission: IntakeSubmission) -> str:
        parts = [
            submission.message_text,
            submission.urgency_hint or "",
        ]
        return " ".join(part.strip() for part in parts if part).lower()

    def _detect_category(self, text: str) -> RequestCategory:
        if self._contains_any(text, self._BILLING_KEYWORDS):
            return RequestCategory.BILLING_ISSUE
        if self._contains_any(text, self._ACCESS_KEYWORDS):
            return RequestCategory.ACCOUNT_ACCESS
        if self._contains_any(text, self._INCIDENT_KEYWORDS):
            return RequestCategory.INCIDENT_REPORT
        if self._contains_any(text, self._VENDOR_KEYWORDS):
            return RequestCategory.VENDOR_REQUEST
        if self._contains_any(text, self._FEATURE_KEYWORDS):
            return RequestCategory.FEATURE_REQUEST
        return RequestCategory.OTHER

    def _detect_priority(
        self,
        text: str,
        category: RequestCategory,
        customer_tier: CustomerTier,
    ) -> PriorityLevel:
        if self._contains_any(text, self._URGENT_KEYWORDS):
            return PriorityLevel.URGENT
        if category is RequestCategory.INCIDENT_REPORT:
            return (
                PriorityLevel.URGENT
                if customer_tier in {CustomerTier.ENTERPRISE, CustomerTier.PREMIUM}
                else PriorityLevel.HIGH
            )
        if category in {RequestCategory.ACCOUNT_ACCESS, RequestCategory.BILLING_ISSUE}:
            return (
                PriorityLevel.HIGH
                if customer_tier in {CustomerTier.ENTERPRISE, CustomerTier.PREMIUM}
                else PriorityLevel.MEDIUM
            )
        if category is RequestCategory.VENDOR_REQUEST:
            return PriorityLevel.MEDIUM
        if category is RequestCategory.FEATURE_REQUEST:
            return PriorityLevel.LOW
        return PriorityLevel.MEDIUM

    def _detect_team(self, category: RequestCategory) -> RecommendedTeam:
        mapping = {
            RequestCategory.BILLING_ISSUE: RecommendedTeam.BILLING,
            RequestCategory.ACCOUNT_ACCESS: RecommendedTeam.SUPPORT,
            RequestCategory.INCIDENT_REPORT: RecommendedTeam.ENGINEERING,
            RequestCategory.FEATURE_REQUEST: RecommendedTeam.ENGINEERING,
            RequestCategory.VENDOR_REQUEST: RecommendedTeam.OPERATIONS,
            RequestCategory.OTHER: RecommendedTeam.SUPPORT,
        }
        return mapping[category]

    def _detect_action(
        self, category: RequestCategory, priority: PriorityLevel, text: str
    ) -> RecommendedAction:
        if priority is PriorityLevel.URGENT:
            return RecommendedAction.ESCALATE
        if category is RequestCategory.OTHER:
            return RecommendedAction.REQUEST_MORE_INFO
        if category is RequestCategory.FEATURE_REQUEST:
            return RecommendedAction.REVIEW_MANUALLY
        if self._contains_any(
            text,
            ("need more info", "unclear", "not enough details", "missing"),
        ):
            return RecommendedAction.REQUEST_MORE_INFO
        return RecommendedAction.ROUTE_TO_TEAM

    def _detect_missing_information(
        self, submission: IntakeSubmission, category: RequestCategory
    ) -> list[str]:
        message = submission.message_text.lower()
        missing: list[str] = []
        if category is RequestCategory.ACCOUNT_ACCESS and not self._contains_any(
            message, ("workspace", "account", "email", "username", "user")
        ):
            missing.append("affected account or username")
        if category is RequestCategory.BILLING_ISSUE and not self._contains_any(
            message, ("invoice", "amount", "charge", "payment", "subscription")
        ):
            missing.append("invoice or charge reference")
        if category is RequestCategory.INCIDENT_REPORT and not self._contains_any(
            message, ("error", "screenshots", "steps", "timestamp", "environment")
        ):
            missing.append("error details or reproduction steps")
        if category is RequestCategory.OTHER:
            missing.append("business context")
        return missing

    def _score_confidence(
        self,
        category: RequestCategory,
        priority: PriorityLevel,
        missing_information: list[str],
        text: str,
    ) -> float:
        score = 0.55
        if category is not RequestCategory.OTHER:
            score += 0.2
        if priority in {PriorityLevel.HIGH, PriorityLevel.URGENT}:
            score += 0.1
        if not missing_information:
            score += 0.1
        if self._contains_any(text, self._URGENT_KEYWORDS):
            score += 0.05
        return round(min(score, 0.98), 2)

    def _build_request_id(self, submission: IntakeSubmission) -> str:
        fingerprint = "|".join(
            [
                submission.message_text.strip().lower(),
                submission.sender_email.lower(),
                submission.company.strip().lower(),
                submission.received_at.isoformat(),
            ]
        )
        return f"mock-{sha1(fingerprint.encode('utf-8')).hexdigest()[:12]}"

    def _build_summary(
        self,
        submission: IntakeSubmission,
        category: RequestCategory,
        priority: PriorityLevel,
        missing_information: list[str],
    ) -> str:
        base = f"{category.value.replace('_', ' ')} triage for {submission.company}"
        if missing_information:
            base = f"{base} with {len(missing_information)} missing detail(s)"
        return f"{base} marked {priority.value}"

    def _build_explanation(
        self,
        category: RequestCategory,
        priority: PriorityLevel,
        team: RecommendedTeam,
        action: RecommendedAction,
        confidence: float,
    ) -> str:
        return (
            f"Classified as {category.value.replace('_', ' ')} with {priority.value} priority, "
            f"routed to {team.value}, and set to {action.value}. "
            f"Confidence score: {confidence:.2f}."
        )

    def _collect_signals(self, text: str) -> dict[str, bool]:
        return {
            "billing_signal": self._contains_any(text, self._BILLING_KEYWORDS),
            "access_signal": self._contains_any(text, self._ACCESS_KEYWORDS),
            "incident_signal": self._contains_any(text, self._INCIDENT_KEYWORDS),
            "feature_signal": self._contains_any(text, self._FEATURE_KEYWORDS),
            "vendor_signal": self._contains_any(text, self._VENDOR_KEYWORDS),
            "urgent_signal": self._contains_any(text, self._URGENT_KEYWORDS),
        }

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _elapsed_ms(self, started_at: float) -> int:
        return max(int((perf_counter() - started_at) * 1000), 1)

    def _coerce_customer_tier(self, value: CustomerTier | str) -> CustomerTier:
        return value if isinstance(value, CustomerTier) else CustomerTier(str(value))
