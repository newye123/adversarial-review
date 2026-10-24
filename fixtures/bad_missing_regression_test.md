# 对抗式审查报告：上传并发改动

基线：`f00dfeed`；本轮未改业务代码。

一句话结论：有一条 finding 没有防回归测试。

VERDICT: CONCERNS

## findings

### [WARNING] src/upload/chunk.ts:64 — 分片拼接前未校验总字节数
- 问题：破了「拼接前必须逐块核对字节数」这条契约。
- 证据：`grep -n "concat" src/upload/chunk.ts` → rc=0，命中 `64: await concat(chunks)`，其上一行只有长度判空。
- 影响：丢块时会把残缺文件当成完整文件写入，且不报错。
- 修复路径：拼接前累加各块 byteLength，与 `Content-Length` 比对，不等则抛错。
- 防回归测试：无

## 负控

- 式一：短路式
  改动：`src/upload/chunk.ts:64` 的 `await concat(chunks)` 改成 `await concat(chunks.slice(0, 1))`
  基线：rc=0（绿）
  注入后：rc=1（红）
  还原：sha256 deadbeef… == 改动前
  判定：拼接测试在拦东西

## 覆盖缺口

- 未审：断点续传的恢复路径

## 本次未动什么

- 未改代码、未提交
