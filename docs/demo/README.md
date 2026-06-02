# AI Workflow Automation Assistant Demo Storyboard

Use this storyboard for a short public-safe walkthrough. The seeded requests are synthetic and run in mock-provider mode.

## 90-Second Reviewer Flow

1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\run_demo.ps1`.
2. Open the landing page and explain the boundary: the app prepares workflow decisions, but a reviewer owns the final state.
3. Open `/queue` and show pending requests with priority, category, recommended team, and confidence.
4. Open one request detail page.
5. Point to the original request, parsed recommendation, provider metadata, and missing-information fields.
6. Edit or approve the review decision and save it.
7. Return to the queue or history state to show the request is no longer just a model response; it is tracked workflow state.

## Screenshots To Capture

- `docs/screenshots/home.png`: landing page with local-first workflow framing.
- `docs/screenshots/queue.png`: populated queue after seeding demo data.
- `docs/screenshots/request-detail.png`: request detail with recommendation and review controls.
- `docs/screenshots/queue-mobile.png`: mobile queue view.

## What To Say

This project demonstrates applied AI inside a bounded operations workflow. The useful part is the review system: validation, persistence, provider boundaries, and human approval before any operational action.
