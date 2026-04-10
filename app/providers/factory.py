from __future__ import annotations

from app.core.config import get_settings
from app.providers.base import AIProvider
from app.providers.mock import LocalMockProvider
from app.providers.openai_adapter import OpenAIProvider


def get_provider(mode: str | None = None) -> AIProvider:
    settings = get_settings()
    selected = (mode or settings.provider_mode).strip().lower()
    if selected in {"mock", "local", "dev"}:
        return LocalMockProvider()
    if selected == "openai":
        return OpenAIProvider(
            model=settings.openai_model,
            api_key=settings.openai_api_key or None,
            allow_mock_fallback=settings.openai_fallback_to_mock,
        )
    raise ValueError(f"Unsupported provider mode: {selected}")
