import json
from pathlib import Path

from app.domain.enums import PriorityLevel, RecommendedAction, RecommendedTeam, RequestCategory
from app.domain.schemas import IntakeSubmission

ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_requests_are_valid_intake_submissions() -> None:
    payload = json.loads((ROOT / "sample_data" / "synthetic_requests.json").read_text())

    assert payload
    for item in payload:
        submission = IntakeSubmission.model_validate(item)
        assert submission.sender_email.endswith(".example")


def test_eval_cases_use_supported_expected_labels() -> None:
    payload = json.loads((ROOT / "evals" / "sample_cases.json").read_text())

    assert payload
    for item in payload:
        IntakeSubmission.model_validate(item["submission"])
        expected = item["expected"]
        assert expected["category"] in {label.value for label in RequestCategory}
        assert expected["priority"] in {label.value for label in PriorityLevel}
        assert expected["recommended_team"] in {label.value for label in RecommendedTeam}
        assert expected["recommended_action"] in {label.value for label in RecommendedAction}
