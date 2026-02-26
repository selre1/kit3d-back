from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class ProjectCreate(BaseModel):
    project_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class ProjectResponse(BaseModel):
    project_id: UUID
    name: str
    description : str | None = None
    created_at: datetime | None = None
    models_count: int = 0

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")
