"""
Raw facts data model — the structured output of deterministic repository analysis.

These models are produced by the analysis pipeline (Phase 2) and consumed by
the graph builder (Phase 3).  They are intentionally plain data — no NetworkX,
no AI reasoning.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Language / file inventory
# ---------------------------------------------------------------------------

class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    JAVA = "java"
    RUST = "rust"
    RUBY = "ruby"
    CSHARP = "csharp"
    CPP = "cpp"
    C = "c"
    YAML = "yaml"
    JSON = "json"
    DOCKERFILE = "dockerfile"
    SHELL = "shell"
    PROTO = "proto"
    UNKNOWN = "unknown"


class FileInfo(BaseModel):
    """Metadata about a single file in the repository."""
    path: str                          # relative to repo root
    language: Language
    size_bytes: int = 0
    line_count: int = 0


# ---------------------------------------------------------------------------
# Source analysis facts (2a)
# ---------------------------------------------------------------------------

class ImportFact(BaseModel):
    """A single import/require statement."""
    source_file: str
    line: int
    imported_name: str                 # e.g. "os", "fastapi", "./utils"
    is_external: bool = False          # True if from a third-party / stdlib package


class FunctionFact(BaseModel):
    """A function or method definition."""
    file: str
    line: int
    name: str
    class_name: str | None = None      # set if inside a class
    is_async: bool = False
    decorators: list[str] = Field(default_factory=list)


class ClassFact(BaseModel):
    """A class definition."""
    file: str
    line: int
    name: str
    bases: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)


class APIEndpointFact(BaseModel):
    """An HTTP API endpoint detected from route decorators or framework patterns."""
    file: str
    line: int
    method: str                        # GET, POST, PUT, DELETE, PATCH, *
    path: str                          # route path, e.g. "/users/{id}"
    handler: str                       # function/method name
    framework: str = ""                # fastapi, flask, express, gin, …


class DependencyFact(BaseModel):
    """An external package dependency declared in a manifest file."""
    manifest_file: str                 # e.g. "requirements.txt", "package.json"
    name: str
    version_spec: str = ""             # e.g. ">=2.7.0", "^1.2.3"
    is_dev: bool = False


# ---------------------------------------------------------------------------
# Git history facts (2b)
# ---------------------------------------------------------------------------

class CommitFact(BaseModel):
    """A single commit from git log."""
    sha: str
    author: str
    timestamp: str                     # ISO-8601
    message: str
    files_changed: list[str] = Field(default_factory=list)


class CoChangeFact(BaseModel):
    """Two files that frequently change together."""
    file_a: str
    file_b: str
    co_change_count: int
    confidence: float = 0.0            # co_change_count / max(commits_a, commits_b)


class HotspotFact(BaseModel):
    """A file with unusually high churn."""
    file: str
    change_count: int
    unique_authors: int


class FileOwnershipFact(BaseModel):
    """The dominant contributor for a file (from git blame summary)."""
    file: str
    owner: str
    ownership_pct: float               # 0.0–1.0


# ---------------------------------------------------------------------------
# Config / infrastructure facts (2c)
# ---------------------------------------------------------------------------

class ServiceFact(BaseModel):
    """A service declared in docker-compose, kubernetes, or similar."""
    name: str
    source_file: str
    image: str | None = None
    ports: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class BuildCommandFact(BaseModel):
    """A build, test, or run command discovered in manifests."""
    source_file: str
    name: str                          # e.g. "test", "build", "lint"
    command: str


class EnvVarFact(BaseModel):
    """An environment variable reference discovered in config files."""
    source_file: str
    name: str
    default_value: str | None = None


# ---------------------------------------------------------------------------
# Aggregate output
# ---------------------------------------------------------------------------

class RawFacts(BaseModel):
    """
    Full structured output of the deterministic analysis pipeline.
    Produced by the analysis orchestrator; consumed by the graph builder.
    """
    repo_id: str

    # File inventory
    files: list[FileInfo] = Field(default_factory=list)
    language_summary: dict[str, int] = Field(default_factory=dict)  # lang → file count

    # Source facts (2a)
    imports: list[ImportFact] = Field(default_factory=list)
    functions: list[FunctionFact] = Field(default_factory=list)
    classes: list[ClassFact] = Field(default_factory=list)
    api_endpoints: list[APIEndpointFact] = Field(default_factory=list)
    dependencies: list[DependencyFact] = Field(default_factory=list)

    # Git facts (2b)
    commits: list[CommitFact] = Field(default_factory=list)
    co_changes: list[CoChangeFact] = Field(default_factory=list)
    hotspots: list[HotspotFact] = Field(default_factory=list)
    file_ownership: list[FileOwnershipFact] = Field(default_factory=list)

    # Config facts (2c)
    services: list[ServiceFact] = Field(default_factory=list)
    build_commands: list[BuildCommandFact] = Field(default_factory=list)
    env_vars: list[EnvVarFact] = Field(default_factory=list)

    # Analysis metadata
    analysis_errors: list[dict[str, Any]] = Field(default_factory=list)
    analysed_at: str = ""
