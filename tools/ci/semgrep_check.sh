#!/usr/bin/env bash
# semgrep_check.sh — validate the build-hygiene ruleset and run its ruleid/ok test cases.
#   tools/ci/semgrep_check.sh              # needs semgrep on PATH (CI: the xp-ci-reviewer image,
#                                          # so the rules are tested with the reviewer's semgrep)
# Runs from inside .semgrep/: semgrep 1.x skips rule files whose parent directory starts with
# a dot (semgrep/test.py), so `semgrep --test .semgrep/` would find no tests at all.
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || dirname "$0")/.semgrep" 2>/dev/null \
  || cd "$(dirname "$0")/../../.semgrep"
semgrep --version
semgrep --validate --metrics=off --config cpp-build.yml
out="$(semgrep --test --metrics=off . 2>&1)" || { echo "${out}"; exit 1; }
echo "${out}" | grep -E "tests? passed|✓|✖" 
grep -q "All tests passed" <<<"${out}" || { echo "${out}"; exit 1; }
