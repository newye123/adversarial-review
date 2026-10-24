# 对抗式审查报告：adversarial-review 仓库自审

基线：`52cec63`；审查者只读，本轮未改业务代码、未跑门（除负控那一发）、未提交。

方法：五步骨架（固定基线 → 分面只读取证 → 主审逐条证伪 → 收敛 verdict → 负控）。

一句话结论：工具是真的，案例是空的——这个仓库现在能证明「我会写检查器」，证明不了「这套方法抓到过东西」。

VERDICT: CONCERNS

## findings

### [CRITICAL] README.md:10 — 「~150 real review reports」不可核验，且仓库里没有任何一个案例
- 问题：破了本 skill 自己的红线「否定式/存在式断言必须带出处」。这句话是整篇权威感的来源，但读者无法验证 150 这个数，也无法验证「came out of」这个因果关系。
- 证据：`ls cases` → rc=2，目录不存在；`grep -c "案例" README.md` → rc=0，命中 1 处（只在致谢节）。即：宣称有 150 份报告垫底，仓库里可查的案例是 0 个。
- 影响：面试官读到这里的第一反应是「数字哪来的」。一份教人「没出处就写未核实」的文档，自己第一段就在做这件事。这是最伤的那种不一致——不是技术错误，是自我指涉的伪善。
- 修复路径：新增 `cases/` 目录，放 3 个可核验的真实案例（现象 / 取证命令与退出码 / 结论 / 代价），README 直接链接过去；150 这个数字要么给出统计口径，要么删掉。
- 防回归测试：新增 `tests/test_cases.py`，断言 `cases/` 下每个 `.md` 都含「现象」「证据」「结论」三段，且至少一条命令带退出码。

### [CRITICAL] fixtures/good_report.md:39 — 示例报告里用了伪造的哈希
- 问题：示例里引用的哈希是编的（8 位十六进制占位值 `a1b2c3d4`）。这个仓库的全部主张是「证据必须是真的」，而它给读者抄的第一个范例，证据是假的。
- 证据：`grep -c "a1b2c3d4" fixtures/good_report.md` → rc=0，命中 1 处；该处引用的哈希只有 8 位十六进制，属占位值。同类占位值另有 3 处（`bad_missing_regression_test.md:24`、`bad_negative_claim.md:24`、`bad_notrun_as_pass.md:30`）。
- 影响：读者照抄格式就会写假哈希。更糟的是这暴露了工具的盲区——`check_report.py` 只认「有 sha256 字样」，不认这个 sha256 是不是真的。
- 修复路径：① 示例改成真实短哈希；② 给 `check_report.py` 加规则 E013，把 `a1b2c3d4` / `deadbeef` / `0000000` / `fffffff` 这类明显占位哈希判为不合格。
- 防回归测试：`tests/test_check_report.py` 加 `test_e013_placeholder_hash`，注入一个占位哈希，断言 E013 触发。

### [WARNING] README.md:1 — 全文没有一节讲「它抓到过什么」
- 问题：仓库叙事是「我有一套方法 + 两个工具」，缺「这套方法改变了什么」。
- 证据：`grep -n "^## " README.md` → rc=0，列出全部二级标题，没有一个是案例 / 战果 / 结果类。
- 影响：读者看完知道「这东西设计得不错」，但不知道「用了它会怎样」。对面试官来说后者才是决策依据。
- 修复路径：加一节「三个真实案例」，每个 300 字以内，链接到 `cases/`。
- 防回归测试：`tests/test_cases.py` 断言 README 至少链接到 3 个 cases 文件。

### [NOTE] references/pitfalls.md:1 — 九族坑全部匿名化，可核验性归零
- 问题：为了脱敏，所有案例都抽象成了「一次实测」「某次」。脱敏是对的，但抽象到读者无法判断这些坑是真踩过还是编的，就损失了全部说服力。
- 证据：`grep -c "一次实测" references/pitfalls.md` → rc=0，命中 1 处；全文没有任何一条带可复现命令的完整案例。
- 影响：这一节从「血泪史」退化成「经验谈」。
- 修复路径：不去匿名化内部项目，而是补 3 个可公开复现的案例（用开源项目或最小复现），放进 `cases/`，pitfalls 里链过去。
- 防回归测试：由 `tests/test_cases.py` 覆盖。

## 负控

- 式四：变异式
  改动：`tools/check_report.py` 的 `rt.strip().lower() in PLACEHOLDERS` 改成 `False and rt.strip().lower() in PLACEHOLDERS`
  命中：出现 1 次（要求 1 次），替换确实生效
  基线：rc=0（绿）
  注入后：rc=1（红）
  还原：sha256 d9a0213e7254ef98… == 改动前；复跑 rc=0（绿）
  判定：把 E004 那条规则弄哑之后测试立刻转红，说明测试套件确实在守这条规则，非假绿

## 压力测试

- 存在性质疑（Existence Question）：把 `tools/` 整个删掉，这个仓库还剩什么？
  剩余：SKILL.md + references 仍是一套可用方法论，能当 prompt 用；但就退化成「又一份 prompt」，与 fullo 那套没有区别。
  Survived: no —— 工具是本仓库唯一的差异化，不能删。

- 时间旅行（Time Travel）：6 个月后，references 里引用的 arXiv 编号还能被查到吗？
  Survived: yes —— 编号是永久标识，不依赖链接存活。

- 规模跳变（Scale Shift）：报告从 3 条 finding 涨到 300 条，这个检查器还成立吗？
  Survived: no —— 14 条规则是行级正则，300 条 finding 时噪声会把真问题埋掉，需要先按严重度分组再看。

## 覆盖缺口

- 未审：GitHub Actions 徽章在 fork 后是否显示 broken（未建 fork 实测）
- 未审：`check_report.py` 对英文报告的识别率（14 条规则的关键词以中文为主，英文报告可能大面积漏检）
- 未审：`negctl.py` 输出在 Linux 下的可读性（CI 覆盖了 ubuntu，但未人工复核记录文本）
- 已知局限：E013 只查 `sha256` 后紧跟的十六进制串，改写措辞即可绕过——它是防手滑，不是防造假
- 符号在场 ≠ 运行正确：29 个测试全绿只证明被测路径正确，不证明真实审查场景下规则够用

## 本次未动什么

- 未改 SKILL.md、references/、tools/ 的任何逻辑（负控那一发已还原，sha256 一致）
- 未改 LICENSE、未改 CI 配置
- 未提交、未推送
