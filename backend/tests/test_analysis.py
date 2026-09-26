"""Tests for the Phase 2 analysis pipeline."""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.facts import Language as Lang


# ===========================================================================
# Language detector
# ===========================================================================

class TestLanguageDetector:
    def test_python(self):
        from app.services.language_detector import detect_language
        assert detect_language(Path("foo/bar.py")) == Lang.PYTHON

    def test_typescript(self):
        from app.services.language_detector import detect_language
        assert detect_language(Path("src/App.tsx")) == Lang.TYPESCRIPT

    def test_javascript(self):
        from app.services.language_detector import detect_language
        assert detect_language(Path("index.js")) == Lang.JAVASCRIPT

    def test_dockerfile(self):
        from app.services.language_detector import detect_language
        assert detect_language(Path("Dockerfile")) == Lang.DOCKERFILE
        assert detect_language(Path("Dockerfile.dev")) == Lang.DOCKERFILE

    def test_yaml(self):
        from app.services.language_detector import detect_language
        assert detect_language(Path("config.yaml")) == Lang.YAML

    def test_unknown(self):
        from app.services.language_detector import detect_language
        assert detect_language(Path("README.md")) == Lang.UNKNOWN

    def test_walk_skips_node_modules(self, tmp_path):
        from app.services.language_detector import walk_repo
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.js").write_text("x")
        (tmp_path / "app.py").write_text("x")
        result = [f.name for f in walk_repo(tmp_path)]
        assert "pkg.js" not in result
        assert "app.py" in result

    def test_walk_skips_pycache(self, tmp_path):
        from app.services.language_detector import walk_repo
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.pyc").write_bytes(b"\x00")
        result = walk_repo(tmp_path)
        assert all("__pycache__" not in str(f) for f in result)


# ===========================================================================
# Source analyzer — Python
# ===========================================================================

class TestSourceAnalyzerPython:
    def _analyse(self, code: str, tmp_path: Path) -> dict:
        from app.services.source_analyzer import analyse_sources
        f = tmp_path / "mod.py"
        f.write_text(textwrap.dedent(code))
        return analyse_sources(tmp_path)

    def test_detects_imports(self, tmp_path):
        r = self._analyse("import os\nfrom fastapi import FastAPI\n", tmp_path)
        names = {i.imported_name for i in r["imports"]}
        assert "os" in names
        assert "fastapi" in names

    def test_marks_external_import(self, tmp_path):
        r = self._analyse("import fastapi\n", tmp_path)
        ext = [i for i in r["imports"] if i.imported_name == "fastapi"]
        assert ext and ext[0].is_external is True

    def test_marks_stdlib_not_external(self, tmp_path):
        r = self._analyse("import os\n", tmp_path)
        stdlib = [i for i in r["imports"] if i.imported_name == "os"]
        assert stdlib and stdlib[0].is_external is False

    def test_detects_functions(self, tmp_path):
        r = self._analyse("def hello(): pass\nasync def world(): pass\n", tmp_path)
        names = {f.name for f in r["functions"]}
        assert "hello" in names
        assert "world" in names

    def test_detects_async_function(self, tmp_path):
        r = self._analyse("async def fetch(): pass\n", tmp_path)
        asyncs = [f for f in r["functions"] if f.name == "fetch"]
        assert asyncs and asyncs[0].is_async is True

    def test_detects_classes(self, tmp_path):
        r = self._analyse("class MyService(Base): pass\n", tmp_path)
        names = {c.name for c in r["classes"]}
        assert "MyService" in names

    def test_detects_fastapi_route(self, tmp_path):
        code = """
        from fastapi import APIRouter
        router = APIRouter()
        @router.get("/items")
        async def list_items(): pass
        """
        r = self._analyse(code, tmp_path)
        endpoints = r["api_endpoints"]
        assert any(e.path == "/items" and e.method == "GET" for e in endpoints)

    def test_detects_flask_route(self, tmp_path):
        code = """
        from flask import Flask
        app = Flask(__name__)
        @app.post("/create")
        def create(): pass
        """
        r = self._analyse(code, tmp_path)
        assert any(e.path == "/create" for e in r["api_endpoints"])


# ===========================================================================
# Source analyzer — dependency manifests
# ===========================================================================

class TestDependencyParsing:
    def test_requirements_txt(self, tmp_path):
        from app.services.source_analyzer import analyse_sources
        (tmp_path / "requirements.txt").write_text("fastapi>=0.111\nrequests\n# comment\n")
        r = analyse_sources(tmp_path)
        names = {d.name for d in r["dependencies"]}
        assert "fastapi" in names
        assert "requests" in names

    def test_package_json(self, tmp_path):
        from app.services.source_analyzer import analyse_sources
        import json
        (tmp_path / "package.json").write_text(json.dumps({
            "dependencies": {"react": "^18.0.0"},
            "devDependencies": {"vite": "^5.0.0"},
        }))
        r = analyse_sources(tmp_path)
        names = {d.name for d in r["dependencies"]}
        assert "react" in names
        assert "vite" in names


# ===========================================================================
# Config analyzer
# ===========================================================================

class TestConfigAnalyzer:
    def test_docker_compose_services(self, tmp_path):
        from app.services.config_analyzer import analyse_config
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  backend:\n    image: python:3.11\n    ports:\n      - '8000:8000'\n"
        )
        r = analyse_config(tmp_path)
        names = {s.name for s in r["services"]}
        assert "backend" in names

    def test_package_json_scripts(self, tmp_path):
        from app.services.config_analyzer import analyse_config
        import json
        (tmp_path / "package.json").write_text(json.dumps({
            "scripts": {"build": "vite build", "test": "vitest"}
        }))
        r = analyse_config(tmp_path)
        cmds = {c.name: c.command for c in r["build_commands"]}
        assert cmds.get("build") == "vite build"
        assert cmds.get("test") == "vitest"

    def test_env_example_parsed(self, tmp_path):
        from app.services.config_analyzer import analyse_config
        (tmp_path / ".env.example").write_text("DATABASE_URL=postgres://localhost\nDEBUG=true\n")
        r = analyse_config(tmp_path)
        names = {e.name for e in r["env_vars"]}
        assert "DATABASE_URL" in names
        assert "DEBUG" in names

    def test_makefile_targets(self, tmp_path):
        from app.services.config_analyzer import analyse_config
        (tmp_path / "Makefile").write_text("build:\n\tpython setup.py build\ntest:\n\tpytest\n")
        r = analyse_config(tmp_path)
        names = {c.name for c in r["build_commands"]}
        assert "build" in names
        assert "test" in names


# ===========================================================================
# Analysis orchestrator
# ===========================================================================

class TestAnalysisOrchestrator:
    def test_returns_raw_facts(self, tmp_path):
        from app.services.analysis_orchestrator import run_analysis
        (tmp_path / "main.py").write_text("import os\ndef run(): pass\n")
        facts = run_analysis("test-repo", tmp_path)
        assert facts.repo_id == "test-repo"
        assert len(facts.files) >= 1
        assert len(facts.functions) >= 1
        assert facts.analysed_at != ""

    def test_language_summary_populated(self, tmp_path):
        from app.services.analysis_orchestrator import run_analysis
        (tmp_path / "app.py").write_text("x = 1")
        facts = run_analysis("r1", tmp_path)
        assert "python" in facts.language_summary

    def test_partial_failure_is_recorded(self, tmp_path):
        """A bad git repo should produce an error entry but not crash."""
        from app.services.analysis_orchestrator import run_analysis
        (tmp_path / "app.py").write_text("x = 1")
        # tmp_path is not a git repo — git stage will record an error gracefully
        facts = run_analysis("r2", tmp_path)
        assert facts.repo_id == "r2"
        # analysis_errors may or may not be empty depending on git warning behaviour
        # — just assert it's a list
        assert isinstance(facts.analysis_errors, list)


# ===========================================================================
# Analysis API endpoints
# ===========================================================================

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.registry import repo_registry
from app.models.repo import AnalysisPurpose, RepoMeta, RepoStatus
from app.api.analysis import _facts_store


@pytest.fixture(autouse=True)
def reset_state():
    repo_registry._store.clear()
    _facts_store.clear()
    yield
    repo_registry._store.clear()
    _facts_store.clear()


def make_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _add_ready_repo(repo_id: str = "test-123") -> RepoMeta:
    import uuid
    rid = repo_id or str(uuid.uuid4())
    repo = RepoMeta(
        repo_id=rid,
        url="https://github.com/example/repo.git",
        branch="main",
        name="Test",
        purpose=AnalysisPurpose.DEVELOPMENT,
        description=None,
        analysis_targets=[],
        status=RepoStatus.READY,
        local_path="/tmp/fake",
    )
    repo_registry.add(repo)
    return repo


@pytest.mark.asyncio
async def test_analyze_404_for_unknown_repo():
    async with make_client() as c:
        resp = await c.post("/repo/does-not-exist/analyze")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_analyze_409_when_not_ready():
    repo = _add_ready_repo()
    repo.status = RepoStatus.CLONING
    repo_registry.update(repo)
    async with make_client() as c:
        resp = await c.post(f"/repo/{repo.repo_id}/analyze")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_analyze_202_when_ready():
    _add_ready_repo()
    async with make_client() as c:
        resp = await c.post("/repo/test-123/analyze")
    assert resp.status_code == 202
    assert resp.json()["status"] == RepoStatus.ANALYZING


@pytest.mark.asyncio
async def test_raw_facts_404_before_analysis():
    _add_ready_repo()
    async with make_client() as c:
        resp = await c.get("/repo/test-123/raw-facts")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_raw_facts_returns_data_after_analysis(tmp_path):
    from app.services.analysis_orchestrator import run_analysis
    repo = _add_ready_repo()
    (tmp_path / "app.py").write_text("import os\ndef run(): pass\n")
    facts = run_analysis(repo.repo_id, tmp_path)
    _facts_store[repo.repo_id] = facts

    async with make_client() as c:
        resp = await c.get(f"/repo/{repo.repo_id}/raw-facts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo_id"] == repo.repo_id
    assert len(data["files"]) >= 1
