from fastapi import APIRouter, Depends

from fastapi import HTTPException

from app.models.schemas import AccessKeyRecord, AuditBatchDetail, AuditRequest, AuditResult, BatchAuditResponse, ClaimBatchCreate
from app.rag.retriever import chunk_retriever
from app.services.audit_engine import get_citation_auditor
from app.services.access_control import authenticate_access_key, authorize_project
from app.services.audit_workflow import audit_workflow
from app.services.store import store

router = APIRouter(prefix="/api/projects/{project_id}/audits", tags=["audits"])


@router.post("/claim", response_model=AuditResult)
def audit_claim(
    project_id: str,
    payload: AuditRequest,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> AuditResult:
    project = store.get_project(project_id)
    authorize_project(project, access_key)
    if project.access_key_id:
        store.reserve_audit(project.access_key_id)
    try:
        citation_auditor = get_citation_auditor()
        evidence_cards = store.list_project_evidence_cards(project_id=project_id)
        retrieved_chunks = chunk_retriever.retrieve(
            query=payload.claim_text,
            project_id=project_id,
            paper_ids=payload.cited_paper_ids,
            k=payload.top_k,
        )
        result = citation_auditor.audit_claim(
            project_id=project_id,
            payload=payload,
            evidence_cards=evidence_cards,
            retrieved_chunks=retrieved_chunks,
            invalid_cited_paper_ids={paper_id for paper_id in payload.cited_paper_ids if paper_id not in {paper.id for paper in store.list_project_papers(project_id)}},
        )
    except Exception:
        if project.access_key_id:
            store.settle_audit(project.access_key_id, completed=False)
        raise
    if project.access_key_id:
        store.settle_audit(project.access_key_id, completed=True)
    return result


@router.post("/batches", response_model=BatchAuditResponse)
def audit_text_batch(
    project_id: str,
    payload: ClaimBatchCreate,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> BatchAuditResponse:
    project = store.get_project(project_id)
    authorize_project(project, access_key)
    if not project.access_key_id:
        return audit_workflow.audit_batch(project_id=project_id, payload=payload)
    store.reserve_audit(project.access_key_id)
    try:
        response = audit_workflow.audit_batch(project_id=project_id, payload=payload)
    except Exception:
        store.settle_audit(project.access_key_id, completed=False)
        raise
    store.settle_audit(project.access_key_id, completed=True)
    return response


@router.get("/batches/{batch_id}", response_model=AuditBatchDetail)
def get_batch_detail(
    project_id: str,
    batch_id: str,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> AuditBatchDetail:
    project = store.get_project(project_id)
    authorize_project(project, access_key)
    batch = store.get_audit_batch(batch_id)
    if batch.project_id != project_id:
        raise HTTPException(status_code=404, detail="Audit batch not found")
    return AuditBatchDetail(
        batch=batch,
        audit_run=store.get_latest_audit_run(batch_id),
        results=store.list_audit_results(batch_id),
        manuscript_text="\n\n".join(item.text for item in store.list_review_paragraphs(batch_id)),
        papers=store.list_project_papers(project_id),
    )
