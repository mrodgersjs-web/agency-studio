# Contract schema (v1.0.0)

A role contract is one Markdown file with YAML-subset front matter. The
machine-readable copy of this schema is `src/agency_studio/schema.py`
(`agency-studio schema` prints it as JSON); the rules below are enforced by
`agency_studio.contract` and the enforcement engine.

## File shape

```
roles/<name>.md
```

- The front matter is delimited by `---` lines and must parse as key/value pairs.
- Supported values: scalars (string, int, bool), inline lists `[a, b]`, and
  block lists (`- item` lines). Nothing else, on purpose.
- The free-form Markdown body follows the front matter. It is documentation,
  not parsed.

## Front-matter fields

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Contract id: lowercase letters, digits, `_`, `-`. Must match the file stem. |
| `kind` | yes | One of: `scout`, `planner`, `builder`, `reviewer`, `verifier`, `documenter`. |
| `purpose` | yes | One line: what the role does. |
| `allow_read` | no | Glob patterns of paths the role may read. |
| `allow_write` | no | Glob patterns of paths the role may write. |
| `allow_tools` | no | Tool names (executable basenames) the role may run. |
| `allow_actions` | no | Named actions the role may take, for example `commit_local`. |
| `requires_evidence` | see rules | Evidence kinds a done claim must carry. |
| `cannot_verify` | no | Roles this role may never verify. |

Unknown fields are rejected.

## Path rules

- `allow_read` / `allow_write` patterns must be relative and may not contain `..`.
- `*` matches inside one path segment; `**` crosses segments (`src/**` covers
  `src/a/b.py`, `src/*.py` does not).
- Absolute paths and paths that escape the workdir always fail the boundary check.

## Kind rules

- A `verifier` may not declare `allow_write` (verifiers are read-only).
- `builder` and `verifier` contracts must declare at least one
  `requires_evidence` kind.
- Builders declare evidence such as `diff` and `test_output`; verifiers declare
  `test_output`.

## Set rules (across a directory of contracts)

- Contract names must be unique.
- A verifier's write scope may not overlap a builder's write scope.

## Engine rules (what a run can reject)

| Rule | Fires when |
| --- | --- |
| `SELF_VERIFICATION` | The verifier is the builder's role or agent, is not kind `verifier`, or its `cannot_verify` lists the builder role. |
| `BOUNDARY` | A declared or observed read, write, tool or action is outside the role's allow-lists. |
| `EVIDENCE` | Required evidence is missing, empty, ungrounded, fails its `sha256`, is the builder's own evidence reused, or its command exited non-zero. |
| `VERDICT` | The verifier's verdict is not `pass`, or is `pass` while its own executed checks failed. |

## Minimal example

```markdown
---
name: verifier
kind: verifier
purpose: Independently re-run the checks.
allow_read: [src/**, tests/**]
allow_tools: [python, pytest]
requires_evidence: [test_output]
---
# verifier

## Boundary
Read-only, separate agent from the builder.

## Done means
Own test output plus a verdict of pass or fail.
```

## Validating

```bash
agency-studio validate roles       # all bundled contracts
agency-studio validate my.md       # one file
agency-studio schema               # this schema as JSON
```

Exit code 0 means valid; 1 prints `INVALID` plus the problems.
