import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.celery_client import celery_app

from app.repositories.import_job_repository import (
    ProjectNotFoundError as RepoProjectNotFoundError,
    count_upload_job_status_by_project,
    create_upload_job,
    get_upload_file_by_project,
    get_upload_job_by_id,
    list_upload_jobs_by_project,
    reset_job_for_retry,
)
from app.repositories.project_repository import project_exists


class ProjectNotFoundError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class JobNotRetryableError(Exception):
    pass


class JobFileMissingError(Exception):
    pass


class InvalidFileTypeError(Exception):
    pass


class UploadFileNotFoundError(Exception):
    pass


class UploadFileMissingError(Exception):
    pass


class UploadFileAccessError(Exception):
    pass


def save_upload_file(project_id: UUID, upload: UploadFile) -> tuple[str, str, int | None]:
    upload_root = Path(os.getenv("UPLOAD_DIR", "assets"))
    project_rel_dir = Path(str(project_id)) / "uploads"
    project_dir = upload_root / project_rel_dir
    project_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(upload.filename or "upload.ifc").name
    dest_name = f"origin_{filename}"
    dest_path = project_dir / dest_name

    relative_path = (project_rel_dir / dest_name).as_posix()
    file_url = f"/assets/{relative_path}"

    size = 0
    with open(dest_path, "wb") as out_file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            out_file.write(chunk)
            size += len(chunk)

    return str(dest_path), str(file_url), size


def close_uploads(files: list[UploadFile]) -> None:
    for upload in files:
        try:
            upload.file.close()
        except Exception:
            pass

def create_jobs_for_uploads(project_id: UUID, files: list[UploadFile]) -> dict:
    if not files:
        return {"project_id": project_id, "items": []}

    for upload in files:
        filename = upload.filename or ""
        ext = Path(filename).suffix.lower()
        if ext != ".ifc":
            close_uploads(files)
            raise InvalidFileTypeError()

    results = []
    for upload in files:
        file_path = None
        try:
            filename = upload.filename or ""
            file_path, file_url, file_size = save_upload_file(project_id, upload)
            job_id = uuid4()
            db_result = create_upload_job(
                project_id=project_id,
                job_id=job_id,
                file_name=Path(filename).name,
                file_format="ifc",
                file_path=file_path,
                file_url=file_url,
                file_size=file_size,
            )

            celery_app.send_task(
                "import_ifc",
                args=[{
                    "ifcPath": file_path,
                    "projectId": str(project_id),
                    "jobId": str(job_id),
                }],
                queue=os.getenv("CELERY_IMPORT_QUEUE", "import_jobs"),
            )

            results.append({
                "file_id": db_result["file_id"],
                "job_id": job_id,
                "file_name": Path(filename).name,
                "file_path": file_path,
                "project_id": str(project_id),
                "file_format": "ifc",
                "file_url": file_url,
                "file_size": file_size,
                "uploaded_at": db_result["uploaded_at"],
                "job_type": db_result["job_type"],
                "status": db_result["status"],
                "started_at": db_result["started_at"],
                "finished_at": db_result["finished_at"],
                "created_at": db_result["created_at"],
            })
        except RepoProjectNotFoundError as exc:
            raise ProjectNotFoundError() from exc
        except Exception:
            raise
        finally:
            try:
                upload.file.close()
            except Exception:
                pass

    return {"project_id": project_id, "items": results}


def get_upload_file_record(project_id: UUID, file_id: int) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    record = get_upload_file_by_project(project_id, file_id)
    if not record:
        raise UploadFileNotFoundError()

    file_path = record.get("file_path")
    if not file_path:
        raise UploadFileMissingError()

    upload_root = Path(os.getenv("UPLOAD_DIR", "assets")).resolve()
    resolved_path = Path(file_path).resolve()
    if resolved_path != upload_root and upload_root not in resolved_path.parents:
        raise UploadFileAccessError()

    if not resolved_path.is_file():
        raise UploadFileMissingError()

    record["file_path"] = str(resolved_path)
    return record


def list_upload_jobs(project_id: UUID, limit: int = 50, offset: int = 0) -> list[dict]:
    if not project_exists(project_id):
        raise ProjectNotFoundError()
    return list_upload_jobs_by_project(project_id=project_id, limit=limit, offset=offset)


def get_import_job_status_summary(project_id: UUID) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    counts = count_upload_job_status_by_project(project_id=project_id)
    total = sum(counts.values())
    pending = counts.get("PENDING", 0)
    running = counts.get("RUNNING", 0)
    done = counts.get("DONE", 0)
    failed = counts.get("FAILED", 0)
    other = total - pending - running - done - failed
    all_done = total > 0 and (pending + running + other) == 0

    return {
        "project_id": project_id,
        "total": total,
        "pending": pending,
        "running": running,
        "done": done,
        "failed": failed,
        "other": other,
        "all_done": all_done,
    }


def retry_import_job(job_id: UUID) -> dict:
    record = get_upload_job_by_id(job_id)
    if not record:
        raise JobNotFoundError()

    if record.get("status") != "FAILED":
        raise JobNotRetryableError()

    file_path = record.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise JobFileMissingError()

    if not reset_job_for_retry(job_id):
        raise JobNotRetryableError()

    celery_app.send_task(
        "import_ifc",
        args=[{
            "ifcPath": file_path,
            "projectId": str(record["project_id"]),
            "jobId": str(job_id),
        }],
        queue=os.getenv("CELERY_QUEUE", "ifc_jobs"),
    )

    refreshed = get_upload_job_by_id(job_id)
    if refreshed:
        return refreshed

    record["status"] = "PENDING"
    record["started_at"] = None
    record["finished_at"] = None
    return record
