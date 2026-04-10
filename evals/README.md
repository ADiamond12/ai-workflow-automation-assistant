# Evals

This directory holds small labeled fixtures for workflow-review regression checks.

Current state:

- API and provider behavior are covered by `tests/`
- the committed fixture here is a lightweight labeled set for future prompt or routing evaluation
- the repo does not claim a full benchmark suite yet

Committed fixture:

- `sample_cases.json`
  - each case includes a synthetic submission plus the expected category, priority, team, and action
  - intended for future offline scoring or prompt-regression scripts

Near-term eval goal:

- run the same labeled cases through both the mock provider and the live provider path
- compare category/priority drift before changing prompts or routing rules
