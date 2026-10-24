# 对抗式审查报告：定时任务改动

基线：`f00dfeed`；本轮未改业务代码。

一句话结论：负控记录缺还原这一步。

VERDICT: CONCERNS

## findings

### [WARNING] src/cron/cleanup.ts:33 — 清理任务把保留期从 30 天改成 3 天
- 问题：破了「日志保留不少于 30 天」这条契约。
- 证据：`grep -n "RETENTION_DAYS" src/cron/cleanup.ts` → rc=0，命中 `33: RETENTION_DAYS = 3`。
- 影响：三天前的日志被删，事故回溯时没有现场。
- 修复路径：改回 30，或先改契约。
- 防回归测试：`tests/cron/retention.test.ts` 断言 `RETENTION_DAYS >= 30`。

## 负控

- 式二：抬基线式
  改动：`src/cron/cleanup.ts:33` 的 `= 30` 改成 `= 0`
  基线：rc=0（绿）
  注入后：rc=1（红）
  判定：保留期测试在拦东西

## 覆盖缺口

- 未审：生产定时器的实际调度配置

## 本次未动什么

- 未改代码、未提交
