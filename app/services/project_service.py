from uuid import uuid4

from app.repositories.project_repository import (
    ProjectAlreadyExistsError,
    fetch_projects,
    insert_project,
)
from app.schemas.project import ProjectCreate


def create_project(payload: ProjectCreate) -> dict:
    project_id = payload.project_id or uuid4()
    return insert_project(project_id=project_id, name=payload.name, description=payload.description)


def list_projects(limit: int = 50, offset: int = 0) -> list[dict]:
    return fetch_projects(limit=limit, offset=offset)