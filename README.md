# AI Workflow Automation Assistant

Local-first applied AI workflow project for intake triage, structured decision support, and human review preparation.

## Overview

This project accepts semi-structured operations requests, runs deterministic preprocessing, optionally calls an OpenAI-backed provider, validates the structured output, persists the result, and exposes a review queue for follow-up.

The main design goal is simple: use AI inside a controlled workflow, not as the owner of business state.

## Why This Repo Exists

- shows applied AI usage in a realistic operations-style workflow
- keeps deterministic validation and persistence visible
- demonstrates provider abstraction instead of hard-coding model logic into the app
- includes reviewable API, UI, persistence, and test layers in one small project

## Current Features

- `POST /api/v1/requests` to submit and analyze a request
- `GET /api/v1/requests/{request_id}` to inspect one request and its decision
- `GET /api/v1/queue` to list pending queue items
- `POST /api/v1/requests/{request_id}/review` to approve or edit a workflow decision
- `GET /health` for service health
- starter UI surfaces for queue and request detail review
- `mock` and `openai` provider modes behind a provider boundary
- local SQLite persistence for demo and development
- automated test coverage for API, parsing, health, and provider behavior

## Stack

- Python 3.11+
- FastAPI
- SQLAlchemy
- Pydantic
- Jinja2
- SQLite
- OpenAI Python SDK
- Docker
- GitHub Actions

## Local Run

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Copy `.env.example` to `.env`.
4. Start the app:

```bash
uvicorn app.main:app --reload
```

5. Open `http://127.0.0.1:8000`

Main local surfaces:

- `/` for the landing page
- `/queue` for the reviewer queue
- `/requests/{request_id}` for request detail and review history

For a containerized local run:

```bash
docker compose up --build
```

## Provider Modes

- `mock`
  - safest local default for demos and tests
- `openai`
  - real provider path with structured output validation

The OpenAI path is intentionally optional. The workflow should still be understandable and testable when the provider is mocked.

## Example Workflow

1. Submit an intake request through the API or starter UI.
2. Normalize and validate the input.
3. Run provider-backed or mock decision generation.
4. Validate the structured response.
5. Persist request, decision, and review state to SQLite.
6. Review the result in the queue or request-detail view.

## Quality Checks

```bash
ruff check .
pytest
```

Repository validation also includes GitHub Actions CI for:

- linting
- test execution
- Docker build verification
- container health smoke test

## Repository Layout

- `app/`
  - API, core app wiring, providers, repositories, services, templates, and UI routes
- `docs/`
  - architecture and project notes
- `sample_data/`
  - sanitized demo requests
- `evals/`
  - evaluation-oriented sample cases
- `tests/`
  - API, provider, parser, and health checks

## Documentation

- [docs/architecture.md](docs/architecture.md)
- [docs/README.md](docs/README.md)
- [sample_data/README.md](sample_data/README.md)
- [SECURITY.md](SECURITY.md)

## Current Limits

- no authentication or multi-user access control yet
- single-tenant local-demo posture only
- local SQLite is suitable for development, not as a production database strategy
- Docker support is for local packaging, not a full deployment platform
- screenshots and deployment runbooks are intentionally still light

## Public Repo Notes

- do not commit a real `.env` file
- do not commit populated runtime databases or local state under `.local/`
- do not present this as production-ready without auth, stronger deployment controls, and a production database plan
- treat the OpenAI path as optional and bounded, not as the authoritative core of the workflow
