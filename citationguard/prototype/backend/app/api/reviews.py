from fastapi import APIRouter, Depends

from app.models.schemas import (
    AccessKeyRecord,
    PreSubmissionReviewResponse,
    ReviewSkillRequest,
)
from app.services.access_control import authenticate_access_key, authorize_project
from app.services.reviewer_skills import reviewer_skill_runner
from app.services.store import store


router = APIRouter(prefix="/api/projects/{project_id}/reviews", tags=["reviews"])


@router.post("/pre-submission", response_model=PreSubmissionReviewResponse)
def pre_submission_review(
    project_id: str,
    payload: ReviewSkillRequest,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> PreSubmissionReviewResponse:
    project = store.get_project(project_id)
    authorize_project(project, access_key)
    if project.access_key_id:
        store.reserve_audit(project.access_key_id)
    try:
        response = reviewer_skill_runner.run(project_id=project_id, payload=payload)
    except Exception:
        if project.access_key_id:
            store.settle_audit(project.access_key_id, completed=False)
        raise
    if project.access_key_id:
        store.settle_audit(project.access_key_id, completed=True)
    return response
