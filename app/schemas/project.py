from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class ProjectCreate(BaseModel):
    project_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    # 이 프로젝트에 올라올 모델의 좌표계. 임포트·변환이 모두 이 값을 쓴다.
    crs: int


class ProjectResponse(BaseModel):
    project_id: UUID
    name: str
    description : str | None = None
    format: str
    crs: int
    created_at: datetime | None = None
    models_count: int = 0

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")
