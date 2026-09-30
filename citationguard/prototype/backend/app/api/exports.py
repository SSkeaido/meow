from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.services.exporter import audit_report_markdown, audit_results_csv, citation_ledger_csv, evidence_cards_csv
from app.models.schemas import Project
from app.services.access_control import authorize_project_id
from app.services.store import store


router = APIRouter(prefix="/api/projects/{project_id}/exports", tags=["exports"])


@router.get("/audits/{batch_id}.md")
def export_audit_markdown(
    project_id: str,
    batch_id: str,
    _project: Project = Depends(authorize_project_id),
) -> Response:
    batch, audit_run, results = _load_audit_export(project_id, batch_id)
    return Response(
        audit_report_markdown(batch, audit_run, results),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="citation-audit-{batch_id}.md"'},
    )


@router.get("/audits/{batch_id}.csv")
def export_audit_results_csv(
    project_id: str,
    batch_id: str,
    _project: Project = Depends(authorize_project_id),
) -> Response:
    _batch, _audit_run, results = _load_audit_export(project_id, batch_id)
    return _csv_response(audit_results_csv(results), f"claim-audit-results-{batch_id}.csv")


@router.get("/audits/{batch_id}/ledger.csv")
def export_citation_ledger_csv(
    project_id: str,
    batch_id: str,
    _project: Project = Depends(authorize_project_id),
) -> Response:
    batch, _audit_run, _results = _load_audit_export(project_id, batch_id)
    return _csv_response(citation_ledger_csv(store.list_citation_ledger_entries(batch.id)), f"citation-ledger-{batch_id}.csv")


@router.get("/evidence.csv")
def export_evidence_cards_csv(
    project_id: str,
    _project: Project = Depends(authorize_project_id),
) -> Response:
    return _csv_response(evidence_cards_csv(store.list_project_evidence_cards(project_id)), f"evidence-cards-{project_id}.csv")


def _load_audit_export(project_id: str, batch_id: str):
    batch = store.get_audit_batch(batch_id)
    if batch.project_id != project_id:
        raise HTTPException(status_code=404, detail="Audit batch not found")
    return batch, store.get_latest_audit_run(batch_id), store.list_audit_results(batch_id)


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        "\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
