from fastapi import APIRouter, Depends

from app.models.schemas import Project, RetrieveChunksRequest, RetrievedChunk
from app.services.access_control import authorize_project_id
from app.rag.retriever import chunk_retriever
from app.services.store import store

router = APIRouter(prefix="/api/projects/{project_id}/retrieval", tags=["retrieval"])


@router.post("/chunks", response_model=list[RetrievedChunk])
def retrieve_chunks(
    project_id: str,
    payload: RetrieveChunksRequest,
    _project: Project = Depends(authorize_project_id),
) -> list[RetrievedChunk]:
    return chunk_retriever.retrieve(
        query=payload.query,
        project_id=project_id,
        paper_ids=payload.paper_ids,
        k=payload.top_k,
    )
