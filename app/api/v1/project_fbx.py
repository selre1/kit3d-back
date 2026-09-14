from fastapi import APIRouter, HTTPException, status

from app.schemas.project import ProjectCreate, ProjectResponse
from app.repositories.project_repository import ProjectAlreadyExistsError
from app.services.project_service import UnsupportedCrsError, create_project, list_projects

router = APIRouter()

# FBX 프로젝트 전용. 동작은 IFC 와 같고 대상 타입만 다르므로 서비스는 공유한다.
FILE_FORMAT = "fbx"


@router.get("/list", response_model=list[ProjectResponse])
def project_list(limit: int = 50, offset: int = 0) -> list[ProjectResponse]:
    return list_projects(limit=limit, offset=offset, file_format=FILE_FORMAT)


@router.post("/create", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def project_create(payload: ProjectCreate) -> ProjectResponse:
    try:
        return create_project(payload, file_format=FILE_FORMAT)
    except UnsupportedCrsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="좌표계는 5185, 5186, 5187, 5188 중에서 선택해 주세요.",
        ) from exc
    except ProjectAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="프로젝트가 이미 존재합니다.",
        ) from exc
