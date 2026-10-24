#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_report.py — lint an adversarial review report for evidence discipline.

This is a FORM checker, not a truth prover. It cannot tell you whether a claim is
true. It can tell you whether the claim was written in a form that *could* be
checked by someone else. That is the whole point: an uncheckable claim is not a
weaker claim, it is not a claim.

Exit codes (three-tier, deliberately):
  0 = report passes
  1 = report has violations
  2 = the checker itself could not run (bad args / unreadable file)

Exit code 2 exists so that a broken checker is never read as "clean". A checker
that dies silently and returns 0 is worse than no checker at all.

Rule codes:
  E001  no VERDICT line
  E002  VERDICT value not in {BLOCK, CONCERNS, CLEAN}
  E003  finding missing a required field
  E004  防回归测试 field empty or placeholder
  E005  finding has neither file:line nor a command in 证据
  E006  negative claim ("没有 / 不存在 / 0 命中") without command + exit code
  E007  "fixed / 修好了" claim with no complete negative-control record
  E008  NOT RUN written as PASS
  E009  negative-control record incomplete (missing 注入/基线/还原/哈希)
  E010  no 覆盖缺口 (coverage gap) section
  E011  stress-test section present but no `Survived:` verdict
  E012  VERDICT: CLEAN but CRITICAL findings exist
  W101  no 基线 (baseline) declaration
  W102  no "本次未动什么" footer
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------- console


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


# ---------------------------------------------------------------- patterns

VERDICT_RE = re.compile(r"^\s*VERDICT\s*[:：]\s*(\S+)", re.MULTILINE)
VALID_VERDICTS = {"BLOCK", "CONCERNS", "CLEAN"}

SEV = r"(CRITICAL|WARNING|NOTE)"
FINDING_HEADER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[-*+]\s+)?\*{0,2}\[\s*" + SEV + r"\s*\]\*{0,2}\s*(.*)$"
)

FIELDS = ("问题", "证据", "影响", "修复路径", "防回归测试")
FIELD_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?\*{0,2}\s*(" + "|".join(FIELDS) + r")\s*\*{0,2}\s*[:：]\s*(.*)$"
)

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
ANY_HEADING_RE = re.compile(r"^#{1,6}\s+")

FILE_LINE_RE = re.compile(r"[\w./\\@-]+\.[A-Za-z0-9]+:\d+(?:-\d+)?")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")

EXIT_CODE_RE = re.compile(
    r"(?:\brc\s*=\s*-?\d+|退出码\s*[:：]?\s*-?\d+|\bexit(?:\s*code)?\s*[:=]\s*-?\d+|\brc=)",
    re.IGNORECASE,
)

NEGATIVE_CLAIM_RE = re.compile(
    r"(没有(?:发现|找到|命中|出现|任何)?|不存在|未发现|未找到|未命中|零命中|0\s*命中|没找到|没出现|"
    r"\bno\s+hits?\b|\bnot\s+found\b|\bdoes\s*n[o']t\s+exist\b|\bzero\s+matches?\b|\babsent\b)",
    re.IGNORECASE,
)

FIXED_CLAIM_RE = re.compile(
    r"(修好了|已修复|修复完成|已解决|改好了|已处理|\bfixed\b|\bresolved\b)", re.IGNORECASE
)

NOT_RUN_RE = re.compile(r"NOT[\s_-]?RUN", re.IGNORECASE)
PASS_RE = re.compile(r"\bPASS\b|通过|全绿", re.IGNORECASE)

NEGCTL_KEYS = {
    "注入": re.compile(r"(改动|注入|mutation)"),
    "基线": re.compile(r"(基线|注入后|baseline|after)"),
    "还原": re.compile(r"(还原|恢复|restore)"),
    "哈希": re.compile(r"(哈希|sha256|hash)"),
}

PLACEHOLDERS = {
    "", "-", "—", "–", "无", "暂无", "待补", "待定", "todo", "tbd", "n/a", "na",
    "...", "…", "略", "none", "null",
}

COVERAGE_GAP_HINTS = ("覆盖缺口", "覆盖 缺口", "coverage gap", "未覆盖", "残留检验点")
FOOTER_HINTS = ("本次未动什么", "本次未动", "未动什么", "未修改什么")
BASELINE_HINTS = ("基线", "baseline")
STRESS_HINTS = ("压力测试", "七把刀", "stress test", "stress-test")
SURVIVED_RE = re.compile(r"Survived\s*[:：]\s*(yes|no)", re.IGNORECASE)


@dataclass
class Finding:
    severity: str
    header: str
    line: int
    fields: dict = field(default_factory=dict)


@dataclass
class Issue:
    code: str
    line: int
    message: str


def _clean(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^\*+|\*+$", "", s).strip()
    s = re.sub(r"^`+|`+$", "", s).strip()
    return s


def _sections(lines: list[str]) -> list[tuple[str, int, int]]:
    """Return (title, start_line_idx, end_line_idx) for each `## ` section."""
    out = []
    idxs = [i for i, ln in enumerate(lines) if SECTION_RE.match(ln)]
    for n, i in enumerate(idxs):
        end = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
        out.append((SECTION_RE.match(lines[i]).group(1).strip(), i, end))
    return out


def _find_findings(lines: list[str]) -> list[Finding]:
    hits: list[Finding] = []
    for i, ln in enumerate(lines):
        m = FINDING_HEADER_RE.match(ln)
        if not m:
            continue
        hits.append(Finding(m.group(1), _clean(m.group(2)), i + 1))
    for n, f in enumerate(hits):
        start = f.line  # 0-based index of the line AFTER the header
        end = hits[n + 1].line - 1 if n + 1 < len(hits) else len(lines)
        for ln in lines[start:end]:
            fm = FIELD_RE.match(ln)
            if fm:
                f.fields.setdefault(fm.group(1), _clean(fm.group(2)))
    return hits


def check(text: str, strict: bool = False) -> tuple[list[Issue], dict]:
    lines = text.splitlines()
    issues: list[Issue] = []

    # ---- VERDICT
    vm = VERDICT_RE.search(text)
    verdict = vm.group(1).strip().rstrip(".,;") if vm else None
    if not vm:
        issues.append(Issue("E001", 0, "报告里没有 `VERDICT:` 行"))
    elif verdict.upper() not in VALID_VERDICTS:
        issues.append(
            Issue("E002", text[: vm.start()].count("\n") + 1,
                  f"VERDICT 值 `{verdict}` 非法，只接受 BLOCK / CONCERNS / CLEAN")
        )

    # ---- baseline declaration
    head = "\n".join(lines[:12])
    if not any(h in head for h in BASELINE_HINTS):
        issues.append(Issue("W101", 0, "页首 12 行内没有基线声明（`基线：<sha>`）"))

    # ---- findings
    findings = _find_findings(lines)
    crit = 0
    for f in findings:
        if f.severity == "CRITICAL":
            crit += 1
        for name in FIELDS:
            if name not in f.fields:
                issues.append(Issue("E003", f.line, f"finding「{f.header[:40]}」缺字段：{name}"))
        rt = f.fields.get("防回归测试", "")
        if "防回归测试" in f.fields and rt.strip().lower() in PLACEHOLDERS:
            issues.append(Issue("E004", f.line,
                                f"finding「{f.header[:40]}」的防回归测试为空或占位（{rt!r}）"))

        evidence = f.fields.get("证据", "")
        has_loc = bool(FILE_LINE_RE.search(f.header) or FILE_LINE_RE.search(evidence))
        has_cmd = bool(BACKTICK_RE.search(evidence))
        if not (has_loc or has_cmd):
            issues.append(Issue("E005", f.line,
                                f"finding「{f.header[:40]}」既无 file:line 也无命令原式"))

        if NEGATIVE_CLAIM_RE.search(evidence):
            if not (has_cmd and EXIT_CODE_RE.search(evidence)):
                issues.append(Issue(
                    "E006", f.line,
                    f"finding「{f.header[:40]}」含否定式断言，但证据里没有「命令原式 + 真实退出码」"))

    if verdict and verdict.upper() == "CLEAN" and crit:
        issues.append(Issue("E012", 0, f"VERDICT 是 CLEAN，但存在 {crit} 条 CRITICAL finding"))

    # ---- NOT RUN written as PASS
    for i, ln in enumerate(lines, start=1):
        if NOT_RUN_RE.search(ln) and PASS_RE.search(ln):
            issues.append(Issue("E008", i, "同一行把 NOT RUN 写成了 PASS/通过"))

    # ---- negative control section
    secs = _sections(lines)
    neg_sec = next((s for s in secs if "负控" in s[0] or "negative control" in s[0].lower()), None)
    has_fixed = bool(FIXED_CLAIM_RE.search(text))
    if neg_sec is None:
        if has_fixed:
            issues.append(Issue(
                "E007", 0,
                "报告里有「修好了 / 已修复」类断言，但完全没有负控记录（注入→变红→还原→哈希）"))
    else:
        body = lines[neg_sec[1] + 1: neg_sec[2]]
        blocks: list[list[str]] = [[]]
        for ln in body:
            if re.match(r"^\s*(?:[-*+]\s+)?(式[一二三四五六七八九十]|###|\d+[.、)])", ln) and blocks[-1]:
                blocks.append([ln])
            else:
                blocks[-1].append(ln)
        blocks = [b for b in blocks if any(x.strip() for x in b)]
        for b in blocks:
            joined = "\n".join(b)
            if not NEGCTL_KEYS["注入"].search(joined):
                continue  # narrative line, not a record block
            missing = [k for k, rx in NEGCTL_KEYS.items() if not rx.search(joined)]
            if missing:
                issues.append(Issue("E009", neg_sec[1] + 1,
                                    f"负控记录不完整，缺：{'、'.join(missing)}"))

    # ---- coverage gap section
    if not any(any(h in t for h in COVERAGE_GAP_HINTS) for t, _, _ in secs):
        issues.append(Issue("E010", 0, "没有「覆盖缺口」节（这一节不许省）"))

    # ---- stress test / Survived
    stress_sec = next((s for s in secs if any(h in s[0].lower() for h in STRESS_HINTS)), None)
    if stress_sec is not None:
        body = "\n".join(lines[stress_sec[1]: stress_sec[2]])
        if not SURVIVED_RE.search(body):
            issues.append(Issue("E011", stress_sec[1] + 1,
                                "有压力测试节，但没有任何 `Survived: yes/no` 判定"))

    # ---- footer
    tail = "\n".join(lines[-15:])
    if not any(h in tail for h in FOOTER_HINTS):
        issues.append(Issue("W102", 0, "页尾没有「本次未动什么」声明"))

    stats = {
        "verdict": verdict,
        "findings": len(findings),
        "critical": crit,
        "errors": sum(1 for i in issues if i.code.startswith("E")),
        "warnings": sum(1 for i in issues if i.code.startswith("W")),
    }
    if strict:
        for i in issues:
            if i.code.startswith("W"):
                i.code = "E" + i.code[1:]
    return issues, stats


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(
        description="Lint an adversarial review report for evidence discipline.")
    ap.add_argument("report", help="path to the review report (.md)")
    ap.add_argument("--strict", action="store_true", help="treat W-level warnings as errors")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    try:
        with open(args.report, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"check_report: cannot read {args.report}: {exc}", file=sys.stderr)
        return 2

    issues, stats = check(text, strict=args.strict)
    hard = [i for i in issues if i.code.startswith("E")]
    rc = 1 if hard else 0

    if args.json:
        print(json.dumps({
            "file": args.report,
            "result": "FAIL" if rc else "PASS",
            "exit": rc,
            "stats": stats,
            "issues": [asdict(i) for i in issues],
        }, ensure_ascii=False, indent=2))
        return rc

    print(f"check_report: {args.report}")
    print(f"  VERDICT : {stats['verdict']}")
    print(f"  findings: {stats['findings']}  (CRITICAL={stats['critical']})")
    if issues:
        print()
        for i in sorted(issues, key=lambda x: (x.code, x.line)):
            loc = f"line {i.line}" if i.line else "report"
            print(f"  {i.code}  [{loc}]  {i.message}")
    print()
    if rc:
        print(f"RESULT: FAIL  ({stats['errors']} error(s), {stats['warnings']} warning(s))")
    else:
        print(f"RESULT: PASS  (0 error(s), {stats['warnings']} warning(s))")
    return rc


if __name__ == "__main__":
    sys.exit(main())
