# Architecture

```
roles/*.md  --load/validate-->  Contract objects  --+
                                                    +--> engine.run_task --> ACCEPTED | REJECTED + violations
task.json (builder phase + verifier phase) ---------+
```

1. `contract.py` parses markdown with a YAML-subset front matter and validates it (required fields, known kinds, relative globs, verifiers are read-only, builders and verifiers must declare evidence). `validate_set` checks across contracts.
2. `engine.py` copies the task's workdir to a temp dir, runs the builder phase then the verifier phase, and checks each against its contract. The original workdir is never modified.
3. A phase is either an inline `report` (declared actions, evidence, verdict) or a `command` that prints that report as JSON. For commands the engine also hashes the workdir before and after, so a write the command did not declare is still checked against `allow_write`.

## Rules (each has a test in `tests/test_engine.py`)
| Rule | Fires when |
| --- | --- |
| SELF_VERIFICATION | verifier role equals builder role, verifier agent equals builder agent, verifier role is not kind `verifier`, or its `cannot_verify` lists the builder role. Checked before anything runs. |
| BOUNDARY | an action (declared or observed) is outside `allow_read` / `allow_write` (globs), `allow_tools` or `allow_actions`; paths that are absolute or escape the workdir always fail. |
| EVIDENCE | a kind in `requires_evidence` is missing, empty, points at a missing or empty file, fails its `sha256`, a verifier supplies bare text instead of an engine-run command or a sha256-checked file, a command the engine ran for the verifier exits non-zero, or the verifier's evidence is identical to the builder's. |
| VERDICT | the verifier's verdict is not `pass`, or is `pass` while its own executed evidence failed. |

Limits: "agent" is an identifier the task file declares. The engine compares ids; it cannot prove two ids are different models or processes. Observed-write detection covers files in the workdir, not network or process side effects.
