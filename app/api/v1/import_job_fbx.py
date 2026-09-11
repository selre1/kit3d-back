from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.schemas.import_job import ImportJobBase, ImportJobsResponse
from app.services.import_job_fbx_service import (
    InvalidFileTypeError,
    ProjectNotFoundError,
    UploadFileAccessError,
    UploadFileMissingError,
    UploadFileNotFoundError,
    create_fbx_uploads,
    get_fbx_file_record,
    list_fbx_files,
)

router = APIRouter()


@router.post(
    "/{project_id}/process",
    response_model=ImportJobsResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_fbx_files(
    project_id: UUID,
    files: list[UploadFile] = File(...),
) -> ImportJobsResponse:
    try:
        return create_fbx_uploads(project_id, files)
    except InvalidFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FBX 파일만 업로드할 수 있습니다.",
        ) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다.",
        ) from exc


@router.get("/{project_id}/list", response_model=list[ImportJobBase])
def fbx_list(
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[ImportJobBase]:
    try:
        return list_fbx_files(project_id=project_id, limit=limit, offset=offset)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다.",
        ) from exc


@router.get("/{project_id}/{file_id}/download")
def download_fbx(
    project_id: UUID,
    file_id: int,
) -> FileResponse:
    try:
        record = get_fbx_file_record(project_id, file_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다.",
        ) from exc
    except UploadFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다.",
        ) from exc
    except UploadFileMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다.",
        ) from exc
    except UploadFileAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="파일 접근이 거부되었습니다.",
        ) from exc

    filename = record.get("file_name") or "download.fbx"
    return FileResponse(
        path=record["file_path"],
        filename=filename,
        media_type="application/octet-stream",
    )
