# Copilot instructions

## What this repo is

`agency-studio` holds agent role contracts as markdown with YAML front matter,
plus the `agency_studio` Python package that validates them and an engine that
checks a real run against them. The engine enforces Builder-Verifier
separation: a contract says what one role may read, write, run and do, and what
evidence proves its work is done, and a run that breaks a rule is rejected
loudly rather than graded by the agent that produced it.

## Layout

- `roles/` - six bundled contracts: scout, planner, builder, reviewer, verifier,
  documenter.
- `src/agency_studio/` - package: contract loader, schema, engine, CLI.
- `tests/` - pytest suite: schema, contract loading, engine rules, CLI, repo hygiene.
- `examples/` - `pass/task.json` (accepted run) and
  `blocked-self-verify/task.json` (rejected run).
- `docs/` - contract schema, architecture, evaluation strategy, public boundary.
- `scripts/smoke.sh` - end-to-end smoke: a sound run is accepted and a
  self-verification run is blocked.
- `.github/workflows/` - `ci.yml` (lint, contract validation, tests, smoke) and
  `rig-lattice.yml`.

## Commands

Run from the repository root in a virtual environment:

```bash
pip install -e '.[dev]'      # installs pytest, pytest-cov, ruff
ruff check src tests         # lint
agency-studio validate roles # every bundled contract is valid
pytest -q                    # full test suite
pytest -q --cov=agency_studio
bash scripts/smoke.sh        # smoke
```

## Conventions

- Conventional commit messages: `feat:`, `fix:`, `test:`, `docs:`, `ci:`, `chore:`.
- Every behavior change lands with a test that exercises it and passes on a clean install.
- A contract change means editing the markdown under `roles/` (or a new contract
  with the same front-matter shape) and re-running `agency-studio validate roles`.
- No secrets, credentials, client PII or private monorepo content in any tracked
  file. No machine paths such as `/Users/...` or `~/Developer/...`.
- Never weaken Builder-Verifier separation or the evidence requirements to make a
  run pass.

## Truth rule

Any number in docs, comments, or commit messages must come from a command run in
this repository, for example a contract count from `agency-studio validate roles`
or a test count from `pytest -q`. Quote the command and its output rather than a
memory of it.
