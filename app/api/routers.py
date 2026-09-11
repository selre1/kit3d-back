
from fastapi import APIRouter
from app.api.v1.home import router as home_router
from app.api.v1.import_job import router as impot_router
from app.api.v1.import_job_fbx import router as import_fbx_router
from app.api.v1.health import router as health_router
from app.api.v1.project import router as project_router
from app.api.v1.project_fbx import router as project_fbx_router
from app.api.v1.tile_job import router as tile_router
from app.api.v1.dem import router as dem_router

api_router = APIRouter()

# FBX 전용 라우터를 먼저 등록해 /import/fbx/... 가 /import/{project_id}/... 로 잡히지 않게 한다.
api_router.include_router(import_fbx_router, prefix="/import/fbx")
api_router.include_router(impot_router, prefix="/import")
api_router.include_router(health_router, prefix="/health")
api_router.include_router(home_router, prefix="/home")
api_router.include_router(project_fbx_router, prefix="/project/fbx")
api_router.include_router(project_router, prefix="/project")
api_router.include_router(tile_router, prefix="/tile")
api_router.include_router(dem_router, prefix="/dem")
