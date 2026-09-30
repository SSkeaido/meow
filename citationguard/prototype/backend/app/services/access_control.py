import os

from fastapi import Depends, Header, HTTPException

from app.models.schemas import AccessKeyRecord, Project
from app.services.store import store


def access_key_required() -> bool:
    return os.getenv("ACCESS_KEY_REQUIRED", "false").lower() in {"1", "true", "yes", "on"}


def authenticate_access_key(x_access_key: str | None = Header(default=None)) -> AccessKeyRecord | None:
    if not x_access_key:
        if access_key_required():
            raise HTTPException(status_code=401, detail="X-Access-Key header is required")
        return None
    record = store.verify_access_key(x_access_key)
    if not record:
        raise HTTPException(status_code=401, detail="Invalid or inactive access key")
    return record


def require_access_key(
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> AccessKeyRecord:
    if not access_key:
        raise HTTPException(status_code=401, detail="Access key is required")
    return access_key


def authorize_project(project: Project, access_key: AccessKeyRecord | None) -> None:
    if not project.access_key_id:
        if access_key_required():
            raise HTTPException(status_code=403, detail="Project is not bound to an access key")
        return
    if not access_key or project.access_key_id != access_key.id:
        raise HTTPException(status_code=403, detail="Access key cannot access this project")


def authorize_project_id(
    project_id: str,
    access_key: AccessKeyRecord | None = Depends(authenticate_access_key),
) -> Project:
    project = store.get_project(project_id)
    authorize_project(project, access_key)
    return project
