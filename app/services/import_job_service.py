import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.celery import celery_app
from app.redis import JobStatus, normalize_job_status
from app.repositories.import_job_repository import (
    ProjectNotFoundError as RepoProjectNotFoundError,
    create_upload_job,
    get_upload_file_by_project,
    get_upload_job_by_id,
    list_upload_jobs_by_project,
    reset_job_for_retry,
    upload_file_name_exists,
)
from app.repositories.project_repository import project_exists
from app.services.upload_storage import (
    DuplicateFileNameError,
    UploadFileAccessError,  # noqa: F401 - 라우터가 이 모듈에서 import 한다
    UploadFileMissingError,  # noqa: F401 - 라우터가 이 모듈에서 import 한다
    close_uploads,
    resolve_file_format,
    resolve_stored_path,
    save_upload_file,
)

# 이 모듈은 IFC 전용이다. 다른 포맷은 포맷별 서비스에서 처리한다.
FILE_FORMAT = "ifc"


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


def get_import_status(record: dict) -> dict:
    if not record:
        return record

    updated = dict(record)
    db_status = normalize_job_status(updated.get("status"))
    updated["status"] = db_status.value
    return updated


def create_jobs_for_uploads(project_id: UUID, files: list[UploadFile]) -> dict:
    if not files:
        return {"project_id": project_id, "uploaded": [], "skipped": [], "items": []}

    for upload in files:
        filename = Path(upload.filename or "").name
        if not filename or resolve_file_format(filename) != FILE_FORMAT:
            close_uploads(files)
            raise InvalidFileTypeError()

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
            job_id = uuid4()
            db_result = create_upload_job(
                project_id=project_id,
                job_id=job_id,
                file_name=filename,
                file_format=FILE_FORMAT,
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

            uploaded.append(
                {
                    "file_id": db_result["file_id"],
                    "job_id": job_id,
                    "file_name": filename,
                    "file_path": file_path,
                    "project_id": str(project_id),
                    "file_format": FILE_FORMAT,
                    "file_url": file_url,
                    "file_size": file_size,
                    "uploaded_at": db_result["uploaded_at"],
                    "job_type": db_result["job_type"],
                    "status": JobStatus.PENDING.value,
                    "started_at": db_result["started_at"],
                    "finished_at": db_result["finished_at"],
                    "created_at": db_result["created_at"],
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


def get_upload_file_record(project_id: UUID, file_id: int) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    record = get_upload_file_by_project(project_id, file_id)
    if not record:
        raise UploadFileNotFoundError()

    record["file_path"] = resolve_stored_path(record.get("file_path"))
    return record


def list_upload_jobs(project_id: UUID, limit: int = 50, offset: int = 0) -> list[dict]:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    records = list_upload_jobs_by_project(
        project_id=project_id,
        limit=limit,
        offset=offset,
        file_format=FILE_FORMAT,
    )
    return [get_import_status(record) for record in records]


def get_import_job_status_summary(project_id: UUID) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    jobs = list_upload_jobs(project_id=project_id, limit=10000, offset=0)
    counts = {
        JobStatus.PENDING.value: 0,
        JobStatus.RUNNING.value: 0,
        JobStatus.DONE.value: 0,
        JobStatus.FAILED.value: 0,
    }

    for job in jobs:
        status = normalize_job_status(job.get("status"))
        counts[status.value] += 1

    total = len(jobs)
    pending = counts[JobStatus.PENDING.value]
    running = counts[JobStatus.RUNNING.value]
    
    return {
        "project_id": project_id,
        "total": len(jobs),
        "pending": counts[JobStatus.PENDING.value],
        "running": counts[JobStatus.RUNNING.value],
        "done": counts[JobStatus.DONE.value],
        "failed": counts[JobStatus.FAILED.value],
        "all_done": total > 0 and (pending + running) == 0,
    }


def retry_import_job(job_id: UUID) -> dict:
    record = get_upload_job_by_id(job_id)
    if not record:
        raise JobNotFoundError()

    resolved = get_import_status(record)
    if normalize_job_status(resolved.get("status")) != JobStatus.FAILED:
        raise JobNotRetryableError()

    file_path = record.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise JobFileMissingError()

    reset_job_for_retry(job_id)

    celery_app.send_task(
        "import_ifc",
        args=[{
            "ifcPath": file_path,
            "projectId": str(record["project_id"]),
            "jobId": str(job_id),
        }],
        queue=os.getenv("CELERY_IMPORT_QUEUE", "import_jobs"),
    )

    refreshed = get_upload_job_by_id(job_id)
    if refreshed:
        return get_import_status(refreshed)

    record["status"] = JobStatus.PENDING.value
    record["started_at"] = None
    record["finished_at"] = None
    return record
