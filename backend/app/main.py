from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.health import router as health_router
from app.api.repo import router as repo_router
from app.api.analysis import router as analysis_router
from app.services.repo_service import seed_known_repos


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Seed the known repositories on startup."""
    seed_known_repos()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Repository intelligence backend for Bob the Onboarder",
    lifespan=lifespan,
)

# CORS — allow the frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(repo_router)
app.include_router(analysis_router)
