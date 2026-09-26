"""
Analysis orchestrator — coordinates 2a/2b/2c analyzers and produces RawFacts.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.models.facts import RawFacts
from app.services.source_analyzer import analyse_sources
from app.services.git_analyzer import analyse_git
from app.services.config_analyzer import analyse_config

logger = logging.getLogger(__name__)


def run_analysis(repo_id: str, repo_path: Path) -> RawFacts:
    """
    Run the full deterministic analysis pipeline against a cloned repository.
    Returns a populated RawFacts instance.
    """
    facts = RawFacts(repo_id=repo_id)
    errors: list[dict] = []

    # 2a — Source analysis
    logger.info("[%s] Running source analysis...", repo_id)
    try:
        src = analyse_sources(repo_path)
        facts.files       = src["files"]
        facts.imports     = src["imports"]
        facts.functions   = src["functions"]
        facts.classes     = src["classes"]
        facts.api_endpoints = src["api_endpoints"]
        facts.dependencies  = src["dependencies"]
        facts.language_summary = dict(
            Counter(f.language.value for f in facts.files)
        )
        logger.info("[%s] Source: %d files, %d imports, %d functions, %d classes, %d endpoints",
                    repo_id, len(facts.files), len(facts.imports),
                    len(facts.functions), len(facts.classes), len(facts.api_endpoints))
    except Exception as exc:
        logger.error("[%s] Source analysis failed: %s", repo_id, exc, exc_info=True)
        errors.append({"stage": "source", "error": str(exc)})

    # 2b — Git history analysis
    logger.info("[%s] Running git history analysis...", repo_id)
    try:
        git_facts = analyse_git(repo_path)
        facts.commits       = git_facts["commits"]
        facts.co_changes    = git_facts["co_changes"]
        facts.hotspots      = git_facts["hotspots"]
        facts.file_ownership = git_facts["file_ownership"]
        logger.info("[%s] Git: %d commits, %d co-changes, %d hotspots",
                    repo_id, len(facts.commits), len(facts.co_changes), len(facts.hotspots))
    except Exception as exc:
        logger.error("[%s] Git analysis failed: %s", repo_id, exc, exc_info=True)
        errors.append({"stage": "git", "error": str(exc)})

    # 2c — Config analysis
    logger.info("[%s] Running config analysis...", repo_id)
    try:
        cfg = analyse_config(repo_path)
        facts.services      = cfg["services"]
        facts.build_commands = cfg["build_commands"]
        facts.env_vars      = cfg["env_vars"]
        logger.info("[%s] Config: %d services, %d build commands, %d env vars",
                    repo_id, len(facts.services), len(facts.build_commands), len(facts.env_vars))
    except Exception as exc:
        logger.error("[%s] Config analysis failed: %s", repo_id, exc, exc_info=True)
        errors.append({"stage": "config", "error": str(exc)})

    facts.analysis_errors = errors
    facts.analysed_at = datetime.now(timezone.utc).isoformat()

    return facts
