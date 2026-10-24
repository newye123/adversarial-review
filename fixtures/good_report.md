# 对抗式审查报告：支付开关默认值改动

基线：`a593f1b`；本轮未改业务代码、未跑门、未碰两站。审查者只读。

一句话结论：改动本身是对的，但缺一道能拦住「默认值被改回去」的回归测试。

VERDICT: CONCERNS

## findings

### [CRITICAL] src/config/payment.ts:14 — 支付开关默认值从 false 变成 true
- 问题：破了「支付开关默认关闭」这条契约。该契约写在 `docs/invariants.md:22`，任何默认值变更必须先过发布闸。
- 证据：`git diff a593f1b -- src/config/payment.ts` → rc=0，diff 显示 `PAYMENT_ENABLED = false` 改成 `= true`；`grep -rn "PAYMENT_ENABLED" src/` → rc=0，命中 6 处，其中 4 处直接读该常量、无二次开关。
- 影响：测试环境下单未支付也会走支付回调路径，可能产生假订单。生产若同样默认，等于闸门常开。
- 修复路径：默认值改回 false；需要开启的环境用显式 env 覆盖，并在启动时打印一次「支付已开启」。
- 防回归测试：新增 `tests/config/payment-default.test.ts`，断言未设置 env 时 `PAYMENT_ENABLED === false`；并加一条负控（把默认值改回 true，该测试必须红）。

### [WARNING] src/server/webhook.ts:88 — 回调签名校验在 env 缺失时被跳过
- 问题：破了「签名校验不可跳过」这条契约。
- 证据：`grep -rn "SKIP_SIGNATURE" src/` → rc=0，命中 `webhook.ts:88` 一处；该分支条件为 `if (!secret) return true`。
- 影响：部署漏配 secret 时，回调校验静默失效，且日志里没有任何告警。
- 修复路径：`!secret` 时改为抛错并拒绝启动，而不是放行。
- 防回归测试：`tests/server/webhook-nosecret.test.ts`，未配 secret 时断言启动失败（rc≠0）。

### [NOTE] src/server/webhook.ts:31 — 未见对重放攻击的防护
- 问题：契约要求回调幂等，但没看到 nonce 或时间窗校验。
- 证据：`grep -rn "nonce\|timestamp\|replay" src/server/` → rc=1，零命中。该 grep 在零命中时返回 1，已做阳性对照：同一命令换成 `signature` 关键字返回 rc=0、命中 3 处，说明探针本身是好的。
- 影响：同一条回调被重放会重复入账。
- 修复路径：记录已处理 event id，24 小时内重复则直接返回 200。
- 防回归测试：`tests/server/webhook-replay.test.ts`，同一 payload 连发两次，断言只入账一次。

## 负控

- 式四：变异式
  改动：`src/config/payment.ts:14` 的 `= false` 改成 `= true`
  命中：出现 1 次（要求 1 次），替换确实生效
  基线：rc=0（绿）
  注入后：rc=1（红）
  还原：sha256 7f3a9c21e4b8d056… == 改动前；复跑 rc=0（绿）
  判定：新增的默认值测试确实在拦东西，非假绿

## 压力测试

- 需求反转（Requirement Inversion）：如果产品要求「默认开启」，这套推理还剩多少？
  剩余有效：env 覆盖路径与告警日志仍成立。失效：默认值断言需整体反转。
  Survived: no —— 断言绑死在 false 上，需求一反转就全废，应改成「默认值必须等于未设 env 时的显式声明值」。

- 规模跳变（Scale Shift）：并发回调从 1 涨到 1000 会怎样？
  Survived: yes —— 幂等键压在 DB 唯一索引上，与并发数无关。

## 覆盖缺口

- 未审：支付渠道侧的退款回调（无沙箱凭据，未跑）
- 未审：生产环境实际 env 配置（只读了仓库里的 `.env.example`）
- 符号在场 ≠ 运行正确：`webhook.ts:31` 的 nonce 结论基于 grep 零命中，未验证运行时行为

## 本次未动什么

- 未改任何业务代码、未跑发布闸、未碰两站、未提交
