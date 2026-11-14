# xp-platform (build engineers)

The build machinery for every quant version. Pinned by tag (platform-v1.0.0); generated
repos get a **real copy** of this tree at a pinned tag.

- `cmake/` — `XpPricer.cmake` (the one call quants get), `XpProject.cmake` (root wiring),
  `XpTarget.cmake` + warnings/sanitizers/analyzers/quarantine, `GitVersion`, `Packaging`.
- `toolchains/`, `triplets/` — RHEL 8 (gcc13, clang17), Windows (v143 static-md), Ubuntu (NEW).
- `presets/CMakePresets.json` — paths point at `${sourceDir}/platform/...` (generated-repo layout).
- `testing/` — FP-trap test main, compiled into every pricer's tests.
- `vcpkg.json` — dependencies incl. QuantLib, pinned by `builtin-baseline` (no QuantLib fork).
- `ci/cpp-build.yml`, `tools/` — the CI component + step runner (exit codes 81–86).
- `semgrep/`, `guards/` — the deny-list rules and the four allow-list guards (4a–4d).
- `ci/review.yml`, `review/` — MR review component, rule-based, run from the pinned tag:
  - `review` (exit 87): guards 4a–4d + semgrep rules on the files the MR changed.
  - `testreview` (exit 88): pricer code changed ⇒ its tests changed; every pricer has a
    golden-value test; no removed tests, fewer assertions, wider tolerances or skip markers;
    `quarantine.txt` owner + issue + 14-day SLA (rules reused from xp-pricer).
  - Self-tests: `python3 review/tests/test_testreview.py`.

**Untested on this box:** the Ubuntu toolchain/triplet and the Windows preset. They
`cmake --list-presets` cleanly but have not been built here.
