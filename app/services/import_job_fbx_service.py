"""FBX 전용 업로드 서비스.

FBX 는 임포트 워커와 변환 엔진이 아직 없으므로 **원본 파일 보관까지만** 한다.
- import_job 을 만들지 않는다 (만들면 영원히 PENDING 으로 남아 프로젝트 집계를 막는다)
- celery 태스크를 보내지 않는다

뒤처리(임포트/변환)가 준비되면 이 모듈에 그 단계를 추가한다.
IFC 파이프라인은 import_job_service.py 에 그대로 둔다.
"""

from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.repositories.import_job_repository import (
    ProjectNotFoundError as RepoProjectNotFoundError,
    create_upload_file,
    get_upload_file_by_project,
    list_upload_jobs_by_project,
    upload_file_name_exists,
)
from app.repositories.project_repository import project_exists
from app.services.project_service import (
    ProjectFormatMismatchError,  # noqa: F401 - 라우터가 이 모듈에서 import 한다
    ProjectNotFoundError as ProjectMissingError,
    assert_project_format,
)
from app.services.upload_storage import (
    DuplicateFileNameError,
    UploadFileAccessError,  # noqa: F401 - 라우터가 이 모듈에서 import 한다
    UploadFileMissingError,  # noqa: F401 - 라우터가 이 모듈에서 import 한다
    close_uploads,
    normalize_file_format,
    resolve_file_format,
    resolve_stored_path,
    save_upload_file,
)

FILE_FORMAT = "fbx"


class ProjectNotFoundError(Exception):
    pass


class InvalidFileTypeError(Exception):
    pass


class UploadFileNotFoundError(Exception):
    pass


def create_fbx_uploads(project_id: UUID, files: list[UploadFile]) -> dict:
    if not files:
        return {"project_id": project_id, "uploaded": [], "skipped": [], "items": []}

    for upload in files:
        filename = Path(upload.filename or "").name
        if not filename or resolve_file_format(filename) != FILE_FORMAT:
            close_uploads(files)
            raise InvalidFileTypeError()

    try:
        assert_project_format(project_id, FILE_FORMAT)
    except ProjectMissingError as exc:
        close_uploads(files)
        raise ProjectNotFoundError() from exc
    except ProjectFormatMismatchError:
        close_uploads(files)
        raise

    uploaded: list[dict] = []
    skipped: list[dict] = []
    seen_names: set[str] = set()

    for upload in files:
        filename = Path(upload.filename or "").name
        key = filename.lower()

        if key in seen_names or upload_file_name_exists(project_id, filename):
            skipped.append({
                "file_name": filename,
                "reason": "duplicate_file_name",
            })
            try:
                upload.file.close()
            except Exception:
                pass
            continue

        seen_names.add(key)

        try:
            file_path, file_url, file_size = save_upload_file(project_id, upload, FILE_FORMAT)
            db_result = create_upload_file(
                project_id=project_id,
                file_name=filename,
                file_format=FILE_FORMAT,
                file_path=file_path,
                file_url=file_url,
                file_size=file_size,
            )

            uploaded.append(
                {
                    "file_id": db_result["file_id"],
                    "file_name": filename,
                    "file_path": file_path,
                    "project_id": str(project_id),
                    "file_format": FILE_FORMAT,
                    "file_url": file_url,
                    "file_size": file_size,
                    "uploaded_at": db_result["uploaded_at"],
                }
            )
        except RepoProjectNotFoundError as exc:
            raise ProjectNotFoundError() from exc
        except DuplicateFileNameError:
            skipped.append(
                {
                    "file_name": filename,
                    "reason": "duplicate_file_name",
                }
            )
        finally:
            try:
                upload.file.close()
            except Exception:
                pass

    return {
        "project_id": project_id,
        "uploaded": uploaded,
        "skipped": skipped,
        "items": uploaded,
    }


def list_fbx_files(project_id: UUID, limit: int = 50, offset: int = 0) -> list[dict]:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    return list_upload_jobs_by_project(
        project_id=project_id,
        limit=limit,
        offset=offset,
        file_format=FILE_FORMAT,
    )


def get_fbx_file_record(project_id: UUID, file_id: int) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    record = get_upload_file_by_project(project_id, file_id)
    if not record or normalize_file_format(record.get("file_format")) != FILE_FORMAT:
        raise UploadFileNotFoundError()

    record["file_path"] = resolve_stored_path(record.get("file_path"))
    return record
