# Changelog

Notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
semantic versioning.

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
