"""Tests for Phase 9 — Verify capability: POST /repo/{id}/test."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.registry import repo_registry
from app.api.analysis import _facts_store
from app.models.repo import AnalysisPurpose, RepoMeta, RepoStatus
from app.models.facts import RawFacts, BuildCommandFact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _ready_repo(repo_id: str = "repo-1", status: RepoStatus = RepoStatus.ANALYZED,
                local_path: str = "/tmp/fake-repo") -> RepoMeta:
    repo = RepoMeta(
        repo_id=repo_id,
        url="https://github.com/example/x.git",
        branch="main",
        name="ExampleProject",
        purpose=AnalysisPurpose.DEVELOPMENT,
        description=None,
        analysis_targets=[],
        status=status,
        local_path=local_path,
    )
    repo_registry.add(repo)
    return repo


def _facts_with_test_command(repo_id: str = "repo-1") -> RawFacts:
    return RawFacts(
        repo_id=repo_id,
        build_commands=[
            BuildCommandFact(source_file="Makefile", name="test", command="pytest -q"),
            BuildCommandFact(source_file="Makefile", name="lint", command="ruff check ."),
        ],
    )


@pytest.fixture(autouse=True)
def reset_all():
    repo_registry._store.clear()
    _facts_store.clear()
    yield
    repo_registry._store.clear()
    _facts_store.clear()


# ---------------------------------------------------------------------------
# POST /repo/{id}/test — guard conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_404_unknown_repo():
    async with make_client() as c:
        resp = await c.post("/repo/unknown/test")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_test_409_repo_not_cloned():
    """A repo in PENDING state has not been cloned yet."""
    _ready_repo(status=RepoStatus.PENDING)
    async with make_client() as c:
        resp = await c.post("/repo/repo-1/test")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_test_409_repo_cloning():
    """A repo in CLONING state is not ready."""
    _ready_repo(status=RepoStatus.CLONING)
    async with make_client() as c:
        resp = await c.post("/repo/repo-1/test")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /repo/{id}/test — success path (passing tests)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_passes_when_exit_0():
    """Mock subprocess returning exit 0 → passed=True."""
    _ready_repo()
    _facts_store["repo-1"] = _facts_with_test_command()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "2 passed in 0.5s"
    mock_result.stderr = ""

    with patch("app.api.verify.subprocess.run", return_value=mock_result):
        async with make_client() as c:
            resp = await c.post("/repo/repo-1/test")

    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is True
    assert data["return_code"] == 0
    assert data["repo_id"] == "repo-1"


@pytest.mark.asyncio
async def test_test_uses_command_from_facts():
    """The detected command should come from the BuildCommandFact named 'test'."""
    _ready_repo()
    _facts_store["repo-1"] = _facts_with_test_command()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("app.api.verify.subprocess.run", return_value=mock_result) as mock_run:
        async with make_client() as c:
            await c.post("/repo/repo-1/test")

    call_kwargs = mock_run.call_args
    assert "pytest -q" in call_kwargs[0][0]


# ---------------------------------------------------------------------------
# POST /repo/{id}/test — failure path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_fails_when_exit_nonzero():
    """Mock subprocess returning exit 1 → passed=False."""
    _ready_repo()
    _facts_store["repo-1"] = _facts_with_test_command()

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "FAILED tests/test_foo.py::test_bar"

    with patch("app.api.verify.subprocess.run", return_value=mock_result):
        async with make_client() as c:
            resp = await c.post("/repo/repo-1/test")

    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    assert data["return_code"] == 1
    assert "FAILED" in data["output"]


@pytest.mark.asyncio
async def test_test_output_truncated_to_4000_chars():
    """Output longer than 4 000 chars should be truncated (keeping the tail)."""
    _ready_repo()
    _facts_store["repo-1"] = _facts_with_test_command()

    long_output = "x" * 5_000 + "END"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = long_output
    mock_result.stderr = ""

    with patch("app.api.verify.subprocess.run", return_value=mock_result):
        async with make_client() as c:
            resp = await c.post("/repo/repo-1/test")

    data = resp.json()
    assert len(data["output"]) <= 4_000
    assert data["output"].endswith("END")


# ---------------------------------------------------------------------------
# POST /repo/{id}/test — timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_timeout_returns_failure():
    """subprocess.TimeoutExpired should be caught and returned as passed=False."""
    import subprocess as _sp
    _ready_repo()
    _facts_store["repo-1"] = _facts_with_test_command()

    with patch("app.api.verify.subprocess.run", side_effect=_sp.TimeoutExpired("pytest -q", 300)):
        async with make_client() as c:
            resp = await c.post("/repo/repo-1/test")

    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    assert data["return_code"] == -1
    assert "timed out" in data["output"].lower()


# ---------------------------------------------------------------------------
# Command detection — fallback logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_fallback_to_pytest_when_no_facts():
    """With no facts, the command should fall back (pytest for empty dir)."""
    _ready_repo()
    # No facts stored — fallback detection runs

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("app.api.verify.subprocess.run", return_value=mock_result) as mock_run:
        with patch("app.api.verify.os.path.exists", return_value=False):
            async with make_client() as c:
                await c.post("/repo/repo-1/test")

    call_kwargs = mock_run.call_args
    assert call_kwargs[0][0] == "pytest"


@pytest.mark.asyncio
async def test_test_response_contains_command_field():
    """Response always includes the command that was run."""
    _ready_repo()
    _facts_store["repo-1"] = _facts_with_test_command()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("app.api.verify.subprocess.run", return_value=mock_result):
        async with make_client() as c:
            resp = await c.post("/repo/repo-1/test")

    data = resp.json()
    assert "command" in data
    assert data["command"] == "pytest -q"
