"""Sample builder: implements greeting(), writes a test and real evidence, prints a run report."""
import hashlib
import json
import pathlib
import subprocess
import sys

src = pathlib.Path("src")
src.mkdir(exist_ok=True)
(src / "greeting.py").write_text('def greeting(name):\n    return f"Hello, {name}!"\n')
tests = pathlib.Path("tests")
tests.mkdir(exist_ok=True)
(tests / "check_greeting.py").write_text(
    "import sys\nsys.path.insert(0, 'src')\nfrom greeting import greeting\n"
    "assert greeting('Ada') == 'Hello, Ada!'\nprint('greeting ok')\n"
)
out = subprocess.run([sys.executable, "tests/check_greeting.py"], capture_output=True, text=True, check=True).stdout
ev = pathlib.Path("evidence/builder")
ev.mkdir(parents=True, exist_ok=True)
(ev / "test-output.txt").write_text(out)
(ev / "diff.txt").write_text("+ src/greeting.py\n+ tests/check_greeting.py\n")
sha = hashlib.sha256((ev / "test-output.txt").read_bytes()).hexdigest()
print(json.dumps({
    "actions": [
        {"type": "write", "target": "src/greeting.py"},
        {"type": "write", "target": "tests/check_greeting.py"},
        {"type": "tool", "target": "python"},
    ],
    "evidence": [
        {"kind": "diff", "ref": "evidence/builder/diff.txt"},
        {"kind": "test_output", "ref": "evidence/builder/test-output.txt", "sha256": sha},
    ],
}))
