import os
import tempfile
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.schemas.tile_job import TileJobCreate, TileJobResponse
from app.services.tile_job_service import (
    ProjectNotFoundError as TileProjectNotFoundError,
    TileJobNotFoundError,
    TilePathAccessError,
    TilePathMissingError,
    get_tile_job_record,
    list_tileset_urls,
    list_tile_jobs,
    run_tile_job,
)

router = APIRouter()


@router.post(
    "/{project_id}/tiling",
    response_model=TileJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_tiling(
    project_id: UUID,
    payload: TileJobCreate = Body(default_factory=TileJobCreate),
) -> TileJobResponse:
    try:
        return run_tile_job(project_id, payload)
    except TileProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc


@router.get(
    "/{project_id}/list",
    response_model=list[TileJobResponse],
)
def list_tiles(
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[TileJobResponse]:
    try:
        return list_tile_jobs(project_id=project_id, limit=limit, offset=offset)
    except TileProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc


@router.get("/{project_id}/{tile_job_id}/download")
def download_tiles(
    project_id: UUID,
    tile_job_id: UUID,
    background_tasks: BackgroundTasks,
):
    try:
        record = get_tile_job_record(project_id=project_id, tile_job_id=tile_job_id)
    except TileProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc
    except TileJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tile job not found",
        ) from exc
    except TilePathMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tile path not found",
        ) from exc
    except TilePathAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tile path access denied",
        ) from exc

    tile_path = Path(record["tile_path"])
    if tile_path.is_dir():
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tmp_path = tmp_file.name
        tmp_file.close()

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in tile_path.rglob("*"):
                if item.is_file():
                    archive.write(item, item.relative_to(tile_path).as_posix())

        background_tasks.add_task(os.remove, tmp_path)
        filename = f"tiles.zip"
        return FileResponse(
            path=tmp_path,
            filename=filename,
            media_type="application/zip",
            background=background_tasks,
        )

    filename = tile_path.name
    return FileResponse(
        path=str(tile_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/{project_id}/{tile_job_id}/tileset/urls")
def get_tileset_urls(
    project_id: UUID,
    tile_job_id: UUID,
    request: Request,
    only_done: bool = True,
):
    try:
        data = list_tileset_urls(
            project_id=project_id,
            tile_job_id=tile_job_id,
            only_done=only_done,
        )
        base_url = str(request.base_url).rstrip("/")
        absolute_urls = []
        for url in data.get("urls", []):
            if url.startswith("http://") or url.startswith("https://"):
                absolute_urls.append(url)
            elif url.startswith("/"):
                absolute_urls.append(f"{base_url}{url}")
            else:
                absolute_urls.append(f"{base_url}/{url}")
        data["urls"] = absolute_urls
        return data
    except TileProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc
    except TileJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tile job not found",
        ) from exc
