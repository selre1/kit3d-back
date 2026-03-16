from datetime import datetime

from pydantic import BaseModel, field_serializer


class DemUploadResponse(BaseModel):
    file_name: str
    file_path: str
    file_url: str
    file_size: int
    uploaded_at: datetime

    @field_serializer("uploaded_at")
    def serialize_uploaded_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")
