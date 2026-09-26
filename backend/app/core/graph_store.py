"""
In-memory graph store with snapshot support.

Stores the live ArchitectureGraph per repo_id plus named snapshots
(used for graph diff between analyses).
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from app.models.graph import ArchitectureGraph, GraphDiff


class GraphStore:
    """Thread-safe in-memory store for architecture graphs and snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # repo_id → current ArchitectureGraph
        self._graphs: dict[str, ArchitectureGraph] = {}
        # snapshot_id → ArchitectureGraph
        self._snapshots: dict[str, ArchitectureGraph] = {}
        # repo_id → list[snapshot_id] (chronological)
        self._repo_snapshots: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Current graph
    # ------------------------------------------------------------------

    def set_graph(self, repo_id: str, graph: ArchitectureGraph) -> None:
        with self._lock:
            self._graphs[repo_id] = graph

    def get_graph(self, repo_id: str) -> ArchitectureGraph | None:
        with self._lock:
            return self._graphs.get(repo_id)

    def has_graph(self, repo_id: str) -> bool:
        with self._lock:
            return repo_id in self._graphs

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def create_snapshot(self, repo_id: str) -> str | None:
        """
        Snapshot the current graph for repo_id.
        Returns the snapshot_id, or None if no graph exists yet.
        """
        with self._lock:
            graph = self._graphs.get(repo_id)
            if graph is None:
                return None
            snap_id = str(uuid.uuid4())
            self._snapshots[snap_id] = graph.model_copy(deep=True)
            self._repo_snapshots.setdefault(repo_id, []).append(snap_id)
            return snap_id

    def get_snapshot(self, snapshot_id: str) -> ArchitectureGraph | None:
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def list_snapshots(self, repo_id: str) -> list[str]:
        with self._lock:
            return list(self._repo_snapshots.get(repo_id, []))

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff(self, repo_id: str, before_id: str, after_id: str | None = None) -> GraphDiff | None:
        """
        Compare two snapshots (or a snapshot against the current graph).
        Returns a GraphDiff, or None if either snapshot is missing.
        """
        with self._lock:
            before = self._snapshots.get(before_id)
            if before is None:
                return None
            after = (
                self._graphs.get(repo_id)
                if after_id is None
                else self._snapshots.get(after_id)
            )
            if after is None:
                return None

        before_nodes = {n.id: n for n in before.nodes}
        after_nodes  = {n.id: n for n in after.nodes}
        before_edges = {e.id: e for e in before.edges}
        after_edges  = {e.id: e for e in after.edges}

        added_nodes   = [after_nodes[i]  for i in after_nodes  if i not in before_nodes]
        removed_nodes = [before_nodes[i] for i in before_nodes if i not in after_nodes]
        added_edges   = [after_edges[i]  for i in after_edges  if i not in before_edges]
        removed_edges = [before_edges[i] for i in before_edges if i not in after_edges]

        # Modified nodes: same id but different label/type/metadata
        modified_nodes = [
            after_nodes[i]
            for i in after_nodes
            if i in before_nodes and after_nodes[i] != before_nodes[i]
        ]

        return GraphDiff(
            repo_id=repo_id,
            before_snapshot_id=before_id,
            after_snapshot_id=after_id or "current",
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            added_edges=added_edges,
            removed_edges=removed_edges,
            modified_nodes=modified_nodes,
        )


# Application-scoped singleton
graph_store = GraphStore()
