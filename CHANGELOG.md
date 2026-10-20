# Changelog

Notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
semantic versioning.

## [0.2.1] - 2026-10-19

### Added

- `.github/CODEOWNERS` assigning `*` to `@mrodgersjs-web`.
- `.github/copilot-instructions.md` (2374 bytes): what the repository is, the
  layout, the exact commands (`pip install -e '.[dev]'`, `ruff check src tests`,
  `agency-studio validate roles`, `pytest -q`, `bash scripts/smoke.sh`),
  conventions (conventional commits, a test for every change, no secrets, no
  machine paths) and the truth rule that every number in docs comes from a
  command run in this repository.
- `tests/test_repo_hygiene.py`: 4 checks read from the files on disk that
  `.github/CODEOWNERS` assigns `*` to `@mrodgersjs-web`, that
  `.github/copilot-instructions.md` is non-empty, at most 8000 bytes and names a
  test command, that `README.md` carries a `github/actions/workflow/status` badge,
  the "Built by Mike Rodgers - rodgersintelligence.com" footer, a test command and
  only clones `mrodgersjs-web/agency-studio`, and that every job under
  `.github/workflows/` sets `timeout-minutes` and never sets `continue-on-error: true`.

### Changed

- `.github/workflows/ci.yml` and `.github/workflows/rig-lattice.yml`:
  `timeout-minutes: 15` on every job.
- `README.md`: footer is the plain literal "Built by Mike Rodgers -
  rodgersintelligence.com", and the Quickstart comment reads `# 56 tests`, the
  number `pytest -q` prints after the hygiene tests landed.

### Verified

- Fresh venv `python3.12 -m venv`, `pip install -e '.[dev]'`, `ruff check src tests`
  clean, `agency-studio validate roles` reports 6 contracts valid,
  `pytest -q --cov=agency_studio` 56 passed with 91 percent coverage.

## [0.2.0] - 2026-10-19

### Added

- Documented contract schema: `docs/contract-schema.md` plus a machine-readable
  `src/agency_studio/schema.py`, and an `agency-studio schema` command that
  prints it as JSON.
- CI workflow (`.github/workflows/ci.yml`) on Python 3.10 to 3.13 running ruff,
  schema validation of all bundled contracts, pytest with coverage, and the
  end-to-end smoke. It replaces the smoke-only workflow.
- Tests for the schema module and the CLI (validate, schema, roles, run exit
  codes and JSON output).
- `py.typed` marker, pytest-cov in the dev extras, and full packaging metadata
  (authors, classifiers, project URLs).

### Changed

- README restructured with badges, a Quickstart whose numbers come from the
  test run, a mermaid flow, and runnable proof checks.
- SECURITY.md reporting address is now security@rodgersintelligence.com;
  CONTRIBUTING.md reflects the real test and lint commands.
- The MCP wrapper resolves `rig-loop` from `PATH` or `RIG_LOOP` instead of a
  machine-specific home path.

## [0.1.0] - 2026-10-10

### Added

- Role contract format (markdown with YAML-subset front matter), parser and
  validator (`src/agency_studio/contract.py`).
- Builder-Verifier enforcement engine with SELF_VERIFICATION, BOUNDARY,
  EVIDENCE and VERDICT rules (`src/agency_studio/engine.py`).
- `agency-studio` CLI: `validate`, `run`, `roles`.
- Six bundled role contracts and two runnable examples (one accepted, one
  blocked), with tests and the end-to-end smoke script.
