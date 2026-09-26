"""Pydantic models for the repository ingestion layer."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class RepoStatus(str, Enum):
    """Lifecycle states of an ingested repository."""
    PENDING = "pending"       # queued, not yet cloned
    CLONING = "cloning"       # git clone in progress
    READY = "ready"           # cloned and available for analysis
    ANALYZING = "analyzing"   # analysis pipeline running
    ANALYZED = "analyzed"     # architecture model built
    ERROR = "error"           # something went wrong


class AnalysisPurpose(str, Enum):
    DEVELOPMENT = "development"
    INTEGRATION = "integration"
    STRESS_TEST = "stress_test"


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    """Body for POST /repo/ingest."""
    url: str = Field(..., description="Git remote URL (HTTPS or SSH)")
    branch: str = Field("main", description="Branch or ref to check out")
    name: str | None = Field(None, description="Human-readable display name")
    purpose: AnalysisPurpose = Field(AnalysisPurpose.DEVELOPMENT)
    description: str | None = Field(None)
    analysis_targets: list[str] = Field(default_factory=list)

    @field_validator("url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url must not be empty")
        return v


class RepoMeta(BaseModel):
    """Full metadata record stored in the registry."""
    repo_id: str = Field(..., description="UUID assigned at ingestion time")
    url: str
    branch: str
    name: str
    purpose: AnalysisPurpose
    description: str | None
    analysis_targets: list[str]

    # Runtime state
    status: RepoStatus = RepoStatus.PENDING
    local_path: str | None = None      # absolute path on disk once cloned
    error: str | None = None           # last error message if status == ERROR

    # Timestamps (UTC)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cloned_at: datetime | None = None

    # Populated after analysis (Phase 3+)
    graph_path: str | None = None      # path to the serialized graph JSON
    snapshot_ids: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    def touch(self) -> None:
        """Update updated_at to now."""
        self.updated_at = datetime.now(timezone.utc)


class RepoSummary(BaseModel):
    """Lightweight list-view of a repo (no graph/path details)."""
    repo_id: str
    name: str
    url: str
    branch: str
    purpose: AnalysisPurpose
    status: RepoStatus
    description: str | None
    analysis_targets: list[str]
    created_at: datetime
    updated_at: datetime


class IngestResponse(BaseModel):
    repo_id: str
    status: RepoStatus
    message: str
