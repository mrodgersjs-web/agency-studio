#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
test -f README.md
for r in scout planner builder reviewer verifier documenter; do test -f "roles/$r.md"; done
test -f docs/public-boundary.md
echo "agency-studio smoke PASS"
