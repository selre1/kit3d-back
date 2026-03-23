from datetime import datetime

from pydantic import BaseModel, field_serializer


class DemUploadResponse(BaseModel):
    dem_id: str
    file_name: str
    file_path: str
    file_url: str
    file_size: int
    created_at: datetime
    job_id: str | None = None
    terrain_status: str | None = None
    terrain_download_url: str | None = None
    terrain_tileset_url: str | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class DemListItemResponse(BaseModel):
    dem_id: str
    file_name: str
    file_path: str
    file_url: str
    job_id: str | None = None
    terrain_status: str | None = None
    terrain_download_url: str | None = None
    terrain_tileset_url: str | None = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class DemConvertResponse(BaseModel):
    job_id: str
    dem_id: str
    status: str
    task_id: str
