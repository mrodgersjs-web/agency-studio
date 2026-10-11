#!/usr/bin/env bash
# End-to-end smoke: validate shipped contracts, accept a sound run, block self-verification.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
"$PY" -m agency_studio.cli validate roles
"$PY" -m agency_studio.cli run examples/pass/task.json
if "$PY" -m agency_studio.cli run examples/blocked-self-verify/task.json; then
  echo "smoke FAIL: self-verification was not blocked" >&2
  exit 1
else
  code=$?
  test "$code" -eq 1 || { echo "smoke FAIL: expected exit 1, got $code" >&2; exit 1; }
fi
echo "agency-studio smoke PASS"
