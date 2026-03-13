import os
from pathlib import Path
from uuid import UUID, uuid4

from app.celery_client import celery_app
from app.redis import JobStatus, get_status_from_redis, normalize_job_status
from app.repositories.project_repository import project_exists
from app.repositories.tile_job_repository import (
    ProjectNotFoundError,
    create_tile_job,
    get_tile_job_by_project,
    list_tile_jobs_by_project,
    list_tilesets_by_tile_job,
    list_tilesets_by_tile_job_ids,
)
from app.schemas.tile_job import TileJobCreate


class TileJobNotFoundError(Exception):
    pass


class TilePathMissingError(Exception):
    pass


class TilePathAccessError(Exception):
    pass



def get_tile_status(record: dict, tilesets: list[dict] | None = None) -> dict:
    if not record:
        return record

    merged = dict(record)
    db_status = normalize_job_status(merged.get("status"))

    resolved = None
    if db_status not in (JobStatus.DONE, JobStatus.FAILED):
        try:
            candidate = get_status_from_redis(merged.get("tile_job_id"))
        except Exception:
            candidate = None
        if candidate is not None and candidate.has_runtime:
            resolved = candidate

    if resolved is not None:
        merged["status"] = resolved.status.value
        payload = resolved.payload if isinstance(resolved.payload, dict) else {}
        for key in ("total_classes", "done_classes", "failed_classes", "tile_path"):
            if key in payload and payload.get(key) is not None:
                merged[key] = payload.get(key)
    else:
        merged["status"] = db_status.value

    if tilesets is None:
        merged["tilesets"] = list_tilesets_by_tile_job(merged.get("tile_job_id"))
    else:
        merged["tilesets"] = tilesets

    return merged


def run_tile_job(project_id: UUID, payload: TileJobCreate) -> dict:
    tile_job_id = uuid4()
    assets_root = Path(os.getenv("UPLOAD_DIR", "assets"))
    tile_path = str(assets_root / str(project_id) / "tiles" / str(tile_job_id))

    result = create_tile_job(
        project_id=project_id,
        tile_job_id=tile_job_id,
        tile_name=payload.tile_name,
        tile_path=tile_path,
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
        task_id=str(tile_job_id),
    )

    return result


def list_tile_jobs(project_id: UUID, limit: int = 50, offset: int = 0) -> list[dict]:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    base = list_tile_jobs_by_project(project_id=project_id, limit=limit, offset=offset)
    tile_job_ids = list(dict.fromkeys(row.get("tile_job_id") for row in base if row.get("tile_job_id")))
    tilesets_by_job = list_tilesets_by_tile_job_ids(tile_job_ids)

    return [
        get_tile_status(
            row,
            tilesets=tilesets_by_job.get(str(row.get("tile_job_id")), []),
        )
        for row in base
    ]


def get_tile_job_record(project_id: UUID, tile_job_id: UUID) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    record = get_tile_job_by_project(project_id=project_id, tile_job_id=tile_job_id)
    if not record:
        raise TileJobNotFoundError()

    record = get_tile_status(record)

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

    tilesets = list_tilesets_by_tile_job(tile_job_id)

    done_count = 0
    urls: list[str] = []
    for tileset in tilesets:
        status = normalize_job_status(tileset.get("status"))
        if status == JobStatus.DONE:
            done_count += 1
        if only_done and status != JobStatus.DONE:
            continue
        url = tileset.get("tileset_url")
        if url:
            urls.append(url)

    return {
        "urls": urls,
        "total": len(tilesets),
        "done": done_count,
    }
