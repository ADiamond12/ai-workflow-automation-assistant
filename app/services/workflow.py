from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.enums import ReviewStatus
from app.domain.schemas import (
    IntakeSubmission,
    ProcessingMetadata,
    QueueItem,
    QueueResponse,
    RequestDetail,
    ReviewEvent,
    ReviewUpdate,
    WorkflowDecision,
)
from app.providers import (
    AIProvider,
    ProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
    get_provider,
)
from app.repositories import (
    DecisionRecord,
    RequestAggregate,
    RequestRecord,
    RequestRepository,
    ReviewRecord,
    ReviewRepository,
)
from app.repositories.request_repository import DecisionRepository
from app.services.errors import (
    RequestNotFoundError,
    WorkflowProviderResponseError,
    WorkflowProviderUnavailableError,
)


class WorkflowService:
    """Happy-path workflow orchestration for intake submission and review queue reads."""

    def __init__(
        self,
        session: Session,
        provider: AIProvider | None = None,
    ) -> None:
        self.session = session
        self.request_repository = RequestRepository(session)
        self.decision_repository = DecisionRepository(session)
        self.review_repository = ReviewRepository(session)
        self.provider = provider or get_provider(get_settings().provider_mode)

    def submit_request(self, submission: IntakeSubmission) -> WorkflowDecision:
        try:
            request = self.request_repository.create_request(submission)
            provider_response = self.provider.analyze(submission)
            decision = provider_response.decision.model_copy(
                update={"request_id": request.id}
            )
            self.decision_repository.create_decision(
                request_id=request.id,
                decision=decision,
                raw_payload=provider_response.raw_payload,
            )
            self.session.commit()
            self.session.refresh(request)
            return decision
        except ProviderResponseError as exc:
            self.session.rollback()
            raise WorkflowProviderResponseError(str(exc)) from exc
        except ProviderUnavailableError as exc:
            self.session.rollback()
            raise WorkflowProviderUnavailableError(str(exc)) from exc
        except ProviderError as exc:
            self.session.rollback()
            raise WorkflowProviderUnavailableError(str(exc)) from exc
        except Exception:
            self.session.rollback()
            raise

    def get_request_detail(self, request_id: str) -> RequestDetail:
        aggregate = self.request_repository.get_by_id(request_id)
        if aggregate is None or aggregate.decision is None:
            raise RequestNotFoundError(f"Request '{request_id}' was not found.")
        return self._build_request_detail(aggregate)

    def list_queue(self, limit: int = 50) -> QueueResponse:
        items = self.request_repository.list_queue(limit=limit)
        queue_items = [
            self._build_queue_item(item.request, item.decision, item.review)
            for item in items
            if item.decision
        ]
        return QueueResponse(
            items=queue_items,
            total=len(queue_items),
        )

    def apply_review_update(
        self,
        request_id: str,
        update: ReviewUpdate,
    ) -> RequestDetail:
        aggregate = self.request_repository.get_by_id(request_id)
        if aggregate is None or aggregate.decision is None:
            raise RequestNotFoundError(f"Request '{request_id}' was not found.")

        decision = aggregate.decision
        edited_fields: dict[str, str] = {}

        if update.review_status == ReviewStatus.EDITED:
            decision, edited_fields = self.decision_repository.apply_review_edits(
                decision.id,
                update,
            )
        else:
            decision = self.decision_repository.update_review_status(
                decision.id,
                update.review_status,
            )

        if decision is None:
            self.session.rollback()
            raise RequestNotFoundError(f"Request '{request_id}' was not found.")

        self.review_repository.apply_review_update(
            request_id=request_id,
            decision_id=decision.id,
            update=update,
            edited_fields=edited_fields,
        )
        self.session.commit()
        self.session.expire_all()

        refreshed = self.request_repository.get_by_id(request_id)
        if refreshed is None or refreshed.decision is None:
            raise RequestNotFoundError(f"Request '{request_id}' was not found.")
        return self._build_request_detail(refreshed)

    def _build_request_detail(self, aggregate: RequestAggregate) -> RequestDetail:
        request = aggregate.request
        decision = aggregate.decision
        review = aggregate.review

        queue_position = self.request_repository.get_queue_position(request.id)
        return RequestDetail(
            request_id=request.id,
            submission=IntakeSubmission(
                message_text=request.message_text,
                sender_name=request.sender_name,
                sender_email=request.sender_email,
                company=request.company,
                channel=request.channel,
                customer_tier=request.customer_tier,
                received_at=request.received_at,
                urgency_hint=request.urgency_hint,
            ),
            decision=self._build_decision(request.id, decision) if decision else None,
            review_status=review.review_status
            if review
            else (decision.review_status if decision else ReviewStatus.PENDING),
            created_at=request.created_at,
            updated_at=request.updated_at,
            queue_position=queue_position,
            reviews=[
                self._build_review_event(item)
                for item in sorted(
                    request.reviews,
                    key=lambda review_item: review_item.created_at,
                    reverse=True,
                )
            ],
        )

    def _build_queue_item(
        self,
        request: RequestRecord,
        decision: DecisionRecord | None,
        review: ReviewRecord | None,
    ) -> QueueItem:
        if decision is None:
            raise RequestNotFoundError(
                f"Request '{request.id}' does not have a stored decision."
            )
        review_status = review.review_status if review else decision.review_status
        return QueueItem(
            request_id=request.id,
            sender_name=request.sender_name,
            company=request.company,
            summary=decision.summary,
            category=decision.category,
            priority=decision.priority,
            review_status=review_status,
            confidence=decision.confidence,
            recommended_team=decision.recommended_team,
            received_at=request.received_at,
            created_at=request.created_at,
            updated_at=request.updated_at,
        )

    def _build_decision(
        self,
        request_id: str,
        decision: DecisionRecord,
    ) -> WorkflowDecision:
        return WorkflowDecision(
            request_id=request_id,
            category=decision.category,
            priority=decision.priority,
            summary=decision.summary,
            recommended_team=decision.recommended_team,
            recommended_action=decision.recommended_action,
            missing_information=decision.missing_information,
            confidence=decision.confidence,
            explanation=decision.explanation,
            review_status=decision.review_status,
            prompt_version=decision.prompt_version,
            processing_metadata=ProcessingMetadata(
                provider_name=decision.provider_name,
                model_name=decision.model_name,
                latency_ms=decision.latency_ms,
                token_usage=decision.token_usage,
            ),
        )

    def _build_review_event(self, review: ReviewRecord) -> ReviewEvent:
        return ReviewEvent(
            review_status=review.review_status,
            reviewer_name=review.reviewer_name,
            reviewer_notes=review.reviewer_notes,
            edited_fields=review.edited_fields,
            created_at=review.created_at,
        )
