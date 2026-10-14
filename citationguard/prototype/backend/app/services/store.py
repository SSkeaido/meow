import os
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import Engine, create_engine, text

from app.models.schemas import (
    AuditRun,
    AccessKeyRecord,
    CitationBindingRecord,
    CitationLedgerEntry,
    ClaimBatch,
    EvidenceCard,
    Paper,
    PersistedAuditResult,
    Project,
    ProjectCreate,
    ReviewClaim,
    ReviewParagraph,
    SourceChunk,
)


DEFAULT_DB_PATH = Path("data/app.db")


class SQLiteStore:
    def __init__(
        self,
        db_path: str | Path | None = None,
        database_url: str | None = None,
    ) -> None:
        url = database_url or os.getenv("DATABASE_URL")
        if url:
            self.engine = create_engine(url, future=True, pool_pre_ping=True)
        else:
            path = Path(db_path or os.getenv("APP_DB_PATH") or DEFAULT_DB_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_engine(f"sqlite:///{path}", future=True)
        self._create_schema()

    def _create_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS access_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT UNIQUE NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS source_chunks (
                id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS evidence_cards (
                id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_papers_project_id ON papers(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_chunks_paper_id ON source_chunks(paper_id)",
            "CREATE INDEX IF NOT EXISTS idx_chunks_project_id ON source_chunks(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_evidence_paper_id ON evidence_cards(paper_id)",
            "CREATE INDEX IF NOT EXISTS idx_evidence_project_id ON evidence_cards(project_id)",
            """
            CREATE TABLE IF NOT EXISTS claim_batches (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS review_paragraphs (
                id TEXT PRIMARY KEY,
                claim_batch_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS review_claims (
                id TEXT PRIMARY KEY,
                review_paragraph_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_runs (
                id TEXT PRIMARY KEY,
                claim_batch_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_results (
                id TEXT PRIMARY KEY,
                audit_run_id TEXT NOT NULL,
                review_claim_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS citation_ledger_entries (
                id TEXT PRIMARY KEY,
                claim_batch_id TEXT NOT NULL,
                review_claim_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                paper_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS citation_binding_records (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                marker TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_batches_project_id ON claim_batches(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_paragraphs_batch_id ON review_paragraphs(claim_batch_id)",
            "CREATE INDEX IF NOT EXISTS idx_claims_paragraph_id ON review_claims(review_paragraph_id)",
            "CREATE INDEX IF NOT EXISTS idx_runs_batch_id ON audit_runs(claim_batch_id)",
            "CREATE INDEX IF NOT EXISTS idx_results_run_id ON audit_results(audit_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_ledger_batch_id ON citation_ledger_entries(claim_batch_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_binding_records_project_marker ON citation_binding_records(project_id, marker)",
        ]
        with self.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    def create_project(self, payload: ProjectCreate, access_key_id: str = "") -> Project:
        project = Project(**payload.model_dump(), access_key_id=access_key_id)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO projects (id, payload, created_at)
                    VALUES (:id, :payload, :created_at)
                    """
                ),
                {
                    "id": project.id,
                    "payload": project.model_dump_json(),
                    "created_at": project.created_at.isoformat(),
                },
            )
        return project

    def create_access_key(
        self,
        max_completed_audits: int = 0,
        valid_days: int = 7,
    ) -> tuple[str, AccessKeyRecord]:
        raw_key = "cak_" + secrets.token_urlsafe(24)
        record = AccessKeyRecord(
            key_hash=_hash_access_key(raw_key),
            key_prefix=raw_key[:10],
            max_completed_audits=max_completed_audits,
            valid_days=valid_days,
        )
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO access_keys (id, key_hash, payload) VALUES (:id, :key_hash, :payload)"),
                {"id": record.id, "key_hash": record.key_hash, "payload": record.model_dump_json()},
            )
        return raw_key, record

    def verify_access_key(self, raw_key: str) -> AccessKeyRecord | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT id, payload FROM access_keys WHERE key_hash = :key_hash"),
                {"key_hash": _hash_access_key(raw_key)},
            ).first()
            if not row:
                return None
            record = AccessKeyRecord.model_validate_json(row.payload)
            now = datetime.now(UTC)
            if not record.active or (record.expires_at and record.expires_at <= now):
                return None
            if not record.first_used_at:
                record = record.model_copy(
                    update={
                        "first_used_at": now,
                        "expires_at": now + timedelta(days=record.valid_days),
                    }
                )
                connection.execute(
                    text("UPDATE access_keys SET payload = :payload WHERE id = :id"),
                    {"id": record.id, "payload": record.model_dump_json()},
                )
            return record

    def get_access_key(self, access_key_id: str) -> AccessKeyRecord:
        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT payload FROM access_keys WHERE id = :id"),
                {"id": access_key_id},
            ).first()
        if not row:
            raise HTTPException(status_code=401, detail="Access key not found")
        return AccessKeyRecord.model_validate_json(row.payload)

    def reserve_audit(self, access_key_id: str) -> AccessKeyRecord:
        with self.engine.begin() as connection:
            lock_suffix = "" if self.engine.dialect.name == "sqlite" else " FOR UPDATE"
            row = connection.execute(
                text(f"SELECT payload FROM access_keys WHERE id = :id{lock_suffix}"),
                {"id": access_key_id},
            ).first()
            if not row:
                raise HTTPException(status_code=401, detail="Access key not found")
            record = AccessKeyRecord.model_validate_json(row.payload)
            if not record.active:
                raise HTTPException(status_code=403, detail="Access key is inactive")
            if record.expires_at and record.expires_at <= datetime.now(UTC):
                raise HTTPException(status_code=401, detail="Access key has expired")
            if (
                record.max_completed_audits > 0
                and record.completed_audits + record.reserved_audits >= record.max_completed_audits
            ):
                raise HTTPException(status_code=429, detail="Audit quota exhausted")
            record = record.model_copy(update={"reserved_audits": record.reserved_audits + 1})
            connection.execute(
                text("UPDATE access_keys SET payload = :payload WHERE id = :id"),
                {"id": record.id, "payload": record.model_dump_json()},
            )
        return record

    def settle_audit(self, access_key_id: str, completed: bool) -> AccessKeyRecord:
        with self.engine.begin() as connection:
            lock_suffix = "" if self.engine.dialect.name == "sqlite" else " FOR UPDATE"
            row = connection.execute(
                text(f"SELECT payload FROM access_keys WHERE id = :id{lock_suffix}"),
                {"id": access_key_id},
            ).first()
            if not row:
                raise HTTPException(status_code=401, detail="Access key not found")
            record = AccessKeyRecord.model_validate_json(row.payload)
            record = record.model_copy(
                update={
                    "reserved_audits": max(0, record.reserved_audits - 1),
                    "completed_audits": record.completed_audits + (1 if completed else 0),
                }
            )
            connection.execute(
                text("UPDATE access_keys SET payload = :payload WHERE id = :id"),
                {"id": record.id, "payload": record.model_dump_json()},
            )
        return record

    def list_projects(self) -> list[Project]:
        with self.engine.begin() as connection:
            rows = connection.execute(text("SELECT payload FROM projects ORDER BY created_at DESC")).all()
        return [Project.model_validate_json(row.payload) for row in rows]

    def list_access_key_projects(self, access_key_id: str) -> list[Project]:
        return [project for project in self.list_projects() if project.access_key_id == access_key_id]

    def get_project(self, project_id: str) -> Project:
        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT payload FROM projects WHERE id = :id"),
                {"id": project_id},
            ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        return Project.model_validate_json(row.payload)

    def add_paper(self, paper: Paper, chunks: list[SourceChunk]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO papers (id, project_id, payload, created_at)
                    VALUES (:id, :project_id, :payload, :created_at)
                    ON CONFLICT(id) DO UPDATE SET
                        project_id = excluded.project_id,
                        payload = excluded.payload,
                        created_at = excluded.created_at
                    """
                ),
                {
                    "id": paper.id,
                    "project_id": paper.project_id,
                    "payload": paper.model_dump_json(),
                    "created_at": paper.created_at.isoformat(),
                },
            )
            connection.execute(
                text("DELETE FROM source_chunks WHERE paper_id = :paper_id"),
                {"paper_id": paper.id},
            )
            if chunks:
                connection.execute(
                    text(
                        """
                        INSERT INTO source_chunks (id, paper_id, project_id, chunk_index, payload)
                        VALUES (:id, :paper_id, :project_id, :chunk_index, :payload)
                        """
                    ),
                    [
                        {
                            "id": chunk.id,
                            "paper_id": chunk.paper_id,
                            "project_id": chunk.project_id,
                            "chunk_index": chunk.chunk_index,
                            "payload": chunk.model_dump_json(),
                        }
                        for chunk in chunks
                    ],
                )

    def get_paper(self, paper_id: str) -> Paper:
        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT payload FROM papers WHERE id = :id"),
                {"id": paper_id},
            ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Paper not found")
        return Paper.model_validate_json(row.payload)

    def list_project_papers(self, project_id: str) -> list[Paper]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text("SELECT payload FROM papers WHERE project_id = :project_id ORDER BY created_at DESC"),
                {"project_id": project_id},
            ).all()
        return [Paper.model_validate_json(row.payload) for row in rows]

    def list_project_audit_batches(self, project_id: str) -> list[ClaimBatch]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT payload FROM claim_batches "
                    "WHERE project_id = :project_id ORDER BY created_at DESC"
                ),
                {"project_id": project_id},
            ).all()
        return [ClaimBatch.model_validate_json(row.payload) for row in rows]

    def list_review_paragraphs(self, batch_id: str) -> list[ReviewParagraph]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT payload FROM review_paragraphs "
                    "WHERE claim_batch_id = :batch_id ORDER BY rowid ASC"
                ),
                {"batch_id": batch_id},
            ).all()
        return [ReviewParagraph.model_validate_json(row.payload) for row in rows]

    def list_chunks(self, paper_id: str) -> list[SourceChunk]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text("SELECT payload FROM source_chunks WHERE paper_id = :paper_id ORDER BY chunk_index ASC"),
                {"paper_id": paper_id},
            ).all()
        return [SourceChunk.model_validate_json(row.payload) for row in rows]

    def replace_evidence_cards(self, paper_id: str, cards: list[EvidenceCard]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM evidence_cards WHERE paper_id = :paper_id"),
                {"paper_id": paper_id},
            )
            if cards:
                connection.execute(
                    text(
                        """
                        INSERT INTO evidence_cards (id, paper_id, project_id, payload)
                        VALUES (:id, :paper_id, :project_id, :payload)
                        """
                    ),
                    [
                        {
                            "id": card.id,
                            "paper_id": card.paper_id,
                            "project_id": card.project_id,
                            "payload": card.model_dump_json(),
                        }
                        for card in cards
                    ],
                )

    def list_evidence_cards(self, paper_id: str) -> list[EvidenceCard]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text("SELECT payload FROM evidence_cards WHERE paper_id = :paper_id"),
                {"paper_id": paper_id},
            ).all()
        return [EvidenceCard.model_validate_json(row.payload) for row in rows]

    def list_project_evidence_cards(self, project_id: str) -> list[EvidenceCard]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text("SELECT payload FROM evidence_cards WHERE project_id = :project_id"),
                {"project_id": project_id},
            ).all()
        return [EvidenceCard.model_validate_json(row.payload) for row in rows]

    def save_audit_batch(
        self,
        batch: ClaimBatch,
        paragraphs: list[ReviewParagraph],
        claims: list[ReviewClaim],
        audit_run: AuditRun,
        results: list[PersistedAuditResult],
        ledger_entries: list[CitationLedgerEntry],
    ) -> None:
        """Persist one audit as a coherent, exportable evidence trail."""
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO claim_batches (id, project_id, payload, created_at) VALUES (:id, :project_id, :payload, :created_at)"),
                {"id": batch.id, "project_id": batch.project_id, "payload": batch.model_dump_json(), "created_at": batch.created_at.isoformat()},
            )
            self._insert_payloads(connection, "review_paragraphs", paragraphs, ("id", "claim_batch_id", "project_id"))
            self._insert_payloads(connection, "review_claims", claims, ("id", "review_paragraph_id", "project_id"))
            self._insert_payloads(connection, "audit_runs", [audit_run], ("id", "claim_batch_id", "project_id"))
            self._insert_payloads(connection, "audit_results", results, ("id", "audit_run_id", "review_claim_id", "project_id"))
            self._insert_payloads(
                connection,
                "citation_ledger_entries",
                ledger_entries,
                ("id", "claim_batch_id", "review_claim_id", "project_id", "paper_id"),
            )

    def get_audit_batch(self, batch_id: str) -> ClaimBatch:
        with self.engine.begin() as connection:
            row = connection.execute(text("SELECT payload FROM claim_batches WHERE id = :id"), {"id": batch_id}).first()
        if not row:
            raise HTTPException(status_code=404, detail="Audit batch not found")
        return ClaimBatch.model_validate_json(row.payload)

    def list_audit_results(self, batch_id: str) -> list[PersistedAuditResult]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT audit_results.payload FROM audit_results
                    INNER JOIN audit_runs ON audit_runs.id = audit_results.audit_run_id
                    WHERE audit_runs.claim_batch_id = :batch_id
                    ORDER BY audit_results.id ASC
                    """
                ),
                {"batch_id": batch_id},
            ).all()
        return [PersistedAuditResult.model_validate_json(row.payload) for row in rows]

    def get_latest_audit_run(self, batch_id: str) -> AuditRun:
        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT payload FROM audit_runs WHERE claim_batch_id = :batch_id ORDER BY id DESC LIMIT 1"),
                {"batch_id": batch_id},
            ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Audit run not found")
        return AuditRun.model_validate_json(row.payload)

    def list_citation_ledger_entries(self, batch_id: str) -> list[CitationLedgerEntry]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT payload FROM citation_ledger_entries WHERE claim_batch_id = :batch_id ORDER BY id ASC"
                ),
                {"batch_id": batch_id},
            ).all()
        return [CitationLedgerEntry.model_validate_json(row.payload) for row in rows]

    def list_citation_binding_records(self, project_id: str) -> list[CitationBindingRecord]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text("SELECT payload FROM citation_binding_records WHERE project_id = :project_id ORDER BY marker ASC"),
                {"project_id": project_id},
            ).all()
        return [CitationBindingRecord.model_validate_json(row.payload) for row in rows]

    def upsert_citation_binding_record(self, record: CitationBindingRecord) -> CitationBindingRecord:
        existing = next(
            (item for item in self.list_citation_binding_records(record.project_id) if item.marker == record.marker),
            None,
        )
        if existing and existing.status == "confirmed" and record.source == "auto":
            return existing
        if existing:
            record = record.model_copy(update={"id": existing.id, "created_at": existing.created_at})
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO citation_binding_records (id, project_id, marker, payload, updated_at)
                    VALUES (:id, :project_id, :marker, :payload, :updated_at)
                    ON CONFLICT(id) DO UPDATE SET
                        project_id = excluded.project_id,
                        marker = excluded.marker,
                        payload = excluded.payload,
                        updated_at = excluded.updated_at
                    """
                ),
                {
                    "id": record.id,
                    "project_id": record.project_id,
                    "marker": record.marker,
                    "payload": record.model_dump_json(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )
        return record

    def get_citation_binding_record(self, project_id: str, binding_id: str) -> CitationBindingRecord:
        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT payload FROM citation_binding_records WHERE project_id = :project_id AND id = :id"),
                {"project_id": project_id, "id": binding_id},
            ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Citation binding not found")
        return CitationBindingRecord.model_validate_json(row.payload)

    @staticmethod
    def _insert_payloads(connection, table: str, payloads: list, columns: tuple[str, ...]) -> None:
        if not payloads:
            return
        fields = ", ".join((*columns, "payload"))
        values = ", ".join(f":{column}" for column in (*columns, "payload"))
        connection.execute(
            text(f"INSERT INTO {table} ({fields}) VALUES ({values})"),
            [
                {**{column: getattr(payload, column) for column in columns}, "payload": payload.model_dump_json()}
                for payload in payloads
            ],
        )


store = SQLiteStore()


def _hash_access_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
