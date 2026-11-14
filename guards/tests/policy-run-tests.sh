#!/usr/bin/env bash
# run.sh — test cases for the pricer allow-list guard (gap 3). Mirrors xp-pricer's
# semgrep ruleid/ok convention: the ok case must pass, the bad case must fail.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
guard="$here/../check_pricer_cmakelists.py"
rc=0

python3 "$guard" --selftest || rc=1

if python3 "$guard" "$here/pricer-ok.cmake" >/dev/null; then
  echo "PASS ok-case accepted"
else
  echo "FAIL ok-case should have been accepted"; rc=1
fi

if python3 "$guard" "$here/pricer-bad.cmake" >/dev/null 2>&1; then
  echo "FAIL bad-case should have been rejected"; rc=1
else
  echo "PASS bad-case rejected"
fi

exit $rc
