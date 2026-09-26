"""Phase 9 — Test run response model."""
from __future__ import annotations

from pydantic import BaseModel


class TestRunResponse(BaseModel):
    """
    Result of running the repository's test suite — returned by POST /repo/{id}/test.
    Consumed by Bob to confirm a change did not break anything.
    """
    repo_id: str
    passed: bool                   # True if the test command exited with code 0
    command: str                   # The test command that was executed
    return_code: int               # Raw process exit code
    output: str = ""               # Combined stdout + stderr (last 4 000 chars)
