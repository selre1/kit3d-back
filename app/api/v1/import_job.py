from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.schemas.import_job import (
    ImportJobBase,
    ImportJobsResponse,
    ImportJobStatusResponse,
)
from app.services.import_job_service import (
    InvalidFileTypeError,
    JobFileMissingError,
    JobNotFoundError,
    JobNotRetryableError,
    ProjectNotFoundError,
    UploadFileAccessError,
    UploadFileMissingError,
    UploadFileNotFoundError,
    create_jobs_for_uploads,
    get_import_job_status_summary,
    get_upload_file_record,
    list_upload_jobs,
    retry_import_job,
)

router = APIRouter()

@router.post(
    "/{project_id}/process",
    response_model=ImportJobsResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_files(
    project_id: UUID,
    files: list[UploadFile] = File(...),
) -> ImportJobsResponse:
    try:
        return create_jobs_for_uploads(project_id, files)
    except InvalidFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .ifc files are supported",
        ) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc


@router.get("/{project_id}/list",response_model=list[ImportJobBase],)
def import_list(
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[ImportJobBase]:
    try:
        return list_upload_jobs(project_id=project_id, limit=limit, offset=offset)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc


@router.get("/{project_id}/{file_id}/download")
def download_ifc(
    project_id: UUID,
    file_id: int,
) -> FileResponse:
    try:
        record = get_upload_file_record(project_id, file_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc
    except UploadFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from exc
    except UploadFileMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from exc
    except UploadFileAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="File access denied",
        ) from exc

    filename = record.get("file_name") or "download.ifc"
    return FileResponse(
        path=record["file_path"],
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/{project_id}/status", response_model=ImportJobStatusResponse)
def get_import_job_status(project_id: UUID) -> ImportJobStatusResponse:
    try:
        return get_import_job_status_summary(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc


@router.post("/{job_id}/retry", response_model=ImportJobBase)
def retry_job(job_id: UUID) -> ImportJobBase:
    try:
        return retry_import_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
    except JobFileMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="File not found",
        ) from exc
    except JobNotRetryableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job is not retryable",
        ) from exc
