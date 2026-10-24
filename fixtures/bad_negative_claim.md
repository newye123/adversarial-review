# 对抗式审查报告：导出功能改动

基线：`f00dfeed`；本轮未改业务代码。

一句话结论：有一处否定式断言没给出处。

VERDICT: CONCERNS

## findings

### [WARNING] src/export/csv.ts:27 — 导出未做字段转义
- 问题：破了「导出必须转义逗号与引号」这条契约。
- 证据：检查过了，没有发现任何转义逻辑。
- 影响：字段里带逗号时列会错位。
- 修复路径：改用现成的 CSV 序列化库，或手工双引号包裹并转义内部引号。
- 防回归测试：`tests/export/csv-escape.test.ts`，字段含 `a,b` 时断言输出为 `"a,b"`。

## 负控

- 式一：短路式
  改动：`src/export/csv.ts:27` 的 `return escape(row)` 改成 `return row.join(',')`
  基线：rc=0（绿）
  注入后：rc=1（红）
  还原：sha256 4c81b0e5d9a27f63… == 改动前
  判定：转义测试在拦东西

## 覆盖缺口

- 未审：Excel 直接打开时的编码识别

## 本次未动什么

- 未改代码、未提交
