"""
Phase 4 — Bob Skill query endpoints.

These endpoints are consumed by the Bob Skill (SKILL.md) to answer the three
core intelligence questions:

    GET /repo/{id}/summary  — Understand: high-level architecture overview
    GET /repo/{id}/paths    — Explore:    flow tracing between two nodes
    GET /repo/{id}/impact   — Analyze:    blast radius of changing a node

All three require a built architecture graph
(POST /repo/{id}/analyze → POST /repo/{id}/graph/build first).
"""
from __future__ import annotations

import logging
from collections import deque

from fastapi import APIRouter, HTTPException, Query

from app.core.graph_store import graph_store
from app.models.graph import GraphEdge, GraphNode, NodeType
from app.models.query import (
    AffectedNode,
    ImpactResponse,
    PathHop,
    PathResult,
    PathsResponse,
    RepoSummaryResponse,
)
from app.services import repo_service
from app.api.analysis import _facts_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repo", tags=["query"])

_MAX_PATHS = 10          # cap on simple paths to prevent combinatorial explosion
_MAX_PATH_DEPTH = 8      # max hops per path
_MAX_BFS_DEPTH = 6       # max BFS depth for impact analysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_graph(repo_id: str):
    """
    Return the ArchitectureGraph for repo_id, raising 404 / 409 as needed.
    """
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    arch = graph_store.get_graph(repo_id)
    if arch is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No architecture graph for '{repo_id}'. "
                f"Run POST /repo/{repo_id}/analyze then POST /repo/{repo_id}/graph/build first."
            ),
        )
    return arch


def _nodes_by_label(arch, label: str) -> list[GraphNode]:
    """Case-insensitive substring match on node label or id."""
    lower = label.lower()
    return [
        n for n in arch.nodes
        if lower in n.label.lower() or lower in n.id.lower()
    ]


def _is_test_file(path: str | None) -> bool:
    if not path:
        return False
    p = path.lower()
    return (
        "/test" in p or "\\test" in p
        or p.startswith("test")
        or "_test." in p
        or "test_" in p.split("/")[-1]
        or "/spec" in p
    )


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}/summary
# ---------------------------------------------------------------------------

@router.get(
    "/{repo_id}/summary",
    response_model=RepoSummaryResponse,
    summary="Repository overview (Understand capability)",
)
async def get_summary(repo_id: str) -> RepoSummaryResponse:
    """
    Return a high-level overview of the repository's architecture.

    Consumed by Bob to produce structured onboarding documents covering
    services, APIs, dependencies, build commands, and entry points.
    """
    arch = _require_graph(repo_id)
    facts = _facts_store.get(repo_id)

    # Language breakdown from facts (most accurate) or graph node metadata
    if facts:
        lang_breakdown = dict(facts.language_summary)
        if not lang_breakdown:
            # Recompute from file list
            for fi in facts.files:
                lang_breakdown[fi.language.value] = lang_breakdown.get(fi.language.value, 0) + 1
    else:
        lang_breakdown = {}
        for node in arch.nodes:
            if node.language:
                lang_breakdown[node.language] = lang_breakdown.get(node.language, 0) + 1

    # Services
    services = [n.label for n in arch.nodes if n.type == NodeType.SERVICE]

    # API endpoints
    api_endpoints = [
        n.label for n in arch.nodes if n.type == NodeType.API_ENDPOINT
    ]

    # Dependencies (external packages)
    dependencies = [n.label for n in arch.nodes if n.type == NodeType.DEPENDENCY]

    # Build commands from facts
    build_commands: list[dict[str, str]] = []
    if facts:
        build_commands = [
            {"name": bc.name, "command": bc.command, "source": bc.source_file}
            for bc in facts.build_commands
        ]

    # Hotspots (high-churn files from facts)
    hotspots: list[str] = []
    if facts:
        sorted_hot = sorted(facts.hotspots, key=lambda h: h.change_count, reverse=True)
        hotspots = [h.file for h in sorted_hot[:10]]

    # Entry points: files matching common entry-point patterns
    entry_points: list[str] = []
    for node in arch.nodes:
        if node.type == NodeType.MODULE and node.file:
            fname = node.file.lower().split("/")[-1]
            if fname in ("main.py", "app.py", "index.py", "server.py",
                         "index.ts", "index.js", "main.ts", "main.go",
                         "main.rs", "main.rb", "program.cs"):
                entry_points.append(node.file)
        elif node.type == NodeType.MODULE and node.metadata.get("module_name", "").endswith(".__main__"):
            if node.file:
                entry_points.append(node.file)

    # Repo name from registry metadata, fall back to repo_id
    repo = repo_service.get_repo(repo_id)
    name = (repo.name or repo_id) if repo else repo_id

    return RepoSummaryResponse(
        repo_id=repo_id,
        name=name,
        node_count=arch.node_count,
        edge_count=arch.edge_count,
        language_breakdown=lang_breakdown,
        services=services,
        api_endpoints=api_endpoints,
        dependencies=dependencies[:50],   # cap at 50 for readability
        build_commands=build_commands,
        hotspots=hotspots,
        entry_points=entry_points,
        built_at=arch.built_at,
    )


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}/paths
# ---------------------------------------------------------------------------

@router.get(
    "/{repo_id}/paths",
    response_model=PathsResponse,
    summary="Trace paths between two nodes (Explore capability)",
)
async def get_paths(
    repo_id: str,
    from_: str = Query(..., alias="from", description="Source node label or ID"),
    to: str = Query(..., description="Target node label or ID"),
) -> PathsResponse:
    """
    Return all simple paths (up to ``_MAX_PATHS``) between two architecture nodes.

    ``from`` and ``to`` are matched by **case-insensitive substring** against
    node labels and IDs.  If multiple nodes match, the first match is used.

    Consumed by Bob to produce step-by-step flow narratives.
    """
    arch = _require_graph(repo_id)

    from_nodes = _nodes_by_label(arch, from_)
    to_nodes   = _nodes_by_label(arch, to)

    if not from_nodes:
        raise HTTPException(status_code=404, detail=f"No node matching '{from_}'.")
    if not to_nodes:
        raise HTTPException(status_code=404, detail=f"No node matching '{to}'.")

    from_node = from_nodes[0]
    to_node   = to_nodes[0]

    # Build lookup structures
    node_map: dict[str, GraphNode] = {n.id: n for n in arch.nodes}
    # adjacency: node_id → list[(neighbour_id, GraphEdge)]
    adj: dict[str, list[tuple[str, GraphEdge]]] = {n.id: [] for n in arch.nodes}
    for edge in arch.edges:
        adj[edge.source].append((edge.target, edge))

    # DFS to find simple paths (bounded by _MAX_PATHS and _MAX_PATH_DEPTH)
    results: list[PathResult] = []

    def _dfs(
        current_id: str,
        target_id: str,
        path_nodes: list[str],
        path_edges: list[GraphEdge],
        visited: set[str],
    ) -> None:
        if len(results) >= _MAX_PATHS:
            return
        if current_id == target_id:
            hops: list[PathHop] = []
            for i, nid in enumerate(path_nodes):
                hops.append(PathHop(
                    node=node_map[nid],
                    edge=path_edges[i - 1] if i > 0 else None,
                ))
            results.append(PathResult(hops=hops, length=len(hops) - 1))
            return
        if len(path_nodes) > _MAX_PATH_DEPTH:
            return
        for neighbour_id, edge in adj.get(current_id, []):
            if neighbour_id not in visited:
                visited.add(neighbour_id)
                _dfs(neighbour_id, target_id, path_nodes + [neighbour_id],
                     path_edges + [edge], visited)
                visited.discard(neighbour_id)

    visited: set[str] = {from_node.id}
    _dfs(from_node.id, to_node.id, [from_node.id], [], visited)

    return PathsResponse(
        repo_id=repo_id,
        from_node=from_,
        to_node=to,
        paths=results,
        resolved_from=[n.id for n in from_nodes],
        resolved_to=[n.id for n in to_nodes],
    )


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}/impact
# ---------------------------------------------------------------------------

@router.get(
    "/{repo_id}/impact",
    response_model=ImpactResponse,
    summary="Blast-radius analysis for a node change (Analyze capability)",
)
async def get_impact(
    repo_id: str,
    node: str = Query(..., description="Node label or ID to analyze"),
) -> ImpactResponse:
    """
    BFS reachability analysis for a proposed change to ``node``.

    Returns nodes that directly or transitively depend on the target, grouped
    by distance, along with test files that should be run.

    Consumed by Bob to produce impact analysis reports.
    """
    arch = _require_graph(repo_id)

    # Resolve the target node
    matched = _nodes_by_label(arch, node)
    if not matched:
        raise HTTPException(status_code=404, detail=f"No node matching '{node}'.")
    target = matched[0]

    # Build reverse-adjacency (who depends ON the target?)
    # An edge  A → B means A references / imports B.
    # If B changes, A is affected, so we traverse *reverse* edges.
    rev_adj: dict[str, list[tuple[str, GraphEdge]]] = {n.id: [] for n in arch.nodes}
    # Track edge confidence per (source, target) pair for scoring
    edge_map: dict[tuple[str, str], float] = {}
    for edge in arch.edges:
        rev_adj[edge.target].append((edge.source, edge))
        edge_map[(edge.source, edge.target)] = max(
            edge_map.get((edge.source, edge.target), 0.0),
            edge.confidence,
        )

    node_map: dict[str, GraphNode] = {n.id: n for n in arch.nodes}

    # BFS from target through reverse edges
    queue: deque[tuple[str, int, float]] = deque()  # (node_id, distance, max_conf)
    queue.append((target.id, 0, 1.0))
    visited: dict[str, int] = {target.id: 0}  # node_id → distance

    direct: list[AffectedNode] = []
    transitive: list[AffectedNode] = []
    tests_to_run: set[str] = set()

    while queue:
        current_id, dist, conf = queue.popleft()
        if dist > _MAX_BFS_DEPTH:
            continue

        # Enqueue neighbours regardless of dist; only record affected nodes for dist > 0
        if dist < _MAX_BFS_DEPTH:
            for neighbour_id, edge in rev_adj.get(current_id, []):
                if neighbour_id not in visited:
                    visited[neighbour_id] = dist + 1
                    edge_conf = edge_map.get((neighbour_id, current_id), edge.confidence)
                    queue.append((neighbour_id, dist + 1, min(conf, edge_conf)))

        if dist == 0:
            continue  # skip recording the target itself in affected lists

        n = node_map.get(current_id)
        if n is None:
            continue

        affected = AffectedNode(
            node=n,
            distance=dist,
            max_confidence=round(conf, 4),
            is_test=_is_test_file(n.file),
        )

        if n.file and _is_test_file(n.file):
            tests_to_run.add(n.file)

        if dist == 1:
            direct.append(affected)
        else:
            transitive.append(affected)

    # Also collect test files that import or co-change with affected source files
    affected_files = {
        a.node.file
        for a in (direct + transitive)
        if a.node.file and not _is_test_file(a.node.file)
    }
    for n in arch.nodes:
        if n.file and _is_test_file(n.file) and n.id not in visited:
            # heuristic: test file name contains an affected file's stem
            for af in affected_files:
                stem = af.split("/")[-1].replace(".py", "").replace(".ts", "").replace(".js", "")
                if stem and stem in n.file:
                    tests_to_run.add(n.file)
                    break

    return ImpactResponse(
        repo_id=repo_id,
        target_node_id=target.id,
        target_node=target,
        direct=direct,
        transitive=transitive,
        tests_to_run=sorted(tests_to_run),
        total_affected=len(direct) + len(transitive),
    )
