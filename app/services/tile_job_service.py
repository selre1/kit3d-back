import os
from pathlib import Path
from uuid import UUID, uuid4

from app.celery_client import celery_app
from app.repositories.project_repository import project_exists
from app.repositories.tile_job_repository import (
    ProjectNotFoundError,
    create_tile_job,
    get_tile_job_by_project,
    list_tile_jobs_by_project,
)
from app.schemas.tile_job import TileJobCreate


class TileJobNotFoundError(Exception):
    pass


class TilePathMissingError(Exception):
    pass


class TilePathAccessError(Exception):
    pass


def run_tile_job(project_id: UUID, payload: TileJobCreate) -> dict:
    tile_job_id = uuid4()
    result = create_tile_job(
        project_id=project_id,
        tile_job_id=tile_job_id,
        tile_name=payload.tile_name,
    )

    options = {
        "max_features_per_tile": payload.max_features_per_tile,
        "geometric_error": payload.geometric_error,
    }

    task_payload = {
        "projectId": str(project_id),
        "tileJobId": str(tile_job_id),
        "options": options,
    }
    if payload.ifc_classes:
        task_payload["ifc_classes"] = payload.ifc_classes

    celery_app.send_task(
        "run_3dtiles_by_class",
        args=[task_payload],
        queue=os.getenv("CELERY_TILES_QUEUE", "tile_jobs"),
    )

    return result


def list_tile_jobs(project_id: UUID, limit: int = 50, offset: int = 0) -> list[dict]:
    if not project_exists(project_id):
        raise ProjectNotFoundError()
    return list_tile_jobs_by_project(project_id=project_id, limit=limit, offset=offset)


def get_tile_job_record(project_id: UUID, tile_job_id: UUID) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    record = get_tile_job_by_project(project_id=project_id, tile_job_id=tile_job_id)
    if not record:
        raise TileJobNotFoundError()

    tile_path = record.get("tile_path")
    if not tile_path:
        raise TilePathMissingError()

    resolved_path = Path(tile_path).resolve()

    if not resolved_path.exists():
        raise TilePathMissingError()

    record["tile_path"] = str(resolved_path)
    return record


def list_tileset_urls(
    project_id: UUID,
    tile_job_id: UUID,
    only_done: bool = True,
) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    record = get_tile_job_by_project(project_id=project_id, tile_job_id=tile_job_id)
    if not record:
        raise TileJobNotFoundError()

    tilesets = record.get("tilesets") or []
    done_count = 0
    urls: list[str] = []
    for tileset in tilesets:
        status = (tileset.get("status") or "").upper()
        if status == "DONE":
            done_count += 1
        if only_done and status != "DONE":
            continue
        url = tileset.get("tileset_url")
        if url:
            urls.append(url)

    return {
        "urls": urls,
        "total": len(tilesets),
        "done": done_count,
    }
