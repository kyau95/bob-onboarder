"""
2b — Git history analyzer.

Extracts commit log, co-change relationships, hotspots, and file ownership
from a cloned git repository using GitPython.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from pathlib import Path

import git

from app.models.facts import (
    CoChangeFact,
    CommitFact,
    FileOwnershipFact,
    HotspotFact,
)

logger = logging.getLogger(__name__)

# How many commits to inspect (keep fast for large repos)
MAX_COMMITS = 500
# Minimum co-changes to create an edge
MIN_CO_CHANGE = 3


def analyse_git(repo_path: Path) -> dict:
    """
    Run all git history analysis on the repo at repo_path.
    Returns a dict with keys: commits, co_changes, hotspots, file_ownership.
    """
    try:
        repo = git.Repo(str(repo_path))
    except git.InvalidGitRepositoryError:
        logger.warning("Not a git repo: %s", repo_path)
        return {"commits": [], "co_changes": [], "hotspots": [], "file_ownership": []}

    commits = _extract_commits(repo)
    co_changes = _extract_co_changes(commits)
    hotspots = _extract_hotspots(commits)
    file_ownership = _extract_ownership(repo)

    return {
        "commits": commits,
        "co_changes": co_changes,
        "hotspots": hotspots,
        "file_ownership": file_ownership,
    }


# ---------------------------------------------------------------------------
# Commit log
# ---------------------------------------------------------------------------

def _extract_commits(repo: git.Repo) -> list[CommitFact]:
    facts: list[CommitFact] = []
    try:
        for commit in repo.iter_commits(max_count=MAX_COMMITS):
            changed: list[str] = []
            try:
                if commit.parents:
                    diffs = commit.parents[0].diff(commit)
                    changed = [
                        d.b_path or d.a_path
                        for d in diffs
                        if (d.b_path or d.a_path)
                    ]
                else:
                    # Initial commit — list all files in tree
                    changed = [item.path for item in commit.tree.traverse()
                                if item.type == "blob"]
            except Exception:
                pass  # some commits may have malformed diffs

            facts.append(CommitFact(
                sha=commit.hexsha[:12],
                author=str(commit.author),
                timestamp=commit.committed_datetime.isoformat(),
                message=commit.message.strip()[:200],
                files_changed=changed,
            ))
    except Exception as exc:
        logger.warning("Error reading commits: %s", exc)
    return facts


# ---------------------------------------------------------------------------
# Co-change relationships
# ---------------------------------------------------------------------------

def _extract_co_changes(commits: list[CommitFact]) -> list[CoChangeFact]:
    pair_counts: Counter = Counter()
    file_counts: Counter = Counter()

    for commit in commits:
        files = commit.files_changed
        file_counts.update(files)
        # Only count pairs for commits that touch multiple files
        if len(files) < 2:
            continue
        for i, fa in enumerate(files):
            for fb in files[i + 1:]:
                pair_counts[tuple(sorted([fa, fb]))] += 1

    facts: list[CoChangeFact] = []
    for (fa, fb), count in pair_counts.items():
        if count < MIN_CO_CHANGE:
            continue
        denom = max(file_counts[fa], file_counts[fb], 1)
        facts.append(CoChangeFact(
            file_a=fa,
            file_b=fb,
            co_change_count=count,
            confidence=round(count / denom, 3),
        ))

    # Return highest-confidence pairs first
    facts.sort(key=lambda x: x.confidence, reverse=True)
    return facts


# ---------------------------------------------------------------------------
# Hotspots
# ---------------------------------------------------------------------------

def _extract_hotspots(commits: list[CommitFact]) -> list[HotspotFact]:
    file_changes: Counter = Counter()
    file_authors: dict[str, set] = defaultdict(set)

    for commit in commits:
        for f in commit.files_changed:
            file_changes[f] += 1
            file_authors[f].add(commit.author)

    if not file_changes:
        return []

    # Top 20 most changed files
    facts: list[HotspotFact] = []
    for path, count in file_changes.most_common(20):
        facts.append(HotspotFact(
            file=path,
            change_count=count,
            unique_authors=len(file_authors[path]),
        ))
    return facts


# ---------------------------------------------------------------------------
# File ownership
# ---------------------------------------------------------------------------

def _extract_ownership(repo: git.Repo) -> list[FileOwnershipFact]:
    """
    Use git shortlog to determine the dominant author per tracked file.
    Operates on the HEAD tree; blame per-file is too slow for large repos.
    """
    facts: list[FileOwnershipFact] = []
    try:
        # Get all tracked files
        tracked = [item.path for item in repo.head.commit.tree.traverse()
                   if item.type == "blob"]

        # Build author → files contributed map from commit log
        file_author_counts: dict[str, Counter] = defaultdict(Counter)
        for commit in repo.iter_commits(max_count=MAX_COMMITS):
            try:
                if commit.parents:
                    diffs = commit.parents[0].diff(commit)
                    changed = [d.b_path or d.a_path for d in diffs if (d.b_path or d.a_path)]
                else:
                    changed = [item.path for item in commit.tree.traverse()
                                if item.type == "blob"]
            except Exception:
                changed = []
            author = str(commit.author)
            for f in changed:
                file_author_counts[f][author] += 1

        for f in tracked:
            counts = file_author_counts.get(f)
            if not counts:
                continue
            top_author, top_count = counts.most_common(1)[0]
            total = sum(counts.values())
            facts.append(FileOwnershipFact(
                file=f,
                owner=top_author,
                ownership_pct=round(top_count / total, 3),
            ))
    except Exception as exc:
        logger.warning("Error extracting ownership: %s", exc)

    return facts
