from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import (
    CitationBindingRecord,
    CitationBindingReviewUpdate,
    CitationBindingSuggestionRequest,
    Project,
)
from app.services.access_control import authorize_project_id
from app.services.citation_suggester import suggest_citation_bindings
from app.services.store import store


router = APIRouter(prefix="/api/projects/{project_id}/citation-bindings", tags=["citation bindings"])


@router.get("", response_model=list[CitationBindingRecord])
def list_bindings(
    project_id: str,
    _project: Project = Depends(authorize_project_id),
) -> list[CitationBindingRecord]:
    return store.list_citation_binding_records(project_id)


@router.post("/suggest", response_model=list[CitationBindingRecord])
def suggest_bindings(
    project_id: str,
    payload: CitationBindingSuggestionRequest,
    _project: Project = Depends(authorize_project_id),
) -> list[CitationBindingRecord]:
    papers = store.list_project_papers(project_id)
    selected_papers = [paper for paper in papers if not payload.paper_ids or paper.id in payload.paper_ids]
    existing = {record.marker: record for record in store.list_citation_binding_records(project_id)}
    records: list[CitationBindingRecord] = []
    for suggestion in suggest_citation_bindings(payload.text, selected_papers):
        previous = existing.get(suggestion.marker)
        if previous and previous.status == "confirmed":
            records.append(previous)
            continue
        record = CitationBindingRecord(
            project_id=project_id,
            marker=suggestion.marker,
            paper_id=suggestion.paper_id,
            confidence=suggestion.confidence,
            reason=suggestion.reason,
            source="auto",
            status="suggested",
        )
        if previous:
            record = record.model_copy(update={"id": previous.id, "created_at": previous.created_at})
        records.append(store.upsert_citation_binding_record(record))
    return records


@router.patch("/{binding_id}", response_model=CitationBindingRecord)
def review_binding(
    project_id: str,
    binding_id: str,
    payload: CitationBindingReviewUpdate,
    _project: Project = Depends(authorize_project_id),
) -> CitationBindingRecord:
    if payload.status not in {"confirmed", "rejected", "suggested"}:
        raise HTTPException(status_code=422, detail="Unsupported binding status")
    if payload.paper_id:
        paper = store.get_paper(payload.paper_id)
        if paper.project_id != project_id:
            raise HTTPException(status_code=422, detail="Paper is not in this project")
    record = store.get_citation_binding_record(project_id, binding_id)
    return store.upsert_citation_binding_record(
        record.model_copy(
            update={
                "paper_id": payload.paper_id,
                "status": payload.status,
                "source": "manual" if payload.status == "confirmed" else record.source,
                "updated_at": datetime.now(UTC),
            }
        )
    )
