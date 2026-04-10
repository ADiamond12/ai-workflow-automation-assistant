from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def normalize_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_whitespace(value)
    return normalized or None


def normalize_text_list(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        candidate = normalize_optional_text(value)
        if candidate is None or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def normalize_token_usage(token_usage: dict[str, Any] | None) -> dict[str, int]:
    if not token_usage:
        return {}

    normalized: dict[str, int] = {}
    for key, value in token_usage.items():
        if value is None:
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count < 0:
            continue
        normalized[str(key)] = count
    return normalized


def clamp_float(value: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))
