#!/usr/bin/env python3
"""Self-tests for testreview.py: every check has an ok case and at least one case that must fire.

    python3 review/tests/test_testreview.py        # stdlib only (unittest), needs git

Each test builds a throwaway git repo with one pricer ("alpha"), commits it as the merge base,
applies the scenario as a second commit and runs testreview against the base.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import testreview  # noqa: E402

CMAKE = """xp_pricer(
  NAME     alpha
  SOURCES  alpha.cpp
  TESTS    test_alpha.cpp
  USES     QuantLib::QuantLib
)
"""
SOURCE = "double alpha(double s) { return s * 0.5; }\n"
TEST = """#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>
using Catch::Matchers::WithinAbs;
TEST_CASE("alpha matches golden value", "[regression]") {
  constexpr double kGolden = 50.0;   // closed form: 100 * 0.5
  constexpr double kTol = 1e-12;
  CHECK_THAT(alpha(100.0), WithinAbs(kGolden, kTol));
}
TEST_CASE("alpha is monotone", "[property]") {
  CHECK(alpha(2.0) > alpha(1.0));
}
"""
QUARANTINE_OK = ("unit.alpha.alpha is monotone | @quant/desk | https://gitlab/x/issues/1 | "
                 "2026-11-14 | 2026-11-20\n")  # fmt: skip
TODAY = "2026-11-15"


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}  # fmt: skip
        self.env = {**os.environ, **env}
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()  # fmt: skip

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def delete(self, rel: str) -> None:
        (self.root / rel).unlink()

    def commit(self, msg: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.git("rev-parse", "HEAD")


class TestReview(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repo(Path(self.tmp.name))
        self.repo.write("pricers/alpha/CMakeLists.txt", CMAKE)
        self.repo.write("pricers/alpha/alpha.cpp", SOURCE)
        self.repo.write("pricers/alpha/test_alpha.cpp", TEST)
        self.base = self.repo.commit("base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_review(self) -> tuple[int, str]:
        self.repo.commit("change")
        report = self.repo.root / "report.md"
        with open(os.devnull, "w") as null:
            old, sys.stdout = sys.stdout, null
            try:
                code = testreview.main(["--repo", str(self.repo.root), "--base", self.base,
                                        "--report", str(report), "--today", TODAY])  # fmt: skip
            finally:
                sys.stdout = old
        return code, report.read_text()

    def assert_blocks(self, check: str) -> str:
        code, report = self.run_review()
        self.assertEqual(code, 88, report)
        self.assertIn(f"**BLOCK** `testreview/{check}`", report)
        return report

    def assert_passes(self) -> str:
        code, report = self.run_review()
        self.assertEqual(code, 0, report)
        self.assertIn("# testreview: PASS", report)
        return report

    # ---- ok cases
    def test_ok_code_and_test_change(self):
        self.repo.write("pricers/alpha/alpha.cpp", SOURCE.replace("0.5", "0.5 /*tuned*/"))
        self.repo.write("pricers/alpha/test_alpha.cpp",
                        TEST + 'TEST_CASE("alpha at zero") { CHECK(alpha(0.0) == 0.0); }\n')  # fmt: skip
        self.assert_passes()

    def test_ok_valid_quarantine_entry(self):
        self.repo.write("quarantine.txt", QUARANTINE_OK)
        report = self.assert_passes()
        self.assertIn("newly quarantined", report)

    # ---- code-needs-tests
    def test_code_without_tests_blocks(self):
        self.repo.write("pricers/alpha/alpha.cpp", SOURCE.replace("0.5", "0.55"))
        self.assert_blocks("code-needs-tests")

    # ---- golden-value
    def test_new_pricer_without_golden_blocks(self):
        self.repo.write("pricers/beta/CMakeLists.txt",
                        CMAKE.replace("alpha", "beta"))  # fmt: skip
        self.repo.write("pricers/beta/beta.cpp", SOURCE.replace("alpha", "beta"))
        self.repo.write("pricers/beta/test_beta.cpp",
                        'TEST_CASE("beta positive") { CHECK(beta(1.0) > 0.0); }\n')  # fmt: skip
        self.assert_blocks("golden-value")

    def test_computed_expected_value_is_not_golden(self):
        self.repo.write("pricers/alpha/alpha.cpp", SOURCE.replace("0.5", "0.5 /*x*/"))
        self.repo.write("pricers/alpha/test_alpha.cpp", TEST.replace(
            "WithinAbs(kGolden, kTol)", "WithinAbs(alpha(100.0), kTol)"))  # fmt: skip
        self.assert_blocks("golden-value")

    # ---- no-weakening
    def test_widened_tolerance_blocks(self):
        self.repo.write("pricers/alpha/test_alpha.cpp", TEST.replace("1e-12", "1e-3"))
        report = self.assert_blocks("no-weakening")
        self.assertIn("1e-12 → 0.001", report)

    def test_removed_test_case_blocks(self):
        self.repo.write("pricers/alpha/test_alpha.cpp", TEST.split('TEST_CASE("alpha is')[0])
        self.assert_blocks("no-weakening")

    def test_mayfail_tag_blocks(self):
        self.repo.write("pricers/alpha/test_alpha.cpp",
                        TEST.replace('"[property]"', '"[property][!mayfail]"'))  # fmt: skip
        self.assert_blocks("no-weakening")

    def test_deleted_test_file_blocks(self):
        self.repo.delete("pricers/alpha/test_alpha.cpp")
        self.assert_blocks("no-weakening")

    # ---- quarantine
    def test_expired_quarantine_blocks(self):
        self.repo.write("quarantine.txt", QUARANTINE_OK.replace("2026-11-20", "2026-11-14"))
        self.assert_blocks("quarantine")

    def test_quarantine_without_owner_blocks(self):
        self.repo.write("quarantine.txt", QUARANTINE_OK.replace("@quant/desk", "jdoe"))
        self.assert_blocks("quarantine")

    def test_quarantine_over_sla_blocks(self):
        self.repo.write("quarantine.txt", QUARANTINE_OK.replace("2026-11-20", "2026-12-31"))
        self.assert_blocks("quarantine")

    def test_quarantine_unknown_test_blocks(self):
        self.repo.write("quarantine.txt", QUARANTINE_OK.replace("alpha is monotone", "no such"))
        self.assert_blocks("quarantine")


if __name__ == "__main__":
    unittest.main(verbosity=2)
