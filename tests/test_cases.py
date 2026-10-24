#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for cases/ — the real case studies.

These exist because the repo shipped for a while with zero cases while the
README claimed it was built on "real review reports". A repo that teaches
evidence discipline must hold its own case library to the same standard.

Three things are pinned:

1. Structure   — every case has 现象 and 结论, and is long enough to be real
2. Linkage     — README and cases/README.md actually point at >= 3 cases
3. Desens      — no client / product / SKU strings leaked into the public repo
"""

from __future__ import annotations

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES = os.path.join(ROOT, "cases")
README = os.path.join(ROOT, "README.md")

# Strings that must never appear in the public repo. Keep this list short and
# specific — broad words produce false alarms and get deleted, which is worse.
BANNED = ["图译", "工坊", "SmallRig", "斯莫格", "5775", "6746", "yt-visual", "飞书"]

MIN_CHARS = 800


def case_files() -> list[str]:
    return sorted(
        os.path.join(CASES, f)
        for f in os.listdir(CASES)
        if f.endswith(".md") and f.lower() != "readme.md"
    )


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestCaseStructure(unittest.TestCase):
    def test_at_least_three_cases(self):
        files = case_files()
        self.assertGreaterEqual(len(files), 3, f"expected >=3 cases, got {files}")

    def test_each_case_has_required_sections(self):
        for path in case_files():
            name = os.path.basename(path)
            with self.subTest(case=name):
                text = read(path)
                self.assertIn("## 现象", text, f"{name} 缺「现象」节")
                self.assertIn("## 结论", text, f"{name} 缺「结论」节")

    def test_each_case_is_substantial(self):
        for path in case_files():
            name = os.path.basename(path)
            with self.subTest(case=name):
                body = read(path)
                self.assertGreater(
                    len(body), MIN_CHARS,
                    f"{name} 只有 {len(body)} 字符，低于 {MIN_CHARS}，不像一个完整案例")

    def test_each_case_names_a_reusable_criterion(self):
        """A case that does not hand over a transferable rule is just a war story."""
        for path in case_files():
            name = os.path.basename(path)
            with self.subTest(case=name):
                text = read(path)
                self.assertIn("可迁移的判据", text,
                              f"{name} 缺「可迁移的判据」——案例要交出一条能复用的规则")


class TestLinkage(unittest.TestCase):
    def test_readme_links_to_three_cases(self):
        text = read(README)
        links = re.findall(r"\(cases/([0-9a-z-]+\.md)\)", text)
        self.assertGreaterEqual(
            len(set(links)), 3, f"README 只链接了 {len(set(links))} 个案例：{sorted(set(links))}")

    def test_cases_index_links_to_every_case(self):
        index = read(os.path.join(CASES, "README.md"))
        for path in case_files():
            fname = os.path.basename(path)
            with self.subTest(case=fname):
                self.assertIn(fname, index, f"cases/README.md 没有链接到 {fname}")

    def test_readme_links_resolve(self):
        text = read(README)
        for rel in set(re.findall(r"\((cases/[0-9a-z-]+\.md)\)", text)):
            with self.subTest(link=rel):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)),
                                f"README 里的链接 {rel} 指向不存在的文件")


class TestDesensitization(unittest.TestCase):
    def test_no_banned_strings_in_cases(self):
        for path in case_files():
            text = read(path)
            for word in BANNED:
                with self.subTest(case=os.path.basename(path), word=word):
                    self.assertNotIn(word, text, f"{os.path.basename(path)} 含敏感词 {word!r}")

    def test_no_banned_strings_in_repo_markdown(self):
        """Scan the whole repo — except this file, which has to contain the list.

        (A desensitization test that scans itself fails on its own blacklist.
        Took one run to notice.)
        """
        me = os.path.abspath(__file__)
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            for f in filenames:
                if not f.endswith((".md", ".py")):
                    continue
                path = os.path.join(dirpath, f)
                if os.path.abspath(path) == me:
                    continue
                text = read(path)
                for word in BANNED:
                    with self.subTest(file=os.path.relpath(path, ROOT), word=word):
                        self.assertNotIn(word, text, f"{path} 含敏感词 {word!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
