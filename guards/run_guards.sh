#!/usr/bin/env bash
# run_guards.sh — run all four enforcement guards against a generated repo, from the PINNED
# platform checkout (this directory's repo), not the quant's working tree.
#
#   run_guards.sh <generated-repo-dir> <xp-platform-repo-dir> <platform-tag>
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
gen=${1:?usage: run_guards.sh <generated-repo> <xp-platform-repo> <platform-tag>}
platform_repo=${2:?missing xp-platform repo}
tag=${3:?missing platform tag}
rc=0

echo "== guard 4a: pricer CMakeLists allow-list =="
python3 "$here/check_pricer_cmakelists.py" "$gen"/pricers/*/CMakeLists.txt || rc=1

echo "== guard 4b: no build files outside platform/ =="
python3 "$here/check_forbidden_build_files.py" "$gen" || rc=1

echo "== guard 4c: platform/ pinned to $tag =="
bash "$here/check_platform_pinned.sh" "$gen" "$platform_repo" "$tag" || rc=1

echo "== guard 4d: root CMakeLists.txt thin/platform-owned =="
python3 "$here/check_root_cmakelists.py" "$gen/CMakeLists.txt" || rc=1

echo "== result: $([ $rc -eq 0 ] && echo ALL GUARDS PASS || echo GUARDS FAILED) =="
exit $rc
