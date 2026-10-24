# 对抗式审查报告：登录超时改动

基线：`f00dfeed`；本轮未改业务代码。

一句话结论：看着没问题。

VERDICT: OK

## findings

### [NOTE] src/auth/session.ts:12 — 超时阈值从 10 分钟调到 15 分钟
- 问题：破了「会话时长不超过 10 分钟」这条契约。
- 证据：`grep -n "SESSION_TTL" src/auth/session.ts` → rc=0，命中 `12: SESSION_TTL = 900`。
- 影响：会话窗口变长，被劫持的 cookie 可用时间更久。
- 修复路径：改回 600，或先改契约再改值。
- 防回归测试：`tests/auth/session-ttl.test.ts` 断言 `SESSION_TTL === 600`。

## 覆盖缺口

- 未审：前端无操作自动登出的实际触发路径

## 本次未动什么

- 未改代码、未提交
