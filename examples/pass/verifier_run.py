"""Sample verifier: re-runs the check itself, writes nothing, reports inline evidence."""
import json
import subprocess
import sys

run = subprocess.run([sys.executable, "tests/check_greeting.py"], capture_output=True, text=True)
print(json.dumps({
    "actions": [
        {"type": "read", "target": "src/greeting.py"},
        {"type": "read", "target": "tests/check_greeting.py"},
        {"type": "tool", "target": "python"},
    ],
    "evidence": [{"kind": "test_output", "text": "independent re-run: " + run.stdout.strip()}],
    "verdict": "pass" if run.returncode == 0 else "fail",
}))
