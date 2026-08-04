#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for r in scout planner builder reviewer verifier documenter; do test -f "roles/$r.md"; done
echo "agency-studio smoke PASS"
