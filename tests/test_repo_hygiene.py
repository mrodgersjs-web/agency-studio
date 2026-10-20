"""Repository hygiene checks, asserted from the files on disk.

These guard the reader-facing contract: CODEOWNERS ownership, the copilot
instructions bound and test command, the README badge and footer, and CI jobs
that always carry a timeout and never hide a failure.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_codeowners_assigns_every_file_to_the_org() -> None:
    owners = (ROOT / ".github" / "CODEOWNERS").read_text()
    assert re.search(r"^\*\s+@mrodgersjs-web\s*$", owners, re.MULTILINE)


def test_copilot_instructions_bounded_and_name_a_test_command() -> None:
    doc = (ROOT / ".github" / "copilot-instructions.md").read_text()
    assert doc.strip(), "copilot-instructions.md must not be empty"
    assert len(doc) <= 8000, f"copilot-instructions.md is {len(doc)} bytes, limit 8000"
    assert re.search(r"pytest|smoke|npm test", doc), "must name a test command"


def test_readme_carries_badge_footer_and_only_self_clones() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "github/actions/workflow/status" in readme, "needs a workflow status badge"
    assert "Built by Mike Rodgers" in readme, "needs the footer"
    assert "rodgersintelligence.com" in readme, "needs the site in the footer"
    assert re.search(r"pytest|smoke|npm test|node --test", readme), "needs a test command"
    for line in readme.splitlines():
        if "git clone" in line:
            assert "mrodgersjs-web/agency-studio" in line, f"clone must target this repo: {line}"


def test_every_workflow_job_sets_timeout_and_never_continues_on_error() -> None:
    wf_dir = ROOT / ".github" / "workflows"
    files = sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml"))
    assert files, "at least one workflow must exist"
    for path in files:
        text = path.read_text()
        assert not re.search(r"continue-on-error:\s*true", text), f"{path.name} continues on error"
        jobs: list[tuple[str, bool]] = []
        current: str | None = None
        has_timeout = False
        in_jobs = False
        for line in text.splitlines():
            if re.match(r"^jobs:\s*$", line):
                in_jobs = True
                continue
            if not in_jobs:
                continue
            job = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
            if job:
                if current:
                    jobs.append((current, has_timeout))
                current, has_timeout = job.group(1), False
                continue
            if re.match(r"^[A-Za-z]", line):
                if current:
                    jobs.append((current, has_timeout))
                current, in_jobs = None, False
                continue
            if current and re.match(r"^\s+timeout-minutes:\s*\d+", line):
                has_timeout = True
        if current:
            jobs.append((current, has_timeout))
        assert jobs, f"{path.name} declares no jobs"
        for name, timed in jobs:
            assert timed, f'{path.name} job "{name}" must set timeout-minutes'
