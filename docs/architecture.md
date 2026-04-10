# Architecture

## Goal

Provide a local-first intake triage service that demonstrates applied AI workflow design without making the model the owner of business state.

## Current Runtime Shape

- FastAPI serves the API and the starter UI surface
- SQLAlchemy persists requests, decisions, and review records to SQLite
- deterministic logic normalizes the intake before provider execution
- provider selection happens behind a boundary that supports `mock` and `openai`
- structured output is validated before it becomes part of the stored decision
- reviewer queue and detail views sit on top of the same service layer as the API

## Main Flow

1. Client submits an `IntakeSubmission`
2. Service orchestrates preprocessing and provider execution
3. Provider returns a structured `ProviderResponse`
4. Response parser and domain schemas validate the decision
5. Repository layer persists the request, decision, and review-ready state
6. API exposes request detail and pending queue views
7. Reviewer actions update the stored decision and append review history

## Key Modules

- `app/api`
  - route handlers and HTTP error mapping
- `app/core`
  - settings, database wiring, application lifecycle
- `app/domain`
  - enums and request/decision schemas
- `app/providers`
  - mock provider, OpenAI adapter, prompt builder, response parsing
- `app/repositories`
  - SQLAlchemy models and queue/detail persistence helpers
- `app/services`
  - workflow orchestration and queue assembly

## Provider Posture

- `mock` is the safest demo mode
- `openai` is optional and bounded behind the provider interface
- fallback to mock should be explicit, not silent by accident
- the model does not own final review semantics

## What Is Not Implemented Yet

- authentication and multi-user access control
- a production database strategy
- full deployment and observability posture
- richer evaluation/reporting assets for public release

## Why This Shape Matters

The project is stronger as a portfolio piece when the deterministic workflow, persistence, and review boundary stay legible. The AI layer should assist the workflow, not replace the application's control over state and safety.
