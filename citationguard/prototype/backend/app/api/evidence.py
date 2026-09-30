from fastapi import APIRouter, Depends

from app.models.schemas import AccessKeyRecord, EvidenceCard
from app.services.access_control import authenticate_access_key, authorize_project
from app.services.evidence_extractor import evidence_extractor
from app.services.evidence_validator import validate_evidence_cards
from app.services.store import store

router = APIRouter(prefix="/api/papers/{paper_id}/evidence", tags=["evidence"])


@router.post("/generate", response_model=list[EvidenceCard])
def generate_evidence(
    paper_id: str,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> list[EvidenceCard]:
    paper = store.get_paper(paper_id)
    authorize_project(store.get_project(paper.project_id), access_key)
    chunks = store.list_chunks(paper_id=paper_id)
    cards = validate_evidence_cards(evidence_extractor.generate(paper=paper, chunks=chunks), chunks)
    store.replace_evidence_cards(paper_id=paper_id, cards=cards)
    return cards


@router.get("", response_model=list[EvidenceCard])
def list_evidence(
    paper_id: str,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> list[EvidenceCard]:
    paper = store.get_paper(paper_id)
    authorize_project(store.get_project(paper.project_id), access_key)
    return store.list_evidence_cards(paper_id=paper_id)
