# 版权与归属声明 / Copyright & Attribution

## 著作权人

**yt** — GitHub [@newye123](https://github.com/newye123)

## 作品

`adversarial-review` — 对抗式审查与深挖探查 skill，含 `SKILL.md`、`references/`、`cases/`、
`tools/`、`tests/` 与全部文档。

## 许可

**非商业使用许可 1.0（NC-1.0）** — 见 [LICENSE](LICENSE)。

一句话：**可以免费用，不能拿去赚钱；转载和修改必须署名并保留本声明。**

⚠️ **许可变更说明（请读完）**：本仓库 v1.0.0–v1.1.0 曾以 **MIT** 发布。
许可变更**不追溯**——任何在该时期取得副本的人，对其已取得的副本仍可主张 MIT 授予的权利（含商用）。
本声明不假装能收回已经授予的权利；它只约束此后取得的版本。
如果你需要「可自由商用」的版本，请以 MIT 时期的历史提交为准。

## 引用格式

学术或公开引用请使用：

```
yt (@newye123). adversarial-review: 对抗式审查与深挖探查.
2026. https://github.com/newye123/adversarial-review
```

中文行文可写作：「参考 yt 的 adversarial-review（github.com/newye123/adversarial-review）」。

## 第三方内容

**借来的**（已在正文逐处标注；完整清单见 README「来源与致谢」）：

- Clock / Cloud 问题分类、九条认知强制术 — [fullo/claude-adversarial-thinking](https://github.com/fullo/claude-adversarial-thinking)（MIT）
- Chain-of-Verification、mutation probe、`Survived` 判定的表述 — [fullo/claude-adversarial-skill](https://github.com/fullo/claude-adversarial-skill)（MIT）
- 加宽版 5 Whys（候选摆开 + 反向验证）— `ase-meta-why` skill（**只记名称，出处未核实，故不给链接**）
- 怀疑清单五模块 — `insightsloop` skill（**同上，只记名称**）
- diff entropy 深度升级 — `code-review-deep` skill（**同上，只记名称**）
- IS / IS-NOT 四维对比 — Kepner-Tregoe
- 5 Whys 的反方证据 — BMJ Qual Saf 2017, A.J. Card
- 论文引用见 `SKILL.md`（arXiv 2603.04582 / 2508.12358 / 2608.18167 / 2607.21656）

**自己的**：五步骨架的具体形态、负控四式与「负控不红的断言＝没有断言」这套判据、
三值分歧协议、九族 25 项假绿案例、两个可执行工具与三值退出码设计、三条反直觉判据。

上述第三方内容各自的权利归其原作者，不在本作品的著作权范围内。

> 关于「出处未核实」那三条：早先的 README 给它们填了 `https://github.com/` 这个占位链接，
> 点进去是首页，等于**声明了来源却没有来源**。现在改为只记名称并标明未核实。
> 一条打不开的出处链接，比不写更糟——它看起来像有据可查。

## 案例的脱敏范围

`cases/` 中的案例来自真实项目。已移除：公司名、品牌名、产品型号、SKU、客户文案、凭据、服务器地址、盘符绝对路径。

保留：`file:line`、命令原式、真实退出码、时间线、代码片段。

理由：案例的可核验性建立在后者上；去掉前者不影响任何人，去掉后者会让案例退化成传闻。
