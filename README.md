# AI Workflow Automation Assistant

Local-first applied AI workflow project for intake triage and review-queue preparation.

## What It Does

The app accepts semi-structured operations requests, runs deterministic preprocessing, optionally calls an OpenAI-backed provider, validates the structured output, persists the result, and exposes a pending queue for reviewer follow-up.

Implemented today:

- `POST /api/v1/requests` to submit and analyze a request
- `GET /api/v1/requests/{request_id}` to inspect one request and its decision
- `GET /api/v1/queue` to list pending queue items
- `POST /api/v1/requests/{request_id}/review` to approve or edit a workflow decision
- `GET /health` for service health
- local queue and request-detail pages for reviewer follow-up
- mock and OpenAI provider modes with explicit fallback handling
- local SQLite persistence for demo and development
- automated test coverage for API, health, provider behavior, and response parsing

## Technology

- Python 3.11+
- FastAPI
- SQLAlchemy
- Pydantic
- Jinja2
- SQLite
- OpenAI Python SDK
- Docker for local packaging

## Quickstart

1. Create and activate a virtual environment.
2. Install dependencies: `pip install -e .[dev]`
3. Copy `.env.example` to `.env`
4. Start the app: `uvicorn app.main:app --reload`
5. Open `http://127.0.0.1:8000`

Main local surfaces:

- `/` for the starter landing page
- `/queue` for the reviewer queue
- `/requests/{request_id}` for request detail and review history

For a development container:

```bash
docker compose up --build
```

## Provider Modes

- `mock`: safest local default for demos and tests
- `openai`: real provider path with structured output validation

If the OpenAI path is enabled, fallback to mock should be an explicit choice. Keep it off by default when you want provider failures to surface clearly.

## Quality Checks

```bash
ruff check .
pytest
```

Current local verification uses:

- `ruff check .`
- `pytest`
- GitHub Actions CI for lint, tests, and Docker image validation

## Documentation

- Architecture notes: [docs/architecture.md](docs/architecture.md)
- Docs overview: [docs/README.md](docs/README.md)
- Synthetic sample-data notes: [sample_data/README.md](sample_data/README.md)

## Current Limits

- no authentication or multi-user access control yet
- single-tenant local-demo posture only
- local SQLite is fine for development but not a production database choice
- Docker support is for local packaging, not a full deployment story on its own

## Notes For Public Sharing

- Do not publish a real `.env` file or a populated runtime database
- Runtime SQLite state should stay under `.local/`, not in tracked repo files
- Do not position this as production-ready without auth, stronger deployment controls, and a production database plan
- Treat the OpenAI path as optional and bounded, not as the authoritative core of the workflow
