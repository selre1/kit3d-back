from uuid import uuid4

from app.repositories.project_repository import (
    ProjectAlreadyExistsError,  # noqa: F401 - 라우터가 이 모듈에서 import 한다
    fetch_projects,
    insert_project,
)
from app.schemas.project import ProjectCreate
from app.services.upload_storage import MODEL_FORMATS


def fill_format_counts(project: dict) -> dict:
    """models_count_by_format 에 지원 포맷 키를 항상 채워 둔다.

    프론트가 models_count_by_format[modelType] 을 그대로 읽을 수 있게,
    업로드가 없는 포맷도 0 으로 내려보낸다.
    """
    counts = project.get("models_count_by_format") or {}
    filled = {file_format: 0 for file_format in MODEL_FORMATS}
    for file_format, count in counts.items():
        filled[file_format] = int(count)

    project["models_count_by_format"] = filled
    return project


def create_project(payload: ProjectCreate) -> dict:
    project_id = payload.project_id or uuid4()
    project = insert_project(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
    )
    return fill_format_counts(project)


def list_projects(limit: int = 50, offset: int = 0) -> list[dict]:
    return [fill_format_counts(project) for project in fetch_projects(limit=limit, offset=offset)]
