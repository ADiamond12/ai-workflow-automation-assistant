# Scripts

Use this directory for developer utilities such as seed scripts, export helpers, and local setup automation.

## Current Utilities

- `seed_demo.py`
  - posts the sanitized fixtures from `sample_data/synthetic_requests.json` into a running local server
  - defaults to `http://127.0.0.1:8000`
  - override with `AWA_DEMO_BASE_URL` when the app runs elsewhere

Example:

```bash
python scripts/seed_demo.py
```
