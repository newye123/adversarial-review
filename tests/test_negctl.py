#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for tools/negctl.py — the negative control harness.

Each test here is itself a control: it pins one specific way a negative control
can silently lie, and asserts the tool refuses to report success in that case.

The five lies being pinned:
  1. the mutation never hit        -> PRECONDITION-FAILED (2), not PASS
  2. the gate was already red      -> PRECONDITION-FAILED (2), not PASS
  3. the gate never went red       -> NEGATIVE-CONTROL-FAILED (1)
  4. the file was left mutated     -> bytes compared after every run
  5. a \\n edit silently missed on
     a CRLF tree                    -> counted, reported, refused
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "tools", "negctl.py")

GATE = """\
import sys
data = open("target.txt", "rb").read()
sys.exit(1 if b"BAD" in data else 0)
"""

GATE_ALWAYS_RED = """\
import sys
sys.exit(1)
"""


class NegctlCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.target = os.path.join(self.dir, "target.txt")
        with open(self.target, "wb") as fh:
            fh.write(b"STATUS=GOOD\n")
        with open(os.path.join(self.dir, "gate.py"), "w", encoding="utf-8") as fh:
            fh.write(GATE)
        self.cmd = f'"{sys.executable}" gate.py'

    def tearDown(self):
        self.tmp.cleanup()

    def negctl(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, TOOL, "--cwd", self.dir, *args],
            capture_output=True, text=True, encoding="utf-8",
        )

    def bytes_now(self) -> bytes:
        with open(self.target, "rb") as fh:
            return fh.read()


class TestHappyPath(NegctlCase):
    def test_gate_goes_red_then_restored(self):
        p = self.negctl("--file", self.target, "--mutate", "GOOD", "--to", "BAD",
                        "--cmd", self.cmd)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("RESULT: PASS", p.stdout)
        self.assertIn("负控：变异式", p.stdout)
        # restore must be byte-exact
        self.assertEqual(self.bytes_now(), b"STATUS=GOOD\n")

    def test_json_record_is_pasteable(self):
        import json

        p = self.negctl("--file", self.target, "--mutate", "GOOD", "--to", "BAD",
                        "--cmd", self.cmd, "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertEqual(data["result"], "PASS")
        self.assertEqual(data["sha256_before"], data["sha256_after"])
        self.assertIn("负控：变异式", data["record"])


class TestRefusesToLie(NegctlCase):
    def test_mutation_that_never_hit_is_not_a_pass(self):
        p = self.negctl("--file", self.target, "--mutate", "NOPE", "--to", "BAD",
                        "--cmd", self.cmd)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("PRECONDITION-FAILED", p.stdout)
        self.assertEqual(self.bytes_now(), b"STATUS=GOOD\n")

    def test_already_red_baseline_is_not_a_pass(self):
        with open(os.path.join(self.dir, "gate.py"), "w", encoding="utf-8") as fh:
            fh.write(GATE_ALWAYS_RED)
        p = self.negctl("--file", self.target, "--mutate", "GOOD", "--to", "BAD",
                        "--cmd", self.cmd)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("PRECONDITION-FAILED", p.stdout)
        self.assertIn("基线前置", p.stdout)

    def test_gate_that_stays_green_is_a_failure(self):
        # mutate something the gate does not look at
        p = self.negctl("--file", self.target, "--mutate", "STATUS", "--to", "STATE",
                        "--cmd", self.cmd)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("NEGATIVE-CONTROL-FAILED", p.stdout)
        self.assertIn("空门", p.stdout)
        # even on failure the file must be restored
        self.assertEqual(self.bytes_now(), b"STATUS=GOOD\n")

    def test_occurrence_count_is_enforced(self):
        p = self.negctl("--file", self.target, "--mutate", "O", "--to", "0",
                        "--cmd", self.cmd, "--occurrences", "1")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)


class TestCrlf(NegctlCase):
    """The classic silent miss: a \\n-based edit on a CRLF tree."""

    def setUp(self):
        super().setUp()
        with open(self.target, "wb") as fh:
            fh.write(b"A\r\nGOOD\r\n")

    def test_newline_mutation_misses_and_says_so(self):
        p = self.negctl("--file", self.target, "--mutate", "A\nGOOD", "--to", "A\nBAD",
                        "--cmd", self.cmd)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("0 次", p.stdout)

    def test_crlf_bytes_survive_restore(self):
        p = self.negctl("--file", self.target, "--mutate", "GOOD", "--to", "BAD",
                        "--cmd", self.cmd)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.bytes_now(), b"A\r\nGOOD\r\n")


class TestDryRun(NegctlCase):
    def test_dry_run_does_not_write(self):
        p = self.negctl("--file", self.target, "--mutate", "GOOD", "--to", "BAD",
                        "--cmd", self.cmd, "--dry-run")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("DRY-RUN-OK", p.stdout)
        self.assertEqual(self.bytes_now(), b"STATUS=GOOD\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
