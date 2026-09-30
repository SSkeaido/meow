from app.llm.citation_audit import _build_evidence_packet
from app.models.schemas import AuditRequest, EvidenceCard, RetrievedChunk
from app.services.audit_engine import get_citation_auditor


def test_evidence_packet_is_limited_to_five_cited_evidence_cards() -> None:
    cards = [
        EvidenceCard(
            id=f"evidence-{index}",
            project_id="project1",
            paper_id="paper1",
            source_chunk_id=f"chunk-{index}",
            claim_type="result",
            summary="summary",
            source_quote=f"Evidence quote {index}",
            page=index + 1,
            section="result",
            support_scope="benchmark",
            limitations="fixture",
        )
        for index in range(6)
    ]
    chunks = [
        RetrievedChunk(
            source_chunk_id="extra-chunk",
            paper_id="paper1",
            project_id="project1",
            page_start=10,
            page_end=10,
            section_type="result",
            text="This should not fit after five evidence cards.",
        )
    ]

    packet = _build_evidence_packet(
        AuditRequest(claim_text="A test claim.", cited_paper_ids=["paper1"]),
        cards,
        chunks,
    )

    assert len(packet) == 5
    assert [item["evidence_card_id"] for item in packet] == [f"evidence-{index}" for index in range(5)]


def test_audit_engine_defaults_to_local_heuristic_mode(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    get_citation_auditor.cache_clear()

    auditor = get_citation_auditor()

    assert auditor.provider == "heuristic"
    assert auditor.sent_payload_summary == "heuristic-only; no external model call"


def test_evidence_packet_excludes_cards_with_untraceable_quotes() -> None:
    invalid_card = EvidenceCard(
        id="invalid-card",
        project_id="project1",
        paper_id="paper1",
        source_chunk_id="chunk1",
        claim_type="result",
        summary="summary",
        source_quote="quote",
        page=1,
        section="result",
        support_scope="scope",
        limitations="fixture",
        validation_flags=["quote_not_found"],
    )

    packet = _build_evidence_packet(
        AuditRequest(claim_text="A test claim.", cited_paper_ids=["paper1"]),
        [invalid_card],
        [],
    )

    assert packet == []
