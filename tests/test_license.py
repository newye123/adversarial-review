#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""许可与归属声明自检。

为什么需要这组断言：本仓库 v1.0.0–v1.1.0 曾以 MIT 发布，后来改为 NC-1.0。
改许可这件事最怕的不是改错，是**改回去**——某次顺手复制旧模板、某次合并旧分支，
MIT 会安静地回来，而且没有任何东西会红。

所以把「不许是 MIT」「必须有 NOTICE」「必须写明不追溯」钉成断言。
"""

from __future__ import annotations

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


class TestLicense(unittest.TestCase):
    def test_license_is_nc_not_mit(self):
        body = read("LICENSE")
        self.assertIn("NC-1.0", body)
        # MIT 允许商用，NC 不允许。只要首行还是 MIT，商用授权就回来了。
        self.assertNotRegex(
            body[:80], r"(?i)^\s*MIT License",
            "LICENSE 首行又变回 MIT 了——这会把商用授权悄悄放回去",
        )

    def test_license_prohibits_commercial_use(self):
        body = read("LICENSE")
        self.assertIn("禁止任何形式的商业使用", body)
        self.assertIn("禁止销售", body)

    def test_license_states_non_retroactivity(self):
        """必须写明 MIT 时期不可追溯——否则等于假装能收回已授予的权利。"""
        body = read("LICENSE")
        self.assertIn("不能追溯", body)
        self.assertIn("MIT", body)

    def test_notice_exists_and_names_the_holder(self):
        body = read("NOTICE.md")
        self.assertIn("yt", body)
        self.assertIn("newye123", body)
        self.assertIn("NC-1.0", body)

    def test_readme_license_section_matches(self):
        body = read("README.md")
        self.assertNotIn("license-MIT", body, "README 徽章还写着 MIT")
        self.assertIn("NC-1.0", body)

    def test_skill_frontmatter_declares_license(self):
        body = read("SKILL.md")
        m = re.match(r"^---\n(.*?)\n---\n", body, re.S)
        self.assertIsNotNone(m)
        self.assertIn("license:", m.group(1))
        self.assertIn("NC-1.0", m.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
