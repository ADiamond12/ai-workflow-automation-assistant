from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_workflow_service
from app.core.config import get_settings
from app.core.database import get_engine
from app.domain.schemas import IntakeSubmission
from app.providers.base import AIProvider
from app.providers.errors import ProviderUnavailableError
from app.providers.openai_adapter import OpenAIProvider
from app.repositories.models import RequestRecord
from app.services.workflow import WorkflowService


def build_submission(
    message_text: str = "Our enterprise invoice was charged twice and needs review.",
) -> dict:
    return {
        "message_text": message_text,
        "sender_name": "  Alex Morgan  ",
        "sender_email": "alex@example.com",
        "company": "  Northwind Labs ",
        "channel": "email",
        "customer_tier": "enterprise",
        "received_at": datetime(2026, 3, 26, 10, 0, tzinfo=timezone.utc).isoformat(),
        "urgency_hint": "  urgent follow-up requested  ",
    }


def test_submit_request_persists_and_can_be_fetched(client: TestClient) -> None:
    create_response = client.post("/api/v1/requests", json=build_submission())

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["category"] == "billing_issue"
    assert created["priority"] == "urgent"
    assert created["request_id"]
    assert created["processing_metadata"]["provider_name"] == "mock-local"

    detail_response = client.get(f"/api/v1/requests/{created['request_id']}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["request_id"] == created["request_id"]
    assert detail["submission"]["sender_name"] == "Alex Morgan"
    assert detail["submission"]["company"] == "Northwind Labs"
    assert detail["decision"]["request_id"] == created["request_id"]
    assert detail["queue_position"] == 1


def test_queue_lists_pending_items(client: TestClient) -> None:
    client.post("/api/v1/requests", json=build_submission())
    client.post(
        "/api/v1/requests",
        json=build_submission(
            "Users cannot log in after MFA reset for our premium workspace."
        ),
    )

    queue_response = client.get("/api/v1/queue", params={"limit": 10})

    assert queue_response.status_code == 200
    payload = queue_response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert {item["category"] for item in payload["items"]} == {
        "billing_issue",
        "account_access",
    }


def test_review_approval_updates_status_and_clears_queue_item(client: TestClient) -> None:
    created = client.post("/api/v1/requests", json=build_submission()).json()
    request_id = created["request_id"]

    review_response = client.post(
        f"/api/v1/requests/{request_id}/review",
        json={
            "review_status": "approved",
            "reviewer_name": "Jordan Lee",
            "reviewer_notes": "Approved for routing as-is.",
        },
    )

    assert review_response.status_code == 200
    detail = review_response.json()
    assert detail["review_status"] == "approved"
    assert detail["decision"]["review_status"] == "approved"
    assert detail["reviews"][0]["review_status"] == "approved"
    assert detail["reviews"][0]["reviewer_name"] == "Jordan Lee"
    assert detail["reviews"][0]["reviewer_notes"] == "Approved for routing as-is."

    queue_response = client.get("/api/v1/queue")
    assert queue_response.status_code == 200
    assert queue_response.json()["total"] == 0


def test_review_edit_updates_decision_fields_and_records_edits(client: TestClient) -> None:
    created = client.post("/api/v1/requests", json=build_submission()).json()
    request_id = created["request_id"]

    review_response = client.post(
        f"/api/v1/requests/{request_id}/review",
        json={
            "review_status": "edited",
            "reviewer_name": "Jordan Lee",
            "reviewer_notes": "Escalating to operations with manual review.",
            "priority": "high",
            "recommended_team": "operations",
            "recommended_action": "review_manually",
        },
    )

    assert review_response.status_code == 200
    detail = review_response.json()
    assert detail["review_status"] == "edited"
    assert detail["decision"]["review_status"] == "edited"
    assert detail["decision"]["priority"] == "high"
    assert detail["decision"]["recommended_team"] == "operations"
    assert detail["decision"]["recommended_action"] == "review_manually"
    assert detail["reviews"][0]["edited_fields"] == {
        "priority": "high",
        "recommended_team": "operations",
        "recommended_action": "review_manually",
    }


def test_missing_request_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/requests/does-not-exist")

    assert response.status_code == 404


def test_invalid_submission_returns_422(client: TestClient) -> None:
    payload = build_submission()
    payload["message_text"] = "   "

    response = client.post("/api/v1/requests", json=payload)

    assert response.status_code == 422


class FailingProvider(AIProvider):
    name = "failing-test-provider"

    def analyze(self, submission: IntakeSubmission):
        raise RuntimeError("provider failure")


def test_provider_failure_rolls_back_request_persistence() -> None:
    def override_workflow_service():
        with Session(get_engine()) as session:
            yield WorkflowService(session=session, provider=FailingProvider())

    from app.main import app

    app.dependency_overrides[get_workflow_service] = override_workflow_service
    try:
        with TestClient(app, raise_server_exceptions=False) as failing_client:
            response = failing_client.post("/api/v1/requests", json=build_submission())

        assert response.status_code == 500

        with Session(get_engine()) as session:
            request_count = session.scalar(select(func.count()).select_from(RequestRecord))
            assert request_count == 0
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)


class UnavailableProvider(AIProvider):
    name = "unavailable-provider"

    def analyze(self, submission: IntakeSubmission):
        raise ProviderUnavailableError("OpenAI provider failed without fallback: unavailable")


def test_provider_unavailable_maps_to_503(client: TestClient) -> None:
    def override_workflow_service():
        with Session(get_engine()) as session:
            yield WorkflowService(session=session, provider=UnavailableProvider())

    from app.main import app

    app.dependency_overrides[get_workflow_service] = override_workflow_service
    try:
        response = client.post("/api/v1/requests", json=build_submission())

        assert response.status_code == 503
        assert "without fallback" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)


def test_openai_provider_without_fallback_maps_to_502_and_persists_nothing(
    client: TestClient,
) -> None:
    def override_workflow_service():
        with Session(get_engine()) as session:
            provider = OpenAIProvider(
                api_key="",
                allow_mock_fallback=False,
            )
            yield WorkflowService(session=session, provider=provider)

    from app.main import app

    app.dependency_overrides[get_workflow_service] = override_workflow_service
    try:
        response = client.post("/api/v1/requests", json=build_submission())

        assert response.status_code == 503

        with Session(get_engine()) as session:
            request_count = session.scalar(select(func.count()).select_from(RequestRecord))
            assert request_count == 0
    finally:
        app.dependency_overrides.pop(get_workflow_service, None)


def test_openai_mode_with_fallback_enabled_uses_mock_through_real_service_path(
    client: TestClient,
) -> None:
    settings = get_settings()
    original_provider_mode = settings.provider_mode
    original_fallback = settings.openai_fallback_to_mock
    original_api_key = settings.openai_api_key

    settings.provider_mode = "openai"
    settings.openai_fallback_to_mock = True
    settings.openai_api_key = ""
    try:
        response = client.post("/api/v1/requests", json=build_submission())

        assert response.status_code == 200
        payload = response.json()
        assert payload["processing_metadata"]["provider_name"].startswith(
            "openai->fallback:"
        )
    finally:
        settings.provider_mode = original_provider_mode
        settings.openai_fallback_to_mock = original_fallback
        settings.openai_api_key = original_api_key
