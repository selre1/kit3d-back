from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.dem import DemListItemResponse, DemUploadResponse
from app.services.dem_service import (
    DemFileSaveError,
    DuplicateDemFileNameError,
    InvalidDemFileTypeError,
    list_dem_files,
    save_dem_file,
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
