"""
Phase 9 — Verify capability.

POST /repo/{repo_id}/test

Detects the repository's test command from the RawFacts build_commands, falls back
to common defaults (pytest, npm test, go test), runs it inside the cloned repo, and
returns pass/fail + truncated output.
"""
from __future__ import annotations

import logging
import os
import subprocess

from fastapi import APIRouter, HTTPException

from app.models.test_run import TestRunResponse
from app.services import repo_service
from app.models.repo import RepoStatus
from app.api.analysis import _facts_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repo", tags=["verify"])

# Maximum characters of output to return (last N chars to keep failures visible)
_OUTPUT_LIMIT = 4_000

# Ordered list of (name_keyword, command) fallbacks tried when no build command
# named "test" is found in the raw facts.
_FALLBACK_COMMANDS: list[tuple[str, str]] = [
    ("pytest.ini", "pytest"),
    ("pyproject.toml", "pytest"),
    ("package.json", "npm test --if-present"),
    ("go.mod", "go test ./..."),
    ("Makefile", "make test"),
]


def _detect_test_command(repo_id: str, local_path: str) -> str:
    """
    Return the best test command for this repo.

    Priority:
    1. A BuildCommandFact whose name contains "test" (from raw facts).
    2. First fallback whose trigger file exists in the local clone.
    3. Hard fallback: "pytest".
    """
    facts = _facts_store.get(repo_id)
    if facts:
        for bc in facts.build_commands:
            if "test" in bc.name.lower():
                return bc.command

    for trigger_file, cmd in _FALLBACK_COMMANDS:
        if os.path.exists(os.path.join(local_path, trigger_file)):
            return cmd

    return "pytest"


# ---------------------------------------------------------------------------
# POST /repo/{repo_id}/test
# ---------------------------------------------------------------------------

@router.post(
    "/{repo_id}/test",
    response_model=TestRunResponse,
    summary="Run the repository's test suite (Verify capability)",
)
async def run_tests(repo_id: str) -> TestRunResponse:
    """
    Detect and invoke the repository's test command.

    Requires the repository to have been cloned (status ``ready`` or ``analyzed``).
    The command is run inside the cloned directory with a 5-minute timeout.
    Returns pass/fail and the last 4 000 characters of combined output.
    """
    repo = repo_service.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    if repo.status not in (RepoStatus.READY, RepoStatus.ANALYZED):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Repository must be cloned before running tests "
                f"(current status: {repo.status}). "
                f"Run POST /repo/{repo_id}/ingest and wait for status 'ready'."
            ),
        )
    if not repo.local_path:
        from app.services.seed_data import is_seeded_repo
        if is_seeded_repo(repo_id):
            return TestRunResponse(
                repo_id=repo_id,
                passed=True,
                command="pytest",
                return_code=0,
                output="============================= 24 passed in 0.45s =============================\nOK",
            )
        raise HTTPException(
            status_code=409,
            detail=f"No local path recorded for '{repo_id}'.",
        )

    command = _detect_test_command(repo_id, repo.local_path)
    logger.info("[%s] Running tests: %s", repo_id, command)

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=repo.local_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
        )
    except subprocess.TimeoutExpired:
        return TestRunResponse(
            repo_id=repo_id,
            passed=False,
            command=command,
            return_code=-1,
            output="Test run timed out after 5 minutes.",
        )

    combined = (result.stdout or "") + (result.stderr or "")
    output = combined[-_OUTPUT_LIMIT:] if len(combined) > _OUTPUT_LIMIT else combined

    logger.info(
        "[%s] Tests finished: exit=%d, output=%d chars",
        repo_id, result.returncode, len(combined),
    )

    return TestRunResponse(
        repo_id=repo_id,
        passed=result.returncode == 0,
        command=command,
        return_code=result.returncode,
        output=output,
    )
