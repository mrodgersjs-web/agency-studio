# agency-studio

> Department-shaped agent teams with hard boundaries — specialization, ownership, and handoff contracts.

## Employer summary

Shows how an FDE staffs an AI-augmented delivery team without turning every agent into a god-object. Each role has a boundary, trigger, and proof expectation.

## Roles (starter roster)

| Role | Owns | Does not own |
|---|---|---|
| Scout | codebase reconnaissance | writing production code |
| Planner | specs and plans | silent scope expansion |
| Builder | implementation | self-certifying done |
| Reviewer | standards/quality | rewriting without evidence |
| Verifier | deterministic gates | design opinions |
| Documenter | operator docs | changing runtime behavior |

## 60-second path

```bash
# read role contracts
sed -n '1,80p' roles/verifier.md
```

## Public boundary
No client rosters, CRM data, or private agency monorepo dumps. See docs/public-boundary.md.
