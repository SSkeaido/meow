# SiliconFlow 中文模型选型与成本测算

版本：v0.1

日期：2026-07-20

## 1. 目标

这份文档只服务当前产品范围：

```text
引用准确性检查器
```

它不讨论“自动生成综述正文”，只讨论下面这条链路该如何选模型：

```text
PDF 解析
-> 文本清洗
-> 切块与索引
-> claim 抽取
-> 候选证据检索
-> rerank
-> claim 级 citation audit
-> 高风险 claim 复核
```

## 2. 为什么优先考虑 SiliconFlow 上的中文模型

对我们这个产品，优先选 SiliconFlow 上可直接购买 token 的中文模型，有四个现实好处：

1. 采购简单，适合 MVP 快速上线。
2. 中文指令理解更稳，适合中文论文、中文摘要、中文批注和中文 UI。
3. 同一个平台就能拿到 chat、embedding、rerank、OCR/VLM 能力，工程接入更统一。
4. 未来如果做 BYOK 模式，用户自己填 SiliconFlow API Key 也更容易解释。

## 3. 先说结论

当前最推荐的默认路线不是“全链路都上一个大模型”，而是：

```text
传统 PDF 解析
+ 免费 embedding / rerank
+ 低价中文推理模型做主审计
+ 更强模型只复核高风险 claim
```

如果今天就开始做商业 MVP，我建议优先这样配：

| 链路 | 推荐模型/组件 | 作用 | 备注 |
|---|---|---|---|
| PDF 解析 | PyMuPDF / pdfplumber / GROBID | 抽正文、页码、章节、参考文献 | 不走 LLM，先省掉大头成本 |
| OCR 兜底 | PaddleOCR-VL-1.5 | 处理扫描版 PDF、复杂版面 | 只在解析失败时启用 |
| Embedding | BAAI/bge-m3 | 中文检索向量化 | 当前公开价格页显示免费 |
| Rerank | BAAI/bge-reranker-v2-m3 | claim 到证据片段重排 | 当前公开价格页显示免费 |
| Claim 抽取 | Qwen/Qwen3.5-35B-A3B | 从待审文本抽 claim | 成本低，足够做第一层结构化 |
| 主审计 | Qwen/Qwen3.5-122B-A10B 或 Qwen/Qwen3.5-35B-A3B | 判断引用是否支持 claim | 二选一，取决于准确率目标 |
| 高风险复核 | deepseek-ai/DeepSeek-V4-Flash | 复核 disputed / risky claim | 独立模型且输出价格更低，只打到少量 claim 上 |

## 4. 不同档位的推荐

### 4.1 低成本版

适合：

```text
MVP
学生版
低价 SaaS 套餐
```

推荐：

| 环节 | 方案 |
|---|---|
| Embedding | BAAI/bge-m3 |
| Rerank | BAAI/bge-reranker-v2-m3 |
| Claim 抽取 | Qwen/Qwen3.5-35B-A3B |
| 主审计 | Qwen/Qwen3.5-35B-A3B |
| 复核 | 不默认开启，或只人工复核 |

优点：

1. 成本最低。
2. 技术路径最简单。
3. 对中文任务已经足够可用。

不足：

1. 对复杂因果表述、限定条件、跨句合并 claim 的审计会更保守。
2. 高风险学术场景下，人工复核压力会更大。

### 4.2 平衡版

适合：

```text
正式商业 MVP
教师 / 研究团队
医院知识整理团队
```

推荐：

| 环节 | 方案 |
|---|---|
| Embedding | BAAI/bge-m3 |
| Rerank | BAAI/bge-reranker-v2-m3 |
| Claim 抽取 | Qwen/Qwen3.5-35B-A3B |
| 主审计 | Qwen/Qwen3.5-122B-A10B |
| 高风险复核 | deepseek-ai/DeepSeek-V4-Flash |

这是我最推荐的首发商用组合，因为：

1. 便宜步骤继续便宜。
2. 真正影响结果质量的 claim 审计，换到更强模型。
3. 高风险 claim 再单独复核，整体准确率会明显更稳。

### 4.3 严格版

适合：

```text
高风险学术场景
医学论文
投稿前终审
机构版
```

推荐：

| 环节 | 方案 |
|---|---|
| Embedding | BAAI/bge-m3 或 Qwen/Qwen3-Embedding-8B 做 A/B 测试 |
| Rerank | BAAI/bge-reranker-v2-m3 或 Qwen/Qwen3-Reranker-8B 做 A/B 测试 |
| Claim 抽取 | Qwen/Qwen3.5-122B-A10B |
| 主审计 | Qwen/Qwen3.6-35B-A3B |
| 高风险复核 | Qwen/Qwen3.6-27B |

这档不是默认推荐给所有用户，因为它的性价比没有前两档那么高。

## 5. 为什么 embedding 和 rerank 先用 BGE

不是因为 Qwen 不好，而是因为当前公开信息下，BGE 这条路对 MVP 更稳：

1. BAAI/bge-m3 在 SiliconFlow 公开价格页当前显示免费。
2. BAAI/bge-reranker-v2-m3 在 SiliconFlow 公开价格页当前显示免费。
3. BGE 本来就是中文和多语检索常用基线，适合先把检索质量打稳。
4. 我们真正要花钱的地方，应该优先放在 claim 审计这一步。

因此更合理的策略是：

```text
先用免费检索链路把召回和证据定位做稳
再把预算花在“这条证据到底支不支持这个 claim”的判断上
```

## 6. 150 篇参考文献体量下，成本真正由什么决定

“150 篇参考文献”听起来很大，但对这个产品来说，成本主要不由参考文献数量决定，而由下面三项决定：

1. 实际上传了多少篇全文 PDF。
2. 待审稿件里有多少个需要审计的 claim。
3. 有多少 claim 会进入第二轮高风险复核。

也就是说：

```text
150 篇参考文献 != 一定很贵
```

如果我们坚持“只把候选证据片段发给模型”，那成本会比“整篇论文喂给模型”低很多。

## 7. 成本测算假设

下面给一组偏保守、但适合商业估算的假设。

### 7.1 业务假设

1. 用户正在检查 1 篇目标论文。
2. 该论文有 150 篇参考文献。
3. 用户已上传这 150 篇参考文献的 PDF 或大部分 PDF。
4. 目标论文中有 90 个需要审计的 claim。
5. 每个 claim 最终送入主审计模型的上下文约为 2400 tokens。
6. 每个 claim 主审计平均输出 280 tokens。
7. 20% 的高风险 claim 进入第二轮复核。
8. 每个复核 claim 输入约 3200 tokens，输出约 420 tokens。
9. Embedding 和 rerank 先按 BGE 免费档估算。

### 7.2 工程假设

我们不做下面这种高成本设计：

```text
把 150 篇 PDF 全文直接发给大模型
```

我们做的是：

```text
parser 抽文本
-> chunk 入库
-> vector recall
-> rerank
-> 只把 top-k 候选证据送给 LLM
```

## 8. 150 参考文献规模下的粗略成本

### 8.1 低成本版

假设：

| 环节 | 模型 |
|---|---|
| Claim 抽取 | Qwen/Qwen3.5-35B-A3B |
| 主审计 | Qwen/Qwen3.5-35B-A3B |
| 复核 | 不开，或人工复核 |

粗略成本：

1. Claim 抽取：约 0.01 到 0.03 元 / 篇目标论文
2. 主审计：约 0.12 到 0.20 元 / 篇目标论文
3. 总体：约 0.15 到 0.25 元 / 篇目标论文

适合拿来做：

```text
免费试用
新用户首单
低价套餐
```

### 8.2 平衡版

假设：

| 环节 | 模型 |
|---|---|
| Claim 抽取 | Qwen/Qwen3.5-35B-A3B |
| 主审计 | Qwen/Qwen3.5-122B-A10B |
| 高风险复核 | deepseek-ai/DeepSeek-V4-Flash |

粗略成本：

1. Claim 抽取：约 0.01 到 0.03 元
2. 主审计：约 0.20 到 0.30 元
3. 高风险复核：约 0.15 到 0.25 元
4. 总体：约 0.40 到 0.60 元 / 篇目标论文

这是当前最适合商用首发的区间。

### 8.3 严格版

假设：

| 环节 | 模型 |
|---|---|
| Claim 抽取 | Qwen/Qwen3.5-122B-A10B |
| 主审计 | Qwen/Qwen3.6-35B-A3B |
| 高风险复核 | Qwen/Qwen3.6-27B |

粗略成本：

1. Claim 抽取：约 0.03 到 0.06 元
2. 主审计：约 0.35 到 0.60 元
3. 高风险复核：约 0.30 到 0.70 元
4. 总体：约 0.80 到 1.50 元 / 篇目标论文

这个区间依然不算高，但不建议所有用户默认都走这档。

## 9. 什么时候成本会突然上升

下面几种情况会让成本明显变高：

1. 你把整篇论文正文直接丢给大模型，而不是先做检索筛选。
2. 你对每个 claim 都做双模型交叉复核。
3. 你审计的不是 90 个 claim，而是 200 到 300 个 claim。
4. 大量 PDF 是扫描件，必须启用 OCR/VLM 兜底。
5. 你让模型顺带做长篇解释、重写建议、润色建议，而不是只返回结构化审计结果。

所以产品上要刻意限制模型输出：

```text
只返回 verdict
+ risk flags
+ evidence quote
+ fix suggestion
```

而不是默认输出一大段散文解释。

## 10. 隐私模式下的模型接入建议

### 10.1 标准云模式

方案：

```text
解析后文本和候选证据片段经后端发往 SiliconFlow
```

适合：

```text
普通用户
MVP
公开资料
```

优点：

1. 接入最快。
2. 成本最低。
3. 便于统一计费。

### 10.2 BYOK 模式

方案：

```text
用户自己填写 SiliconFlow API Key
我们负责流程编排，不承担 token 成本
```

适合：

```text
高频科研用户
实验室管理员
对账单透明度要求高的团队
```

优点：

1. 用户更放心。
2. 平台现金流压力更小。
3. 企业版更容易谈。

### 10.3 隐私增强模式

方案：

```text
PDF 原文、chunk、向量库保留在本地或私有云
只把 claim + top-k evidence snippets 发往 SiliconFlow
```

适合：

```text
医学和临床研究
未投稿手稿
敏感课题
```

这是我认为最现实、最值得优先落地的隐私方案。

### 10.4 全私有模式

方案：

```text
本地向量库
+ 本地推理服务
+ 开源 Qwen 权重自部署
```

这时就不再是“买 SiliconFlow token”的方案，而是另一条产品线。

## 11. 对 LangChain 的落地建议

如果我们确定以 LangChain 为主框架，建议这么接：

| 能力 | LangChain 角色 |
|---|---|
| Chat 模型 | 用 OpenAI-compatible 接口接 SiliconFlow chat model |
| Embedding | 接 SiliconFlow embedding endpoint，或保留本地 embedding 适配层 |
| Retrieval | VectorStoreRetriever |
| Rerank | 自定义 Runnable 包装 SiliconFlow rerank API |
| Claim 抽取 | Structured output chain |
| Citation Audit | LCEL chain |
| 高风险复核 | Router chain / conditional branch |
| 导出报告 | 后端模板渲染，不占模型预算 |

一个重要原则：

```text
LangChain 负责编排
不是让 LangChain 帮我们“多生成一些字”
```

## 12. 当前推荐的商业化首发方案

如果今天让我拍板，我会这样定：

### 产品默认链路

1. PDF 解析：PyMuPDF / pdfplumber
2. OCR 兜底：PaddleOCR-VL-1.5
3. Embedding：BAAI/bge-m3
4. Rerank：BAAI/bge-reranker-v2-m3
5. Claim 抽取：Qwen/Qwen3.5-35B-A3B
6. 主审计：Qwen/Qwen3.5-122B-A10B
7. 高风险复核：deepseek-ai/DeepSeek-V4-Flash

### 商业意义

1. 成本仍然很低。
2. 中文体验好。
3. 隐私增强模式容易实现。
4. 后续还能加 BYOK。
5. 适合先从医学、教育、科研团队切入。

## 13. 还需要做的验证

这份文档解决的是“工程和商业上大致怎么配”，但在正式定型前，还要做三组 A/B 测试：

1. BGE vs Qwen embedding，在中文医学语料上的召回率差异。
2. Qwen3.5-35B-A3B vs Qwen3.5-122B-A10B，在 claim 审计上的误报率差异。
3. Qwen3.6-35B-A3B vs Qwen3.6-27B，在高风险复核上的稳定性差异。

## 14. 官方页面核实记录

以下信息基于 2026-07-20 可公开访问页面核实：

1. SiliconFlow 公开模型页可见 Qwen 系列模型。
2. SiliconFlow 公开价格页可见 Qwen3.6、Qwen3.5、BGE、PaddleOCR-VL-1.5 等条目。
3. SiliconFlow API 文档可见 embedding 和 rerank 接口，且公开文档中能检索到 Qwen3-Embedding-8B 与 Qwen3-Reranker-8B。
4. SiliconFlow API 文档可见 Batch API，标注价格约为同步调用的 50%。

官方链接：

- https://siliconflow.cn/models
- https://siliconflow.cn/pricing
- https://api-docs.siliconflow.cn/docs/api/embeddings-post
- https://api-docs.siliconflow.cn/docs/api/rerank-post
- https://api-docs.siliconflow.cn/docs/api/batch-api
