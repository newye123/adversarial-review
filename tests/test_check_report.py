#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for tools/check_report.py.

Two layers, on purpose:

1. Fixture tests — each `fixtures/bad_*.md` must be rejected with its own rule code,
   and `fixtures/good_report.md` must pass with zero issues.

2. Mutation tests — take the *good* report and inject one defect at a time, asserting
   the matching rule fires. This is a negative control on the checker itself: if the
   checker silently stops detecting a defect, layer 1 would still pass (the fixture
   might be broken for an unrelated reason), but layer 2 goes red.

A linter whose own failures are invisible is worse than no linter.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "tools", "check_report.py")
FIX = os.path.join(ROOT, "fixtures")

sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_report  # noqa: E402


def read(name: str) -> str:
    with open(os.path.join(FIX, name), "r", encoding="utf-8") as fh:
        return fh.read()


def codes(text: str, strict: bool = False) -> set[str]:
    issues, _ = check_report.check(text, strict=strict)
    return {i.code for i in issues}


def replace_line(text: str, needle: str, newline: str, occurrence: int = 0) -> str:
    """Replace the whole line that contains `needle`."""
    lines = text.split("\n")
    seen = 0
    for i, ln in enumerate(lines):
        if needle in ln:
            if seen == occurrence:
                lines[i] = newline
                return "\n".join(lines)
            seen += 1
    raise AssertionError(f"needle not found: {needle!r}")


# --------------------------------------------------------------- layer 1


class TestFixtures(unittest.TestCase):
    CASES = {
        "bad_verdict.md": "E002",
        "bad_missing_regression_test.md": "E004",
        "bad_negative_claim.md": "E006",
        "bad_fixed_without_negctl.md": "E007",
        "bad_notrun_as_pass.md": "E008",
        "bad_negctl_incomplete.md": "E009",
    }

    def test_good_report_is_clean(self):
        issues, stats = check_report.check(read("good_report.md"))
        self.assertEqual(issues, [], f"good report should be clean, got {issues}")
        self.assertEqual(stats["verdict"], "CONCERNS")
        self.assertEqual(stats["findings"], 3)

    def test_each_bad_fixture_triggers_its_rule(self):
        for name, expected in self.CASES.items():
            with self.subTest(fixture=name):
                got = codes(read(name))
                self.assertIn(expected, got, f"{name} should trigger {expected}, got {sorted(got)}")


# --------------------------------------------------------------- layer 2


class TestMutations(unittest.TestCase):
    """Inject one defect into the good report; the matching rule must fire."""

    def setUp(self):
        self.good = read("good_report.md")

    def test_e002_invalid_verdict(self):
        t = self.good.replace("VERDICT: CONCERNS", "VERDICT: LGTM")
        self.assertIn("E002", codes(t))

    def test_e003_missing_field(self):
        t = replace_line(self.good, "- 影响：测试环境下单未支付", "")
        self.assertIn("E003", codes(t))

    def test_e004_placeholder_regression_test(self):
        t = replace_line(self.good, "- 防回归测试：新增 `tests/config/payment-default", "- 防回归测试：无")
        self.assertIn("E004", codes(t))

    def test_e005_no_anchor_and_no_command(self):
        t = replace_line(self.good, "### [CRITICAL] src/config/payment.ts:14", "### [CRITICAL] 支付开关默认值")
        t = replace_line(t, "- 证据：`git diff a593f1b", "- 证据：看过了，改错了。")
        self.assertIn("E005", codes(t))

    def test_e006_negative_claim_without_command(self):
        t = replace_line(self.good, "- 证据：`grep -rn \"nonce", "- 证据：检查过了，没有发现任何防护。")
        self.assertIn("E006", codes(t))

    def test_e007_fixed_without_negative_control(self):
        t = self.good.replace("## 负控", "## 备注")
        t = replace_line(t, "- 修复路径：默认值改回 false", "- 修复路径：已修复，默认值改回 false")
        self.assertIn("E007", codes(t))

    def test_e008_notrun_as_pass(self):
        t = self.good + "\n- 门禁：NOT RUN → 记为 PASS\n"
        self.assertIn("E008", codes(t))

    def test_e009_incomplete_negative_control(self):
        t = replace_line(self.good, "  还原：sha256 a1b2c3d4", "")
        self.assertIn("E009", codes(t))

    def test_e010_missing_coverage_gap(self):
        t = self.good.replace("## 覆盖缺口", "## 其他")
        self.assertIn("E010", codes(t))

    def test_e011_stress_without_survived(self):
        t = self.good.replace("Survived: yes", "结论：没问题").replace("Survived: no", "结论：有问题")
        self.assertIn("E011", codes(t))

    def test_e012_clean_with_critical(self):
        t = self.good.replace("VERDICT: CONCERNS", "VERDICT: CLEAN")
        self.assertIn("E012", codes(t))

    def test_w001_missing_baseline(self):
        t = replace_line(self.good, "基线：`a593f1b`", "")
        self.assertIn("W101", codes(t))

    def test_w002_missing_footer(self):
        t = self.good.replace("## 本次未动什么", "## 备注")
        self.assertIn("W102", codes(t))

    def test_strict_promotes_warnings(self):
        t = replace_line(self.good, "基线：`a593f1b`", "")
        self.assertIn("W101", codes(t))
        self.assertIn("E101", codes(t, strict=True))
        self.assertNotIn("W101", codes(t, strict=True))


# --------------------------------------------------------------- layer 3


class TestCliExitCodes(unittest.TestCase):
    """The real path: subprocess, real argv, real exit code."""

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, TOOL, *args], capture_output=True, text=True, encoding="utf-8"
        )

    def test_good_exits_zero(self):
        p = self.run_cli(os.path.join(FIX, "good_report.md"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("RESULT: PASS", p.stdout)

    def test_bad_exits_one(self):
        p = self.run_cli(os.path.join(FIX, "bad_verdict.md"))
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("RESULT: FAIL", p.stdout)

    def test_missing_file_exits_two_not_zero(self):
        """A checker that cannot run must never look like a pass."""
        p = self.run_cli(os.path.join(FIX, "does-not-exist.md"))
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)

    def test_json_output_is_parseable(self):
        import json

        p = self.run_cli(os.path.join(FIX, "bad_negative_claim.md"), "--json")
        self.assertEqual(p.returncode, 1)
        data = json.loads(p.stdout)
        self.assertEqual(data["result"], "FAIL")
        self.assertTrue(any(i["code"] == "E006" for i in data["issues"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
