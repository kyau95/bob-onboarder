"""Repository service — handles registration, cloning, and cleanup."""
from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import git

from app.core.config import settings
from app.core.registry import repo_registry
from app.models.repo import AnalysisPurpose, IngestRequest, RepoMeta, RepoStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_dir(repo_id: str) -> Path:
    """Return the local path where a repo should be cloned."""
    return Path(settings.repos_base_dir) / repo_id


def _derive_name(url: str, provided: str | None) -> str:
    """Derive a display name from a URL if one is not provided."""
    if provided:
        return provided
    clean = url.rstrip("/").removesuffix(".git")
    return clean.split("/")[-1] or url


def _mark_error(repo: RepoMeta, message: str) -> None:
    repo.status = RepoStatus.ERROR
    repo.error = message
    repo.touch()
    repo_registry.update(repo)
    logger.error("Ingestion error for %s: %s", repo.repo_id, message)


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def register_repo(request: IngestRequest) -> RepoMeta:
    """
    Create a RepoMeta record in CLONING state and add it to the registry.
    Does NOT clone — call clone_repo() afterwards (e.g. as a background task).
    """
    repo_id = str(uuid.uuid4())
    local_path = _repo_dir(repo_id)

    repo = RepoMeta(
        repo_id=repo_id,
        url=request.url,
        branch=request.branch,
        name=_derive_name(request.url, request.name),
        purpose=request.purpose,
        description=request.description,
        analysis_targets=request.analysis_targets,
        status=RepoStatus.CLONING,
        local_path=str(local_path),
    )
    repo_registry.add(repo)
    return repo


def clone_repo(repo: RepoMeta) -> None:
    """
    Shallow-clone the repository to disk and update its status to READY.
    Safe to call from a background task.
    """
    local_path = Path(repo.local_path)  # type: ignore[arg-type]
    local_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Cloning %s (branch=%s) → %s", repo.url, repo.branch, local_path)

    try:
        git.Repo.clone_from(
            repo.url,
            str(local_path),
            branch=repo.branch,
            depth=1,
            multi_options=["--single-branch"],
        )
    except git.GitCommandError as exc:
        _mark_error(repo, exc.stderr.strip() if exc.stderr else str(exc))
        return

    repo.status = RepoStatus.READY
    repo.cloned_at = datetime.now(timezone.utc)
    repo.touch()
    repo_registry.update(repo)
    logger.info("Cloned %s → READY", repo.repo_id)


def get_repo(repo_id: str) -> RepoMeta | None:
    return repo_registry.get(repo_id)


def list_repos() -> list[RepoMeta]:
    return repo_registry.list()


def delete_repo(repo_id: str) -> bool:
    """Remove the registry entry and wipe the cloned directory."""
    repo = repo_registry.get(repo_id)
    if repo is None:
        return False

    if repo.local_path:
        local = Path(repo.local_path)
        if local.exists():
            shutil.rmtree(local, ignore_errors=True)
            logger.info("Removed clone dir %s", local)

    return repo_registry.remove(repo_id)


# ---------------------------------------------------------------------------
# Startup seed — three known repositories
# ---------------------------------------------------------------------------

KNOWN_REPOS: list[dict] = [
    {
        "name": "FastAPI Full-Stack Template",
        "url": "https://github.com/fastapi/full-stack-fastapi-template.git",
        "branch": "master",
        "purpose": "development",
        "description": (
            "Full-stack application using FastAPI, React, PostgreSQL, "
            "Docker Compose, Pytest, and GitHub Actions."
        ),
        "analysis_targets": [
            "frontend", "backend", "api_endpoints", "database",
            "authentication", "tests", "CI/CD", "docker",
        ],
    },
    {
        "name": "Google Online Boutique",
        "url": "https://github.com/GoogleCloudPlatform/microservices-demo.git",
        "branch": "main",
        "purpose": "integration",
        "description": (
            "Cloud-native e-commerce application consisting of 11 microservices "
            "written in multiple languages and communicating over gRPC."
        ),
        "analysis_targets": [
            "microservices", "service_dependencies", "grpc", "data_flows",
            "redis", "protobuf", "kubernetes", "terraform",
            "cross_language_dependencies",
        ],
    },
    {
        "name": "OpenTelemetry Astronomy Shop",
        "url": "https://github.com/open-telemetry/opentelemetry-demo.git",
        "branch": "main",
        "purpose": "stress_test",
        "description": (
            "Realistic multi-service distributed system designed to demonstrate "
            "OpenTelemetry and observability across multiple languages and components."
        ),
        "analysis_targets": [
            "microservices", "service_dependencies", "data_flows", "databases",
            "queues", "external_services", "docker", "kubernetes", "observability",
        ],
    },
]

_PURPOSE_MAP: dict[str, AnalysisPurpose] = {
    "development": AnalysisPurpose.DEVELOPMENT,
    "integration": AnalysisPurpose.INTEGRATION,
    "stress_test": AnalysisPurpose.STRESS_TEST,
}


def seed_known_repos() -> list[RepoMeta]:
    """
    Register the three known repos with prebuilt architecture graphs.
    Called once at application startup so the UI shows them immediately
    with prebuilt graphs ready to be viewed and explored in the demo.
    Already-registered URLs are skipped to avoid duplicates on hot-reload.
    """
    from app.core.graph_store import graph_store
    from app.api.analysis import _facts_store
    from app.services.seed_data import URL_TO_REPO_ID, get_seeded_template

    existing_urls = {r.url for r in repo_registry.list()}
    results: list[RepoMeta] = []

    for entry in KNOWN_REPOS:
        if entry["url"] in existing_urls:
            continue

        repo_id = URL_TO_REPO_ID.get(entry["url"], str(uuid.uuid4()))
        repo = RepoMeta(
            repo_id=repo_id,
            url=entry["url"],
            branch=entry["branch"],
            name=entry["name"],
            purpose=_PURPOSE_MAP[entry["purpose"]],
            description=entry.get("description"),
            analysis_targets=entry.get("analysis_targets", []),
            status=RepoStatus.ANALYZED,
            graph_path=f"in-memory:{repo_id}",
            cloned_at=datetime.now(timezone.utc),
        )
        repo_registry.add(repo)

        # Prebuild and store the architecture graph and raw facts
        facts, arch = get_seeded_template(entry["url"], repo_id)
        _facts_store[repo_id] = facts
        graph_store.set_graph(repo_id, arch)

        results.append(repo)
        logger.info("Seeded and prebuilt known repo: %s (%s)", repo.name, repo.repo_id)

    return results
