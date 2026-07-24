# Citation Audit 规则设计

版本：v0.1

日期：2026-07-20

## 目标

Citation Audit 的目标不是判断论文结论是否绝对正确，而是判断：

```text
综述中的某个 claim 是否被其引用的文献证据合理支持。
```

系统需要帮助用户发现引用漂移、过度概括、语气变强、引用错位和润色后语义变化。

## 审计粒度

审计最小单位是 claim，而不是整篇综述，也不是整段文本。

流程：

```text
paragraph
-> claim extraction
-> citation extraction
-> evidence retrieval
-> support judgment
-> risk flags
-> suggested fix
```

## Support Level

| 等级 | 含义 | 用户动作 |
|---|---|---|
| PASS | 引用证据充分支持该 claim | 可以保留 |
| CHECK | 部分支持或需要人工确认 | 用户应检查原文 |
| RISK | 存在明显风险，如过度概括或语义漂移 | 建议修改 |
| FAIL | 没有找到支撑证据或引用错位 | 不建议保留 |

## 风险标签

### overgeneralization

过度概括。

典型情况：

```text
原文：在 42 名老年患者中观察到改善。
综述：该方法能改善患者预后。
```

判断规则：

1. claim 把有限样本推广到普遍人群。
2. claim 删除了时间、地点、样本、任务或实验条件。
3. claim 用 `widely`, `generally`, `all`, `consistently` 等强泛化词。

### causal_overclaim

因果夸大。

典型情况：

```text
原文：A 与 B 存在相关性。
综述：A 导致 B。
```

判断规则：

1. 原文是 observational / correlation / association。
2. claim 使用 cause、lead to、result in、drive、determine 等因果表达。
3. 原文没有随机对照、机制实验或因果识别设计。

### population_mismatch

研究对象不匹配。

典型情况：

```text
原文：儿童样本。
综述：成年人或所有患者。
```

判断规则：

1. 原文对象和 claim 对象不一致。
2. 原文是动物实验、细胞实验或模拟数据，claim 写成人类临床结论。
3. 原文是特定国家/机构/数据集，claim 写成全球结论。

### method_mismatch

方法或任务不匹配。

典型情况：

```text
原文：方法用于分类任务。
综述：方法适用于预测和生成任务。
```

判断规则：

1. claim 中的方法用途超出原文实验范围。
2. 原文比较的是 A 与 B，claim 写成 A 优于所有方法。
3. 原文是可行性研究，claim 写成性能已充分验证。

### missing_citation

缺少引用。

判断规则：

1. claim 明显是事实性、比较性或结论性陈述，但没有引用。
2. 段落末尾引用不能覆盖前面多个独立 claim。
3. 多个 claim 共用一个引用，但 evidence 只支持其中一个。

### citation_not_in_allow_list

引用不在白名单中。

判断规则：

1. 生成段落引用了没有进入当前 evidence packet 的论文。
2. 模型编造了不存在的 citation key。
3. 引用格式存在，但无法匹配 Paper 表。

### unsupported_claim

没有证据支持。

判断规则：

1. 检索不到任何相关 evidence。
2. 检索到的 evidence 与 claim 主题相近，但不支持 claim。
3. claim 包含原 evidence 中没有的结论、比较或限定。

### semantic_drift_after_polish

润色后语义漂移。

典型情况：

```text
原句：may improve
润色后：significantly improves
```

判断规则：

1. 润色后语气更强。
2. 润色后新增因果关系。
3. 润色后删除限定条件。
4. 润色后改变研究对象、范围或方法。

### quote_not_found

原文 quote 无法定位。

判断规则：

1. EvidenceCard.source_quote 无法在 SourceChunk.text 中找到。
2. 页码或章节 metadata 缺失。
3. 引用来自模型生成摘要，而不是原文。

## Claim Extraction 规则

需要抽取的 claim 类型：

```text
背景事实
研究趋势
方法比较
结果陈述
因果解释
局限总结
未来方向
```

不需要审计的文本：

```text
纯过渡句
作者自己的研究动机
章节导航句
没有事实含义的修辞句
```

## Evidence Retrieval 规则

检索顺序：

```text
1. 优先在段落已引用论文中检索
2. 如果没有引用，在当前项目 evidence cards 中检索
3. 如果仍不足，提示 missing citation，而不是自动添加陌生引用
```

检索过滤：

```text
project_id
paper_id in citation_allow_list
section_type in relevant_sections
```

召回建议：

```text
top_k_vector = 20
top_k_after_rerank = 5
max_evidence_sent_to_llm = 5
```

## LLM 审计提示原则

审计模型必须遵守：

1. 只判断 evidence 是否支持 claim。
2. 不要补充外部知识。
3. 不要因为 claim 看起来合理就判 PASS。
4. 如果 evidence 不足，返回 CHECK 或 FAIL。
5. 输出必须包含风险标签和简短解释。

## 输出格式

```text
claim_text
support_level
risk_flags
supporting_evidence_ids
explanation
suggested_fix
```

示例：

```text
claim_text: Transformer-based models significantly improve diagnosis in clinical NLP.
support_level: RISK
risk_flags: ["overgeneralization", "causal_overclaim"]
explanation: The cited evidence reports improved performance on one dataset, but does not support a general diagnostic claim.
suggested_fix: Narrow the claim to the evaluated dataset and task.
```

## 用户界面呈现

每个 claim 显示：

```text
状态标签
引用论文
支持证据原文
页码
风险说明
建议改写
```

颜色建议：

```text
PASS: green
CHECK: yellow
RISK: orange
FAIL: red
```

用户操作：

```text
接受
修改 claim
替换引用
添加证据
标记为已人工确认
```

