from fastapi import APIRouter, HTTPException, status

from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import (
    ProjectAlreadyExistsError,
    create_project,
    list_projects,
)

router = APIRouter()
    
@router.get("/list", response_model=list[ProjectResponse])
def project_list(limit: int = 50, offset: int = 0) -> list[ProjectResponse]:
    return list_projects(limit=limit, offset=offset)

@router.post("/create", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def project_create(payload: ProjectCreate) -> ProjectResponse:
    try:
        return create_project(payload)
    except ProjectAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project already exists",
        ) from exc
