from app.models.schemas import CitationBinding, ClaimBatchCreate, Paper, ProjectCreate
from app.services.auditor import HeuristicCitationAuditor
from app.services.claim_extractor import ExtractedClaim
from app.services import audit_workflow as audit_workflow_module
from app.services.audit_workflow import AuditWorkflow
from app.services.store import SQLiteStore


class EmptyRetriever:
    def retrieve(self, **kwargs) -> list:
        return []


class RecordingRetriever(EmptyRetriever):
    def __init__(self) -> None:
        self.paper_id_calls: list[list[str]] = []

    def retrieve(self, **kwargs) -> list:
        self.paper_id_calls.append(kwargs["paper_ids"])
        return []


class ExactClaimExtractor:
    model_name = "fixture"

    @staticmethod
    def extract(paragraph: str) -> list[ExtractedClaim]:
        return [ExtractedClaim(claim_text=paragraph)]


def test_audit_workflow_persists_paragraph_claims_and_results(tmp_path, monkeypatch) -> None:
    isolated_store = SQLiteStore(db_path=tmp_path / "app.db")
    project = isolated_store.create_project(ProjectCreate(name="Audit workflow"))
    monkeypatch.setattr(audit_workflow_module, "store", isolated_store)
    monkeypatch.setattr(audit_workflow_module, "chunk_retriever", EmptyRetriever())

    response = AuditWorkflow().audit_batch(
        project_id=project.id,
        payload=ClaimBatchCreate(text="First factual claim.\n\nSecond factual claim!"),
    )

    assert response.paragraph_count == 2
    assert response.claim_count == 2
    assert len(response.results) == 2
    assert all("missing_citation" in result.risk_flags for result in response.results)
    assert len(isolated_store.list_audit_results(response.batch.id)) == 2


def test_audit_workflow_retrieves_only_papers_bound_to_claim_markers(tmp_path, monkeypatch) -> None:
    isolated_store = SQLiteStore(db_path=tmp_path / "app.db")
    project = isolated_store.create_project(ProjectCreate(name="Citation bindings"))
    first_paper = Paper(
        project_id=project.id,
        title="First paper",
        original_filename="first.pdf",
        file_hash="first",
        page_count=1,
    )
    second_paper = Paper(
        project_id=project.id,
        title="Second paper",
        original_filename="second.pdf",
        file_hash="second",
        page_count=1,
    )
    isolated_store.add_paper(first_paper, [])
    isolated_store.add_paper(second_paper, [])
    retriever = RecordingRetriever()
    monkeypatch.setattr(audit_workflow_module, "store", isolated_store)
    monkeypatch.setattr(audit_workflow_module, "chunk_retriever", retriever)
    monkeypatch.setattr(audit_workflow_module, "get_claim_extractor", lambda: ExactClaimExtractor())
    monkeypatch.setattr(audit_workflow_module, "get_citation_auditor", lambda: HeuristicCitationAuditor())

    AuditWorkflow().audit_batch(
        project_id=project.id,
        payload=ClaimBatchCreate(
            text="The result is supported [1].",
            cited_paper_ids=[first_paper.id, second_paper.id],
            citation_bindings=[CitationBinding(marker="[1]", paper_id=first_paper.id)],
        ),
    )

    assert retriever.paper_id_calls == [[first_paper.id]]
