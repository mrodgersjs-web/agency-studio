"""Role contract format: markdown with a small YAML-subset front matter.

A contract file looks like::

    ---
    name: builder
    kind: builder
    purpose: Implement the change.
    allow_read: [src/**, tests/**]
    allow_write: [src/**]
    allow_tools: [editor, pytest]
    allow_actions: [commit_local]
    requires_evidence: [diff, test_output]
    ---
    # builder
    free-form markdown body

Supported front matter values: scalars (string, int, bool), inline lists
``[a, b]`` and block lists (``- item`` lines). Nothing else, on purpose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("scout", "planner", "builder", "reviewer", "verifier", "documenter")
LIST_FIELDS = (
    "allow_read",
    "allow_write",
    "allow_tools",
    "allow_actions",
    "requires_evidence",
    "cannot_verify",
)
REQUIRED_FIELDS = ("name", "kind", "purpose")
KNOWN_FIELDS = set(REQUIRED_FIELDS) | set(LIST_FIELDS)
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


class ContractError(ValueError):
    """Raised when a contract file cannot be parsed."""


@dataclass
class Contract:
    name: str
    kind: str
    purpose: str
    allow_read: list[str] = field(default_factory=list)
    allow_write: list[str] = field(default_factory=list)
    allow_tools: list[str] = field(default_factory=list)
    allow_actions: list[str] = field(default_factory=list)
    requires_evidence: list[str] = field(default_factory=list)
    cannot_verify: list[str] = field(default_factory=list)
    body: str = ""
    path: str = ""


def _scalar(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Split ``text`` into (front matter dict, markdown body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ContractError("missing front matter: file must start with '---'")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ContractError("unterminated front matter: no closing '---'")
    data: dict = {}
    current: str | None = None
    for n, raw in enumerate(lines[1:end], start=2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip().startswith("- "):
            if current is None or not isinstance(data.get(current), list):
                raise ContractError(f"line {n}: list item without a list key")
            data[current].append(_scalar(raw.lstrip()[2:]))
            continue
        if raw[0] in " \t":
            raise ContractError(f"line {n}: unexpected indentation")
        key, sep, value = raw.partition(":")
        key = key.strip()
        if not sep or not key:
            raise ContractError(f"line {n}: expected 'key: value'")
        if key in data:
            raise ContractError(f"line {n}: duplicate key '{key}'")
        value = value.strip()
        if value == "":
            data[key] = []
            current = key
        elif value.startswith("["):
            if not value.endswith("]"):
                raise ContractError(f"line {n}: unterminated inline list")
            inner = value[1:-1].strip()
            data[key] = [_scalar(p) for p in inner.split(",") if p.strip()]
            current = None
        else:
            data[key] = _scalar(value)
            current = None
    return data, "\n".join(lines[end + 1 :]).strip("\n")


def validate_data(data: dict) -> list[str]:
    """Return schema problems for a parsed front matter dict (empty = valid)."""
    errors: list[str] = []
    for key in REQUIRED_FIELDS:
        if key not in data:
            errors.append(f"missing required field '{key}'")
    for key in data:
        if key not in KNOWN_FIELDS:
            errors.append(f"unknown field '{key}'")
    name = data.get("name")
    if name is not None and not (isinstance(name, str) and NAME_RE.match(name)):
        errors.append(f"name {name!r} must match {NAME_RE.pattern}")
    kind = data.get("kind")
    if kind is not None and kind not in KINDS:
        errors.append(f"kind {kind!r} must be one of {', '.join(KINDS)}")
    purpose = data.get("purpose")
    if purpose is not None and not (isinstance(purpose, str) and purpose.strip()):
        errors.append("purpose must be a non-empty string")
    for key in LIST_FIELDS:
        if key not in data:
            continue
        value = data[key]
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            errors.append(f"{key} must be a list of non-empty strings")
            continue
        if key in ("allow_read", "allow_write"):
            for pat in value:
                if pat.startswith("/") or ".." in pat.split("/"):
                    errors.append(f"{key}: pattern {pat!r} must be relative and may not contain '..'")
        if len(set(value)) != len(value):
            errors.append(f"{key} contains duplicates")
    if kind == "verifier":
        if data.get("allow_write"):
            errors.append("a verifier may not have allow_write (verifiers are read-only)")
        if not data.get("requires_evidence"):
            errors.append("a verifier must declare requires_evidence")
    if kind == "builder" and not data.get("requires_evidence"):
        errors.append("a builder must declare requires_evidence")
    return errors


def load_contract(path: str | Path) -> Contract:
    """Parse and validate one contract file. Raises ContractError on any problem."""
    p = Path(path)
    try:
        data, body = parse_front_matter(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractError(f"{p}: cannot read: {exc}") from exc
    except ContractError as exc:
        raise ContractError(f"{p}: {exc}") from exc
    errors = validate_data(data)
    if errors:
        raise ContractError(f"{p}: " + "; ".join(errors))
    return Contract(body=body, path=str(p), **data)


def load_contracts(directory: str | Path) -> dict[str, Contract]:
    """Load every ``*.md`` contract in a directory, keyed by name."""
    d = Path(directory)
    if not d.is_dir():
        raise ContractError(f"{d}: not a directory")
    contracts: dict[str, Contract] = {}
    problems: list[str] = []
    for f in sorted(d.glob("*.md")):
        try:
            c = load_contract(f)
        except ContractError as exc:
            problems.append(str(exc))
            continue
        if c.name in contracts:
            problems.append(f"{f}: duplicate contract name '{c.name}'")
            continue
        contracts[c.name] = c
    problems += validate_set(contracts)
    if problems:
        raise ContractError("\n".join(problems))
    return contracts


def _glob_overlap_examples(a: str, b: str) -> bool:
    """Conservative check: do two write patterns obviously cover the same files?"""
    if a == b:
        return True
    pa, pb = a.rstrip("*/"), b.rstrip("*/")
    return ("**" in a and pb.startswith(pa)) or ("**" in b and pa.startswith(pb))


def validate_set(contracts: dict[str, Contract]) -> list[str]:
    """Cross-contract rules: verifiers may not share write scope with builders."""
    errors: list[str] = []
    builders = [c for c in contracts.values() if c.kind == "builder"]
    verifiers = [c for c in contracts.values() if c.kind == "verifier"]
    for v in verifiers:
        for b in builders:
            for pat in v.allow_write:
                if any(_glob_overlap_examples(pat, bp) for bp in b.allow_write):
                    errors.append(f"verifier '{v.name}' write scope overlaps builder '{b.name}': {pat}")
    return errors
