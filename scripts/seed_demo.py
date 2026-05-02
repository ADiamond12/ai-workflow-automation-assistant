"""Seed a running local demo server with synthetic intake requests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("AWA_DEMO_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    samples = json.loads((ROOT / "sample_data" / "synthetic_requests.json").read_text())
    for sample in samples:
        created = post_json(f"{BASE_URL}/api/v1/requests", sample)
        print(f"{created['request_id']} {created['priority']} {created['category']}")

    print(f"Seeded {len(samples)} synthetic requests into {BASE_URL}")


if __name__ == "__main__":
    main()
