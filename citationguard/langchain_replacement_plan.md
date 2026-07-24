# LangChain 引用审计替换计划

版本：v0.2

日期：2026-07-20

## 当前状态

后端原型已经跑通 API 和数据流，但目前有两处是占位逻辑：

```text
prototype/backend/app/services/evidence_extractor.py
prototype/backend/app/services/auditor.py
```

当前占位实现：

1. `HeuristicEvidenceExtractor`：从核心章节 chunk 中截取第一句话，生成伪 evidence card。
2. `HeuristicCitationAuditor`：用关键词重合度判断 claim 和 evidence 是否相关。

它们只用于验证接口和流程，不能用于真实学术写作。

## 替换目标

把占位逻辑替换为 LangChain 管线：

```text
PDF chunks
-> embeddings
-> vector store
-> retriever
-> Evidence Extraction Chain
-> Citation Audit Chain
```

关键原则：

```text
不把整篇 PDF 喂给 LLM。
只把候选 chunks 或 evidence cards 发给 LLM。
所有 LLM 输出必须结构化。
每个 source_quote 必须能回查到原文 chunk。
```

## Step 1: 加入 Embedding 和 Vector Store

目标：让 PDF chunks 可检索，而不是在内存里线性扫描。

推荐实现：

```text
langchain_chroma.Chroma
```

Embedding 可以先做两种 provider：

```text
OpenAI-compatible embedding
本地 BGE-M3 embedding
```

新增模块：

```text
app/rag/embeddings.py
app/rag/vectorstore.py
app/rag/retriever.py
```

## Step 2: 替换 Evidence Extraction

当前文件：

```text
app/services/evidence_extractor.py
```

替换为：

```text
LangChainEvidenceExtractor.generate()
```

输出使用 structured output：

```text
EvidenceCardOutput {
  claim_type
  summary
  source_quote
  support_scope
  limitations
  confidence
  insufficient_evidence
}
```

## Step 3: 加入 Retriever

目标：Citation audit 时不读取全文，只检索和 claim 相关的证据。

检索流程：

```text
claim_text
-> filter paper_id in cited_paper_ids
-> vector similarity top 20
-> rerank top 5
-> 只把 top 5 发给 LLM
```

MVP 简化版：

```text
Chroma similarity_search(query, k=8, filter={project_id, paper_id})
```

## Step 4: 替换 Citation Audit

当前文件：

```text
app/services/auditor.py
```

替换为：

```text
LangChainCitationAuditor.audit_claim()
```

Chain 输入：

```text
claim_text
cited_paper_ids
candidate evidence cards
source quotes
page metadata
```

Chain 输出：

```text
AuditResultOutput {
  support_level: PASS / CHECK / RISK / FAIL
  supporting_evidence_ids
  risk_flags
  explanation
  suggested_fix
}
```

## 当前判断

当前程序不做 review generation。优先把证据抽取、向量检索和 claim 级审计做到可靠，再考虑是否把文本生成放到另一个独立程序中。
