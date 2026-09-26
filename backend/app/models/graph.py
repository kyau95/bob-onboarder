"""
Architecture graph models.

These represent the living architecture model produced by Phase 3.
The canonical store is a NetworkX DiGraph; these Pydantic models define
the serialised wire format consumed by the frontend (React Flow) and Bob.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    # Top-level architecture
    SERVICE       = "service"        # a distinct deployable service
    COMPONENT     = "component"      # a logical module / package inside a service
    # Code entities
    MODULE        = "module"         # a source file treated as a unit
    CLASS         = "class"
    FUNCTION      = "function"
    API_ENDPOINT  = "api_endpoint"   # an HTTP route
    # Infrastructure
    DATABASE      = "database"
    QUEUE         = "queue"
    CACHE         = "cache"
    EXTERNAL      = "external"       # third-party service / SaaS
    DEPENDENCY    = "dependency"     # an external package dependency
    # Meta
    UNKNOWN       = "unknown"


# ---------------------------------------------------------------------------
# Edge (relationship) types
# ---------------------------------------------------------------------------

class EdgeType(str, Enum):
    IMPORTS        = "IMPORTS"        # file imports another file/package
    CALLS          = "CALLS"          # function calls another function
    HTTP_CALL      = "HTTP_CALL"      # outbound HTTP request
    DB_QUERY       = "DB_QUERY"       # database interaction
    PUBLISHES_TO   = "PUBLISHES_TO"   # publishes a message/event
    SUBSCRIBES_TO  = "SUBSCRIBES_TO"  # subscribes to a message/event
    DEPENDS_ON     = "DEPENDS_ON"     # declared package dependency
    CO_CHANGE      = "CO_CHANGE"      # frequently changed together (git)
    CONTAINS       = "CONTAINS"       # structural containment (service → component)
    EXPOSES        = "EXPOSES"        # service exposes an API endpoint


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """A single piece of evidence backing a relationship."""
    file: str
    line: int | None = None
    snippet: str = ""


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    """A node in the architecture graph (serialised form)."""
    id: str                           # stable unique key used in edges
    type: NodeType
    label: str                        # human-readable display name
    file: str | None = None           # primary source file
    language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

class GraphEdge(BaseModel):
    """A directed edge in the architecture graph (serialised form)."""
    id: str
    source: str                       # GraphNode.id
    target: str                       # GraphNode.id
    type: EdgeType
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = 1.0           # 0.0–1.0


# ---------------------------------------------------------------------------
# Full graph (wire format)
# ---------------------------------------------------------------------------

class ArchitectureGraph(BaseModel):
    """Serialised architecture graph returned by the API."""
    repo_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    built_at: str = ""
    # Counts for quick display
    node_count: int = 0
    edge_count: int = 0

    def model_post_init(self, __context: Any) -> None:
        self.node_count = len(self.nodes)
        self.edge_count = len(self.edges)


# ---------------------------------------------------------------------------
# Graph diff
# ---------------------------------------------------------------------------

class GraphDiff(BaseModel):
    """Diff between two architecture graph snapshots."""
    repo_id: str
    before_snapshot_id: str
    after_snapshot_id: str
    added_nodes: list[GraphNode] = Field(default_factory=list)
    removed_nodes: list[GraphNode] = Field(default_factory=list)
    added_edges: list[GraphEdge] = Field(default_factory=list)
    removed_edges: list[GraphEdge] = Field(default_factory=list)
    modified_nodes: list[GraphNode] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# React Flow wire format
# ---------------------------------------------------------------------------

class ReactFlowPosition(BaseModel):
    x: float = 0.0
    y: float = 0.0


class ReactFlowNode(BaseModel):
    id: str
    type: str = "default"
    data: dict[str, Any]
    position: ReactFlowPosition = Field(default_factory=ReactFlowPosition)


class ReactFlowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class ReactFlowGraph(BaseModel):
    nodes: list[ReactFlowNode]
    edges: list[ReactFlowEdge]
