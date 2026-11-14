#!/usr/bin/env python3
"""check_forbidden_build_files.py — guard 4b.

Build-system files may exist ONLY inside the copied platform/ zone and as the single
3-line root CMakePresets.json. A quant must not reintroduce presets, vcpkg manifests,
triplets or toolchains elsewhere in a generated repo (that would re-open the door the
split closed). This is a path allow-list, enforced from the pinned platform tag.

    check_forbidden_build_files.py <generated-repo-dir>
Exit 0 = clean, non-zero = a forbidden file was found outside platform/.
"""
from __future__ import annotations
import os
import sys

FORBIDDEN_NAMES = {
    "CMakePresets.json",
    "CMakeUserPresets.json",
    "vcpkg.json",
    "vcpkg-configuration.json",
}
FORBIDDEN_DIRS = {"triplets", "toolchains"}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: check_forbidden_build_files.py <generated-repo-dir>", file=sys.stderr)
        return 2
    root = os.path.abspath(argv[0])
    bad: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        top = rel.split(os.sep)[0]
        if top in (".git", "platform", "build"):
            dirnames[:] = []
            continue
        for d in list(dirnames):
            if d in FORBIDDEN_DIRS:
                bad.append(os.path.join(rel, d) + "/  (triplets/ or toolchains/ belong only in platform/)")
        for f in filenames:
            if f in FORBIDDEN_NAMES:
                # the single root CMakePresets.json is allowed; everything else is not
                if not (rel == "." and f == "CMakePresets.json"):
                    bad.append(os.path.join(rel, f))
    if bad:
        print("FAIL guard 4b — forbidden build files outside platform/:")
        for b in bad:
            print(f"     - {b}")
        return 1
    print("ok   guard 4b — no build files outside platform/ (and only the root presets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
