"""Machine-readable contract schema, derived from contract.py constants.

The Markdown copy of this schema is docs/contract-schema.md. Both describe the
same format; this module is the single source of truth for field names and
rules, so docs and code cannot drift without a test noticing.
"""

from __future__ import annotations

from .contract import KINDS, LIST_FIELDS, REQUIRED_FIELDS
from .engine import BOUNDARY, EVIDENCE, SELF_VERIFICATION, VERDICT

SCHEMA_VERSION = "1.0.0"

FIELD_DOCS: dict[str, str] = {
    "name": "Contract id: lowercase letters, digits, '_' and '-' (must match the file stem).",
    "kind": "Role kind. One of the kinds in `kinds`.",
    "purpose": "One line: what the role does.",
    "allow_read": "Glob patterns of paths the role may read.",
    "allow_write": "Glob patterns of paths the role may write. Must be empty for verifiers.",
    "allow_tools": "Tool names (executable basenames) the role may run.",
    "allow_actions": "Named actions the role may take (for example commit_local).",
    "requires_evidence": "Evidence kinds a done claim must carry (at least one for builders and verifiers).",
    "cannot_verify": "Roles this role may never verify (self-verification guard).",
}


def schema_as_dict() -> dict:
    """The full contract schema: fields, kinds, path rules, and engine rules."""
    return {
        "schema_version": SCHEMA_VERSION,
        "format": "markdown-with-yaml-subset-front-matter",
        "front_matter": {
            "required": list(REQUIRED_FIELDS),
            "list_fields": list(LIST_FIELDS),
            "fields": {name: FIELD_DOCS[name] for name in (*REQUIRED_FIELDS, *LIST_FIELDS)},
        },
        "path_rules": [
            "allow_read and allow_write patterns must be relative and may not contain '..'",
            "patterns with '*' stay inside a path segment; '**' crosses segments",
        ],
        "kind_rules": [
            f"kinds: {', '.join(KINDS)}",
            "a verifier may not have allow_write (verifiers are read-only)",
            "builders and verifiers must declare at least one requires_evidence kind",
        ],
        "set_rules": [
            "contract names are unique within a directory",
            "a verifier's write scope may not overlap a builder's write scope",
        ],
        "engine_rules": [
            (
                f"{SELF_VERIFICATION}: verifier must not be the builder's role or agent, "
                "must be kind 'verifier', and must not be forbidden by cannot_verify"
            ),
            f"{BOUNDARY}: every declared or observed read, write, tool and action must be allowed",
            (
                f"{EVIDENCE}: required evidence must be present and grounded "
                "(verifier evidence is an engine-run command or a sha256-checked file)"
            ),
            f"{VERDICT}: the verifier's verdict must be 'pass', consistent with its own executed checks",
        ],
    }
