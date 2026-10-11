# agency-studio

![agency-studio](assets/agency-studio-hero.png)

Agent role contracts written as markdown, with a validator and an engine that enforces **Builder-Verifier separation**.

A contract says what one role may read, write, run and do, and what evidence proves its work is done. The engine runs a task through a Builder and then an independent Verifier and **rejects** the run when:

- the verifier is the builder's role or the same agent (self-verification),
- anyone touches a file, tool or action outside their contract (boundary),
- required evidence is missing, empty, tampered with or just copied from the builder (evidence),
- the verifier's verdict is not `pass`.

## Install and run

```bash
pip install -e '.[dev]'
agency-studio validate roles                       # check all contracts
agency-studio roles                                # list them
agency-studio run examples/pass/task.json          # ACCEPTED, exit 0
agency-studio run examples/blocked-self-verify/task.json   # REJECTED, exit 1
bash scripts/smoke.sh                              # the same, as the CI smoke
pytest -q && ruff check src tests
```

Exit codes for `run`: 0 accepted, 1 rejected, 2 bad input (unreadable task, unknown role, invalid contract).

## Contract format

```markdown
---
name: verifier
kind: verifier            # scout|planner|builder|reviewer|verifier|documenter
purpose: Independently re-run the checks.
allow_read: [src/**, tests/**, evidence/**]
allow_write: []           # verifiers must be read-only
allow_tools: [python, pytest]
allow_actions: []
cannot_verify: []         # optional: roles this role may never verify
requires_evidence: [test_output]
---
Free-form markdown body.
```

Six sample contracts live in [`roles/`](roles). Design notes: [docs/architecture.md](docs/architecture.md).

## Task format

A task names a builder phase and a verifier phase, each with a `role`, an `agent` id and either an inline `report` or a `command` that prints a JSON report (`actions`, `evidence`, and for the verifier a `verdict`). See [`examples/`](examples). Commands run in a temporary copy of `workdir`, and undeclared file changes are detected and checked too.

## Limits

- Agent identity is the id the task declares; the engine cannot prove two ids are different models.
- Only file changes in the workdir are observed. Network and process side effects are not.

## Roadmap

- Roles beyond builder and verifier (planner, reviewer, documenter) have contracts, but the engine runs only the Builder-Verifier pair.
- Multi-step handoff chains with more than two phases.
- MCP server (`mcp/server.py`) is a separate results wrapper and is not part of the enforcement engine.
- Network and process side-effect observation.

## Related
- [jake-studio](https://github.com/mrodgersjs-web/jake-studio) · [doctrine](https://github.com/mrodgersjs-web/doctrine) · [proof-studio](https://github.com/mrodgersjs-web/proof-studio)

## Public boundary
See [docs/public-boundary.md](docs/public-boundary.md). Video walkthrough script: [docs/video-script.md](docs/video-script.md).
