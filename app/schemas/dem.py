from datetime import datetime

from pydantic import BaseModel, field_serializer


class DemUploadResponse(BaseModel):
    dem_id: str
    file_name: str
    file_path: str
    file_url: str
    file_size: int
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class DemListItemResponse(BaseModel):
    dem_id: str
    file_name: str
    file_path: str
    file_url: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")
