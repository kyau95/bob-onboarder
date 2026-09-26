"""
Phase 4 — Bob Skill query response models.

These wire-format models are returned by the /summary, /paths, and /impact
endpoints that Bob uses to answer Understand, Explore, and Analyze questions.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.graph import GraphEdge, GraphNode


# ---------------------------------------------------------------------------
# Summary (Understand capability)
# ---------------------------------------------------------------------------

class RepoSummaryResponse(BaseModel):
    """
    High-level overview of a repository — returned by GET /repo/{id}/summary.
    Consumed by Bob to produce onboarding documents.
    """
    repo_id: str
    name: str
    node_count: int
    edge_count: int
    # Language breakdown: language → number of files
    language_breakdown: dict[str, int] = Field(default_factory=dict)
    # Services found (from docker-compose / k8s)
    services: list[str] = Field(default_factory=list)
    # Detected API endpoints: "METHOD /path"
    api_endpoints: list[str] = Field(default_factory=list)
    # Top-level dependencies
    dependencies: list[str] = Field(default_factory=list)
    # Build / test commands discovered
    build_commands: list[dict[str, str]] = Field(default_factory=list)
    # High-churn files (hotspots from git analysis)
    hotspots: list[str] = Field(default_factory=list)
    # Entry point files (files with __main__ or index.* pattern)
    entry_points: list[str] = Field(default_factory=list)
    built_at: str = ""


# ---------------------------------------------------------------------------
# Paths (Explore / Flow-Tracing capability)
# ---------------------------------------------------------------------------

class PathHop(BaseModel):
    """A single hop in a traced path through the architecture graph."""
    node: GraphNode
    edge: GraphEdge | None = None  # None for the first (source) node


class PathResult(BaseModel):
    """One path from source to target node."""
    hops: list[PathHop] = Field(default_factory=list)
    length: int = 0


class PathsResponse(BaseModel):
    """
    All simple paths between two nodes — returned by GET /repo/{id}/paths.
    Consumed by Bob to produce step-by-step flow narratives.
    """
    repo_id: str
    from_node: str
    to_node: str
    paths: list[PathResult] = Field(default_factory=list)
    # How nodes were resolved (label search may match multiple nodes)
    resolved_from: list[str] = Field(default_factory=list)  # matched node IDs
    resolved_to: list[str] = Field(default_factory=list)    # matched node IDs


# ---------------------------------------------------------------------------
# Impact (Analyze capability)
# ---------------------------------------------------------------------------

class AffectedNode(BaseModel):
    """A node in the blast radius of a proposed change."""
    node: GraphNode
    distance: int           # hops from the target node (1 = direct)
    # Max confidence of any edge on the shortest path to this node
    max_confidence: float = 1.0
    # Is this a test file?
    is_test: bool = False


class ImpactResponse(BaseModel):
    """
    Blast radius of changing a given node — returned by GET /repo/{id}/impact.
    Consumed by Bob to produce impact analysis reports.
    """
    repo_id: str
    target_node_id: str
    target_node: GraphNode | None = None
    # Nodes that directly reference the target (distance=1)
    direct: list[AffectedNode] = Field(default_factory=list)
    # All transitively reachable nodes (distance>=2)
    transitive: list[AffectedNode] = Field(default_factory=list)
    # Test files that should be run
    tests_to_run: list[str] = Field(default_factory=list)
    total_affected: int = 0
