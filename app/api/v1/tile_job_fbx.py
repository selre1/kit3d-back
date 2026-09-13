from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, status

from app.schemas.fbx_tile_job import FbxTileJobCreate, FbxTileJobResponse
from app.services.fbx_tile_job_service import (
    FbxTileJobNotFoundError,
    NoFbxFileError,
    ProjectNotFoundError,
    get_fbx_tile_job_record,
    list_fbx_tile_jobs,
    run_fbx_tile_job,
)
from app.services.project_service import ProjectFormatMismatchError

router = APIRouter()


@router.post(
    "/{project_id}/tiling",
    response_model=FbxTileJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_fbx_tiling(
    project_id: UUID,
    payload: FbxTileJobCreate = Body(default_factory=FbxTileJobCreate),
) -> FbxTileJobResponse:
    try:
        return run_fbx_tile_job(project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다.",
        ) from exc
    except ProjectFormatMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="FBX 프로젝트가 아닙니다.",
        ) from exc
    except NoFbxFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="변환할 FBX 파일이 없습니다.",
        ) from exc


@router.get("/{project_id}/list", response_model=list[FbxTileJobResponse])
def fbx_tile_list(
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[FbxTileJobResponse]:
    try:
        return list_fbx_tile_jobs(project_id=project_id, limit=limit, offset=offset)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다.",
        ) from exc


@router.get("/{project_id}/{fbx_job_id}", response_model=FbxTileJobResponse)
def fbx_tile_detail(project_id: UUID, fbx_job_id: UUID) -> FbxTileJobResponse:
    try:
        return get_fbx_tile_job_record(project_id=project_id, fbx_job_id=fbx_job_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다.",
        ) from exc
    except FbxTileJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="변환 작업을 찾을 수 없습니다.",
        ) from exc
