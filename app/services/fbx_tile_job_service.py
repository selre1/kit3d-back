import os
from uuid import UUID, uuid4

from app.celery import celery_app
from app.redis import JobStatus, get_status_from_redis, normalize_job_status
from app.repositories.fbx_tile_job_repository import (
    create_fbx_tile_job,
    get_fbx_tile_job,
    list_fbx_tile_jobs_by_project,
    save_fbx_tile_job_result,
)
from app.repositories.project_repository import project_exists
from app.schemas.fbx_tile_job import FbxTileJobCreate
from app.services.import_job_fbx_service import (
    FILE_FORMAT,
    get_fbx_upload_dir,
    list_fbx_files,
)
from app.services.project_service import (
    ProjectNotFoundError as ProjectMissingError,
    assert_project_format,
)



class ProjectNotFoundError(Exception):
    pass


class FbxTileJobNotFoundError(Exception):
    pass


class NoFbxFileError(Exception):
    """변환할 FBX 원본이 프로젝트에 없다."""


def run_fbx_tile_job(project_id: UUID, payload: FbxTileJobCreate) -> dict:
    try:
        assert_project_format(project_id, FILE_FORMAT)
    except ProjectMissingError as exc:
        raise ProjectNotFoundError() from exc

    if not list_fbx_files(project_id=project_id, limit=1, offset=0):
        raise NoFbxFileError()

    input_dir = get_fbx_upload_dir(project_id)
    if not input_dir.is_dir():
        raise NoFbxFileError()

    fbx_job_id = uuid4()
    options = {
        "crs": payload.crs,
        "rotateXAxis": payload.rotate_x_axis,
        # bool 그대로 실어야 한다. 문자열이면 워커에서 항상 참이 된다.
        "splitByNode": bool(payload.split_by_node),
    }

    job = create_fbx_tile_job(
        fbx_job_id=fbx_job_id,
        project_id=project_id,
        task_id=str(fbx_job_id),
        tile_name=payload.tile_name,
        input_dir=str(input_dir),
        options=options,
    )

    celery_app.send_task(
        "convert_fbx",
        args=[{
            "projectId": str(project_id),
            "jobId": str(fbx_job_id),
            # 디렉터리를 넘긴다. 그 안의 FBX 전체가 하나의 타일셋이 된다.
            "fbxPath": str(input_dir),
            "options": options,
        }],
        queue=os.getenv("CELERY_FBX_QUEUE", "fbx_jobs"),
        task_id=str(fbx_job_id),
    )

    return job


def resolve_fbx_tile_job(record: dict) -> dict:
    """DB 상태가 확정되지 않았으면 Redis 결과를 확인하고, 확정되면 DB 에 옮긴다."""
    if not record:
        return record

    merged = dict(record)
    db_status = normalize_job_status(merged.get("status"))
    if db_status in (JobStatus.DONE, JobStatus.FAILED):
        merged["status"] = db_status.value
        return merged

    try:
        resolution = get_status_from_redis(merged.get("task_id"))
    except Exception:
        merged["status"] = db_status.value
        return merged

    if not resolution.has_runtime:
        merged["status"] = db_status.value
        return merged

    result = resolution.payload if isinstance(resolution.payload, dict) else {}
    merged["status"] = resolution.status.value
    merged["tileset_url"] = result.get("tileset_url")
    merged["output_dir"] = result.get("output_dir")
    merged["error"] = result.get("error")

    if resolution.status in (JobStatus.DONE, JobStatus.FAILED):
        save_fbx_tile_job_result(
            fbx_job_id=merged["fbx_job_id"],
            status=resolution.status.value,
            tileset_url=merged.get("tileset_url"),
            output_dir=merged.get("output_dir"),
            error=merged.get("error"),
        )

    return merged


def list_fbx_tile_jobs(project_id: UUID, limit: int = 50, offset: int = 0) -> list[dict]:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    records = list_fbx_tile_jobs_by_project(project_id=project_id, limit=limit, offset=offset)
    return [resolve_fbx_tile_job(record) for record in records]


def get_fbx_tile_job_record(project_id: UUID, fbx_job_id: UUID) -> dict:
    if not project_exists(project_id):
        raise ProjectNotFoundError()

    record = get_fbx_tile_job(project_id=project_id, fbx_job_id=fbx_job_id)
    if not record:
        raise FbxTileJobNotFoundError()

    return resolve_fbx_tile_job(record)
