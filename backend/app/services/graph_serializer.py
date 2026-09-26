"""
Graph serializer — converts a NetworkX DiGraph into wire-format models
(ArchitectureGraph and ReactFlowGraph).
"""
from __future__ import annotations

import math
from typing import Any

import networkx as nx

from app.models.graph import (
    ArchitectureGraph,
    EdgeType,
    Evidence,
    GraphEdge,
    GraphNode,
    NodeType,
    ReactFlowEdge,
    ReactFlowGraph,
    ReactFlowNode,
    ReactFlowPosition,
)


def graph_to_architecture(repo_id: str, G: nx.DiGraph, built_at: str = "") -> ArchitectureGraph:
    """Serialize a NetworkX DiGraph into an ArchitectureGraph Pydantic model."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    for nid, data in G.nodes(data=True):
        nodes.append(GraphNode(
            id=nid,
            type=NodeType(data.get("type", NodeType.UNKNOWN)),
            label=data.get("label", nid),
            file=data.get("file"),
            language=data.get("language"),
            metadata=data.get("metadata", {}),
        ))

    for src, tgt, data in G.edges(data=True):
        raw_ev = data.get("evidence", [])
        evidence = [
            Evidence(**e) if isinstance(e, dict) else e
            for e in raw_ev
        ]
        edges.append(GraphEdge(
            id=data.get("id", f"{src}-{tgt}"),
            source=src,
            target=tgt,
            type=EdgeType(data.get("type", EdgeType.IMPORTS)),
            evidence=evidence,
            confidence=data.get("confidence", 1.0),
        ))

    return ArchitectureGraph(
        repo_id=repo_id,
        nodes=nodes,
        edges=edges,
        built_at=built_at,
    )


def graph_to_react_flow(arch: ArchitectureGraph) -> ReactFlowGraph:
    """Convert an ArchitectureGraph to React Flow's node+edge format."""
    # Assign positions using a spring layout via networkx
    G_pos = nx.DiGraph()
    G_pos.add_nodes_from([n.id for n in arch.nodes])
    G_pos.add_edges_from([(e.source, e.target) for e in arch.edges])

    if G_pos.number_of_nodes() > 0:
        positions = nx.spring_layout(G_pos, seed=42, k=200)
    else:
        positions = {}

    rf_nodes: list[ReactFlowNode] = []
    for node in arch.nodes:
        raw_pos = positions.get(node.id, (0.0, 0.0))
        rf_nodes.append(ReactFlowNode(
            id=node.id,
            type=_rf_node_type(node.type),
            data={
                "label": node.label,
                "nodeType": node.type.value,
                "file": node.file,
                "language": node.language,
                **node.metadata,
            },
            position=ReactFlowPosition(
                x=round(float(raw_pos[0]) * 600, 2),
                y=round(float(raw_pos[1]) * 600, 2),
            ),
        ))

    rf_edges: list[ReactFlowEdge] = []
    for edge in arch.edges:
        rf_edges.append(ReactFlowEdge(
            id=edge.id,
            source=edge.source,
            target=edge.target,
            label=edge.type.value,
            data={
                "edgeType": edge.type.value,
                "confidence": edge.confidence,
                "evidence": [e.model_dump() for e in edge.evidence],
            },
        ))

    return ReactFlowGraph(nodes=rf_nodes, edges=rf_edges)


def _rf_node_type(node_type: NodeType) -> str:
    """Map architecture node types to React Flow node type names."""
    return {
        NodeType.SERVICE:      "service",
        NodeType.COMPONENT:    "component",
        NodeType.MODULE:       "module",
        NodeType.CLASS:        "class",
        NodeType.FUNCTION:     "function",
        NodeType.API_ENDPOINT: "apiEndpoint",
        NodeType.DATABASE:     "database",
        NodeType.QUEUE:        "queue",
        NodeType.CACHE:        "cache",
        NodeType.EXTERNAL:     "external",
        NodeType.DEPENDENCY:   "dependency",
    }.get(node_type, "default")
