"""Each rejection rule must fire; the sound run must pass."""

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

from agency_studio.cli import main
from agency_studio.contract import ContractError, load_contracts
from agency_studio.engine import BOUNDARY, EVIDENCE, SELF_VERIFICATION, VERDICT, TaskError, run_task

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = load_contracts(ROOT / "roles")
PASS_DIR = ROOT / "examples" / "pass"


def good_task():
    return json.loads((PASS_DIR / "task.json").read_text())


def rules(result):
    return {v.rule for v in result.violations}


def inline(builder_report=None, verifier_report=None, **overrides):
    """A task with inline reports over a scratch workdir (so no commands run)."""
    b = {"actions": [{"type": "write", "target": "src/a.py"}], "evidence": [
        {"kind": "diff", "text": "+ a"}, {"kind": "test_output", "text": "1 passed"}]}
    v = {"actions": [{"type": "read", "target": "src/a.py"}],
         "evidence": [{"kind": "test_output", "text": "re-run: 1 passed"}], "verdict": "pass"}
    task = {
        "task": "t", "workdir": ".",
        "builder": {"role": "builder", "agent": "a1", "report": builder_report or b},
        "verifier": {"role": "verifier", "agent": "a2", "report": verifier_report or v},
    }
    task.update(overrides)
    return task


def test_end_to_end_pass_leaves_workdir_untouched():
    before = sorted(p.name for p in PASS_DIR.rglob("*"))
    result = run_task(good_task(), CONTRACTS, PASS_DIR)
    assert result.accepted, [str(v) for v in result.violations]
    assert sorted(p.name for p in PASS_DIR.rglob("*")) == before


def test_inline_baseline_accepted(tmp_path):
    assert run_task(inline(), CONTRACTS, tmp_path).accepted


def test_self_verification_same_agent():
    task = good_task()
    task["verifier"]["agent"] = task["builder"]["agent"]
    result = run_task(task, CONTRACTS, PASS_DIR)
    assert rules(result) == {SELF_VERIFICATION}
    assert "agent" in result.violations[0].message


def test_self_verification_same_role(tmp_path):
    task = inline()
    task["verifier"]["role"] = "builder"
    assert SELF_VERIFICATION in rules(run_task(task, CONTRACTS, tmp_path))


def test_self_verification_non_verifier_role(tmp_path):
    task = inline()
    task["verifier"]["role"] = "reviewer"
    assert SELF_VERIFICATION in rules(run_task(task, CONTRACTS, tmp_path))


def test_self_verification_blocks_before_anything_runs():
    task = good_task()
    task["verifier"]["agent"] = task["builder"]["agent"]
    task["builder"]["command"] = ["python3", "does_not_exist.py"]  # would raise TaskError if it ran
    assert rules(run_task(task, CONTRACTS, PASS_DIR)) == {SELF_VERIFICATION}


def test_boundary_declared_write_outside_allow_list(tmp_path):
    task = inline()
    task["builder"]["report"]["actions"].append({"type": "write", "target": ".github/workflows/x.yml"})
    result = run_task(task, CONTRACTS, tmp_path)
    assert rules(result) == {BOUNDARY}
    assert ".github/workflows/x.yml" in result.violations[0].message


def test_boundary_path_traversal(tmp_path):
    task = inline()
    task["builder"]["report"]["actions"].append({"type": "write", "target": "src/../../etc/passwd"})
    assert BOUNDARY in rules(run_task(task, CONTRACTS, tmp_path))


def test_boundary_disallowed_tool_and_action(tmp_path):
    task = inline()
    task["builder"]["report"]["actions"] += [
        {"type": "tool", "target": "curl"}, {"type": "action", "target": "git_push"}]
    result = run_task(task, CONTRACTS, tmp_path)
    assert [v.rule for v in result.violations] == [BOUNDARY, BOUNDARY]


def test_boundary_verifier_cannot_write(tmp_path):
    task = inline()
    task["verifier"]["report"]["actions"].append({"type": "write", "target": "evidence/x.txt"})
    result = run_task(task, CONTRACTS, tmp_path)
    assert rules(result) == {BOUNDARY} and result.violations[0].phase == "verifier"


def test_boundary_malformed_action(tmp_path):
    task = inline()
    task["builder"]["report"]["actions"].append({"type": "teleport", "target": "x"})
    assert BOUNDARY in rules(run_task(task, CONTRACTS, tmp_path))


def test_boundary_observed_undeclared_write(tmp_path):
    """A command that writes a forbidden file without declaring it is still caught."""
    script = tmp_path / "sneaky.py"
    script.write_text(
        "import json,pathlib\npathlib.Path('secrets.txt').write_text('x')\n"
        "print(json.dumps({'actions': [], 'evidence': [{'kind':'diff','text':'d'},{'kind':'test_output','text':'t'}]}))\n"
    )
    task = inline()
    task["builder"] = {"role": "builder", "agent": "a1", "command": [sys.executable, "sneaky.py"]}
    result = run_task(task, CONTRACTS, tmp_path)
    assert rules(result) == {BOUNDARY}
    assert "secrets.txt" in result.violations[0].message
    assert not (tmp_path / "secrets.txt").exists()  # ran in a copy


def test_evidence_missing_kind(tmp_path):
    task = inline()
    task["builder"]["report"]["evidence"] = [{"kind": "diff", "text": "+ a"}]
    result = run_task(task, CONTRACTS, tmp_path)
    assert rules(result) == {EVIDENCE} and "test_output" in result.violations[0].message


def test_evidence_empty_report(tmp_path):
    task = inline()
    del task["verifier"]["report"]["evidence"]
    assert EVIDENCE in rules(run_task(task, CONTRACTS, tmp_path))


def test_evidence_file_missing_empty_and_bad_sha(tmp_path):
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / "real.txt").write_text("ok")
    for ref, extra, needle in [
        ("nope.txt", {}, "does not exist"),
        ("empty.txt", {}, "empty"),
        ("real.txt", {"sha256": "0" * 64}, "sha256"),
    ]:
        task = inline()
        task["builder"]["report"]["evidence"][1] = {"kind": "test_output", "ref": ref, **extra}
        result = run_task(task, CONTRACTS, tmp_path)
        assert rules(result) == {EVIDENCE}, ref
        assert needle in result.violations[0].message


def test_evidence_verifier_reuses_builder_evidence(tmp_path):
    task = inline()
    task["verifier"]["report"]["evidence"] = copy.deepcopy(task["builder"]["report"]["evidence"][1:])
    result = run_task(task, CONTRACTS, tmp_path)
    assert rules(result) == {EVIDENCE} and "identical" in result.violations[0].message


def test_verdict_fail_rejects(tmp_path):
    task = inline()
    task["verifier"]["report"]["verdict"] = "fail"
    assert rules(run_task(task, CONTRACTS, tmp_path)) == {VERDICT}


def test_malformed_task_raises(tmp_path):
    with pytest.raises(TaskError):
        run_task({"task": "x"}, CONTRACTS, tmp_path)
    task = inline()
    task["builder"]["role"] = "ghost"
    with pytest.raises(TaskError):
        run_task(task, CONTRACTS, tmp_path)
    task = inline()
    task["builder"] = {"role": "builder", "agent": "a1", "command": [sys.executable, "-c", "print('not json')"]}
    with pytest.raises(TaskError, match="JSON"):
        run_task(task, CONTRACTS, tmp_path)


def test_cli_exit_codes(capsys, monkeypatch):
    monkeypatch.chdir(ROOT)
    assert main(["validate", "roles"]) == 0
    assert main(["run", "examples/pass/task.json"]) == 0
    assert "ACCEPTED" in capsys.readouterr().out
    assert main(["run", "examples/blocked-self-verify/task.json"]) == 1
    assert "SELF_VERIFICATION" in capsys.readouterr().out
    assert main(["run", "examples/missing.json"]) == 2


def test_cli_validate_rejects_bad_contract(tmp_path, capsys):
    bad = tmp_path / "bad.md"
    bad.write_text("---\nname: v\nkind: verifier\npurpose: p\nrequires_evidence: [x]\nallow_write: [src/**]\n---\n")
    assert main(["validate", str(bad)]) == 1
    assert "read-only" in capsys.readouterr().err


def test_self_verification_cannot_verify_clause(tmp_path):
    roles = tmp_path / "roles"
    shutil.copytree(ROOT / "roles", roles)
    text = (roles / "verifier.md").read_text().replace(
        "allow_tools: [python, pytest]", "allow_tools: [python, pytest]\ncannot_verify: [builder]")
    (roles / "verifier.md").write_text(text)
    result = run_task(inline(), load_contracts(roles), tmp_path)
    assert rules(result) == {SELF_VERIFICATION} and "forbids" in result.violations[0].message


def test_static_overlap_rejected(tmp_path):
    shutil.copy(ROOT / "roles" / "builder.md", tmp_path / "builder.md")
    (tmp_path / "v.md").write_text(
        "---\nname: v\nkind: verifier\npurpose: p\nrequires_evidence: [x]\nallow_write: [src/**]\n---\n")
    with pytest.raises(ContractError):  # a verifier with write scope is invalid on its own
        load_contracts(tmp_path)
    (tmp_path / "v.md").write_text(
        "---\nname: v\nkind: verifier\npurpose: p\nrequires_evidence: [x]\n---\n")
    assert "v" in load_contracts(tmp_path)
