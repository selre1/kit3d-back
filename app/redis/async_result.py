from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.celery_client import celery_app
from app.redis.job_status import JobStatus, normalize_job_status


@dataclass
class RedisTaskResolution:
    status: JobStatus
    has_runtime: bool
    payload: dict[str, Any] = field(default_factory=dict)


def get_status_from_redis(task_id: UUID | str | None) -> RedisTaskResolution:
    if not task_id:
        return RedisTaskResolution(status=JobStatus.PENDING, has_runtime=False)

    async_result = celery_app.AsyncResult(str(task_id))
    state = str(async_result.state or "PENDING").upper()

    payload: dict[str, Any] = {}
    if state == "SUCCESS" and isinstance(async_result.result, dict):
        payload = async_result.result
    elif isinstance(async_result.info, dict):
        payload = async_result.info

    if state in ("STARTED", "PROGRESS"):
        return RedisTaskResolution(status=JobStatus.RUNNING, has_runtime=True, payload=payload)

    if state in ("FAILURE", "REVOKED"):
        return RedisTaskResolution(status=JobStatus.FAILED, has_runtime=True, payload=payload)

    if state == "SUCCESS":
        payload_status = normalize_job_status(payload.get("status"), default=JobStatus.DONE)
        return RedisTaskResolution(status=payload_status, has_runtime=True, payload=payload)

    return RedisTaskResolution(status=JobStatus.PENDING, has_runtime=False, payload=payload)

