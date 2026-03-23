import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.celery_client import terrain_celery_app
from app.repositories.dem_repository import (
    DuplicateDemPathError,
    create_dem,
    create_terrain_job,
    get_dem_by_id,
    get_terrain_job_by_dem,
    list_dems,
    set_terrain_job_failed,
    set_terrain_job_task_id,
)


class InvalidDemFileTypeError(Exception):
    pass


class DuplicateDemFileNameError(Exception):
    pass


class DemFileSaveError(Exception):
    pass


class DemNotFoundError(Exception):
    pass


class TerrainJobAlreadyRunningError(Exception):
    pass


class TerrainTaskDispatchError(Exception):
    pass


def _remove_file_safely(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _extract_dem_filename(upload: UploadFile) -> str:
    filename = Path(upload.filename or "").name
    ext = Path(filename).suffix.lower()
    if not filename or ext not in {".tif", ".tiff"}:
        raise InvalidDemFileTypeError()
    return filename


def _resolve_dem_paths(filename: str) -> tuple[Path, str]:
    upload_root = Path(os.getenv("ASSETS_DIR", "/data/assets"))
    file_rel_path = (Path("dem") / "tif" / filename).as_posix()
    dest_path = upload_root / file_rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    return dest_path, file_rel_path


def _write_upload_file(upload: UploadFile, dest_path: Path) -> int:
    size = 0
    with open(dest_path, "xb") as out_file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            out_file.write(chunk)
            size += len(chunk)
    return size


def save_dem_file(upload: UploadFile) -> dict:
    filename = _extract_dem_filename(upload)
    dest_path, file_rel_path = _resolve_dem_paths(filename)

    if dest_path.exists():
        raise DuplicateDemFileNameError()

    try:
        size = _write_upload_file(upload, dest_path)
    except FileExistsError as exc:
        raise DuplicateDemFileNameError() from exc
    except Exception as exc:
        _remove_file_safely(dest_path)
        raise DemFileSaveError() from exc

    try:
        dem_row = create_dem(
            dem_id=uuid4(),
            file_name=filename,
            file_path=file_rel_path,
            file_url=f"/assets/{file_rel_path}",
            file_size=size,
        )
    except DuplicateDemPathError as exc:
        _remove_file_safely(dest_path)
        raise DuplicateDemFileNameError() from exc
    except Exception as exc:
        _remove_file_safely(dest_path)
        raise DemFileSaveError() from exc

    return {
        "dem_id": dem_row["dem_id"],
        "file_name": dem_row["file_name"],
        "file_path": dem_row["file_path"],
        "file_url": dem_row["file_url"],
        "file_size": dem_row["file_size"],
        "created_at": dem_row["created_at"],
    }


def list_dem_files(limit: int = 100, offset: int = 0) -> list[dict]:
    return list_dems(limit=limit, offset=offset)


def start_dem_terrain_job(dem_id: str) -> dict:
    dem_row = get_dem_by_id(dem_id)
    if not dem_row:
        raise DemNotFoundError()

    latest_job = get_terrain_job_by_dem(dem_id)
    latest_status = (latest_job or {}).get("status")
    if latest_status in {"PENDING", "RUNNING", "ZIPPING"}:
        raise TerrainJobAlreadyRunningError()

    job_id = uuid4()
    input_file = str(Path(os.getenv("ASSETS_DIR")) / dem_row["file_path"])

    job_row = create_terrain_job(job_id=job_id, dem_id=dem_id, status="PENDING")

    payload = {
        "job_id": str(job_id),
        "dem_id": dem_id,
        "file_path": input_file,
    }

    try:
        async_result = terrain_celery_app.send_task(
            "terrain.convert_dem",
            args=[payload],
            queue=os.getenv("CELERY_TERRAIN_QUEUE", "terrain_jobs"),
        )
        set_terrain_job_task_id(job_id=str(job_id), task_id=async_result.id)
    except Exception as exc:
        set_terrain_job_failed(job_id=str(job_id), err=str(exc))
        raise TerrainTaskDispatchError() from exc

    return {
        "job_id": job_row["job_id"],
        "dem_id": job_row["dem_id"],
        "status": "PENDING",
        "task_id": async_result.id,
    }
