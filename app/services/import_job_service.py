import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.celery_client import celery_app
from app.redis import JobStatus, normalize_job_status, get_status_from_redis
from app.repositories.import_job_repository import (
    ProjectNotFoundError as RepoProjectNotFoundError,
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


def get_import_status(record: dict) -> dict:
    if not record:
        return record

    updated = dict(record)
    resolved = get_status_from_redis(updated.get("job_id"))
    db_status = normalize_job_status(updated.get("status"))
    updated_status = resolved.status if resolved.has_runtime else db_status
    updated["status"] = updated_status.value
    return updated


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
                task_id=str(job_id),
            )

            results.append(
                {
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
                    "status": JobStatus.PENDING.value,
                    "started_at": db_result["started_at"],
                    "finished_at": db_result["finished_at"],
                    "created_at": db_result["created_at"],
                }
            )
        except RepoProjectNotFoundError as exc:
            raise ProjectNotFoundError() from exc
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

    records = list_upload_jobs_by_project(project_id=project_id, limit=limit, offset=offset)
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
        task_id=str(job_id),
    )

    refreshed = get_upload_job_by_id(job_id)
    if refreshed:
        return get_import_status(refreshed)

    record["status"] = JobStatus.PENDING.value
    record["started_at"] = None
    record["finished_at"] = None
    return record