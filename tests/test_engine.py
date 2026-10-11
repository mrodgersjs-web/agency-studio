"""Each rejection rule must fire; the sound run must pass."""

import json
import shlex
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
         "evidence": [{"kind": "test_output", "command": [sys.executable, "-c", "print('re-run: 1 passed')"]}],
         "verdict": "pass"}
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




def test_disallowed_builder_phase_command_does_not_execute(tmp_path):
    marker = tmp_path / "builder-ran.txt"
    task = inline()
    payload = json.dumps({
        "actions": [],
        "evidence": [{"kind": "diff", "text": "d"}, {"kind": "test_output", "text": "t"}],
    })
    task["builder"] = {
        "role": "builder",
        "agent": "a1",
        "command": ["bash", "-c", f"touch {marker}; printf '%s\n' {shlex.quote(payload)}"],
    }
    result = run_task(task, CONTRACTS, tmp_path)
    assert rules(result) == {BOUNDARY}
    assert result.violations[0].phase == "builder"
    assert "bash" in result.violations[0].message
    assert not marker.exists()


def test_disallowed_verifier_phase_command_does_not_execute(tmp_path):
    marker = tmp_path / "verifier-ran.txt"
    task = inline()
    payload = json.dumps({
        "actions": [],
        "evidence": [{"kind": "test_output", "text": "t"}],
        "verdict": "pass",
    })
    task["verifier"] = {
        "role": "verifier",
        "agent": "a2",
        "command": ["bash", "-c", f"touch {marker}; printf '%s\n' {shlex.quote(payload)}"],
    }
    result = run_task(task, CONTRACTS, tmp_path)
    assert rules(result) == {BOUNDARY}
    assert result.violations[0].phase == "verifier"
    assert "bash" in result.violations[0].message
    assert not marker.exists()


def test_allowed_builder_phase_command_still_executes(tmp_path):
    script = tmp_path / "builder.py"
    script.write_text(
        "import json\n"
        "print(json.dumps({"
        "'actions': [], "
        "'evidence': [{'kind':'diff','text':'d'}, {'kind':'test_output','text':'t'}]"
        "}))\n"
    )
    task = inline()
    task["builder"] = {"role": "builder", "agent": "a1", "command": [sys.executable, "builder.py"]}
    result = run_task(task, CONTRACTS, tmp_path)
    assert result.accepted, [str(v) for v in result.violations]


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


def test_evidence_verifier_reuses_builder_file_evidence(tmp_path):
    import hashlib
    (tmp_path / "out.txt").write_text("1 passed")
    sha = hashlib.sha256(b"1 passed").hexdigest()
    item = {"kind": "test_output", "ref": "out.txt", "sha256": sha}
    task = inline()
    task["builder"]["report"]["evidence"][1] = dict(item)
    task["verifier"]["report"]["evidence"] = [dict(item)]
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


# --- grounded verifier evidence (reviewer's case and its neighbours) ---------------------------


def failing_workdir(tmp_path):
    """A builder whose test genuinely fails; its output file holds the traceback."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def f():\n    return 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "check_x.py").write_text("import sys\nsys.path.insert(0, 'src')\nfrom x import f\nassert f() == 2\n")
    (tmp_path / "tb.txt").write_text("AssertionError\n")
    return {
        "actions": [],
        "evidence": [{"kind": "diff", "text": "+ x"}, {"kind": "test_output", "ref": "tb.txt"}],
    }


def test_reviewer_case_bare_text_pass_over_failing_builder_is_rejected(tmp_path):
    task = inline(builder_report=failing_workdir(tmp_path), verifier_report={
        "actions": [], "evidence": [{"kind": "test_output", "text": "all good"}], "verdict": "pass"})
    result = run_task(task, CONTRACTS, tmp_path)
    assert not result.accepted
    assert rules(result) == {EVIDENCE}
    assert "bare text" in result.violations[0].message


def test_verifier_pass_contradicted_by_its_own_failing_command(tmp_path):
    task = inline(builder_report=failing_workdir(tmp_path), verifier_report={
        "actions": [],
        "evidence": [{"kind": "test_output", "command": [sys.executable, "tests/check_x.py"]}],
        "verdict": "pass"})
    result = run_task(task, CONTRACTS, tmp_path)
    assert {EVIDENCE, VERDICT} <= rules(result)
    assert result.evidence_log[-1]["exit_code"] == 1
    assert "AssertionError" in result.evidence_log[-1]["output"]


def test_honest_verifier_with_executed_command_passes(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def f():\n    return 2\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "check_x.py").write_text("import sys\nsys.path.insert(0, 'src')\nfrom x import f\nassert f() == 2\n")
    task = inline(verifier_report={
        "actions": [{"type": "read", "target": "tests/check_x.py"}],
        "evidence": [{"kind": "test_output", "command": [sys.executable, "tests/check_x.py"]}],
        "verdict": "pass"})
    result = run_task(task, CONTRACTS, tmp_path)
    assert result.accepted, [str(v) for v in result.violations]
    assert result.evidence_log[-1]["exit_code"] == 0


def test_honest_verifier_with_sha_checked_file_passes(tmp_path):
    import hashlib
    (tmp_path / "check.log").write_text("checked: ok\n")
    sha = hashlib.sha256(b"checked: ok\n").hexdigest()
    task = inline(verifier_report={
        "actions": [], "evidence": [{"kind": "test_output", "ref": "check.log", "sha256": sha}], "verdict": "pass"})
    assert run_task(task, CONTRACTS, tmp_path).accepted


def test_verifier_file_ref_without_or_with_wrong_sha_rejected(tmp_path):
    (tmp_path / "check.log").write_text("ok")
    for extra, needle in [({}, "needs a sha256"), ({"sha256": "0" * 64}, "sha256 mismatch")]:
        task = inline(verifier_report={
            "actions": [], "evidence": [{"kind": "test_output", "ref": "check.log", **extra}], "verdict": "pass"})
        result = run_task(task, CONTRACTS, tmp_path)
        assert rules(result) == {EVIDENCE} and needle in result.violations[0].message


def test_verifier_command_with_unlisted_tool_is_not_run(tmp_path):
    task = inline(verifier_report={
        "actions": [], "evidence": [{"kind": "test_output", "command": ["curl", "http://example.invalid"]}],
        "verdict": "pass"})
    result = run_task(task, CONTRACTS, tmp_path)
    assert BOUNDARY in rules(result) and result.evidence_log == []


def test_verifier_command_that_writes_is_boundary_violation(tmp_path):
    code = "import pathlib; pathlib.Path('planted.txt').write_text('x'); print('ok')"
    task = inline(verifier_report={
        "actions": [], "evidence": [{"kind": "test_output", "command": [sys.executable, "-c", code]}],
        "verdict": "pass"})
    result = run_task(task, CONTRACTS, tmp_path)
    assert BOUNDARY in rules(result) and "planted.txt" in str(result.violations[0])


def test_cli_json_includes_evidence_log(capsys, monkeypatch):
    monkeypatch.chdir(ROOT)
    assert main(["run", "examples/pass/task.json", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["result"] == "ACCEPTED" and data["evidence_log"][0]["exit_code"] == 0
