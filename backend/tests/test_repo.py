"""Tests for the repository ingestion API (Phase 1)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.registry import repo_registry
from app.models.repo import AnalysisPurpose, RepoMeta, RepoStatus


@pytest.fixture(autouse=True)
def clear_registry():
    """Wipe the registry before each test for isolation."""
    repo_registry._store.clear()
    yield
    repo_registry._store.clear()


def make_client() -> AsyncClient:
    """Create a fresh AsyncClient — httpx clients cannot be re-entered."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# POST /repo/ingest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_returns_202_and_repo_id():
    """A valid ingest request should return 202 with a repo_id."""
    async with make_client() as c:
        resp = await c.post("/repo/ingest", json={
            "url": "https://github.com/example/repo.git",
            "branch": "main",
            "name": "Test Repo",
        })
    assert resp.status_code == 202
    body = resp.json()
    assert "repo_id" in body
    assert body["status"] == RepoStatus.CLONING


@pytest.mark.asyncio
async def test_ingest_registers_repo_in_registry():
    """After ingest the repo should appear in the registry."""
    async with make_client() as c:
        resp = await c.post("/repo/ingest", json={
            "url": "https://github.com/example/repo.git",
            "branch": "main",
        })
    repo_id = resp.json()["repo_id"]
    assert repo_registry.get(repo_id) is not None


@pytest.mark.asyncio
async def test_ingest_derives_name_from_url():
    """Name should be derived from the URL when not provided."""
    async with make_client() as c:
        resp = await c.post("/repo/ingest", json={
            "url": "https://github.com/acme/my-service.git",
            "branch": "main",
        })
    repo_id = resp.json()["repo_id"]
    repo = repo_registry.get(repo_id)
    assert repo is not None
    assert repo.name == "my-service"


@pytest.mark.asyncio
async def test_ingest_empty_url_returns_422():
    """An empty URL should be rejected with 422."""
    async with make_client() as c:
        resp = await c.post("/repo/ingest", json={"url": "", "branch": "main"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /repo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_repos_empty():
    """With an empty registry the list should be []."""
    async with make_client() as c:
        resp = await c.get("/repo")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_repos_returns_seeded_after_startup():
    """seed_known_repos populates 3 known repos; list should return them."""
    from app.services.repo_service import seed_known_repos
    seed_known_repos()
    async with make_client() as c:
        resp = await c.get("/repo")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    names = {r["name"] for r in data}
    assert "FastAPI Full-Stack Template" in names
    assert "Google Online Boutique" in names
    assert "OpenTelemetry Astronomy Shop" in names


# ---------------------------------------------------------------------------
# GET /repo/{repo_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_repo_not_found():
    async with make_client() as c:
        resp = await c.get("/repo/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_repo_returns_full_meta():
    async with make_client() as c:
        ingest = await c.post("/repo/ingest", json={
            "url": "https://github.com/example/app.git",
            "branch": "develop",
            "name": "App",
            "description": "A test app",
            "analysis_targets": ["backend"],
        })
    repo_id = ingest.json()["repo_id"]

    async with make_client() as c:
        resp = await c.get(f"/repo/{repo_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo_id"] == repo_id
    assert data["name"] == "App"
    assert data["branch"] == "develop"
    assert data["description"] == "A test app"
    assert data["analysis_targets"] == ["backend"]


# ---------------------------------------------------------------------------
# DELETE /repo/{repo_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_repo_not_found():
    async with make_client() as c:
        resp = await c.delete("/repo/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_repo_removes_from_registry():
    async with make_client() as c:
        ingest = await c.post("/repo/ingest", json={
            "url": "https://github.com/example/to-delete.git",
            "branch": "main",
        })
    repo_id = ingest.json()["repo_id"]

    async with make_client() as c:
        resp = await c.delete(f"/repo/{repo_id}")
    assert resp.status_code == 204
    assert repo_registry.get(repo_id) is None


@pytest.mark.asyncio
async def test_delete_repo_returns_404_on_second_call():
    async with make_client() as c:
        ingest = await c.post("/repo/ingest", json={
            "url": "https://github.com/example/once.git",
            "branch": "main",
        })
    repo_id = ingest.json()["repo_id"]

    async with make_client() as c:
        await c.delete(f"/repo/{repo_id}")
    async with make_client() as c:
        resp = await c.delete(f"/repo/{repo_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# clone_repo (service unit tests — no actual git)
# ---------------------------------------------------------------------------

def test_clone_repo_marks_ready_on_success():
    """clone_repo should transition status to READY on a successful git clone."""
    from app.services.repo_service import clone_repo

    repo_id = str(uuid.uuid4())
    repo = RepoMeta(
        repo_id=repo_id,
        url="https://github.com/example/x.git",
        branch="main",
        name="x",
        purpose=AnalysisPurpose.DEVELOPMENT,
        description=None,
        analysis_targets=[],
        status=RepoStatus.CLONING,
        local_path=f"/tmp/onboarder_repos/{repo_id}",
    )
    repo_registry.add(repo)

    with patch("app.services.repo_service.git.Repo.clone_from") as mock_clone:
        mock_clone.return_value = MagicMock()
        clone_repo(repo)

    updated = repo_registry.get(repo_id)
    assert updated is not None
    assert updated.status == RepoStatus.READY
    assert updated.cloned_at is not None


def test_clone_repo_marks_error_on_git_failure():
    """clone_repo should transition status to ERROR on a GitCommandError."""
    import git as gitlib

    from app.services.repo_service import clone_repo

    repo_id = str(uuid.uuid4())
    repo = RepoMeta(
        repo_id=repo_id,
        url="https://github.com/example/bad.git",
        branch="main",
        name="bad",
        purpose=AnalysisPurpose.DEVELOPMENT,
        description=None,
        analysis_targets=[],
        status=RepoStatus.CLONING,
        local_path=f"/tmp/onboarder_repos/{repo_id}",
    )
    repo_registry.add(repo)

    with patch("app.services.repo_service.git.Repo.clone_from") as mock_clone:
        mock_clone.side_effect = gitlib.GitCommandError("clone", "repository not found")
        clone_repo(repo)

    updated = repo_registry.get(repo_id)
    assert updated is not None
    assert updated.status == RepoStatus.ERROR
    assert updated.error is not None
