"""In-memory repository registry — thread-safe singleton."""
from __future__ import annotations

import threading
from typing import Iterator

from app.models.repo import RepoMeta


class RepoRegistry:
    """Thread-safe in-memory store for RepoMeta records."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, RepoMeta] = {}

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add(self, repo: RepoMeta) -> None:
        with self._lock:
            self._store[repo.repo_id] = repo

    def update(self, repo: RepoMeta) -> None:
        repo.touch()
        with self._lock:
            self._store[repo.repo_id] = repo

    def remove(self, repo_id: str) -> bool:
        with self._lock:
            if repo_id in self._store:
                del self._store[repo_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, repo_id: str) -> RepoMeta | None:
        with self._lock:
            return self._store.get(repo_id)

    def list(self) -> list[RepoMeta]:
        with self._lock:
            return list(self._store.values())

    def __iter__(self) -> Iterator[RepoMeta]:
        with self._lock:
            return iter(list(self._store.values()))

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# Application-scoped singleton — imported everywhere that needs the registry
repo_registry = RepoRegistry()
