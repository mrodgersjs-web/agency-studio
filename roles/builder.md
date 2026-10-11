---
name: builder
kind: builder
purpose: Implement the planned change and show it works.
allow_read: [src/**, tests/**, docs/**]
allow_write: [src/**, tests/**, evidence/builder/**]
allow_tools: [editor, python, pytest]
allow_actions: [commit_local]
requires_evidence: [diff, test_output]
---
# builder

## Boundary
Writes only source, tests and its own evidence folder. Cannot push, merge or publish. A builder never verifies its own work: the verifier must be a different role and a different agent.

## Done means
A diff and test output, both as real files or captured text.
