"""Enforcement engine: run a task through a Builder then an independent Verifier.

A run is REJECTED (never silently accepted) when:
  SELF_VERIFICATION  the verifier is the builder's role, the same agent, or a
                     role whose contract lists the builder's role in cannot_verify
  BOUNDARY           an action touches a file, tool or action outside the
                     acting role's allow-list (declared OR observed on disk)
  EVIDENCE           required evidence is missing, empty, points at a missing
                     file, fails its sha256, or the verifier only reuses the
                     builder's evidence
  VERDICT            the verifier did not return verdict "pass"
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .contract import Contract

SELF_VERIFICATION = "SELF_VERIFICATION"
BOUNDARY = "BOUNDARY"
EVIDENCE = "EVIDENCE"
VERDICT = "VERDICT"
ACTION_TYPES = {"read": "allow_read", "write": "allow_write", "tool": "allow_tools", "action": "allow_actions"}
IGNORED_DIRS = {".git", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache"}


class TaskError(ValueError):
    """The task file itself is malformed."""


@dataclass
class Violation:
    rule: str
    phase: str
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.phase}: {self.message}"


@dataclass
class RunResult:
    task: str
    violations: list[Violation] = field(default_factory=list)
    evidence_log: list[dict] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "result": "ACCEPTED" if self.accepted else "REJECTED",
            "violations": [vars(v) for v in self.violations],
            "evidence_log": self.evidence_log,
        }


def glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a path glob: ``*`` stays inside a segment, ``**`` crosses them."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out + r"\Z")


def normalize(target: str) -> str | None:
    """Normalise a relative path; None if it is absolute or escapes the workdir."""
    if target.startswith("/") or "\\" in target:
        return None
    parts: list[str] = []
    for seg in target.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


def path_allowed(patterns: list[str], target: str) -> bool:
    norm = normalize(target)
    return norm is not None and any(glob_to_regex(p).match(norm) for p in patterns)


def check_actions(contract: Contract, actions: list[dict], phase: str) -> list[Violation]:
    out: list[Violation] = []
    for act in actions:
        typ, target = act.get("type"), act.get("target")
        if typ not in ACTION_TYPES or not isinstance(target, str) or not target:
            out.append(Violation(BOUNDARY, phase, f"malformed action {act!r}"))
            continue
        allow = getattr(contract, ACTION_TYPES[typ])
        ok = path_allowed(allow, target) if typ in ("read", "write") else target in allow
        if not ok:
            out.append(
                Violation(BOUNDARY, phase, f"role '{contract.name}' may not {typ} '{target}' (not in {ACTION_TYPES[typ]})")
            )
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    snap: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and not (set(rel.parts) & IGNORED_DIRS):
            snap[rel.as_posix()] = _sha256(p)
    return snap


def _tool_name(exe: str) -> str:
    """Basename without version suffix: /x/bin/python3.12 -> python."""
    return re.sub(r"[\d.]+$", "", exe.rsplit("/", 1)[-1])


def run_evidence_command(
    item: dict, contract: Contract, root: Path, phase: str, log: list[dict]
) -> tuple[str | None, list[Violation]]:
    """Execute an evidence command ourselves. Returns (problem or None, violations)."""
    cmd = item.get("command")
    if not (isinstance(cmd, list) and cmd and all(isinstance(c, str) and c for c in cmd)):
        return "command must be a non-empty list of strings", []
    tool = _tool_name(cmd[0])
    if tool not in contract.allow_tools:
        return f"tool '{tool}' not allowed", [
            Violation(BOUNDARY, phase, f"role '{contract.name}' may not run tool '{tool}' (not in allow_tools)")
        ]
    before = snapshot(root)
    try:
        proc = subprocess.run(cmd, check=False, cwd=root, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"command could not run: {exc}", []
    after = snapshot(root)
    changed = [f for f in after if before.get(f) != after[f]] + [f for f in before if f not in after]
    violations = check_actions(contract, [{"type": "write", "target": f} for f in changed], phase)
    log.append({
        "phase": phase, "kind": item.get("kind"), "command": cmd, "exit_code": proc.returncode,
        "output": (proc.stdout + proc.stderr)[-500:],
    })
    if proc.returncode != 0:
        return f"command {' '.join(cmd)!r} exited {proc.returncode} (failing check)", violations
    return None, violations


def check_evidence(contract: Contract, report: dict, root: Path, phase: str, log: list[dict]) -> list[Violation]:
    """Check required evidence. A verifier's evidence must be grounded (see _evidence_problem)."""
    out: list[Violation] = []
    items = report.get("evidence")
    if not isinstance(items, list):
        items = []
    grounded = contract.kind == "verifier"
    by_kind: dict[str, list[dict]] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("kind"), str):
            by_kind.setdefault(item["kind"], []).append(item)
    for kind in contract.requires_evidence:
        problems = []
        ok = False
        for item in by_kind.get(kind, []):
            if grounded and "command" in item:
                problem, viol = run_evidence_command(item, contract, root, phase, log)
                out += viol
            else:
                problem = _evidence_problem(item, root, grounded)
            if problem is None:
                ok = True
            else:
                problems.append(problem)
        if not ok:
            detail = problems[0] if problems else "none provided"
            out.append(Violation(EVIDENCE, phase, f"required evidence '{kind}' missing: {detail}"))
    if grounded:
        # A "pass" is void if any evidence command the engine ran actually failed.
        for entry in log:
            if entry["phase"] == phase and entry["exit_code"] != 0 and report.get("verdict") == "pass":
                out.append(Violation(
                    VERDICT, phase, f"verdict 'pass' contradicts own evidence: {' '.join(entry['command'])!r} "
                    f"exited {entry['exit_code']}"))
    return out


def _evidence_problem(item: dict, root: Path, grounded: bool = False) -> str | None:
    """Static check of one non-command evidence item.

    Builder evidence may be inline text or a file ref. Verifier evidence ("grounded") may not be
    bare text: it must be a file ref whose sha256 the engine verifies, or a command the engine runs.
    """
    ref, text = item.get("ref"), item.get("text")
    if grounded:
        if not isinstance(ref, str) or not ref:
            return "verifier evidence must be a command the engine runs or a file ref with sha256, not bare text"
        if not item.get("sha256"):
            return f"verifier file ref '{ref}' needs a sha256"
    elif isinstance(text, str) and text.strip():
        return None
    if not isinstance(ref, str) or not ref:
        return "no ref or text"
    norm = normalize(ref)
    if norm is None or not (root / norm).is_file():
        return f"file '{ref}' does not exist"
    if (root / norm).stat().st_size == 0:
        return f"file '{ref}' is empty"
    want = item.get("sha256")
    if want and want != _sha256(root / norm):
        return f"sha256 mismatch for '{ref}'"
    return None


def _evidence_keys(report: dict) -> set[str]:
    keys = set()
    for item in report.get("evidence") or []:
        if isinstance(item, dict):
            keys.add(item.get("ref") or item.get("text") or "")
    return keys - {""}


def execute_phase(spec: dict, root: Path, phase: str) -> tuple[dict, list[dict]]:
    """Run one phase. Returns (report, observed write actions)."""
    if "report" in spec:
        if not isinstance(spec["report"], dict):
            raise TaskError(f"{phase}: report must be an object")
        return spec["report"], []
    cmd = spec.get("command")
    if not (isinstance(cmd, list) and cmd and all(isinstance(c, str) for c in cmd)):
        raise TaskError(f"{phase}: needs either 'report' (object) or 'command' (list of strings)")
    before = snapshot(root)
    try:
        proc = subprocess.run(cmd, check=False, cwd=root, capture_output=True, text=True, timeout=spec.get("timeout", 60))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TaskError(f"{phase}: command failed to run: {exc}") from exc
    if proc.returncode != 0:
        raise TaskError(f"{phase}: command exited {proc.returncode}: {proc.stderr.strip()[-300:]}")
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise TaskError(f"{phase}: command did not print a JSON report: {exc}") from exc
    if not isinstance(report, dict):
        raise TaskError(f"{phase}: report must be a JSON object")
    after = snapshot(root)
    changed = [f for f in after if before.get(f) != after[f]] + [f for f in before if f not in after]
    return report, [{"type": "write", "target": f} for f in changed]


def run_task(task: dict, contracts: dict[str, Contract], base_dir: Path) -> RunResult:
    """Enforce the Builder-Verifier rules on ``task``. Never mutates ``base_dir``."""
    for key in ("task", "builder", "verifier"):
        if key not in task:
            raise TaskError(f"task file missing '{key}'")
    result = RunResult(task=str(task["task"]))
    phases = {}
    for phase in ("builder", "verifier"):
        spec = task[phase]
        if not isinstance(spec, dict) or not spec.get("role") or not spec.get("agent"):
            raise TaskError(f"{phase}: needs 'role' and 'agent'")
        if spec["role"] not in contracts:
            raise TaskError(f"{phase}: unknown role '{spec['role']}'")
        phases[phase] = (spec, contracts[spec["role"]])
    (b_spec, b_con), (v_spec, v_con) = phases["builder"], phases["verifier"]
    if b_con.kind != "builder":
        raise TaskError(f"builder phase uses role '{b_con.name}' of kind '{b_con.kind}'")

    # Rule: independence. Checked before anything runs.
    if v_con.kind != "verifier":
        result.violations.append(
            Violation(SELF_VERIFICATION, "verifier", f"role '{v_con.name}' is kind '{v_con.kind}', not a verifier")
        )
    if v_con.name == b_con.name:
        result.violations.append(Violation(SELF_VERIFICATION, "verifier", f"role '{v_con.name}' verifies its own work"))
    if v_spec["agent"] == b_spec["agent"]:
        result.violations.append(
            Violation(SELF_VERIFICATION, "verifier", f"agent '{v_spec['agent']}' verifies its own work")
        )
    if b_con.name in v_con.cannot_verify:
        result.violations.append(
            Violation(SELF_VERIFICATION, "verifier", f"contract '{v_con.name}' forbids verifying role '{b_con.name}'")
        )
    if result.violations:
        return result

    with tempfile.TemporaryDirectory(prefix="agency-studio-") as tmp:
        root = Path(tmp) / "work"
        workdir = (base_dir / task.get("workdir", ".")).resolve()
        if not workdir.is_dir():
            raise TaskError(f"workdir '{workdir}' does not exist")
        shutil.copytree(workdir, root, ignore=shutil.ignore_patterns(*IGNORED_DIRS))
        reports = {}
        for phase, (spec, con) in phases.items():
            report, observed = execute_phase(spec, root, phase)
            reports[phase] = report
            declared = report.get("actions") or []
            if not isinstance(declared, list):
                raise TaskError(f"{phase}: actions must be a list")
            result.violations += check_actions(con, declared + observed, phase)
            result.violations += check_evidence(con, report, root, phase, result.evidence_log)
        ran = any(e["phase"] == "verifier" and e["exit_code"] == 0 for e in result.evidence_log)
        if not ran and not (_evidence_keys(reports["verifier"]) - _evidence_keys(reports["builder"])):
            result.violations.append(
                Violation(EVIDENCE, "verifier", "verifier evidence is identical to (or empty versus) the builder's")
            )
        if reports["verifier"].get("verdict") != "pass":
            result.violations.append(
                Violation(VERDICT, "verifier", f"verifier verdict is {reports['verifier'].get('verdict')!r}, not 'pass'")
            )
    return result


def load_task(path: str | Path) -> tuple[dict, Path]:
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8")), p.parent
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskError(f"{p}: {exc}") from exc


__all__ = ["RunResult", "TaskError", "Violation", "load_task", "path_allowed", "run_task"]
