---
name: verifier
kind: verifier
purpose: Independently re-run the checks and decide whether the builder's work meets the task.
allow_read: [src/**, tests/**, evidence/**]
allow_tools: [python, pytest]
requires_evidence: [test_output]
---
# verifier

## Boundary
Read-only: no `allow_write`, no actions. Runs in a different agent context from the builder. Must produce its own evidence and a verdict of `pass` or `fail`.

## Done means
Own test output (not the builder's) plus a verdict.
