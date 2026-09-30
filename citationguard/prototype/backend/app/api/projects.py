from fastapi import APIRouter, Depends

from app.models.schemas import AccessKeyRecord, Project, ProjectCreate
from app.services.access_control import authenticate_access_key, authorize_project
from app.services.store import store

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=Project)
def create_project(
    payload: ProjectCreate,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> Project:
    return store.create_project(payload, access_key_id=access_key.id if access_key else "")


@router.get("", response_model=list[Project])
def list_projects(access_key: AccessKeyRecord | None = Depends(authenticate_access_key)) -> list[Project]:
    projects = store.list_projects()
    if access_key:
        return [project for project in projects if project.access_key_id == access_key.id]
    return [project for project in projects if not project.access_key_id]


@router.get("/{project_id}", response_model=Project)
def get_project(
    project_id: str,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> Project:
    project = store.get_project(project_id)
    authorize_project(project, access_key)
    return project
