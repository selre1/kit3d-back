from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class FbxTileJobCreate(BaseModel):
    tile_name: str | None = None
    # 엔진에 그대로 전달되는 변환 옵션. 나머지 mago 옵션은 엔진에서 고정한다.
    crs: str = "5187"
    rotate_x_axis: float = 90
    # 반드시 불리언으로 직렬화해야 한다. 문자열 "false" 를 보내면 워커에서 참으로 평가된다.
    split_by_node: bool = True


class FbxTileJobResponse(BaseModel):
    fbx_job_id: UUID
    project_id: UUID
    tile_name: str | None = None
    status: str
    tileset_url: str | None = None
    input_dir: str | None = None
    output_dir: str | None = None
    error: str | None = None
    options: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_serializer("created_at", "started_at", "finished_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")
