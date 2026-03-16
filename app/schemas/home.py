from pydantic import BaseModel, Field

from app.schemas.import_job import ImportJobBase
from app.schemas.project import ProjectResponse


class HomeUploadItem(ImportJobBase):
    project_name: str | None = None


class HomeSummaryResponse(BaseModel):
    projects: list[ProjectResponse] = Field(default_factory=list)
    uploads: list[HomeUploadItem] = Field(default_factory=list)
