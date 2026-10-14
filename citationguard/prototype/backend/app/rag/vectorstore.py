import os
from pathlib import Path
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.models.schemas import SourceChunk
from app.rag.embeddings import get_embeddings


DEFAULT_CHROMA_DIR = Path("data/chroma_source_chunks")
SOURCE_CHUNKS_COLLECTION = "source_chunks"


def chunk_to_document(chunk: SourceChunk) -> Document:
    return Document(
        page_content=chunk.cleaned_text,
        metadata={
            "project_id": chunk.project_id,
            "paper_id": chunk.paper_id,
            "source_chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "section": chunk.section,
            "section_type": chunk.section_type,
            "token_estimate": chunk.token_estimate,
        },
    )


class ChunkVectorStore:
    def __init__(
        self,
        persist_directory: str | Path | None = None,
        collection_name: str | None = None,
    ) -> None:
        directory = persist_directory or os.getenv("CHROMA_DIR") or DEFAULT_CHROMA_DIR
        collection_name = collection_name or os.getenv(
            "CHROMA_COLLECTION",
            f"{SOURCE_CHUNKS_COLLECTION}_{os.getenv('EMBEDDING_PROVIDER', 'hash').lower()}",
        )
        self.persist_directory = Path(directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.store = Chroma(
            collection_name=collection_name,
            embedding_function=get_embeddings(),
            persist_directory=str(self.persist_directory),
        )

    def index_chunks(self, chunks: list[SourceChunk]) -> int:
        if not chunks:
            return 0

        documents = [chunk_to_document(chunk) for chunk in chunks]
        ids = [chunk.id for chunk in chunks]
        # Chroma upserts matching ids, so re-ingesting a paper is idempotent for
        # the same chunk ids and safe for prototype iteration.
        self.store.add_documents(documents=documents, ids=ids)
        return len(documents)

    def similarity_search(
        self,
        query: str,
        project_id: str,
        paper_ids: list[str] | None = None,
        k: int = 8,
    ) -> list[Document]:
        metadata_filter = self._build_filter(project_id=project_id, paper_ids=paper_ids)
        return self.store.similarity_search(query=query, k=k, filter=metadata_filter)

    @staticmethod
    def _build_filter(project_id: str, paper_ids: list[str] | None = None) -> dict:
        clauses: list[dict] = [{"project_id": project_id}]
        if paper_ids:
            if len(paper_ids) == 1:
                clauses.append({"paper_id": paper_ids[0]})
            else:
                clauses.append({"paper_id": {"$in": paper_ids}})
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

@lru_cache(maxsize=1)
def get_chunk_vector_store() -> ChunkVectorStore:
    return ChunkVectorStore()
