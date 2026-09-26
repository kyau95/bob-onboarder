"""Tests for Phase 3 — architecture graph builder, serializer, store, and API."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.registry import repo_registry
from app.core.graph_store import graph_store
from app.api.analysis import _facts_store
from app.models.repo import AnalysisPurpose, RepoMeta, RepoStatus
from app.models.facts import (
    RawFacts, FileInfo, ImportFact, FunctionFact, ClassFact,
    APIEndpointFact, DependencyFact, ServiceFact, CoChangeFact,
    Language,
)
from app.models.graph import NodeType, EdgeType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _ready_repo(repo_id: str = "repo-1") -> RepoMeta:
    repo = RepoMeta(
        repo_id=repo_id,
        url="https://github.com/example/x.git",
        branch="main",
        name="X",
        purpose=AnalysisPurpose.DEVELOPMENT,
        description=None,
        analysis_targets=[],
        status=RepoStatus.ANALYZED,
        local_path="/tmp/fake",
    )
    repo_registry.add(repo)
    return repo


def _minimal_facts(repo_id: str = "repo-1") -> RawFacts:
    """Return a small but complete RawFacts object."""
    return RawFacts(
        repo_id=repo_id,
        files=[
            FileInfo(path="app/main.py",    language=Language.PYTHON, line_count=50),
            FileInfo(path="app/service.py", language=Language.PYTHON, line_count=80),
            FileInfo(path="app/utils.py",   language=Language.PYTHON, line_count=20),
        ],
        imports=[
            ImportFact(source_file="app/main.py",    line=1, imported_name="app.service",    is_external=False),
            ImportFact(source_file="app/service.py", line=1, imported_name="fastapi",         is_external=True),
            ImportFact(source_file="app/service.py", line=2, imported_name="app.utils",       is_external=False),
        ],
        functions=[
            FunctionFact(file="app/main.py",    line=10, name="main",        is_async=False),
            FunctionFact(file="app/service.py", line=5,  name="get_items",   is_async=True),
        ],
        classes=[
            ClassFact(file="app/service.py", line=1, name="ItemService", bases=["BaseService"], methods=["get_items"]),
        ],
        api_endpoints=[
            APIEndpointFact(file="app/main.py", line=20, method="GET", path="/items", handler="get_items", framework="fastapi"),
        ],
        dependencies=[
            DependencyFact(manifest_file="requirements.txt", name="fastapi", version_spec=">=0.111"),
        ],
        services=[
            ServiceFact(name="backend", source_file="docker-compose.yml", image="python:3.11",
                        ports=["8000:8000"], depends_on=[]),
        ],
        co_changes=[
            CoChangeFact(file_a="app/main.py", file_b="app/service.py", co_change_count=5, confidence=0.8),
        ],
    )


@pytest.fixture(autouse=True)
def reset_all():
    repo_registry._store.clear()
    _facts_store.clear()
    graph_store._graphs.clear()
    graph_store._snapshots.clear()
    graph_store._repo_snapshots.clear()
    yield
    repo_registry._store.clear()
    _facts_store.clear()
    graph_store._graphs.clear()
    graph_store._snapshots.clear()
    graph_store._repo_snapshots.clear()


# ===========================================================================
# GraphBuilder unit tests
# ===========================================================================

class TestGraphBuilder:
    def _build(self, repo_id="r1"):
        from app.services.graph_builder import build_graph
        facts = _minimal_facts(repo_id)
        return build_graph(facts), facts

    def test_nodes_created(self):
        G, _ = self._build()
        types = {data["type"] for _, data in G.nodes(data=True)}
        assert NodeType.MODULE in types
        assert NodeType.CLASS in types
        assert NodeType.API_ENDPOINT in types
        assert NodeType.DEPENDENCY in types
        assert NodeType.SERVICE in types
        assert NodeType.COMPONENT in types

    def test_module_count(self):
        G, facts = self._build()
        modules = [n for n, d in G.nodes(data=True) if d["type"] == NodeType.MODULE]
        assert len(modules) == len(facts.files)

    def test_import_edges_created(self):
        G, _ = self._build()
        edge_types = {d["type"] for _, _, d in G.edges(data=True)}
        assert EdgeType.IMPORTS in edge_types or EdgeType.DEPENDS_ON in edge_types

    def test_co_change_edge_created(self):
        G, _ = self._build()
        edge_types = {d["type"] for _, _, d in G.edges(data=True)}
        assert EdgeType.CO_CHANGE in edge_types

    def test_api_endpoint_exposes_edge(self):
        G, _ = self._build()
        edge_types = {d["type"] for _, _, d in G.edges(data=True)}
        assert EdgeType.EXPOSES in edge_types

    def test_service_node_has_metadata(self):
        G, _ = self._build()
        svc_nodes = [(n, d) for n, d in G.nodes(data=True) if d["type"] == NodeType.SERVICE]
        assert len(svc_nodes) == 1
        assert svc_nodes[0][1]["label"] == "backend"

    def test_evidence_on_import_edge(self):
        G, _ = self._build()
        for _, _, d in G.edges(data=True):
            if d.get("type") == EdgeType.IMPORTS:
                assert len(d.get("evidence", [])) >= 1
                return
        # DEPENDS_ON is also acceptable
        for _, _, d in G.edges(data=True):
            if d.get("type") == EdgeType.DEPENDS_ON:
                assert len(d.get("evidence", [])) >= 1
                return


# ===========================================================================
# Graph serializer
# ===========================================================================

class TestGraphSerializer:
    def _arch(self, repo_id="r1"):
        from app.services.graph_builder import build_graph
        from app.services.graph_serializer import graph_to_architecture
        facts = _minimal_facts(repo_id)
        G = build_graph(facts)
        return graph_to_architecture(repo_id, G, built_at="2024-01-01T00:00:00+00:00")

    def test_architecture_has_nodes_and_edges(self):
        arch = self._arch()
        assert arch.node_count > 0
        assert arch.edge_count > 0
        assert arch.node_count == len(arch.nodes)
        assert arch.edge_count == len(arch.edges)

    def test_all_nodes_have_valid_types(self):
        arch = self._arch()
        valid_types = set(NodeType)
        for node in arch.nodes:
            assert node.type in valid_types

    def test_react_flow_format(self):
        from app.services.graph_serializer import graph_to_react_flow
        arch = self._arch()
        rf = graph_to_react_flow(arch)
        assert len(rf.nodes) == len(arch.nodes)
        assert len(rf.edges) == len(arch.edges)
        for n in rf.nodes:
            assert "label" in n.data
            assert "nodeType" in n.data
        for e in rf.edges:
            assert e.source
            assert e.target


# ===========================================================================
# Graph store
# ===========================================================================

class TestGraphStore:
    def _store_graph(self, repo_id="r1"):
        from app.services.graph_builder import build_graph
        from app.services.graph_serializer import graph_to_architecture
        facts = _minimal_facts(repo_id)
        G = build_graph(facts)
        arch = graph_to_architecture(repo_id, G)
        graph_store.set_graph(repo_id, arch)
        return arch

    def test_set_and_get(self):
        arch = self._store_graph()
        result = graph_store.get_graph("r1")
        assert result is not None
        assert result.repo_id == "r1"

    def test_snapshot_creates_id(self):
        self._store_graph()
        snap_id = graph_store.create_snapshot("r1")
        assert snap_id is not None
        assert graph_store.get_snapshot(snap_id) is not None

    def test_snapshot_none_without_graph(self):
        snap_id = graph_store.create_snapshot("no-such-repo")
        assert snap_id is None

    def test_diff_detects_added_node(self):
        from app.services.graph_builder import build_graph
        from app.services.graph_serializer import graph_to_architecture
        from app.models.graph import GraphNode

        # Store initial graph and snapshot it
        facts = _minimal_facts("r1")
        G = build_graph(facts)
        arch = graph_to_architecture("r1", G)
        graph_store.set_graph("r1", arch)
        snap_id = graph_store.create_snapshot("r1")

        # Add a node to the current graph
        updated = arch.model_copy(deep=True)
        updated.nodes.append(GraphNode(id="new-node-abc", type=NodeType.SERVICE, label="NewService"))
        updated.node_count = len(updated.nodes)
        graph_store.set_graph("r1", updated)

        diff = graph_store.diff("r1", before_id=snap_id)
        assert diff is not None
        added_ids = {n.id for n in diff.added_nodes}
        assert "new-node-abc" in added_ids

    def test_diff_detects_removed_node(self):
        from app.services.graph_builder import build_graph
        from app.services.graph_serializer import graph_to_architecture

        facts = _minimal_facts("r1")
        G = build_graph(facts)
        arch = graph_to_architecture("r1", G)
        graph_store.set_graph("r1", arch)
        snap_id = graph_store.create_snapshot("r1")

        # Remove first node
        reduced = arch.model_copy(deep=True)
        removed_id = reduced.nodes[0].id
        reduced.nodes = reduced.nodes[1:]
        reduced.node_count = len(reduced.nodes)
        graph_store.set_graph("r1", reduced)

        diff = graph_store.diff("r1", before_id=snap_id)
        assert diff is not None
        removed_ids = {n.id for n in diff.removed_nodes}
        assert removed_id in removed_ids


# ===========================================================================
# Graph API endpoints
# ===========================================================================

@pytest.mark.asyncio
async def test_build_graph_404_unknown_repo():
    async with make_client() as c:
        resp = await c.post("/repo/unknown/graph/build")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_build_graph_409_no_facts():
    _ready_repo()
    async with make_client() as c:
        resp = await c.post("/repo/repo-1/graph/build")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_build_graph_202_with_facts():
    _ready_repo()
    _facts_store["repo-1"] = _minimal_facts("repo-1")
    async with make_client() as c:
        resp = await c.post("/repo/repo-1/graph/build")
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_get_graph_404_before_build():
    _ready_repo()
    async with make_client() as c:
        resp = await c.get("/repo/repo-1/graph")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_graph_returns_architecture():
    from app.services.graph_builder import build_graph
    from app.services.graph_serializer import graph_to_architecture

    _ready_repo()
    facts = _minimal_facts("repo-1")
    G = build_graph(facts)
    arch = graph_to_architecture("repo-1", G, built_at="2024-01-01T00:00:00Z")
    graph_store.set_graph("repo-1", arch)

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo_id"] == "repo-1"
    assert data["node_count"] > 0


@pytest.mark.asyncio
async def test_get_react_flow_graph():
    from app.services.graph_builder import build_graph
    from app.services.graph_serializer import graph_to_architecture

    _ready_repo()
    G = build_graph(_minimal_facts("repo-1"))
    arch = graph_to_architecture("repo-1", G)
    graph_store.set_graph("repo-1", arch)

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/graph/react-flow")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data and "edges" in data
    assert all("position" in n for n in data["nodes"])


@pytest.mark.asyncio
async def test_snapshot_and_diff():
    from app.services.graph_builder import build_graph
    from app.services.graph_serializer import graph_to_architecture
    from app.models.graph import GraphNode

    _ready_repo()
    G = build_graph(_minimal_facts("repo-1"))
    arch = graph_to_architecture("repo-1", G)
    graph_store.set_graph("repo-1", arch)

    # Create snapshot
    async with make_client() as c:
        snap_resp = await c.post("/repo/repo-1/graph/snapshot")
    assert snap_resp.status_code == 200
    snap_id = snap_resp.json()["snapshot_id"]

    # Mutate the live graph
    updated = arch.model_copy(deep=True)
    updated.nodes.append(GraphNode(id="new-xyz", type=NodeType.SERVICE, label="NewSvc"))
    updated.node_count = len(updated.nodes)
    graph_store.set_graph("repo-1", updated)

    # Diff
    async with make_client() as c:
        diff_resp = await c.get(f"/repo/repo-1/graph/diff?before={snap_id}")
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()
    added_ids = {n["id"] for n in diff_data["added_nodes"]}
    assert "new-xyz" in added_ids


@pytest.mark.asyncio
async def test_diff_404_unknown_snapshot():
    _ready_repo()
    async with make_client() as c:
        resp = await c.get("/repo/repo-1/graph/diff?before=nonexistent-snap")
    assert resp.status_code == 404
