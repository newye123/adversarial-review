# adversarial-review

[![tests](https://github.com/newye123/adversarial-review/actions/workflows/ci.yml/badge.svg)](https://github.com/newye123/adversarial-review/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**An adversarial review skill for AI coding agents — with a runnable negative-control harness.**

Most "adversarial review" prompts are prose. They tell the model to be skeptical, then hope it complies. This repo ships the prose *and* two programs that make the discipline checkable: one runs a real negative control against your gate, the other refuses to accept a review report whose claims carry no evidence.

Everything here came out of ~150 real review reports and three months of rework. The case library behind it is not public; the method and the tooling are.

---

## 它解决什么

一个结论说"做完了"，但你并不放心。四种常见情形：

1. **写代码的人审不出自己的毛病。** 这不是态度问题，是测量问题。模型审自己写错的 diff 时最宽容（arXiv 2603.04582 自我归因偏差）；"解释 + 给修复"反而提高误判率（2508.12358）；自我批评在标准 benchmark 上零增益——critic 和 generator 是同一个模型（2608.18167）。
2. **测试全绿不等于对。** 绿可能绿在错误前提上，可能是探针失灵，也可能是门本来就红所以负控"通过"了。判断"绿"有没有意义，唯一办法是**故意把它弄红一次**。
3. **改完现象还在。** UI 调了三轮，真卡点在子系统验票超时和回调地址写死。
4. **别人（或另一个 AI）说做完了。**

## 两个工具（这是与同类 prompt 的主要区别）

```bash
# 1) 跑一次真负控：注入 → 门必须红 → 还原 → 核哈希
python tools/negctl.py --file src/validate.ts \
    --mutate "if (badDate)" --to "if (false && badDate)" \
    --cmd "npm test"

# 2) 检查报告有没有证据纪律
python tools/check_report.py report.md --strict
```

**退出码都是三档：`0` 通过 / `1` 有问题 / `2` 工具自己没能跑起来。**

第三档是关键。一个跑不起来的检查器，绝不许被读成"干净"——这条来自一次真实事故：一道门的极性写反，五道门全绿，把运行时从 22 降回了 20.20.2，没人发现。

### `negctl.py`：把负控变成不可跳过的前置条件

手工做负控有四种经典翻车方式，工具逐条焊死：

| 翻车方式 | 工具的处理 |
|---|---|
| 改了个不存在的字符串，负控是假的 | `--occurrences` 强制断言命中次数，不匹配直接 `2` |
| 门本来就是红的，注入后还是红，误读成"负控成功" | 先跑基线，基线不绿直接 `2` |
| 还原没核，工作区留了个洞 | 还原后比 sha256，不一致直接 `2` |
| 脚本只在最后统一还原，第二发继承第一发 | 一进程一发，用进程边界代替纪律 |

还有一个容易漏的：**按 `\n` 改文件，在 CRLF 树下会静默失配，产出假绿。** 本工具按字节流替换，失配就报命中 0 次，不会假装成功。

真实输出：

```
negctl: /tmp/x/config.ts
  ① 命中断言：`= false` 出现 1 次（要求恰好 1 次）
  ② 原文件 sha256：a01df62aeb078682…（21 B）
  ③ 基线：跑门，必须绿（rc=0）
     读数：rc=0
  ④ 注入：写回 21 B，sha256=c4b956a01c86a5ce…
  ⑤ 再跑门，必须红（rc≠0）
     读数：rc=1
     ✓ 门变红了，这道门确实在拦东西
  ⑥ 还原：sha256=a01df62aeb078682…
     ✓ 哈希一致
  ⑦ 还原后复跑，必须回到绿（rc=0）
     读数：rc=0

RESULT: PASS
```

它打印的负控记录可以直接贴进报告的 `## 负控` 节，`check_report.py` 认得这个格式。两个工具是串起来的。

### `check_report.py`：形式检查，不是真值证明

它**不能**告诉你一条结论是不是真的。它能告诉你：这条结论是不是写成了**别人可以核验**的形式。

14 条规则，其中几条最能拦住常见的糊弄：

| 码 | 拦什么 |
|---|---|
| `E004` | 防回归测试留空或写"无" |
| `E005` | finding 既没有 `file:line` 也没有命令原式 |
| `E006` | 说"没有 X / 0 命中"，但没给命令和退出码 |
| `E007` | 说"已修复"，但没有任何负控记录 |
| `E008` | 把 `NOT RUN` 写成 `PASS` |
| `E009` | 负控记录缺注入/基线/还原/哈希任一项 |
| `E012` | `VERDICT: CLEAN`，但同时存在 CRITICAL finding |

`E012` 是我最喜欢的一条：它抓的不是技术错误，是**结论和证据不一致**。

真实输出：

```
check_report: report.md
  VERDICT : CONCERNS
  findings: 3  (CRITICAL=1)

  E004  [line 11]  finding「src/upload/chunk.ts:64 — 分片拼接前未校验总字节数」的防回归测试为空或占位（'无'）

RESULT: FAIL  (1 error(s), 0 warning(s))
```

## 方法骨架

```
固定基线 → 分面只读取证 → 主审逐条证伪 → 收敛 verdict → 风险门（负控）
```

外加三层让它"有牙齿"的东西：

- **三值分歧协议**：批评者只有三种合法结尾，`AGREE` / `DISAGREE_EVIDENCE: <引证>` / `DISAGREE_CONCERN: <质疑>`。收到 CONCERN 必须在代码里找到确认或反驳，**不许"有道理但算了"**。实测把分歧质量 F1 从 0.457 提到 0.533。
- **证据纪律**：否定式断言必须带 grep 命令原式 + 真实退出码 + 零命中证据，否则只能写"未核实"。探针报 0 之前先喂已知样本自证。
- **钻到底**：六种手法把现象挖到物理层，对活下来的结论再上七把压力刀，每条给 `Survived: yes/no`。**不报 Survived 的地方，就是没审过的地方。**

详见 `SKILL.md` 与 `references/`。

## 安装

作为 skill 用（Claude Code / 兼容 Agent Skills 的运行时）：

```bash
git clone https://github.com/newye123/adversarial-review.git
ln -s "$PWD/adversarial-review" ~/.claude/skills/adversarial-review
```

只想用工具、不当 skill 用：

```bash
python tools/check_report.py --help
python tools/negctl.py --help
```

零依赖，标准库即可，Python 3.10+。Windows / macOS / Linux 都测过（Windows 上按字节流处理 CRLF，见上文）。

## 测试

```bash
python -m unittest discover -s tests -v
```

29 个测试，分三层：

1. **fixture 层**：`fixtures/good_report.md` 必须零问题通过，6 个 `bad_*.md` 各自必须被自己的规则码拒绝。
2. **mutation 层**：拿合格报告逐条注入单一缺陷，断言对应规则必然触发。**这是检查器自己的负控**——如果某条检测悄悄失效了，第 1 层可能因为别的原因仍然通过，第 2 层会红。
3. **CLI 层**：真跑子进程，断言退出码。文件不存在必须是 `2`，不能是 `0`。

## 它明确不做什么

写清楚边界，比多列几个特性有用：

- **不是自动审查器。** 它不生成 finding，不替代审查者。
- **不证明结论为真。** `check_report.py` 只查形式。一份形式完美、内容全错的报告也能通过——形式合规是必要条件，不是充分条件。
- **不无脑开对抗环。** 约 4.5× token 成本。单文件文案、纯格式化、已有强门覆盖的机械改动不该开。
- **不追求"每人必须报 N 条"。** 实测为凑数给的 hedged finding 会被判为捏造（3/5 条）。强制应该落在"必须给可核查证据"上。
- **不管 Cloud 问题。** 架构取舍、产品方向、文案这类没有唯一答案的，走对抗思考路径，不走验证路径。走错路会得到一堆"证据不足"的空转。

## 来源与致谢

这个 skill 不假装全是原创。明确区分：

**借来的**（已在文中逐处标注）：
- Clock / Cloud 问题分类、九条认知强制术 — [fullo/claude-adversarial-thinking](https://github.com/fullo/claude-adversarial-thinking)（MIT）
- Chain-of-Verification、mutation probe、`Survived` 判定的表述 — [fullo/claude-adversarial-skill](https://github.com/fullo/claude-adversarial-skill)（MIT）
- 加宽版 5 Whys（候选摆开 + 反向验证）— [ase-meta-why](https://github.com/) skill
- 怀疑清单五模块 — [sidtheone/insightsloop](https://github.com/) skill
- diff entropy 深度升级 — GitHub `code-review-deep` skill
- IS / IS-NOT 四维对比 — Kepner-Tregoe
- 5 Whys 的反方证据 — BMJ Qual Saf 2017, A.J. Card
- 全部论文引用见 `SKILL.md`（arXiv 2603.04582 / 2508.12358 / 2608.18167 / 2607.21656）

**自己的**：
- 五步骨架的具体形态（固定基线 → 分面取证 → 主审证伪 → 收敛 verdict → 负控）
- **负控四式与"负控不红的断言＝没有断言"这套判据**——这是本仓库的核心贡献
- 三值分歧协议 + 实测 F1 增益
- 九族 25 项假绿 / 静默失败案例（`references/pitfalls.md`，来自真实返工）
- 两个可执行工具，以及"退出码三档、跑不起来不许算通过"的设计
- 三条反直觉判据（全体一致是警告 / 找茬诱发过度工程 / 强制每人报一条会产出捏造）

## License

MIT。见 `LICENSE`。
