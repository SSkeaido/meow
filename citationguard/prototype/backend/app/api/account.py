from fastapi import APIRouter, Depends

from app.models.schemas import (
    AccessKeyRecord,
    AccessKeySession,
    AuditHistoryItem,
    UserHistory,
)
from app.services.access_control import require_access_key
from app.services.store import store

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/session", response_model=AccessKeySession)
def get_session(
    access_key: AccessKeyRecord = Depends(require_access_key),
) -> AccessKeySession:
    return AccessKeySession(
        key_prefix=access_key.key_prefix,
        first_used_at=access_key.first_used_at,
        expires_at=access_key.expires_at,
        completed_audits=access_key.completed_audits,
    )


@router.get("/history", response_model=UserHistory)
def get_history(
    access_key: AccessKeyRecord = Depends(require_access_key),
) -> UserHistory:
    projects = store.list_access_key_projects(access_key.id)
    papers = []
    audits = []
    for project in projects:
        project_papers = store.list_project_papers(project.id)
        papers.extend(project_papers)
        for batch in store.list_project_audit_batches(project.id):
            paragraphs = store.list_review_paragraphs(batch.id)
            manuscript_text = "\n\n".join(item.text for item in paragraphs)
            results = store.list_audit_results(batch.id)
            cited_ids = {
                paper_id
                for result in results
                for paper_id in result.cited_paper_ids
            }
            audits.append(
                AuditHistoryItem(
                    batch=batch,
                    audit_run=store.get_latest_audit_run(batch.id),
                    manuscript_preview=manuscript_text[:240],
                    manuscript_characters=len(manuscript_text),
                    result_count=len(results),
                    papers=[paper for paper in project_papers if paper.id in cited_ids],
                )
            )
    audits.sort(key=lambda item: item.batch.created_at, reverse=True)
    papers.sort(key=lambda item: item.created_at, reverse=True)
    return UserHistory(projects=projects, papers=papers, audits=audits)
