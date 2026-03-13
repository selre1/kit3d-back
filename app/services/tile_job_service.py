import os
from pathlib import Path
from uuid import UUID, uuid4

from app.celery_client import celery_app
from app.redis import JobStatus, normalize_job_status, get_status_from_redis
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


def get_tile_status(record: dict) -> dict:
    if not record:
        return record

    merged = dict(record)
    resolved = get_status_from_redis(merged.get("tile_job_id"))
    db_status = normalize_job_status(merged.get("status"))
    effective_status = resolved.status if resolved.has_runtime else db_status
    merged["status"] = effective_status.value

    if resolved.has_runtime:
        payload = resolved.payload
        for key in ("total_classes", "done_classes", "failed_classes", "tile_path", "tilesets"):
            if key in payload and payload.get(key) is not None:
                merged[key] = payload.get(key)

    if merged.get("tilesets") is None:
        merged["tilesets"] = []

    return merged


def _scan_tilesets(tile_path: str) -> list[dict]:
    root = Path(tile_path)
    if not root.exists():
        return []

    assets_root = Path(os.getenv("UPLOAD_DIR", "assets")).resolve()
    rows = []
    for tileset_file in root.rglob("tileset.json"):
        try:
            rel = tileset_file.resolve().relative_to(assets_root)
            tileset_url = f"/tiles/{rel.as_posix()}"
        except Exception:
            tileset_url = tileset_file.as_posix()

        rows.append(
            {
                "ifc_class": tileset_file.parent.name,
                "tileset_url": tileset_url,
                "status": JobStatus.DONE.value,
                "error": None,
                "updated_at": None,
            }
        )

    rows.sort(key=lambda item: item["ifc_class"])
    return rows


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
    return [get_tile_status(row) for row in base]


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

    record = get_tile_status(record)
    tilesets = record.get("tilesets") or []
    if not tilesets and record.get("tile_path"):
        tilesets = _scan_tilesets(record["tile_path"])

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