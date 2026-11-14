#!/usr/bin/env bash
# check_platform_pinned.sh — guard 4c.
#
#   check_platform_pinned.sh <generated-repo-dir> <xp-platform-repo-dir> <platform-tag>
#
# The generated repo's platform/ must be byte-identical to the pinned platform tag. We
# compare git TREE hashes, which are canonical (same files + modes => same SHA): the tree
# hash of the generated repo's platform/ subtree must equal the tagged tree hash of the
# xp-platform repo root. If a quant edits anything under platform/, the hashes diverge and
# this fails — telling them to open an MR on xp-platform instead of patching their copy.
set -uo pipefail

gen=${1:?usage: check_platform_pinned.sh <generated-repo> <xp-platform-repo> <tag>}
platform_repo=${2:?missing xp-platform repo dir}
tag=${3:?missing platform tag}

expected=$(git -C "$platform_repo" rev-parse "${tag}^{tree}" 2>/dev/null) || {
  echo "FAIL guard 4c — cannot resolve tag '$tag' in $platform_repo"; exit 2; }
actual=$(git -C "$gen" rev-parse "HEAD:platform" 2>/dev/null) || {
  echo "FAIL guard 4c — generated repo has no committed platform/ subtree"; exit 2; }

if [ "$expected" = "$actual" ]; then
  echo "ok   guard 4c — platform/ matches ${tag} (tree ${actual})"
  exit 0
fi
echo "FAIL guard 4c — platform/ modified — open an MR on xp-platform"
echo "     expected ${tag} tree: $expected"
echo "     generated platform/:  $actual"
exit 1
