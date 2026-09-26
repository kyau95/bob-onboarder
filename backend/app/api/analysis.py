"""Analysis API endpoints — trigger and retrieve raw facts for a repository."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.models.facts import RawFacts
from app.models.repo import RepoStatus
from app.services import repo_service
from app.services.analysis_orchestrator import run_analysis
from app.core.registry import repo_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repo", tags=["analysis"])

# In-memory facts store: repo_id → RawFacts
_facts_store: dict[str, RawFacts] = {}


# ---------------------------------------------------------------------------
# POST /repo/{repo_id}/analyze
# ---------------------------------------------------------------------------

@router.post(
    "/{repo_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger analysis pipeline",
    response_model=dict,
)
async def trigger_analysis(repo_id: str, background_tasks: BackgroundTasks) -> dict:
    """
    Kick off the deterministic analysis pipeline (source + git + config).
    Returns immediately; poll ``GET /repo/{repo_id}/raw-facts`` for results.
    """
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    if repo.status not in (RepoStatus.READY, RepoStatus.ANALYZED):
        raise HTTPException(
            status_code=409,
            detail=f"Repository must be in 'ready' or 'analyzed' state to analyze "
                   f"(current: {repo.status}).",
        )

    repo.status = RepoStatus.ANALYZING
    repo.touch()
    repo_registry.update(repo)

    background_tasks.add_task(_run_analysis_task, repo_id, Path(repo.local_path))

    return {
        "repo_id": repo_id,
        "status": RepoStatus.ANALYZING,
        "message": f"Analysis started. Poll GET /repo/{repo_id}/raw-facts for results.",
    }


def _run_analysis_task(repo_id: str, repo_path: Path) -> None:
    """Background task: run analysis, store facts, update repo status."""
    try:
        facts = run_analysis(repo_id, repo_path)
        _facts_store[repo_id] = facts

        repo = repo_service.get_repo(repo_id)
        if repo:
            repo.status = RepoStatus.ANALYZED
            repo.touch()
            repo_registry.update(repo)
        logger.info("Analysis complete for %s", repo_id)
    except Exception as exc:
        logger.error("Analysis task failed for %s: %s", repo_id, exc, exc_info=True)
        repo = repo_service.get_repo(repo_id)
        if repo:
            repo.status = RepoStatus.ERROR
            repo.error = str(exc)
            repo.touch()
            repo_registry.update(repo)


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}/raw-facts
# ---------------------------------------------------------------------------

@router.get(
    "/{repo_id}/raw-facts",
    response_model=RawFacts,
    summary="Get raw analysis facts",
)
async def get_raw_facts(repo_id: str) -> RawFacts:
    """Return the raw facts produced by the last analysis run."""
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    facts = _facts_store.get(repo_id)
    if facts is None:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis results for '{repo_id}'. "
                   f"Run POST /repo/{repo_id}/analyze first.",
        )
    return facts
