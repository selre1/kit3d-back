from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.dem import DemConvertResponse, DemListItemResponse, DemUploadResponse
from app.services.dem_service import (
    DemNotFoundError,
    DemFileSaveError,
    DuplicateDemFileNameError,
    InvalidDemFileTypeError,
    list_dem_files,
    save_dem_file,
    start_dem_terrain_job,
    TerrainJobAlreadyRunningError,
    TerrainTaskDispatchError,
)

router = APIRouter()


@router.get("/list", response_model=list[DemListItemResponse])
def list_dem_tifs(limit: int = 100, offset: int = 0) -> list[DemListItemResponse]:
    try:
        return list_dem_files(limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DEM 목록 로드에 실패했습니다.",
        ) from exc


@router.post(
    "/upload",
    response_model=DemUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_dem_tif(file: UploadFile = File(...)) -> DemUploadResponse:
    try:
        return save_dem_file(file)
    except InvalidDemFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 형식이 올바르지 않습니다. TIFF 형식의 DEM 파일을 업로드해주세요.",
        ) from exc
    except DuplicateDemFileNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="해당 파일 이름이 이미 존재합니다. 다른 이름으로 업로드해주세요.",
        ) from exc
    except DemFileSaveError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DEM 파일 저장 중 오류가 발생했습니다.",
        ) from exc
    finally:
        try:
            file.file.close()
        except Exception:
            pass


@router.post(
    "/{dem_id}/convert",
    response_model=DemConvertResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_dem_convert(dem_id: UUID) -> DemConvertResponse:
    try:
        return start_dem_terrain_job(str(dem_id))
    except DemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DEM 파일을 찾을 수 없습니다.",
        ) from exc
    except TerrainJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 변환 작업이 진행 중입니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    except TerrainTaskDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Terrain 변환 작업을 시작하는 데 실패했습니다.",
        ) from exc
