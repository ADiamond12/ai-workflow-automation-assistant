from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import joinedload

from app.domain.enums import ReviewStatus
from app.domain.schemas import IntakeSubmission, ReviewUpdate, WorkflowDecision
from app.repositories.base import Repository
from app.repositories.models import DecisionRecord, RequestRecord, ReviewRecord


@dataclass(slots=True)
class QueueItem:
    request: RequestRecord
    decision: DecisionRecord | None
    review: ReviewRecord | None


@dataclass(slots=True)
class RequestAggregate:
    request: RequestRecord
    decision: DecisionRecord | None
    review: ReviewRecord | None


class RequestRepository(Repository):
    def create_request(self, submission: IntakeSubmission) -> RequestRecord:
        request = RequestRecord(
            message_text=submission.message_text,
            sender_name=submission.sender_name,
            sender_email=str(submission.sender_email),
            company=submission.company,
            channel=submission.channel,
            customer_tier=submission.customer_tier,
            received_at=submission.received_at,
            urgency_hint=submission.urgency_hint,
        )
        self.session.add(request)
        self.session.flush()
        return request

    def get_by_id(self, request_id: str) -> RequestAggregate | None:
        stmt: Select[tuple[RequestRecord]] = (
            select(RequestRecord)
            .options(
                joinedload(RequestRecord.decisions),
                joinedload(RequestRecord.reviews),
            )
            .where(RequestRecord.id == request_id)
        )
        request = self.session.execute(stmt).unique().scalar_one_or_none()
        if request is None:
            return None

        decision = self._latest_decision(request)
        review = self._latest_review(request)
        return RequestAggregate(request=request, decision=decision, review=review)

    def list_queue(self, limit: int | None = 50) -> list[QueueItem]:
        stmt: Select[tuple[RequestRecord]] = (
            select(RequestRecord)
            .options(
                joinedload(RequestRecord.decisions),
                joinedload(RequestRecord.reviews),
            )
            .order_by(desc(RequestRecord.created_at))
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        requests = self.session.execute(stmt).unique().scalars().all()
        queue: list[QueueItem] = []
        for request in requests:
            decision = self._latest_decision(request)
            review = self._latest_review(request)
            if self._current_review_status(decision, review) == ReviewStatus.PENDING:
                queue.append(QueueItem(request=request, decision=decision, review=review))
        return queue

    def get_queue_position(self, request_id: str) -> int | None:
        queue = self.list_queue(limit=None)
        for index, item in enumerate(queue, start=1):
            if item.request.id == request_id:
                return index
        return None

    def _latest_decision(self, request: RequestRecord) -> DecisionRecord | None:
        if not request.decisions:
            return None
        return max(request.decisions, key=lambda decision: decision.created_at)

    def _latest_review(self, request: RequestRecord) -> ReviewRecord | None:
        if not request.reviews:
            return None
        return max(request.reviews, key=lambda review: review.created_at)

    def _current_review_status(
        self,
        decision: DecisionRecord | None,
        review: ReviewRecord | None,
    ) -> ReviewStatus:
        if review is not None:
            return review.review_status
        if decision is not None:
            return decision.review_status
        return ReviewStatus.PENDING


class DecisionRepository(Repository):
    def create_decision(
        self, request_id: str, decision: WorkflowDecision, raw_payload: dict
    ) -> DecisionRecord:
        record = DecisionRecord(
            request_id=request_id,
            category=decision.category,
            priority=decision.priority,
            summary=decision.summary,
            recommended_team=decision.recommended_team,
            recommended_action=decision.recommended_action,
            missing_information=list(decision.missing_information),
            confidence=decision.confidence,
            explanation=decision.explanation,
            review_status=decision.review_status,
            prompt_version=decision.prompt_version,
            provider_name=decision.processing_metadata.provider_name,
            model_name=decision.processing_metadata.model_name,
            latency_ms=decision.processing_metadata.latency_ms,
            token_usage=dict(decision.processing_metadata.token_usage),
            raw_payload=raw_payload,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def update_review_status(
        self, decision_id: str, review_status: ReviewStatus
    ) -> DecisionRecord | None:
        decision = self.session.get(DecisionRecord, decision_id)
        if decision is None:
            return None
        decision.review_status = review_status
        self.session.flush()
        return decision

    def apply_review_edits(
        self,
        decision_id: str,
        update: ReviewUpdate,
    ) -> tuple[DecisionRecord | None, dict[str, str]]:
        decision = self.session.get(DecisionRecord, decision_id)
        if decision is None:
            return None, {}

        edited_fields: dict[str, str] = {}
        editable_fields = (
            "category",
            "priority",
            "recommended_team",
            "recommended_action",
        )
        for field_name in editable_fields:
            value = getattr(update, field_name)
            if value is None or getattr(decision, field_name) == value:
                continue
            setattr(decision, field_name, value)
            edited_fields[field_name] = (
                value.value if isinstance(value, Enum) else str(value)
            )

        decision.review_status = update.review_status
        self.session.flush()
        return decision, edited_fields


class ReviewRepository(Repository):
    def create_review(
        self,
        request_id: str,
        review_status: ReviewStatus,
        decision_id: str | None = None,
        reviewer_name: str | None = None,
        reviewer_notes: str | None = None,
        edited_fields: dict | None = None,
    ) -> ReviewRecord:
        record = ReviewRecord(
            request_id=request_id,
            decision_id=decision_id,
            review_status=review_status,
            reviewer_name=reviewer_name,
            reviewer_notes=reviewer_notes,
            edited_fields=edited_fields or {},
        )
        self.session.add(record)
        self.session.flush()
        return record

    def apply_review_update(
        self,
        request_id: str,
        decision_id: str | None,
        update: ReviewUpdate,
        edited_fields: dict | None = None,
    ) -> ReviewRecord:
        return self.create_review(
            request_id=request_id,
            decision_id=decision_id,
            review_status=update.review_status,
            reviewer_name=update.reviewer_name,
            reviewer_notes=update.reviewer_notes,
            edited_fields=edited_fields or {},
        )
