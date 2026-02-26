from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class TilesetItem(BaseModel):
    ifc_class: str
    tileset_url: str
    status: str
    error: str | None = None
    updated_at: datetime | None = None

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")


class TileJobCreate(BaseModel):
    tile_name: str | None = None
    ifc_classes: list[str] | None = None
    max_features_per_tile: int = Field(default=1000, ge=1)
    geometric_error: int | float = Field(default=50, ge=0)


class TileJobResponse(BaseModel):
    tile_job_id: UUID
    project_id: UUID
    tile_name: str | None = None
    status: str
    total_classes: int | None = None
    done_classes: int
    failed_classes: int
    tile_path: str | None = None
    tilesets: list[TilesetItem] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None

    @field_serializer("started_at", "finished_at", "created_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")
