from collections.abc import Generator
from typing import Protocol

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.schemas import (
    IntakeSubmission,
    QueueResponse,
    RequestDetail,
    ReviewUpdate,
    WorkflowDecision,
)
from app.services.workflow import WorkflowService


class WorkflowServiceProtocol(Protocol):
    def submit_request(self, submission: IntakeSubmission) -> WorkflowDecision: ...

    def get_request_detail(self, request_id: str) -> RequestDetail: ...

    def list_queue(self, limit: int = 50) -> QueueResponse: ...

    def apply_review_update(
        self,
        request_id: str,
        update: ReviewUpdate,
    ) -> RequestDetail: ...


def get_workflow_service(
    db: Session = Depends(get_db),
) -> Generator[WorkflowServiceProtocol, None, None]:
    yield WorkflowService(session=db)
