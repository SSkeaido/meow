from app.models.schemas import (
    AuditRun,
    CitationLedgerEntry,
    CitationBindingRecord,
    ClaimBatch,
    EvidenceCard,
    Paper,
    PersistedAuditResult,
    ProjectCreate,
    ReviewClaim,
    ReviewParagraph,
    SourceChunk,
)
from app.services.store import SQLiteStore
from fastapi import HTTPException
import pytest


def test_sqlite_store_persists_project_paper_chunks_and_evidence(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    store = SQLiteStore(db_path=db_path)

    project = store.create_project(ProjectCreate(name="Citation audit"))
    paper = Paper(
        project_id=project.id,
        title="Grounded review",
        original_filename="grounded.pdf",
        file_hash="hash1",
        page_count=1,
    )
    chunk = SourceChunk(
        paper_id=paper.id,
        project_id=project.id,
        chunk_index=0,
        page_start=1,
        page_end=1,
        text="Citation audit evidence.",
        cleaned_text="Citation audit evidence.",
        token_estimate=6,
    )
    card = EvidenceCard(
        project_id=project.id,
        paper_id=paper.id,
        source_chunk_id=chunk.id,
        claim_type="result",
        summary="Citation audit evidence.",
        source_quote="Citation audit evidence.",
        page=1,
        section="result",
        support_scope="narrow",
        limitations="test fixture",
    )

    store.add_paper(paper=paper, chunks=[chunk])
    store.replace_evidence_cards(paper_id=paper.id, cards=[card])

    reopened = SQLiteStore(db_path=db_path)
    assert reopened.get_project(project.id).name == "Citation audit"
    assert reopened.get_paper(paper.id).title == "Grounded review"
    assert reopened.list_chunks(paper.id)[0].id == chunk.id
    assert reopened.list_evidence_cards(paper.id)[0].id == card.id
    assert reopened.list_project_evidence_cards(project.id)[0].id == card.id


def test_sqlite_store_persists_audit_trail(tmp_path) -> None:
    store = SQLiteStore(db_path=tmp_path / "app.db")
    project = store.create_project(ProjectCreate(name="Citation audit"))
    batch = ClaimBatch(project_id=project.id, status="audited")
    paragraph = ReviewParagraph(
        claim_batch_id=batch.id,
        project_id=project.id,
        paragraph_index=0,
        text="A supported claim.",
    )
    claim = ReviewClaim(
        review_paragraph_id=paragraph.id,
        project_id=project.id,
        claim_index=0,
        claim_text="A supported claim.",
        normalized_claim="a supported claim.",
        cited_paper_ids=["paper1"],
    )
    run = AuditRun(project_id=project.id, claim_batch_id=batch.id)
    result = PersistedAuditResult(
        audit_run_id=run.id,
        project_id=project.id,
        review_claim_id=claim.id,
        claim_text=claim.claim_text,
        cited_paper_ids=claim.cited_paper_ids,
        supporting_evidence_ids=[],
        support_level="CHECK",
        risk_flags=[],
        explanation="Needs review.",
        suggested_fix="Check the source.",
    )
    ledger = CitationLedgerEntry(
        project_id=project.id,
        claim_batch_id=batch.id,
        review_paragraph_id=paragraph.id,
        review_claim_id=claim.id,
        paper_id="paper1",
        last_audit_status=result.support_level,
    )

    store.save_audit_batch(batch, [paragraph], [claim], run, [result], [ledger])

    reopened = SQLiteStore(db_path=tmp_path / "app.db")
    assert reopened.get_audit_batch(batch.id).status == "audited"
    assert reopened.get_latest_audit_run(batch.id).id == run.id
    assert reopened.list_audit_results(batch.id)[0].review_claim_id == claim.id


def test_sqlite_store_preserves_confirmed_citation_bindings(tmp_path) -> None:
    store = SQLiteStore(db_path=tmp_path / "app.db")
    project = store.create_project(ProjectCreate(name="Citation binding"))
    record = store.upsert_citation_binding_record(
        CitationBindingRecord(
            project_id=project.id,
            marker="[1]",
            paper_id="paper-1",
            confidence=0.9,
            status="confirmed",
        )
    )

    updated = store.upsert_citation_binding_record(
        CitationBindingRecord(
            project_id=project.id,
            marker="[1]",
            paper_id="paper-2",
            confidence=0.5,
            status="suggested",
        )
    )

    assert updated.id == record.id
    assert updated.status == "confirmed"
    assert updated.paper_id == "paper-1"
    assert len(store.list_citation_binding_records(project.id)) == 1


def test_access_key_is_stored_as_a_hash_and_can_be_verified(tmp_path) -> None:
    store = SQLiteStore(db_path=tmp_path / "app.db")

    raw_key, record = store.create_access_key()

    assert raw_key.startswith("cak_")
    assert record.key_hash != raw_key
    verified = store.verify_access_key(raw_key)
    assert verified.id == record.id
    assert verified.first_used_at is not None
    assert verified.expires_at is not None
    assert (verified.expires_at - verified.first_used_at).days == 7
    assert verified.max_completed_audits == 0
    assert store.verify_access_key("cak_invalid") is None


def test_default_access_key_allows_repeated_audits_during_validity(tmp_path) -> None:
    store = SQLiteStore(db_path=tmp_path / "app.db")
    raw_key, record = store.create_access_key()
    store.verify_access_key(raw_key)

    for _ in range(3):
        store.reserve_audit(record.id)
        store.settle_audit(record.id, completed=True)

    assert store.get_access_key(record.id).completed_audits == 3


def test_access_key_audit_quota_reserves_settles_and_rejects_overuse(tmp_path) -> None:
    store = SQLiteStore(db_path=tmp_path / "app.db")
    _, record = store.create_access_key(max_completed_audits=1)

    reserved = store.reserve_audit(record.id)
    assert reserved.reserved_audits == 1

    with pytest.raises(HTTPException) as error:
        store.reserve_audit(record.id)
    assert error.value.status_code == 429

    released = store.settle_audit(record.id, completed=False)
    assert released.reserved_audits == 0
    assert released.completed_audits == 0

    store.reserve_audit(record.id)
    completed = store.settle_audit(record.id, completed=True)
    assert completed.completed_audits == 1

    with pytest.raises(HTTPException) as error:
        store.reserve_audit(record.id)
    assert error.value.status_code == 429


def test_project_can_be_bound_to_access_key(tmp_path) -> None:
    store = SQLiteStore(db_path=tmp_path / "app.db")
    _, record = store.create_access_key()

    project = store.create_project(ProjectCreate(name="Bound project"), access_key_id=record.id)

    assert store.get_project(project.id).access_key_id == record.id
