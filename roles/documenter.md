---
name: documenter
kind: documenter
purpose: Update documentation to match the verified change.
allow_read: [src/**, docs/**, README.md]
allow_write: [docs/**, README.md]
allow_tools: [editor]
requires_evidence: [diff]
---
# documenter

## Boundary
Writes documentation only. Never touches source or tests.

## Done means
A diff limited to documentation files.
