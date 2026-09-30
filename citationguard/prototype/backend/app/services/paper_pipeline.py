import hashlib
import tempfile
from pathlib import Path

from fastapi import UploadFile

from app.models.schemas import Paper, PaperIngestResult
from app.pdf.loader import load_pdf_pages
from app.pdf.metadata import extract_paper_metadata
from app.pdf.splitter import split_pages_to_chunks
from app.rag.vectorstore import get_chunk_vector_store
from app.services.store import store
from app.services.object_storage import object_storage


class PaperPipeline:
    async def ingest_upload(self, project_id: str, upload: UploadFile) -> PaperIngestResult:
        store.get_project(project_id)
        content = await upload.read()
        file_hash = hashlib.sha256(content).hexdigest()
        safe_name = Path(upload.filename or "paper.pdf").name
        storage_key = f"papers/{project_id}/{file_hash}_{safe_name}"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_file.write(content)
            target_path = Path(temporary_file.name)
        try:
            pages = load_pdf_pages(target_path)
            metadata = extract_paper_metadata(target_path, pages)
        finally:
            target_path.unlink(missing_ok=True)
        storage_uri = object_storage.save(content, storage_key)
        metadata["storage_provider"] = object_storage.provider
        metadata["storage_uri"] = storage_uri
        title = metadata.pop("title", "") or safe_name.rsplit(".", 1)[0]
        paper = Paper(
            project_id=project_id,
            title=title,
            original_filename=safe_name,
            file_hash=file_hash,
            page_count=len(pages),
            metadata=metadata,
        )
        chunks = split_pages_to_chunks(project_id=project_id, paper_id=paper.id, pages=pages)
        store.add_paper(paper=paper, chunks=chunks)
        chunk_vector_store = get_chunk_vector_store()
        indexed_chunk_count = chunk_vector_store.index_chunks(chunks)
        return PaperIngestResult(paper=paper, chunk_count=len(chunks), indexed_chunk_count=indexed_chunk_count)

    def list_project_papers(self, project_id: str) -> list[PaperIngestResult]:
        store.get_project(project_id)
        results: list[PaperIngestResult] = []
        for paper in store.list_project_papers(project_id):
            chunks = store.list_chunks(paper.id)
            evidence = store.list_evidence_cards(paper.id)
            results.append(
                PaperIngestResult(
                    paper=paper,
                    chunk_count=len(chunks),
                    indexed_chunk_count=len(chunks),
                    evidence_count=len(evidence),
                )
            )
        return results


paper_pipeline = PaperPipeline()
