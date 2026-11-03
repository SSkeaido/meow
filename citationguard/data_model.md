# 数据模型设计

版本：v0.2

日期：2026-07-20

## 设计目标

数据模型服务于一个核心目标：让待检查文本里的每个被引用观点都能追溯到原始 PDF 中的具体证据，并能在后续润色、改写、翻译后重新审计。

核心链路：

```text
Paper -> Source Chunk -> Evidence Card -> ReviewClaim -> Citation Audit -> Export
```

## 实体总览

| 实体 | 作用 |
|---|---|
| User | 用户账号 |
| Project | 一个引用审计项目 |
| Paper | 单篇论文元数据 |
| PaperFile | 用户上传的 PDF 文件 |
| SourceChunk | 从 PDF 中解析出的原文片段 |
| EvidenceCard | 可用于核查的结构化证据 |
| ClaimBatch | 一次待检查文本提交 |
| ReviewParagraph | 一次提交中的段落 |
| ReviewClaim | 段落中的可审计观点 |
| CitationLedger | 引用台账 |
| AuditRun | 一次审计任务 |
| AuditResult | 某个 claim 的审计结果 |
| ModelCallLog | 模型调用记录 |

## User

```text
id
email
name
password_hash
created_at
updated_at
```

第一版可以先做单用户本地版，后续再加完整账号系统。

## Project

```text
id
user_id
name
description
privacy_mode: cloud_standard / privacy_enhanced / bring_your_own_key / local_private
default_citation_style: APA / MLA / GB_T_7714 / IEEE
created_at
updated_at
deleted_at
```

说明：

1. 一个项目对应一个研究主题、论文写作任务或一组待审计段落。
2. `privacy_mode` 决定文件存储、模型调用和日志策略。

## Paper

```text
id
project_id
title
authors_json
year
journal_or_conference
doi
url
abstract
source: upload / doi / bibtex / openalex / crossref / semantic_scholar / pubmed / arxiv
citation_key
metadata_json
created_at
updated_at
```

## PaperFile

```text
id
paper_id
project_id
original_filename
file_hash
storage_path
mime_type
page_count
parse_status: pending / parsing / parsed / failed
parse_error
uploaded_at
deleted_at
```

## SourceChunk

```text
id
paper_id
paper_file_id
project_id
chunk_index
section
section_type: abstract / introduction / method / result / discussion / conclusion / limitation / reference / caption / unknown
page_start
page_end
text
cleaned_text
char_start
char_end
token_estimate
embedding_id
metadata_json
created_at
```

## EvidenceCard

```text
id
project_id
paper_id
source_chunk_id
claim_type: background / problem / method / data / result / limitation / future_work
summary
source_quote
page
section
support_scope
limitations
confidence
generated_by
created_at
updated_at
```

核心约束：

1. `source_quote` 必须能在 `SourceChunk.text` 中找到。
2. Evidence card 不能引入原文没有的信息。
3. 如果证据不足，应返回 `insufficient_evidence`。

## ClaimBatch

```text
id
project_id
source_label
language
source: pasted / imported / polished
status: pending / audited / exported
created_at
updated_at
```

## ReviewParagraph

```text
id
claim_batch_id
project_id
paragraph_index
text
polished_text
source: user_written / imported / polished
created_at
updated_at
```

说明：

1. `text` 是审计前文本。
2. `polished_text` 用于润色后再审计。
3. 当前程序不负责编辑或生成这些段落，只负责接收并审计它们。

## ReviewClaim

```text
id
review_paragraph_id
project_id
claim_index
claim_text
normalized_claim
claim_type: background / comparison / causal / result / limitation / future_work / recommendation
strength: weak / moderate / strong
cited_paper_ids_json
evidence_card_ids_json
created_at
updated_at
```

## CitationLedger

```text
id
project_id
claim_batch_id
review_paragraph_id
review_claim_id
paper_id
evidence_card_id
citation_key
usage_type: background / method_support / result_support / contrast / limitation / example
last_audit_status: PASS / CHECK / RISK / FAIL
last_audited_at
created_at
updated_at
```

Citation ledger 记录“这篇文献在我的待检查文本中被用来支撑什么观点”，而不是只记录“我引用过这篇文献”。

## AuditRun

```text
id
project_id
claim_batch_id
run_type: user_text_audit / polish_audit / batch_audit
status: pending / running / completed / failed
model_provider
model_name
started_at
finished_at
error_message
```

## AuditResult

```text
id
audit_run_id
project_id
review_claim_id
claim_text
cited_paper_ids_json
supporting_evidence_ids_json
support_level: PASS / CHECK / RISK / FAIL
risk_flags_json
explanation
suggested_fix
sent_payload_summary
created_at
```

## ModelCallLog

```text
id
project_id
task_type: evidence_extraction / claim_audit / polish_audit
model_provider
model_name
input_token_estimate
output_token_estimate
cache_hit
privacy_mode
payload_policy: full_text_forbidden / minimal_chunks / local_only
created_at
```

## 向量库 Metadata

chunk embedding metadata：

```text
project_id
paper_id
paper_file_id
source_chunk_id
section_type
page_start
page_end
title
year
doi
```

evidence embedding metadata：

```text
project_id
paper_id
evidence_card_id
claim_type
page
section
citation_key
```

## 第一版最小表

MVP 可以先实现这些：

```text
projects
papers
paper_files
source_chunks
evidence_cards
claim_batches
review_paragraphs
review_claims
audit_runs
audit_results
```

暂缓：

```text
users
team permissions
billing
full model call audit
advanced citation ledger UI
```
