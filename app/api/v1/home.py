from fastapi import APIRouter, Query

from app.schemas.home import HomeSummaryResponse
from app.services.home_service import get_home_summary

router = APIRouter()


@router.get("/summary", response_model=HomeSummaryResponse)
def home_summary(
    project_limit: int = Query(default=20, ge=1, le=200),
    project_offset: int = Query(default=0, ge=0),
    project_span: int = Query(default=8, ge=0, le=200),
    import_limit: int = Query(default=10, ge=0, le=200),
) -> HomeSummaryResponse:
    return get_home_summary(
        project_limit=project_limit,
        project_offset=project_offset,
        project_span=project_span,
        import_limit=import_limit,
    )
