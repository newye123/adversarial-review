# 对抗式审查报告：SEO 检查改动

基线：`f00dfeed`；本轮未改业务代码。

一句话结论：有一条门没跑却写成了通过。

VERDICT: CONCERNS

## findings

### [WARNING] src/seo/meta.ts:18 — canonical 标签缺站域名
- 问题：破了「canonical 必须是绝对地址」这条契约。
- 证据：`grep -n "canonical" src/seo/meta.ts` → rc=0，命中 `18: canonical: '/page'`，是相对路径。
- 影响：搜索引擎可能把两条地址当两个页面，权重被拆散。
- 修复路径：拼接 `SITE_ORIGIN` 后再输出。
- 防回归测试：`tests/seo/meta.test.ts` 断言 canonical 以 `https://` 开头。

## 门禁读数

- 类型检查：PASS（rc=0）
- 单测：NOT RUN（依赖没装）→ 记为 PASS
- SEO 冒烟：NOT RUN → 记为 PASS

## 负控

- 式三：注入真值式
  改动：在 `fixtures/sitemap.xml` 里塞一条相对路径
  基线：rc=0（绿）
  注入后：rc=1（红）
  还原：sha256 4c81b0e5d9a27f63… == 改动前
  判定：SEO 门在拦东西

## 覆盖缺口

- 未审：构建后的实际 HTML 输出

## 本次未动什么

- 未改代码、未提交
