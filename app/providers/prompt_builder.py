from __future__ import annotations

import json
from dataclasses import dataclass

from app.domain.schemas import IntakeSubmission


@dataclass(slots=True)
class OpenAIPromptBundle:
    system_prompt: str
    user_prompt: str
    messages: list[dict[str, str]]
    prompt_version: str


def build_workflow_prompt(
    submission: IntakeSubmission,
    *,
    prompt_version: str = "openai-workflow-v1",
) -> OpenAIPromptBundle:
    system_prompt = _build_system_prompt(prompt_version=prompt_version)
    user_prompt = _build_user_prompt(submission)
    return OpenAIPromptBundle(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        prompt_version=prompt_version,
    )


def _build_system_prompt(*, prompt_version: str) -> str:
    return "\n".join(
        [
            "You are an internal operations intake assistant.",
            "Classify the request deterministically and return only JSON that matches the schema.",
            "Use concise language and do not add commentary outside the schema.",
            f"Prompt version: {prompt_version}.",
            "Rules:",
            "- Use category, priority, team, and action that best fit the request text.",
            "- Keep missing_information as a short list of concrete missing fields.",
            "- Confidence must be a number between 0 and 1.",
        ]
    )


def _build_user_prompt(submission: IntakeSubmission) -> str:
    payload = submission.model_dump(mode="json")
    return "\n".join(
        [
            "Analyze this intake submission:",
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True),
        ]
    )
