from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_jobs() -> dict:
    return {"message": "health router ready"}