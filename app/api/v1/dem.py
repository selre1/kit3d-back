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
            detail="Failed to load DEM list",
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
            detail="Only .tif or .tiff files are supported",
        ) from exc
    except DuplicateDemFileNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="File already exists",
        ) from exc
    except DemFileSaveError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save DEM file",
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
            detail="DEM not found",
        ) from exc
    except TerrainJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terrain conversion already in progress",
        ) from exc
    except TerrainTaskDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dispatch terrain conversion task",
        ) from exc
