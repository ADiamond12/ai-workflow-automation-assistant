from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.api.deps import WorkflowServiceProtocol, get_workflow_service
from app.core.config import get_settings
from app.domain.enums import (
    PriorityLevel,
    RecommendedAction,
    RecommendedTeam,
    RequestCategory,
)
from app.domain.schemas import ReviewUpdate
from app.services.errors import RequestNotFoundError

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "api_prefix": settings.api_v1_prefix,
        },
    )


@router.get("/queue", response_class=HTMLResponse)
def queue_page(
    request: Request,
    service: WorkflowServiceProtocol = Depends(get_workflow_service),
) -> HTMLResponse:
    settings = get_settings()
    queue = service.list_queue(limit=50)
    return templates.TemplateResponse(
        request=request,
        name="queue.html",
        context={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "queue": queue,
        },
    )


@router.get("/requests/{request_id}", response_class=HTMLResponse)
def request_detail_page(
    request: Request,
    request_id: str,
    service: WorkflowServiceProtocol = Depends(get_workflow_service),
) -> HTMLResponse:
    settings = get_settings()
    try:
        detail = service.get_request_detail(request_id)
    except RequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return templates.TemplateResponse(
        request=request,
        name="request_detail.html",
        context={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "detail": detail,
            "review_status_options": ["approved", "edited"],
            "category_options": [item.value for item in RequestCategory],
            "priority_options": [item.value for item in PriorityLevel],
            "team_options": [item.value for item in RecommendedTeam],
            "action_options": [item.value for item in RecommendedAction],
            "updated": request.query_params.get("updated") == "1",
        },
    )


@router.post("/requests/{request_id}/review", response_class=HTMLResponse)
def submit_review_action(
    request: Request,
    request_id: str,
    review_status: str = Form(...),
    reviewer_name: str | None = Form(default=None),
    reviewer_notes: str | None = Form(default=None),
    category: str | None = Form(default=None),
    priority: str | None = Form(default=None),
    recommended_team: str | None = Form(default=None),
    recommended_action: str | None = Form(default=None),
    service: WorkflowServiceProtocol = Depends(get_workflow_service),
) -> RedirectResponse:
    try:
        update = ReviewUpdate(
            review_status=review_status,
            reviewer_name=_blank_to_none(reviewer_name),
            reviewer_notes=_blank_to_none(reviewer_notes),
            category=_blank_to_none(category),
            priority=_blank_to_none(priority),
            recommended_team=_blank_to_none(recommended_team),
            recommended_action=_blank_to_none(recommended_action),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    try:
        service.apply_review_update(request_id, update)
    except RequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RedirectResponse(url=f"/requests/{request_id}?updated=1", status_code=303)
