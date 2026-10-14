import os

from langchain_core.documents import Document

from app.models.schemas import RetrievedChunk
from app.rag.vectorstore import ChunkVectorStore, get_chunk_vector_store


class ChunkRetriever:
    def __init__(self, vector_store: ChunkVectorStore | None = None) -> None:
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        project_id: str,
        paper_ids: list[str] | None = None,
        k: int = 8,
    ) -> list[RetrievedChunk]:
        vector_store = self.vector_store or get_chunk_vector_store()
        candidate_k = max(k, int(os.getenv("RETRIEVAL_CANDIDATE_K", "20")))
        documents = vector_store.similarity_search(
            query=query,
            project_id=project_id,
            paper_ids=paper_ids,
            k=candidate_k,
        )
        documents = rerank_documents(query=query, documents=documents, top_k=k)
        return [document_to_retrieved_chunk(document) for document in documents]


def document_to_retrieved_chunk(document: Document) -> RetrievedChunk:
    metadata = document.metadata
    return RetrievedChunk(
        source_chunk_id=str(metadata.get("source_chunk_id", "")),
        paper_id=str(metadata.get("paper_id", "")),
        project_id=str(metadata.get("project_id", "")),
        page_start=int(metadata.get("page_start", 0)),
        page_end=int(metadata.get("page_end", 0)),
        section_type=str(metadata.get("section_type", "unknown")),
        text=document.page_content,
        metadata=dict(metadata),
    )

chunk_retriever = ChunkRetriever()


def rerank_documents(query: str, documents: list[Document], top_k: int) -> list[Document]:
    if os.getenv("RERANK_PROVIDER", "disabled").lower() != "siliconflow" or not documents:
        return documents[:top_k]
    from app.integrations.siliconflow import SiliconFlowReranker

    try:
        rankings = SiliconFlowReranker().rerank(
            query=query,
            documents=[document.page_content for document in documents],
            top_n=top_k,
        )
    except Exception:
        # Retrieval remains usable if a free rerank endpoint is unavailable.
        return documents[:top_k]
    return [documents[index] for index, _score in rankings[:top_k]]
