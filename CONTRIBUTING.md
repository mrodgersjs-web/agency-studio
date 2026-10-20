# Contributing

## Bar

1. Public-boundary safe (no PII, secrets, client dumps, ToS-risk bots).
2. `ruff check src tests` clean and `pytest -q` passing.
3. `agency-studio validate roles` clean (bundled contracts must satisfy the schema).
4. README claims must match runnable commands.
5. Prefer small diffs with proof over large narrative refactors.

## Flow

1. Fork or branch from `main`.
2. `pip install -e '.[dev]'`, then add or adjust tests for the change.
3. Run `ruff check src tests && pytest -q --cov=agency_studio` and `bash scripts/smoke.sh`.
4. Open a PR with: what changed, how verified, boundary impact.
