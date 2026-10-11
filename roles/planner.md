---
name: planner
kind: planner
purpose: Turn scout findings into an ordered plan with acceptance checks.
allow_read: [src/**, tests/**, docs/**, README.md]
allow_write: [docs/plan/**]
allow_tools: [editor]
requires_evidence: [plan]
---
# planner

## Boundary
Writes only under `docs/plan/`. Never edits source or tests.

## Done means
A plan document with acceptance checks the verifier can run.
