from uuid import UUID, uuid4

from app.repositories.project_repository import (
    ProjectAlreadyExistsError,  # noqa: F401 - 라우터가 이 모듈에서 import 한다
    fetch_projects,
    get_project_format,
    insert_project,
)
from app.schemas.project import ProjectCreate


class ProjectFormatMismatchError(Exception):
    """프로젝트의 모델 타입과 다른 포맷을 다루려 할 때."""

    def __init__(self, project_format: str):
        super().__init__(project_format)
        self.project_format = project_format


class ProjectNotFoundError(Exception):
    pass


def create_project(payload: ProjectCreate, file_format: str) -> dict:
    project_id = payload.project_id or uuid4()
    return insert_project(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        file_format=file_format,
    )


def list_projects(limit: int = 50, offset: int = 0, file_format: str | None = None) -> list[dict]:
    return fetch_projects(limit=limit, offset=offset, file_format=file_format)


def assert_project_format(project_id: UUID, file_format: str) -> None:
    """업로드 전, 프로젝트가 해당 타입인지 확인한다.

    타입 전용 프로젝트이므로 다른 포맷의 파일을 받으면 그 파일은
    어느 목록에도 나타나지 않는 고아가 된다.
    """
    project_format = get_project_format(project_id)
    if project_format is None:
        raise ProjectNotFoundError()
    if project_format != file_format:
        raise ProjectFormatMismatchError(project_format)
