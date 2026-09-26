"""Graph API endpoints — build, retrieve, snapshot, and diff the architecture graph."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.models.graph import ArchitectureGraph, GraphDiff, ReactFlowGraph
from app.models.repo import RepoStatus
from app.services import repo_service
from app.services.graph_builder import build_graph
from app.services.graph_serializer import graph_to_architecture, graph_to_react_flow
from app.core.graph_store import graph_store
from app.core.registry import repo_registry
from app.api.analysis import _facts_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repo", tags=["graph"])


# ---------------------------------------------------------------------------
# POST /repo/{repo_id}/graph/build
# ---------------------------------------------------------------------------

@router.post(
    "/{repo_id}/graph/build",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Build architecture graph from raw facts",
    response_model=dict,
)
async def build_graph_endpoint(repo_id: str, background_tasks: BackgroundTasks) -> dict:
    """
    Build the architecture graph from the latest raw facts.
    Requires analysis to have been run first (``POST /repo/{id}/analyze``).
    Returns immediately; poll ``GET /repo/{id}/graph`` for results.
    """
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    facts = _facts_store.get(repo_id)
    if facts is None:
        raise HTTPException(
            status_code=409,
            detail=f"No analysis results for '{repo_id}'. Run POST /repo/{repo_id}/analyze first.",
        )

    background_tasks.add_task(_build_graph_task, repo_id)

    return {
        "repo_id": repo_id,
        "message": f"Graph build started. Poll GET /repo/{repo_id}/graph for results.",
    }


def _build_graph_task(repo_id: str) -> None:
    """Background task: build graph, store it, update repo metadata."""
    try:
        from app.services.seed_data import is_seeded_repo, get_seeded_template_by_id
        if is_seeded_repo(repo_id):
            facts, arch = get_seeded_template_by_id(repo_id)
            _facts_store[repo_id] = facts
            graph_store.set_graph(repo_id, arch)
            logger.info("Restored prebuilt graph for %s: %d nodes, %d edges",
                        repo_id, arch.node_count, arch.edge_count)
            return

        facts = _facts_store.get(repo_id)
        if facts is None:
            logger.error("No facts found for %s during graph build", repo_id)
            return

        G = build_graph(facts)
        built_at = datetime.now(timezone.utc).isoformat()
        arch = graph_to_architecture(repo_id, G, built_at=built_at)

        # Auto-snapshot the previous graph before replacing
        if graph_store.has_graph(repo_id):
            snap_id = graph_store.create_snapshot(repo_id)
            logger.info("Auto-snapshotted graph for %s → %s", repo_id, snap_id)
            repo = repo_service.get_repo(repo_id)
            if repo and snap_id:
                repo.snapshot_ids.append(snap_id)
                repo.graph_path = f"in-memory:{repo_id}"
                repo.touch()
                repo_registry.update(repo)

        graph_store.set_graph(repo_id, arch)
        logger.info(
            "Graph built for %s: %d nodes, %d edges",
            repo_id, arch.node_count, arch.edge_count,
        )
    except Exception as exc:
        logger.error("Graph build failed for %s: %s", repo_id, exc, exc_info=True)


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}/graph
# ---------------------------------------------------------------------------

@router.get(
    "/{repo_id}/graph",
    response_model=ArchitectureGraph,
    summary="Get the architecture graph",
)
async def get_graph(repo_id: str) -> ArchitectureGraph:
    """Return the current architecture graph for a repository."""
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    arch = graph_store.get_graph(repo_id)
    if arch is None:
        raise HTTPException(
            status_code=404,
            detail=f"No graph for '{repo_id}'. Run POST /repo/{repo_id}/graph/build first.",
        )
    return arch


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}/graph/react-flow
# ---------------------------------------------------------------------------

@router.get(
    "/{repo_id}/graph/react-flow",
    response_model=ReactFlowGraph,
    summary="Get the graph in React Flow format",
)
async def get_react_flow_graph(repo_id: str) -> ReactFlowGraph:
    """Return the architecture graph formatted for direct use with React Flow."""
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    arch = graph_store.get_graph(repo_id)
    if arch is None:
        raise HTTPException(
            status_code=404,
            detail=f"No graph for '{repo_id}'. Run POST /repo/{repo_id}/graph/build first.",
        )
    return graph_to_react_flow(arch)


# ---------------------------------------------------------------------------
# POST /repo/{repo_id}/graph/snapshot
# ---------------------------------------------------------------------------

@router.post(
    "/{repo_id}/graph/snapshot",
    response_model=dict,
    summary="Snapshot the current graph",
)
async def snapshot_graph(repo_id: str) -> dict:
    """
    Save a named snapshot of the current graph.
    Snapshots are used to compute diffs after code changes.
    """
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    snap_id = graph_store.create_snapshot(repo_id)
    if snap_id is None:
        raise HTTPException(
            status_code=409,
            detail=f"No graph to snapshot for '{repo_id}'.",
        )

    repo = repo_service.get_repo(repo_id)
    if repo:
        repo.snapshot_ids.append(snap_id)
        repo.touch()
        repo_registry.update(repo)

    return {"snapshot_id": snap_id, "repo_id": repo_id}


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}/graph/diff
# ---------------------------------------------------------------------------

@router.get(
    "/{repo_id}/graph/diff",
    response_model=GraphDiff,
    summary="Diff the current graph against a snapshot",
)
async def diff_graph(repo_id: str, before: str) -> GraphDiff:
    """
    Compare the current graph against a previous snapshot.
    Pass ``?before=<snapshot_id>`` to specify the baseline.
    """
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    diff = graph_store.diff(repo_id, before_id=before)
    if diff is None:
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot '{before}' not found or no current graph for '{repo_id}'.",
        )
    return diff
