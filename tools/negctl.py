#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""negctl.py — run one real negative control, as a program.

A negative control means: inject a known breakage, prove the gate turns red,
restore, prove the bytes came back. Without it, "the tests pass" is not evidence.

This tool exists because the discipline is easy to *describe* and easy to
*get wrong silently*. The four classic ways it goes wrong, all handled here:

  1. The mutation never hit.          -> we require an exact occurrence count.
  2. The gate was already red.        -> we require a green baseline first.
  3. Restoration was never verified.  -> we compare sha256 before/after.
  4. The restore ran only at the end,
     so shots 2..n inherited shot 1.   -> one process = one shot, by design.

Bytes, not text: the mutation is applied on the raw byte stream. A `\\n`-based
edit silently misses on a CRLF tree and produces a false green.

Exit codes (three-tier, deliberately):
  0 = negative control PASSED  (baseline green -> injected red -> restored green -> hash match)
  1 = negative control FAILED  (the gate stayed green; it does not catch this breakage)
  2 = precondition broken      (mutation missed / baseline not green / restore failed / tool error)

Exit code 2 is the important one. A negative control that could not be run is
NOT a passing negative control.

Example
-------
  python tools/negctl.py \
      --file src/validate.ts \
      --mutate "if (badDate)" \
      --to     "if (false && badDate)" \
      --cmd    "npm test"

The final block it prints is formatted to paste straight into the `## 负控`
section of a review report, so `check_report.py` can read it back.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import re
import signal
import subprocess
import sys

STATE = {"path": None, "original": None, "dirty": False}


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _restore(silent: bool = False) -> None:
    """Best-effort restore. Runs on normal exit, exception, and Ctrl-C."""
    if STATE["dirty"] and STATE["path"] and STATE["original"] is not None:
        try:
            with open(STATE["path"], "wb") as fh:
                fh.write(STATE["original"])
            STATE["dirty"] = False
            if not silent:
                print(f"\n[restore] 已还原 {STATE['path']}（异常退出路径）", file=sys.stderr)
        except OSError as exc:
            print(f"\n[restore] 还原失败！{STATE['path']}: {exc}", file=sys.stderr)
            print("[restore] 请立即手工恢复该文件。", file=sys.stderr)


def _on_sigint(signum, frame):  # noqa: ARG001
    _restore()
    sys.exit(2)


def run_cmd(cmd: str, cwd: str | None, timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"<timeout after {timeout}s>"
    raw = (p.stdout or b"") + (p.stderr or b"")
    return p.returncode, raw.decode("utf-8", "replace")


def _shown_path(path: str) -> str:
    """Relative path when possible; absolute when on another drive (Windows)."""
    try:
        return os.path.relpath(path, os.getcwd())
    except ValueError:
        return path


def tail(text: str, n: int = 12) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join("      | " + ln for ln in lines[-n:])


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    atexit.register(_restore)
    try:
        signal.signal(signal.SIGINT, _on_sigint)
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Run one negative control against a gate/test command.")
    ap.add_argument("--file", required=True, help="file to mutate")
    ap.add_argument("--mutate", required=True, help="exact substring to replace (the breakage)")
    ap.add_argument("--to", required=True, help="replacement substring")
    ap.add_argument("--cmd", required=True, help="gate/test command; green = exit 0 by default")
    ap.add_argument("--expect-green-exit", type=int, default=0,
                    help="exit code that means 'green' (default 0)")
    ap.add_argument("--occurrences", type=int, default=1,
                    help="exact number of times --mutate must appear (default 1)")
    ap.add_argument("--cwd", default=None, help="working dir for --cmd")
    ap.add_argument("--timeout", type=int, default=600, help="per-run timeout in seconds")
    ap.add_argument("--dry-run", action="store_true", help="check preconditions, do not write")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    path = os.path.abspath(args.file)
    log: list[str] = []

    def say(msg: str = "") -> None:
        log.append(msg)
        if not args.json:
            print(msg)

    # ---------------------------------------------------------- precondition
    if not os.path.isfile(path):
        print(f"negctl: 文件不存在：{path}", file=sys.stderr)
        return 2

    try:
        with open(path, "rb") as fh:
            original = fh.read()
    except OSError as exc:
        print(f"negctl: 读不了 {path}: {exc}", file=sys.stderr)
        return 2

    mut = args.mutate.encode("utf-8")
    rep = args.to.encode("utf-8")

    hits = original.count(mut)
    say(f"negctl: {path}")
    say(f"  ① 命中断言：`{args.mutate}` 出现 {hits} 次（要求恰好 {args.occurrences} 次）")
    if hits != args.occurrences:
        say(f"RESULT: PRECONDITION-FAILED")
        say(f"  替换命中 {hits} 次，期望 {args.occurrences} 次。")
        say("  改了个不存在的字符串 —— 这个负控是假的，不算做过。")
        if args.json:
            print(json.dumps({"result": "PRECONDITION-FAILED", "exit": 2,
                              "reason": "mutation-missed", "hits": hits,
                              "expected": args.occurrences}, ensure_ascii=False, indent=2))
        return 2

    before_sha = _sha(original)
    say(f"  ② 原文件 sha256：{before_sha[:16]}…（{len(original)} B）")

    # ---------------------------------------------------------- baseline
    say(f"  ③ 基线：跑门，必须绿（rc={args.expect_green_exit}）")
    rc, out = run_cmd(args.cmd, args.cwd, args.timeout)
    say(f"     命令：{args.cmd}")
    say(f"     读数：rc={rc}")
    if rc != args.expect_green_exit:
        say(tail(out))
        say("RESULT: PRECONDITION-FAILED")
        say("  门在注入前就是红的（规则一：基线前置）。")
        say("  此时注入后变红不能证明任何事 —— 你会把『本来就红』误读成『负控成功』。")
        if args.json:
            print(json.dumps({"result": "PRECONDITION-FAILED", "exit": 2,
                              "reason": "baseline-not-green", "rc": rc},
                             ensure_ascii=False, indent=2))
        return 2

    if args.dry_run:
        say("RESULT: DRY-RUN-OK（前提成立，未写入）")
        return 0

    # ---------------------------------------------------------- inject
    mutated = original.replace(mut, rep, args.occurrences)
    if mutated == original:
        say("RESULT: PRECONDITION-FAILED")
        say("  --to 与 --mutate 相同，字节流没有变化。")
        return 2

    STATE.update(path=path, original=original, dirty=True)
    try:
        with open(path, "wb") as fh:
            fh.write(mutated)
        say(f"  ④ 注入：写回 {len(mutated)} B，sha256={_sha(mutated)[:16]}…")

        say(f"  ⑤ 再跑门，必须红（rc≠{args.expect_green_exit}）")
        rc2, out2 = run_cmd(args.cmd, args.cwd, args.timeout)
        say(f"     读数：rc={rc2}")
        if rc2 == args.expect_green_exit:
            say(tail(out2))
            say("RESULT: NEGATIVE-CONTROL-FAILED")
            say("  门没拦住：注入了已知破坏，它还是绿的。")
            say("  结论：这道门对这类破坏是空门（或它测的根本不是这条路径）。")
            if args.json:
                print(json.dumps({"result": "NEGATIVE-CONTROL-FAILED", "exit": 1,
                                  "reason": "gate-stayed-green", "rc": rc2},
                                 ensure_ascii=False, indent=2))
            return 1
        say("     ✓ 门变红了，这道门确实在拦东西")
    finally:
        _restore(silent=True)

    # ---------------------------------------------------------- restore verify
    with open(path, "rb") as fh:
        restored = fh.read()
    after_sha = _sha(restored)
    say(f"  ⑥ 还原：sha256={after_sha[:16]}…")
    if after_sha != before_sha:
        say("RESULT: PRECONDITION-FAILED")
        say("  还原后哈希与改动前不一致 —— 工作区现在是脏的，先修好它。")
        if args.json:
            print(json.dumps({"result": "PRECONDITION-FAILED", "exit": 2,
                              "reason": "restore-hash-mismatch"}, ensure_ascii=False, indent=2))
        return 2
    say("     ✓ 哈希一致")

    say(f"  ⑦ 还原后复跑，必须回到绿（rc={args.expect_green_exit}）")
    rc3, out3 = run_cmd(args.cmd, args.cwd, args.timeout)
    say(f"     读数：rc={rc3}")
    if rc3 != args.expect_green_exit:
        say(tail(out3))
        say("RESULT: PRECONDITION-FAILED")
        say("  还原后门仍是红的 —— 要么还原没干净，要么这道门本来就不稳定。")
        if args.json:
            print(json.dumps({"result": "PRECONDITION-FAILED", "exit": 2,
                              "reason": "not-green-after-restore", "rc": rc3},
                             ensure_ascii=False, indent=2))
        return 2

    # ---------------------------------------------------------- record
    verdict = "负控红了，这道门在拦东西，非假绿"
    record = "\n".join([
        "负控：变异式",
        f"  改动：{_shown_path(path)} 的 `{args.mutate}` → `{args.to}`",
        f"  命中：出现 {hits} 次（要求 {args.occurrences} 次），替换确实生效",
        f"  基线：rc={rc}（绿）",
        f"  注入后：rc={rc2}（红）",
        f"  还原：sha256 {after_sha[:16]}… == 改动前；复跑 rc={rc3}（绿）",
        f"  判定：{verdict}",
    ])

    if args.json:
        print(json.dumps({
            "result": "PASS", "exit": 0,
            "file": path,
            "mutation": {"from": args.mutate, "to": args.to, "hits": hits},
            "baseline_rc": rc, "injected_rc": rc2, "restored_rc": rc3,
            "sha256_before": before_sha, "sha256_after": after_sha,
            "record": record,
        }, ensure_ascii=False, indent=2))
    else:
        say()
        say("RESULT: PASS")
        say()
        say("  ↓ 贴进报告的 `## 负控` 节（check_report.py 认得这个格式）")
        for ln in record.splitlines():
            say("  " + ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
