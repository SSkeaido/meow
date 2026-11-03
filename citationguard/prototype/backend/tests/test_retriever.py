from app.models.schemas import SourceChunk
from app.rag.embeddings import HashEmbeddings
from app.rag.retriever import ChunkRetriever
from app.rag.vectorstore import ChunkVectorStore


def test_hash_embeddings_are_deterministic() -> None:
    embeddings = HashEmbeddings(dimensions=32)
    first = embeddings.embed_query("citation grounded retrieval")
    second = embeddings.embed_query("citation grounded retrieval")
    assert first == second
    assert len(first) == 32


def test_chunk_retriever_returns_indexed_chunks(tmp_path) -> None:
    vector_store = ChunkVectorStore(
        persist_directory=tmp_path,
        collection_name="test_source_chunks",
    )
    retriever = ChunkRetriever(vector_store=vector_store)
    chunk = SourceChunk(
        project_id="project1",
        paper_id="paper1",
        chunk_index=0,
        page_start=3,
        page_end=3,
        section_type="result",
        text="Transformer retrieval models improved citation audit accuracy in benchmark experiments.",
        cleaned_text="Transformer retrieval models improved citation audit accuracy in benchmark experiments.",
        token_estimate=16,
    )

    indexed = vector_store.index_chunks([chunk])
    results = retriever.retrieve(
        query="citation audit retrieval accuracy",
        project_id="project1",
        paper_ids=["paper1"],
        k=3,
    )

    assert indexed == 1
    assert len(results) == 1
    assert results[0].source_chunk_id == chunk.id
    assert results[0].page_start == 3

