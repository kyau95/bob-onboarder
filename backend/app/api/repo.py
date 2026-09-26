"""Repository ingestion and management API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.models.repo import IngestRequest, IngestResponse, RepoMeta, RepoStatus, RepoSummary
from app.services import repo_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repo", tags=["repositories"])


# ---------------------------------------------------------------------------
# POST /repo/ingest
# ---------------------------------------------------------------------------

@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a repository",
)
async def ingest_repo(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    """
    Register and clone a Git repository.

    The clone runs in the background so the endpoint returns immediately with
    ``status=cloning``.  Poll ``GET /repo/{repo_id}`` until ``status=ready``.
    """
    repo = repo_service.register_repo(request)
    background_tasks.add_task(repo_service.clone_repo, repo)

    return IngestResponse(
        repo_id=repo.repo_id,
        status=RepoStatus.CLONING,
        message=(
            f"Cloning {request.url} (branch={request.branch}) in the background. "
            f"Poll GET /repo/{repo.repo_id} for status updates."
        ),
    )


# ---------------------------------------------------------------------------
# GET /repo
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[RepoSummary],
    summary="List all repositories",
)
async def list_all_repos() -> list[RepoSummary]:
    """Return a summary list of all registered repositories."""
    return [
        RepoSummary(
            repo_id=r.repo_id,
            name=r.name,
            url=r.url,
            branch=r.branch,
            purpose=r.purpose,
            status=r.status,
            description=r.description,
            analysis_targets=r.analysis_targets,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in repo_service.list_repos()
    ]


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{repo_id}",
    response_model=RepoMeta,
    summary="Get repository details",
)
async def get_repo_detail(repo_id: str) -> RepoMeta:
    """Return full metadata for a single repository."""
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    return repo


# ---------------------------------------------------------------------------
# DELETE /repo/{repo_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a repository",
)
async def remove_repo(repo_id: str) -> None:
    """Remove a repository from the registry and delete its local clone."""
    removed = repo_service.delete_repo(repo_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
