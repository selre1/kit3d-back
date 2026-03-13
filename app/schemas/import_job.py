from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_serializer


class ImportJobBase(BaseModel):
    file_id: int
    project_id: UUID | None = None
    file_name: str
    file_format: str | None = None
    file_path: str
    file_url: str
    file_size: int | None = None
    uploaded_at: datetime | None = None
    job_id: UUID | None = None
    job_type: str | None = None
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None

    @field_serializer(
        "uploaded_at",
        "started_at",
        "finished_at",
        "created_at",
    )
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")


class ImportJobsResponse(BaseModel):
    project_id: UUID
    items: list[ImportJobBase]


class ImportJobStatusResponse(BaseModel):
    project_id: UUID
    total: int
    pending: int
    running: int
    done: int
    failed: int
    all_done: bool
