from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import WorkflowServiceProtocol, get_workflow_service
from app.domain.schemas import (
    IntakeSubmission,
    QueueResponse,
    RequestDetail,
    ReviewUpdate,
    WorkflowDecision,
)
from app.services.errors import (
    RequestNotFoundError,
    WorkflowProviderResponseError,
    WorkflowProviderUnavailableError,
)

router = APIRouter(tags=["requests"])


@router.post("/requests", response_model=WorkflowDecision)
def submit_request(
    submission: IntakeSubmission,
    service: WorkflowServiceProtocol = Depends(get_workflow_service),
) -> WorkflowDecision:
    try:
        return service.submit_request(submission)
    except WorkflowProviderResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except WorkflowProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/requests/{request_id}", response_model=RequestDetail)
def get_request_detail(
    request_id: str,
    service: WorkflowServiceProtocol = Depends(get_workflow_service),
) -> RequestDetail:
    try:
        return service.get_request_detail(request_id)
    except RequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/queue", response_model=QueueResponse)
def list_queue(
    limit: int = Query(default=50, ge=1, le=100),
    service: WorkflowServiceProtocol = Depends(get_workflow_service),
) -> QueueResponse:
    return service.list_queue(limit=limit)


@router.post("/requests/{request_id}/review", response_model=RequestDetail)
def apply_review_update(
    request_id: str,
    update: ReviewUpdate,
    service: WorkflowServiceProtocol = Depends(get_workflow_service),
) -> RequestDetail:
    try:
        return service.apply_review_update(request_id, update)
    except RequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
