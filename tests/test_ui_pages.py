from datetime import datetime, timezone

from fastapi.testclient import TestClient


def build_submission(
    message_text: str = "Our enterprise invoice was charged twice and needs review.",
) -> dict:
    return {
        "message_text": message_text,
        "sender_name": "Alex Morgan",
        "sender_email": "alex@example.com",
        "company": "Northwind Labs",
        "channel": "email",
        "customer_tier": "enterprise",
        "received_at": datetime(2026, 3, 26, 10, 0, tzinfo=timezone.utc).isoformat(),
        "urgency_hint": "urgent follow-up requested",
    }


def test_homepage_presents_review_boundary(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Review decisions before action." in response.text
    assert "Mock provider first" in response.text
    assert "manual inbox triage" in response.text
    assert "review-ready decisions" in response.text
    assert "reviewer owned" in response.text


def test_queue_empty_state_explains_seeded_demo_path(client: TestClient) -> None:
    response = client.get("/queue")

    assert response.status_code == 200
    assert "No pending requests are waiting for review." in response.text
    assert "python scripts/seed_demo.py" in response.text
    assert "POST /api/v1/requests" in response.text


def test_queue_page_presents_operational_metrics(client: TestClient) -> None:
    client.post("/api/v1/requests", json=build_submission())
    client.post(
        "/api/v1/requests",
        json=build_submission(
            "Users cannot log in after MFA reset for our premium workspace."
        ),
    )

    response = client.get("/queue")

    assert response.status_code == 200
    assert "Operational review queue" in response.text
    assert "High or urgent" in response.text
    assert "Review urgent items" in response.text
    assert "Open first" in response.text
    assert "urgent, high-impact items" in response.text
    assert "Northwind Labs" in response.text
    assert "Open review" in response.text


def test_request_detail_presents_decision_gate_and_provider_evidence(
    client: TestClient,
) -> None:
    created = client.post("/api/v1/requests", json=build_submission()).json()

    response = client.get(f"/requests/{created['request_id']}")

    assert response.status_code == 200
    assert "Human decision gate" in response.text
    assert "Action package" in response.text
    assert "Provider evidence" in response.text
    assert "mock-local" in response.text
    assert "Save human review" in response.text
