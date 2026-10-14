# MVP 架构设计

版本：v0.2

日期：2026-07-20

## 目标

第一版 MVP 验证一个闭环：

```text
上传 PDF
-> 解析和切块
-> 生成 evidence cards
-> 导入待检查段落或 claim
-> 对段落做 citation audit
-> 展示证据链和导出结果
```

## 技术选型

```text
Frontend: React / Next.js
Backend: FastAPI
LLM Orchestration: LangChain LCEL
PDF Parsing: PyMuPDFLoader, PDFPlumberLoader
Text Splitting: RecursiveCharacterTextSplitter + custom section splitter
Vector Store: Chroma for MVP, later pgvector / Qdrant
Database: SQLite for local MVP, later PostgreSQL
Task Queue: BackgroundTasks for MVP, later Celery / RQ
Export: Markdown + CSV
```

MVP 可以先做本地开发版，降低部署复杂度。

## 服务模块

```text
app/
  api/
    papers.py
    evidence.py
    audits.py
    claims.py
  core/
    config.py
    privacy.py
    logging.py
  pdf/
    loader.py
    cleaner.py
    splitter.py
  rag/
    embeddings.py
    vectorstore.py
    retriever.py
  chains/
    evidence_extraction.py
    citation_audit.py
    polish_audit.py
  models/
    schemas.py
    database.py
  exports/
    markdown.py
    csv.py
```

## 端到端流程

### Step 1: 上传 PDF

API：

```text
POST /api/projects/{project_id}/papers/upload
```

行为：

1. 保存文件。
2. 计算 file hash。
3. 创建 PaperFile。
4. 如果 hash 已存在，复用解析结果。

### Step 2: 解析 PDF

LangChain 组件：

```text
PyMuPDFLoader
PDFPlumberLoader
```

行为：

1. 按页读取 PDF。
2. 保存 page metadata。
3. 清洗页眉页脚、断行、无效字符。
4. 初步识别 section。
5. 生成 SourceChunk。

### Step 3: 切块和向量化

LangChain 组件：

```text
RecursiveCharacterTextSplitter
Embeddings
Chroma
```

行为：

1. 按 section 优先切块。
2. 对 chunks 生成 embedding。
3. 写入 Chroma。
4. metadata 中保留 paper_id、page、section_type、source_chunk_id。

### Step 4: 生成 Evidence Cards

Chain：

```text
EvidenceExtractionChain
```

输入：

```text
paper metadata
core section chunks
```

策略：

1. 优先处理 Abstract、Introduction、Methods、Results、Discussion、Conclusion、Limitations。
2. 每次只给模型少量候选 chunks。
3. 使用 structured output 生成 EvidenceCard。
4. 检查 source_quote 是否能回查到原文。

输出：

```text
evidence_cards
source_quote
page
section
confidence
```

### Step 5: 导入待检查文本

API：

```text
POST /api/projects/{project_id}/claims/audit
```

输入：

```text
paragraph_text
optional cited paper ids
citation allow-list
```

输出：

```text
claim_list
created claim records
```

约束：

1. 当前程序不生成综述正文。
2. 用户输入文本或从外部草稿导入文本。
3. claim 进入审计前必须先抽取引用和候选 evidence。

### Step 6: Citation Audit

Chain：

```text
CitationAuditChain
```

输入：

```text
paragraph
claims
cited papers
candidate evidence
```

流程：

```text
claim extraction
-> citation extraction
-> retriever top-k evidence
-> support judgment
-> risk flags
```

输出：

```text
AuditResult
support_level
risk_flags
explanation
suggested_fix
```

### Step 7: 导出

MVP 导出：

```text
audit_report.md
evidence_cards.csv
audit_report.csv
citation_ledger.csv
```

后续再支持 DOCX 和 PDF。

## LangChain LCEL 流程草图

```text
load_pdf
| clean_documents
| split_documents
| embed_and_store
| retrieve_core_chunks
| evidence_extraction_chain
| citation_audit_chain
```

MVP 不需要一开始就引入复杂 Agent。每个 chain 都应能独立运行和测试。

## API 草案

```text
POST /api/projects
GET  /api/projects/{project_id}

POST /api/projects/{project_id}/papers/upload
GET  /api/projects/{project_id}/papers
GET  /api/papers/{paper_id}/chunks

POST /api/papers/{paper_id}/evidence/generate
GET  /api/projects/{project_id}/evidence

POST /api/projects/{project_id}/claims/audit
POST /api/projects/{project_id}/polish-audit
GET  /api/audits/{audit_run_id}

POST /api/projects/{project_id}/export-audit
```

## 前端页面

### Project Dashboard

显示：

```text
项目名称
已上传论文
evidence cards 数量
待检查批次数量
最近 audit 状态
```

### Paper Workspace

显示：

```text
PDF 列表
解析状态
论文元数据
chunks 预览
evidence cards
```

### Evidence Board

显示：

```text
按 claim_type 分组的 evidence cards
source quote
页码
confidence
support scope
```

### Audit Panel

显示：

```text
每个 claim 的 PASS / CHECK / RISK / FAIL
引用论文
支持证据
风险说明
建议改写
```

## MVP 开发顺序

1. 后端项目骨架。
2. PDF 上传和解析。
3. chunk 存储和向量库。
4. evidence extraction chain。
5. evidence board 前端。
6. citation audit chain。
7. audit panel 前端。
8. Markdown/CSV 导出。

## 可测试标准

MVP 完成时，应能用 3-5 篇 PDF 完成：

1. 成功解析论文文本和页码。
2. 生成不少于 20 张 evidence cards。
3. 导入 1-3 段待检查文本后能完成 claim 级审计。
4. 每个 claim 都有 audit 状态。
5. 至少能识别 missing citation、overgeneralization、unsupported claim 三类风险。
6. 导出的 Markdown 和 CSV 能回溯到原文页码。

## 后续升级

```text
LangGraph 工作流
PostgreSQL + pgvector
Qdrant
用户自带 API Key
本地模型
DOCX 导出
润色后再审计
论文关系图
```
