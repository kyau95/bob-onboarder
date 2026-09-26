from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health_check() -> HealthResponse:
    """Liveness probe — returns 200 when the server is up."""
    from app.core.config import settings

    return HealthResponse(status="ok", version=settings.app_version)
