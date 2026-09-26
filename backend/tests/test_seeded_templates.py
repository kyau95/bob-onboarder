"""Tests for prebuilt demo templates and their architecture graphs."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.registry import repo_registry
from app.core.graph_store import graph_store
from app.api.analysis import _facts_store
from app.models.repo import RepoStatus
from app.services.repo_service import seed_known_repos
from app.services.seed_data import FASTAPI_REPO_ID, BOUTIQUE_REPO_ID, OTEL_REPO_ID


def make_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def init_seeded_repos():
    repo_registry._store.clear()
    _facts_store.clear()
    graph_store._graphs.clear()
    seed_known_repos()
    yield
    repo_registry._store.clear()
    _facts_store.clear()
    graph_store._graphs.clear()


@pytest.mark.asyncio
async def test_seeded_repos_have_analyzed_status():
    """All 3 default demo templates should be in ANALYZED state on startup."""
    async with make_client() as c:
        resp = await c.get("/repo")
    assert resp.status_code == 200
    repos = resp.json()
    assert len(repos) == 3
    for r in repos:
        assert r["status"] == RepoStatus.ANALYZED.value


@pytest.mark.asyncio
@pytest.mark.parametrize("repo_id", [FASTAPI_REPO_ID, BOUTIQUE_REPO_ID, OTEL_REPO_ID])
async def test_seeded_repos_have_prebuilt_graphs(repo_id: str):
    """GET /repo/{id}/graph should return 200 with populated nodes and edges."""
    async with make_client() as c:
        resp = await c.get(f"/repo/{repo_id}/graph")
    assert resp.status_code == 200
    graph = resp.json()
    assert graph["node_count"] > 0
    assert graph["edge_count"] > 0
    assert len(graph["nodes"]) == graph["node_count"]
    assert len(graph["edges"]) == graph["edge_count"]

    # Verify every edge has evidence
    for edge in graph["edges"]:
        assert "evidence" in edge
        assert isinstance(edge["evidence"], list)


@pytest.mark.asyncio
@pytest.mark.parametrize("repo_id", [FASTAPI_REPO_ID, BOUTIQUE_REPO_ID, OTEL_REPO_ID])
async def test_seeded_repos_react_flow_format(repo_id: str):
    """GET /repo/{id}/graph/react-flow should return 200 with positioned nodes."""
    async with make_client() as c:
        resp = await c.get(f"/repo/{repo_id}/graph/react-flow")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("repo_id", [FASTAPI_REPO_ID, BOUTIQUE_REPO_ID, OTEL_REPO_ID])
async def test_seeded_repos_summary(repo_id: str):
    """GET /repo/{id}/summary should return language breakdown and services."""
    async with make_client() as c:
        resp = await c.get(f"/repo/{repo_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_count"] > 0
    assert data["edge_count"] > 0
    assert len(data["services"]) > 0
    assert len(data["language_breakdown"]) > 0


@pytest.mark.asyncio
async def test_fastapi_paths_and_impact():
    """Verify path tracing and impact analysis on FastAPI template."""
    async with make_client() as c:
        # Trace path from UI to Database
        resp = await c.get(f"/repo/{FASTAPI_REPO_ID}/paths?from=Items&to=PostgreSQL")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["paths"]) > 0

        # Impact analysis on Item class
        resp = await c.get(f"/repo/{FASTAPI_REPO_ID}/impact?node=Item")
        assert resp.status_code == 200
        impact = resp.json()
        assert impact["total_affected"] > 0
        assert len(impact["tests_to_run"]) > 0


@pytest.mark.asyncio
async def test_boutique_paths_and_impact():
    """Verify path tracing and impact analysis on Boutique template."""
    async with make_client() as c:
        # Trace path from frontend to paymentservice
        resp = await c.get(f"/repo/{BOUTIQUE_REPO_ID}/paths?from=frontend&to=paymentservice")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["paths"]) > 0

        # Impact analysis on cartservice
        resp = await c.get(f"/repo/{BOUTIQUE_REPO_ID}/impact?node=cartservice")
        assert resp.status_code == 200
        impact = resp.json()
        assert impact["total_affected"] > 0


@pytest.mark.asyncio
async def test_otel_paths_and_impact():
    """Verify path tracing and impact analysis on OpenTelemetry template."""
    async with make_client() as c:
        # Trace path from frontend to kafka
        resp = await c.get(f"/repo/{OTEL_REPO_ID}/paths?from=frontend&to=kafka")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["paths"]) > 0

        # Impact analysis on checkoutservice
        resp = await c.get(f"/repo/{OTEL_REPO_ID}/impact?node=checkoutservice")
        assert resp.status_code == 200
        impact = resp.json()
        assert impact["total_affected"] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("repo_id", [FASTAPI_REPO_ID, BOUTIQUE_REPO_ID, OTEL_REPO_ID])
async def test_seeded_repos_test_run(repo_id: str):
    """POST /repo/{id}/test should return passed=True for seeded demo templates."""
    async with make_client() as c:
        resp = await c.post(f"/repo/{repo_id}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is True
    assert data["return_code"] == 0
