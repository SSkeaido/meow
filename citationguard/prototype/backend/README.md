# Citation Accuracy Checker Backend Prototype

This is the first backend prototype for the citation accuracy checker.

The initial goal is to make the core pipeline testable without requiring an LLM key:

```text
Upload PDF
-> parse pages
-> clean and split text
-> create source chunks
-> generate evidence-card candidates
-> audit user claims against evidence
```

The backend also persists the audit trail required for later export:

```text
Submitted text -> paragraphs -> claims -> audit run -> audit results -> citation ledger
```

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open:

```text
http://localhost:8000/docs
```

## Docker Compose

From the `literature` directory:

```powershell
docker compose up --build
```

Open `http://localhost:8080`. SQLite and vector-index runtime data are kept in
the `backend-data` Docker volume. Override the public port with `APP_PORT`, and
enable invite-only mode with `ACCESS_KEY_REQUIRED=true`.

Every HTTP response includes `X-Request-ID`. The backend logs the request ID,
method, path, status, and duration so errors can be correlated without logging
manuscript text or model payloads.

The Compose stack uses PostgreSQL for structured records and MinIO for uploaded
PDFs. Change all default passwords before exposing it publicly:

```powershell
$env:POSTGRES_PASSWORD="a-long-random-password"
$env:MINIO_ROOT_USER="a-random-access-id"
$env:MINIO_ROOT_PASSWORD="another-long-random-password"
$env:ACCESS_KEY_REQUIRED="true"
docker compose up -d --build
```

Outside Compose, set `DATABASE_URL` to any SQLAlchemy-compatible PostgreSQL URL.
Set `OBJECT_STORAGE_PROVIDER=s3` and provide the `S3_*` values for AWS S3,
Cloudflare R2, MinIO, or another S3-compatible service. Local development keeps
using SQLite and `data/uploads` when those settings are absent.

## Optional Invite-Only Access

Local development remains open by default. To require an invite key, set:

```text
ACCESS_KEY_REQUIRED=true
```

Create a key from the backend directory:

```powershell
$env:PYTHONPATH=(Get-Location).Path
python scripts/create_access_key.py
```

Clients send the resulting secret as `X-Access-Key`. Projects created with a
key are bound to it. A key becomes valid on first successful use and expires
seven days later. Audits are unlimited during that week by default, so a user
can return and upload references in smaller batches. Use `--days` to change the
validity period, or `--audits` to add an optional completed-audit limit.

## Current Scope

The current implementation includes deterministic placeholder logic for evidence extraction and citation audit. This lets us validate the data flow before connecting a real LLM provider through LangChain.

## Persistence

The prototype now uses SQLite for structured app data:

```text
data/app.db
```

It stores projects, papers, source chunks, and evidence cards. Runtime data is ignored by Git through the project `.gitignore`.

The vector index uses Chroma:

```text
data/chroma_source_chunks
```

The current embedding provider is a local deterministic hash embedding. It is useful for validating the retrieval pipeline without an API key, but it should be replaced with a real embedding model before serious evaluation.

## Audit APIs

`POST /api/projects/{project_id}/audits/claim` audits one claim without storing a batch.

`POST /api/projects/{project_id}/audits/batches` accepts pasted text, splits it into paragraphs and sentence-level claim candidates, audits each claim, and persists the audit trail. The request body is:

```json
{
  "text": "First claim.\n\nSecond claim.",
  "source_label": "related-work-draft",
  "language": "en",
  "source": "pasted",
  "cited_paper_ids": ["paper-id"],
  "top_k": 8
}
```

`GET /api/projects/{project_id}/audits/batches/{batch_id}` retrieves the persisted audit results.

The current claim splitter and auditor remain deterministic placeholders. They flag missing citations and references outside the project allow-list, but they do not make scholarly support judgments. The next replacement point is a LangChain structured-output citation-audit chain.

## Optional LLM Citation Audit

The default is local-only and makes no external model request:

```text
LLM_PROVIDER=heuristic
```

To enable an OpenAI-compatible provider, install the updated requirements and set environment variables before starting the API:

```powershell
$env:LLM_PROVIDER="openai_compatible"
$env:LLM_BASE_URL="https://your-provider.example/v1"
$env:LLM_API_KEY="your-key"
$env:LLM_MODEL="your-model"
```

The chain sends only the claim, its cited paper IDs, and at most five evidence quotes or retrieved source chunks. Missing citations, unknown project papers, empty evidence packets, and model-call failures remain deterministic results rather than fabricated LLM judgments.

## SiliconFlow Balanced Launch Route

The project supports the model routing in `siliconflow_model_routing.md`. Add the following values to the process environment, not to source code:

```powershell
$env:SILICONFLOW_API_KEY="your-key"
$env:EMBEDDING_PROVIDER="siliconflow"
$env:RERANK_PROVIDER="siliconflow"
$env:CLAIM_EXTRACTION_PROVIDER="siliconflow"
$env:LLM_PROVIDER="siliconflow"
```

For local development, copy `.env.example` to the ignored `.env` file and fill the values there; the application loads it at startup. Keep production credentials in deployment secrets instead.

The cost-optimized default route is BAAI/bge-m3 for embeddings, BAAI/bge-reranker-v2-m3 for reranking, Qwen/Qwen3.5-35B-A3B for claim extraction, Qwen/Qwen3.5-122B-A10B for the primary audit, and deepseek-ai/DeepSeek-V4-Flash only for primary `RISK` results. This keeps the strongest judgment model on every claim while using a cheaper, independent model for the small disputed subset. Every model name can be overridden with `SILICONFLOW_*_MODEL` environment variables.

Set `OCR_PROVIDER=siliconflow` to enable the PaddleOCR-VL fallback. It renders and sends only pages whose PyMuPDF extraction falls below `OCR_MIN_TEXT_CHARACTERS` (default `80`), and stops after `OCR_MAX_PAGES` (default `10`). Ordinary text PDFs stay on the deterministic parsing path.

Next integration points:

1. Replace `HashEmbeddings` with a real embedding provider.
2. Replace `HeuristicEvidenceExtractor` with a LangChain structured-output chain.
3. Replace `HeuristicCitationAuditor` with a LangChain citation-audit chain.
4. Add review generation and export flows.
