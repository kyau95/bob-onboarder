"""
Phase 3 — Architecture Graph Builder.

Converts a RawFacts instance (deterministic analysis output) into a
NetworkX DiGraph where nodes are architecture entities and edges are
evidence-backed relationships.

Node IDs are stable string keys derived from the entity's type and name
so the graph can be compared across re-analyses.
"""
from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from pathlib import PurePosixPath

import networkx as nx

from app.models.facts import RawFacts
from app.models.graph import EdgeType, Evidence, GraphEdge, GraphNode, NodeType

logger = logging.getLogger(__name__)

# Confidence thresholds
_CO_CHANGE_MIN_CONFIDENCE = 0.3


def _node_id(*parts: str) -> str:
    """Produce a short, stable node ID from its type + label."""
    raw = ":".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _file_to_module(path: str) -> str:
    """Convert a file path to a dotted module name (best-effort)."""
    p = PurePosixPath(path)
    parts = list(p.with_suffix("").parts)
    # Drop leading src/, app/, lib/ conventions
    if parts and parts[0] in ("src", "app", "lib", "pkg"):
        parts = parts[1:]
    return ".".join(parts) if parts else path


class GraphBuilder:
    """
    Builds a NetworkX DiGraph from a RawFacts instance.

    The graph is populated in five passes:
      1. Service nodes  (from docker-compose / k8s config facts)
      2. Module nodes   (one per source file)
      3. Class/function nodes
      4. API endpoint nodes
      5. Dependency nodes + edges
    Then edges:
      A. Import edges between modules
      B. Co-change edges (git history)
      C. Service → module containment edges
      D. Module → API endpoint edges
    """

    def __init__(self, facts: RawFacts) -> None:
        self.facts = facts
        self.G: nx.DiGraph = nx.DiGraph()
        # Maps for quick lookup: label → node_id
        self._file_to_nid: dict[str, str] = {}   # source file path → module node id
        self._class_to_nid: dict[str, str] = {}  # "file::ClassName" → node id
        self._svc_to_nid: dict[str, str] = {}    # service name → node id
        self._dep_to_nid: dict[str, str] = {}    # dep name → node id

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def build(self) -> nx.DiGraph:
        self._add_service_nodes()
        self._add_module_nodes()
        self._add_class_nodes()
        self._add_api_endpoint_nodes()
        self._add_dependency_nodes()
        self._add_import_edges()
        self._add_co_change_edges()
        self._add_containment_edges()
        self._add_endpoint_edges()
        logger.info(
            "Graph built: %d nodes, %d edges",
            self.G.number_of_nodes(),
            self.G.number_of_edges(),
        )
        return self.G

    # ------------------------------------------------------------------
    # Node passes
    # ------------------------------------------------------------------

    def _add_node(self, node: GraphNode) -> None:
        self.G.add_node(
            node.id,
            **node.model_dump(),
        )

    def _add_service_nodes(self) -> None:
        for svc in self.facts.services:
            nid = _node_id("service", svc.name)
            self._svc_to_nid[svc.name] = nid
            self._add_node(GraphNode(
                id=nid,
                type=NodeType.SERVICE,
                label=svc.name,
                file=svc.source_file,
                metadata={
                    "image": svc.image,
                    "ports": svc.ports,
                    "depends_on": svc.depends_on,
                },
            ))

    def _add_module_nodes(self) -> None:
        # Group files by their top-level directory as a lightweight "component"
        dir_nids: dict[str, str] = {}

        for fi in self.facts.files:
            path = fi.path
            nid = _node_id("module", path)
            self._file_to_nid[path] = nid

            # Determine parent component (top-level dir)
            parts = PurePosixPath(path).parts
            top_dir = parts[0] if len(parts) > 1 else ""
            if top_dir and top_dir not in dir_nids:
                comp_id = _node_id("component", top_dir)
                dir_nids[top_dir] = comp_id
                self._add_node(GraphNode(
                    id=comp_id,
                    type=NodeType.COMPONENT,
                    label=top_dir,
                    metadata={"directory": top_dir},
                ))

            self._add_node(GraphNode(
                id=nid,
                type=NodeType.MODULE,
                label=PurePosixPath(path).name,
                file=path,
                language=fi.language.value,
                metadata={
                    "module_name": _file_to_module(path),
                    "line_count": fi.line_count,
                    "size_bytes": fi.size_bytes,
                    "component": top_dir,
                },
            ))

            # Component → Module containment
            if top_dir and top_dir in dir_nids:
                self._add_edge(GraphEdge(
                    id=_node_id("contains", dir_nids[top_dir], nid),
                    source=dir_nids[top_dir],
                    target=nid,
                    type=EdgeType.CONTAINS,
                    confidence=1.0,
                ))

    def _add_class_nodes(self) -> None:
        for cls in self.facts.classes:
            nid = _node_id("class", cls.file, cls.name)
            key = f"{cls.file}::{cls.name}"
            self._class_to_nid[key] = nid
            self._add_node(GraphNode(
                id=nid,
                type=NodeType.CLASS,
                label=cls.name,
                file=cls.file,
                metadata={"bases": cls.bases, "methods": cls.methods, "line": cls.line},
            ))

    def _add_api_endpoint_nodes(self) -> None:
        for ep in self.facts.api_endpoints:
            nid = _node_id("api", ep.file, ep.method, ep.path)
            label = f"{ep.method} {ep.path}" if ep.path else f"{ep.method} {ep.handler}"
            self._add_node(GraphNode(
                id=nid,
                type=NodeType.API_ENDPOINT,
                label=label,
                file=ep.file,
                metadata={
                    "method": ep.method,
                    "path": ep.path,
                    "handler": ep.handler,
                    "framework": ep.framework,
                    "line": ep.line,
                },
            ))

    def _add_dependency_nodes(self) -> None:
        seen: set[str] = set()
        for dep in self.facts.dependencies:
            if dep.name in seen:
                continue
            seen.add(dep.name)
            nid = _node_id("dep", dep.name)
            self._dep_to_nid[dep.name] = nid
            self._add_node(GraphNode(
                id=nid,
                type=NodeType.DEPENDENCY,
                label=dep.name,
                metadata={"version_spec": dep.version_spec, "is_dev": dep.is_dev},
            ))

    # ------------------------------------------------------------------
    # Edge passes
    # ------------------------------------------------------------------

    def _add_edge(self, edge: GraphEdge) -> None:
        # Only add if both endpoints exist
        if not self.G.has_node(edge.source) or not self.G.has_node(edge.target):
            return
        # Merge evidence if edge already exists
        if self.G.has_edge(edge.source, edge.target):
            existing = self.G[edge.source][edge.target]
            existing_ev = existing.get("evidence", [])
            new_ev = [e.model_dump() for e in edge.evidence]
            existing["evidence"] = existing_ev + new_ev
            # Keep highest confidence
            if edge.confidence > existing.get("confidence", 0):
                existing["confidence"] = edge.confidence
        else:
            self.G.add_edge(
                edge.source,
                edge.target,
                **edge.model_dump(),
            )

    def _add_import_edges(self) -> None:
        """
        Add IMPORTS edges between module nodes based on import facts.
        We match the imported name to known files/modules using heuristics.
        """
        # Build a module-name → file-path index for internal imports
        mod_index: dict[str, str] = {}
        for fi in self.facts.files:
            mod = _file_to_module(fi.path)
            mod_index[mod] = fi.path
            # Also index by stem (last component)
            mod_index[PurePosixPath(fi.path).stem] = fi.path

        for imp in self.facts.imports:
            src_nid = self._file_to_nid.get(imp.source_file)
            if src_nid is None:
                continue

            # Resolve target: relative imports start with "."
            target_file = self._resolve_import(imp.imported_name, imp.source_file, mod_index)
            if target_file:
                tgt_nid = self._file_to_nid.get(target_file)
                if tgt_nid and tgt_nid != src_nid:
                    self._add_edge(GraphEdge(
                        id=_node_id("imports", src_nid, tgt_nid),
                        source=src_nid,
                        target=tgt_nid,
                        type=EdgeType.IMPORTS,
                        evidence=[Evidence(file=imp.source_file, line=imp.line)],
                        confidence=0.9,
                    ))
            elif imp.is_external:
                # Import from external package
                dep_nid = self._dep_to_nid.get(imp.imported_name)
                if not dep_nid:
                    # Create a lightweight external dep node on-the-fly
                    dep_nid = _node_id("dep", imp.imported_name)
                    self._dep_to_nid[imp.imported_name] = dep_nid
                    self._add_node(GraphNode(
                        id=dep_nid,
                        type=NodeType.DEPENDENCY,
                        label=imp.imported_name,
                        metadata={"is_dev": False},
                    ))
                self._add_edge(GraphEdge(
                    id=_node_id("imports-ext", src_nid, dep_nid),
                    source=src_nid,
                    target=dep_nid,
                    type=EdgeType.DEPENDS_ON,
                    evidence=[Evidence(file=imp.source_file, line=imp.line)],
                    confidence=0.95,
                ))

    def _resolve_import(self, name: str, source_file: str, mod_index: dict[str, str]) -> str | None:
        """Try to resolve an import name to a file path. Returns None if not found."""
        # Relative import: "./utils" → resolve against source_file's directory
        if name.startswith("."):
            parent = str(PurePosixPath(source_file).parent)
            rel = name.lstrip("./").replace(".", "/")
            candidates = [
                f"{parent}/{rel}.py",
                f"{parent}/{rel}/index.ts",
                f"{parent}/{rel}.ts",
                f"{parent}/{rel}.js",
                f"{parent}/{rel}/__init__.py",
            ]
            for c in candidates:
                norm = str(PurePosixPath(c))
                if norm in self._file_to_nid:
                    return norm
            return None

        # Dotted module name: "app.services.repo_service"
        parts = name.split(".")
        for length in range(len(parts), 0, -1):
            candidate = ".".join(parts[:length])
            if candidate in mod_index:
                return mod_index[candidate]
        return None

    def _add_co_change_edges(self) -> None:
        for cc in self.facts.co_changes:
            if cc.confidence < _CO_CHANGE_MIN_CONFIDENCE:
                continue
            nid_a = self._file_to_nid.get(cc.file_a)
            nid_b = self._file_to_nid.get(cc.file_b)
            if nid_a and nid_b:
                self._add_edge(GraphEdge(
                    id=_node_id("cochange", nid_a, nid_b),
                    source=nid_a,
                    target=nid_b,
                    type=EdgeType.CO_CHANGE,
                    confidence=cc.confidence,
                    evidence=[Evidence(
                        file=cc.file_a,
                        snippet=f"co-changed {cc.co_change_count} times",
                    )],
                ))

    def _add_containment_edges(self) -> None:
        """Service → Component containment from docker-compose depends_on."""
        for svc in self.facts.services:
            svc_nid = self._svc_to_nid.get(svc.name)
            if svc_nid is None:
                continue
            for dep_name in svc.depends_on:
                dep_svc_nid = self._svc_to_nid.get(dep_name)
                if dep_svc_nid:
                    self._add_edge(GraphEdge(
                        id=_node_id("svc-dep", svc_nid, dep_svc_nid),
                        source=svc_nid,
                        target=dep_svc_nid,
                        type=EdgeType.DEPENDS_ON,
                        evidence=[Evidence(file=svc.source_file)],
                        confidence=1.0,
                    ))

    def _add_endpoint_edges(self) -> None:
        """Module → API endpoint EXPOSES edges."""
        for ep in self.facts.api_endpoints:
            mod_nid = self._file_to_nid.get(ep.file)
            ep_nid = _node_id("api", ep.file, ep.method, ep.path)
            if mod_nid and self.G.has_node(ep_nid):
                self._add_edge(GraphEdge(
                    id=_node_id("exposes", mod_nid, ep_nid),
                    source=mod_nid,
                    target=ep_nid,
                    type=EdgeType.EXPOSES,
                    evidence=[Evidence(file=ep.file, line=ep.line)],
                    confidence=1.0,
                ))


def build_graph(facts: RawFacts) -> nx.DiGraph:
    """Convenience function — build and return the graph."""
    return GraphBuilder(facts).build()
