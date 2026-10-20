import json
from pathlib import Path

from agency_studio.cli import main

ROOT = Path(__file__).resolve().parents[1]
GOOD = """---
name: sample
kind: scout
purpose: Look around.
allow_read: [docs/**]
requires_evidence: [diff]
---
# sample
"""


def test_validate_directory(capsys):
    assert main(["validate", str(ROOT / "roles")]) == 0
    out = capsys.readouterr().out
    assert "6 contracts valid" in out


def test_validate_single_file(tmp_path, capsys):
    f = tmp_path / "sample.md"
    f.write_text(GOOD)
    assert main(["validate", str(f)]) == 0
    assert "OK" in capsys.readouterr().out


def test_validate_invalid_file(tmp_path, capsys):
    f = tmp_path / "sample.md"
    f.write_text("---\nname: x\n---\n")
    assert main(["validate", str(f)]) == 1
    assert "INVALID" in capsys.readouterr().err


def test_roles_listing(capsys):
    assert main(["roles"]) == 0
    out = capsys.readouterr().out
    assert out.split()[0] == "builder" and "verifier" in out


def test_run_rejects_bad_input(tmp_path):
    f = tmp_path / "task.json"
    f.write_text("{}")
    assert main(["run", str(f)]) == 2


def test_run_json_output(capsys):
    rc = main(["run", str(ROOT / "examples" / "pass" / "task.json"), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["result"] == "ACCEPTED"


def test_run_blocked_example():
    rc = main(["run", str(ROOT / "examples" / "blocked-self-verify" / "task.json")])
    assert rc == 1
