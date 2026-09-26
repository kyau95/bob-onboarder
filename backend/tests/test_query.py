"""Tests for Phase 4 — Bob Skill query endpoints: /summary, /paths, /impact."""
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
    BuildCommandFact, HotspotFact, Language,
)
from app.services.graph_builder import build_graph
from app.services.graph_serializer import graph_to_architecture


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
        name="ExampleProject",
        purpose=AnalysisPurpose.DEVELOPMENT,
        description=None,
        analysis_targets=[],
        status=RepoStatus.ANALYZED,
        local_path="/tmp/fake",
    )
    repo_registry.add(repo)
    return repo


def _rich_facts(repo_id: str = "repo-1") -> RawFacts:
    """RawFacts with enough structure to exercise all three query endpoints."""
    return RawFacts(
        repo_id=repo_id,
        language_summary={"python": 3},
        files=[
            FileInfo(path="app/main.py",    language=Language.PYTHON, line_count=50),
            FileInfo(path="app/service.py", language=Language.PYTHON, line_count=80),
            FileInfo(path="app/utils.py",   language=Language.PYTHON, line_count=20),
            FileInfo(path="tests/test_service.py", language=Language.PYTHON, line_count=30),
        ],
        imports=[
            # Relative imports so the graph builder resolves them to actual module nodes
            ImportFact(source_file="app/main.py",    line=1, imported_name="./service",  is_external=False),
            ImportFact(source_file="app/service.py", line=1, imported_name="fastapi",    is_external=True),
            ImportFact(source_file="app/service.py", line=2, imported_name="./utils",    is_external=False),
            # Stem-based import so test_service → service edge is created
            ImportFact(source_file="tests/test_service.py", line=1, imported_name="service", is_external=False),
        ],
        functions=[
            FunctionFact(file="app/main.py",    line=10, name="main",      is_async=False),
            FunctionFact(file="app/service.py", line=5,  name="get_items", is_async=True),
        ],
        classes=[
            ClassFact(file="app/service.py", line=1, name="ItemService",
                      bases=["BaseService"], methods=["get_items"]),
        ],
        api_endpoints=[
            APIEndpointFact(file="app/main.py", line=20, method="GET",
                            path="/items", handler="get_items", framework="fastapi"),
            APIEndpointFact(file="app/main.py", line=30, method="POST",
                            path="/items", handler="create_item", framework="fastapi"),
        ],
        dependencies=[
            DependencyFact(manifest_file="requirements.txt", name="fastapi",  version_spec=">=0.111"),
            DependencyFact(manifest_file="requirements.txt", name="uvicorn",  version_spec=">=0.29"),
        ],
        services=[
            ServiceFact(name="backend", source_file="docker-compose.yml",
                        image="python:3.11", ports=["8000:8000"], depends_on=[]),
        ],
        co_changes=[
            CoChangeFact(file_a="app/main.py", file_b="app/service.py",
                         co_change_count=5, confidence=0.8),
        ],
        build_commands=[
            BuildCommandFact(source_file="Makefile", name="test", command="pytest"),
            BuildCommandFact(source_file="Makefile", name="lint", command="ruff check ."),
        ],
        hotspots=[
            HotspotFact(file="app/main.py", change_count=12, unique_authors=2),
            HotspotFact(file="app/service.py", change_count=8, unique_authors=1),
        ],
    )


def _store_graph(repo_id: str = "repo-1") -> None:
    """Build facts → graph → store in graph_store."""
    facts = _rich_facts(repo_id)
    _facts_store[repo_id] = facts
    G = build_graph(facts)
    arch = graph_to_architecture(repo_id, G, built_at="2024-01-01T00:00:00Z")
    graph_store.set_graph(repo_id, arch)


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
# GET /repo/{id}/summary
# ===========================================================================

@pytest.mark.asyncio
async def test_summary_404_unknown_repo():
    async with make_client() as c:
        resp = await c.get("/repo/unknown/summary")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary_409_no_graph():
    _ready_repo()
    async with make_client() as c:
        resp = await c.get("/repo/repo-1/summary")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_summary_returns_overview():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["repo_id"] == "repo-1"
    assert data["node_count"] > 0
    assert data["edge_count"] > 0
    assert data["name"] == "ExampleProject"


@pytest.mark.asyncio
async def test_summary_language_breakdown():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/summary")
    data = resp.json()
    assert "python" in data["language_breakdown"]
    assert data["language_breakdown"]["python"] >= 3


@pytest.mark.asyncio
async def test_summary_services_and_endpoints():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/summary")
    data = resp.json()
    assert "backend" in data["services"]
    assert any("/items" in ep for ep in data["api_endpoints"])


@pytest.mark.asyncio
async def test_summary_build_commands():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/summary")
    data = resp.json()
    names = [bc["name"] for bc in data["build_commands"]]
    assert "test" in names
    assert "lint" in names


@pytest.mark.asyncio
async def test_summary_hotspots():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/summary")
    data = resp.json()
    # hotspots are sorted by churn; main.py has highest count
    assert len(data["hotspots"]) >= 1
    assert data["hotspots"][0] == "app/main.py"


@pytest.mark.asyncio
async def test_summary_entry_points():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/summary")
    data = resp.json()
    assert "app/main.py" in data["entry_points"]


# ===========================================================================
# GET /repo/{id}/paths
# ===========================================================================

@pytest.mark.asyncio
async def test_paths_404_unknown_repo():
    async with make_client() as c:
        resp = await c.get("/repo/unknown/paths?from=main&to=utils")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_paths_409_no_graph():
    _ready_repo()
    async with make_client() as c:
        resp = await c.get("/repo/repo-1/paths?from=main&to=utils")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_paths_404_unknown_node():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/paths?from=nonexistent_xyz&to=service")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_paths_returns_structure():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/paths?from=main&to=service")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo_id"] == "repo-1"
    assert data["from_node"] == "main"
    assert data["to_node"] == "service"
    assert "paths" in data
    assert "resolved_from" in data
    assert "resolved_to" in data


@pytest.mark.asyncio
async def test_paths_finds_path_between_connected_modules():
    """main.py imports service.py so a path must exist."""
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/paths?from=main.py&to=service.py")
    assert resp.status_code == 200
    data = resp.json()
    # At least one direct path expected (main → service via IMPORTS)
    assert len(data["paths"]) >= 1
    first_path = data["paths"][0]
    assert first_path["length"] >= 1
    # Each hop has a node
    for hop in first_path["hops"]:
        assert "node" in hop
        assert "label" in hop["node"]


@pytest.mark.asyncio
async def test_paths_resolved_from_populated():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/paths?from=service&to=utils")
    data = resp.json()
    assert len(data["resolved_from"]) >= 1
    assert len(data["resolved_to"]) >= 1


# ===========================================================================
# GET /repo/{id}/impact
# ===========================================================================

@pytest.mark.asyncio
async def test_impact_404_unknown_repo():
    async with make_client() as c:
        resp = await c.get("/repo/unknown/impact?node=utils")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_impact_409_no_graph():
    _ready_repo()
    async with make_client() as c:
        resp = await c.get("/repo/repo-1/impact?node=utils")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_impact_404_unknown_node():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/impact?node=nonexistent_xyz_abc")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_impact_returns_structure():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/impact?node=utils")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo_id"] == "repo-1"
    assert "target_node" in data
    assert "direct" in data
    assert "transitive" in data
    assert "tests_to_run" in data
    assert "total_affected" in data


@pytest.mark.asyncio
async def test_impact_utils_affects_service_and_main():
    """
    utils.py is imported by service.py, which is imported by main.py.
    Changing utils should show service as direct and main as transitive.
    """
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/impact?node=utils.py")
    assert resp.status_code == 200
    data = resp.json()

    all_affected_labels = (
        {a["node"]["label"] for a in data["direct"]}
        | {a["node"]["label"] for a in data["transitive"]}
    )
    # service.py imports utils.py → should appear as directly affected
    assert any("service" in lbl.lower() for lbl in all_affected_labels)
    assert data["total_affected"] == len(data["direct"]) + len(data["transitive"])


@pytest.mark.asyncio
async def test_impact_test_files_detected():
    """test_service.py imports service.py; changing service should list the test."""
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/impact?node=service.py")
    assert resp.status_code == 200
    data = resp.json()
    # test_service.py should appear in tests_to_run or as affected is_test node
    test_files = data["tests_to_run"]
    affected_tests = [
        a for a in (data["direct"] + data["transitive"]) if a.get("is_test")
    ]
    assert len(test_files) > 0 or len(affected_tests) > 0


@pytest.mark.asyncio
async def test_impact_total_affected_consistent():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/impact?node=utils")
    data = resp.json()
    assert data["total_affected"] == len(data["direct"]) + len(data["transitive"])


@pytest.mark.asyncio
async def test_impact_target_node_populated():
    _ready_repo()
    _store_graph()

    async with make_client() as c:
        resp = await c.get("/repo/repo-1/impact?node=utils")
    data = resp.json()
    assert data["target_node"] is not None
    assert "label" in data["target_node"]
    assert "utils" in data["target_node"]["label"].lower()
