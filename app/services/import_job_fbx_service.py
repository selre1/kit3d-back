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
    ProjectFormatMismatchError,
    ProjectNotFoundError as ProjectMissingError,
    assert_project_format,
)
from app.services.upload_storage import (
    DuplicateFileNameError,
    InvalidArchiveError,
    close_uploads,
    extract_archive,
    list_archive_names,
    get_assets_root,
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


def get_fbx_upload_dir(project_id: UUID) -> Path:
    """프로젝트의 FBX 원본이 모여 있는 디렉터리. 변환의 입력 디렉터리가 된다."""
    return get_assets_root() / "model" / str(project_id) / FILE_FORMAT


def _take_archive(
    project_id: UUID,
    upload: UploadFile,
    seen_names: set[str],
    uploaded: list[dict],
    skipped: list[dict],
) -> None:
    """zip 을 풀어 안의 FBX 를 등록한다. 텍스처(.fbm 등)는 디스크에만 두고 행을 만들지 않는다."""
    archive_name = Path(upload.filename or "").name

    try:
        names = list_archive_names(upload)
    except InvalidArchiveError:
        skipped.append({"file_name": archive_name, "reason": "invalid_archive"})
        return

    # FBX 로더는 plant.fbx 옆의 plant.fbm/ 을 찾으므로 FBX 는 최상위에 있어야 한다.
    fbx_names = [
        name for name in names
        if "/" not in name and resolve_file_format(name) == FILE_FORMAT
    ]
    if not fbx_names:
        skipped.append({"file_name": archive_name, "reason": "no_model_in_archive"})
        return

    duplicated = [
        name for name in fbx_names
        if name.lower() in seen_names or upload_file_name_exists(project_id, name)
    ]
    if duplicated:
        for name in duplicated:
            skipped.append({"file_name": name, "reason": "duplicate_file_name"})
        return

    try:
        written = extract_archive(upload, project_id, FILE_FORMAT)
    except InvalidArchiveError:
        skipped.append({"file_name": archive_name, "reason": "invalid_archive"})
        return

    upload_root = get_assets_root()
    for name in fbx_names:
        seen_names.add(name.lower())
        rel_path = Path("model") / str(project_id) / FILE_FORMAT / name
        file_path = str(upload_root / rel_path)
        file_url = f"/assets/{rel_path.as_posix()}"
        db_result = create_upload_file(
            project_id=project_id,
            file_name=name,
            file_format=FILE_FORMAT,
            file_path=file_path,
            file_url=file_url,
            file_size=written.get(name),
        )
        uploaded.append(
            {
                "file_id": db_result["file_id"],
                "file_name": name,
                "file_path": file_path,
                "project_id": str(project_id),
                "file_format": FILE_FORMAT,
                "file_url": file_url,
                "file_size": written.get(name),
                "uploaded_at": db_result["uploaded_at"],
            }
        )


def create_fbx_uploads(project_id: UUID, files: list[UploadFile]) -> dict:
    if not files:
        return {"project_id": project_id, "uploaded": [], "skipped": [], "items": []}

    for upload in files:
        filename = Path(upload.filename or "").name
        # FBX 는 텍스처가 plant.fbx / plant.fbm/ 쌍으로 오므로 zip 도 받는다.
        if not filename or resolve_file_format(filename) not in ("fbx", "zip"):
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

        if resolve_file_format(filename) == "zip":
            try:
                _take_archive(project_id, upload, seen_names, uploaded, skipped)
            finally:
                try:
                    upload.file.close()
                except Exception:
                    pass
            continue

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
