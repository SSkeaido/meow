from fastapi import APIRouter, Depends, File, UploadFile

from fastapi import HTTPException

from app.models.schemas import PaperContent, PaperIngestResult, Project
from app.services.access_control import authorize_project_id
from app.services.paper_pipeline import paper_pipeline
from app.services.store import store

router = APIRouter(prefix="/api/projects/{project_id}/papers", tags=["papers"])


@router.post("/upload", response_model=PaperIngestResult)
async def upload_paper(
    project_id: str,
    file: UploadFile = File(...),
    _project: Project = Depends(authorize_project_id),
) -> PaperIngestResult:
    return await paper_pipeline.ingest_upload(project_id=project_id, upload=file)


@router.get("", response_model=list[PaperIngestResult])
def list_project_papers(
    project_id: str,
    _project: Project = Depends(authorize_project_id),
) -> list[PaperIngestResult]:
    return paper_pipeline.list_project_papers(project_id)


@router.get("/{paper_id}", response_model=PaperContent)
def get_paper_content(
    project_id: str,
    paper_id: str,
    _project: Project = Depends(authorize_project_id),
) -> PaperContent:
    paper = store.get_paper(paper_id)
    if paper.project_id != project_id:
        raise HTTPException(status_code=404, detail="Paper not found")
    chunks = store.list_chunks(paper_id)
    return PaperContent(
        paper=paper,
        text="\n\n".join(chunk.text for chunk in chunks),
        chunk_count=len(chunks),
    )
