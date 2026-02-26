import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routers import api_router

app = FastAPI(title="3DTiles Worker API",version="1.0.0")

app.include_router(api_router,prefix="/api/v1")

#assets_dir = Path(os.getenv("UPLOAD_DIR", "assets"))
#if assets_dir.exists():
    #app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
