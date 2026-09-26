"""
2c — Config and infrastructure analyzer.

Extracts services, build/test commands, and environment variables from:
- docker-compose.yml / docker-compose.yaml
- Kubernetes manifests (basic)
- package.json scripts
- Makefile targets
- .env / .env.example files
- pyproject.toml / setup.cfg tool sections
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import yaml

from app.models.facts import BuildCommandFact, EnvVarFact, ServiceFact

logger = logging.getLogger(__name__)


def analyse_config(repo_path: Path) -> dict:
    """
    Run all config analysis on the repo at repo_path.
    Returns a dict with keys: services, build_commands, env_vars.
    """
    services: list[ServiceFact] = []
    build_commands: list[BuildCommandFact] = []
    env_vars: list[EnvVarFact] = []

    errors: list[str] = []

    for handler, patterns in _HANDLERS:
        for pattern in patterns:
            for match in repo_path.rglob(pattern):
                rel = str(match.relative_to(repo_path))
                try:
                    s, b, e = handler(match, rel)
                    services.extend(s)
                    build_commands.extend(b)
                    env_vars.extend(e)
                except Exception as exc:
                    errors.append(f"{rel}: {exc}")
                    logger.debug("Config parse error %s: %s", rel, exc)

    if errors:
        logger.warning("Config analysis errors: %s", errors)

    return {
        "services": services,
        "build_commands": build_commands,
        "env_vars": env_vars,
    }


# ---------------------------------------------------------------------------
# Handler type: (path, rel_path) → (services, build_commands, env_vars)
# ---------------------------------------------------------------------------

_Result = tuple[list[ServiceFact], list[BuildCommandFact], list[EnvVarFact]]


def _parse_docker_compose(path: Path, rel: str) -> _Result:
    services: list[ServiceFact] = []
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    raw_services = data.get("services", {}) or {}
    for name, cfg in raw_services.items():
        cfg = cfg or {}
        ports = [str(p) for p in (cfg.get("ports") or [])]
        env = cfg.get("environment") or []
        if isinstance(env, dict):
            env_names = list(env.keys())
        else:
            env_names = [e.split("=")[0] for e in env if e]
        depends = list(cfg.get("depends_on") or [])
        if isinstance(depends, dict):
            depends = list(depends.keys())
        services.append(ServiceFact(
            name=name,
            source_file=rel,
            image=cfg.get("image"),
            ports=ports,
            env_vars=env_names,
            depends_on=depends,
        ))
    return services, [], []


def _parse_package_json(path: Path, rel: str) -> _Result:
    build_commands: list[BuildCommandFact] = []
    with open(path) as f:
        data = json.load(f)
    scripts = data.get("scripts", {}) or {}
    for name, cmd in scripts.items():
        build_commands.append(BuildCommandFact(source_file=rel, name=name, command=cmd))
    return [], build_commands, []


def _parse_makefile(path: Path, rel: str) -> _Result:
    build_commands: list[BuildCommandFact] = []
    target_re = re.compile(r"^([a-zA-Z0-9_-]+)\s*:", re.MULTILINE)
    text = path.read_text(errors="replace")
    for m in target_re.finditer(text):
        target = m.group(1)
        if target.startswith("."):
            continue  # skip .PHONY etc.
        # Grab the first recipe line
        rest = text[m.end():]
        lines = rest.lstrip("\n").splitlines()
        recipe = next((l.strip() for l in lines if l.startswith("\t")), "")
        build_commands.append(BuildCommandFact(source_file=rel, name=target, command=recipe))
    return [], build_commands, []


def _parse_env_file(path: Path, rel: str) -> _Result:
    env_vars: list[EnvVarFact] = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            name, _, value = line.partition("=")
            env_vars.append(EnvVarFact(
                source_file=rel,
                name=name.strip(),
                default_value=value.strip() or None,
            ))
    return [], [], env_vars


def _parse_k8s_manifest(path: Path, rel: str) -> _Result:
    """Parse a Kubernetes Deployment/Service manifest for service names."""
    services: list[ServiceFact] = []
    try:
        with open(path) as f:
            docs = list(yaml.safe_load_all(f))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            kind = doc.get("kind", "")
            if kind not in ("Deployment", "Service", "StatefulSet"):
                continue
            name = (doc.get("metadata") or {}).get("name", "")
            if not name:
                continue
            ports: list[str] = []
            spec = doc.get("spec") or {}
            for port_entry in spec.get("ports") or []:
                if isinstance(port_entry, dict):
                    p = port_entry.get("port") or port_entry.get("containerPort")
                    if p:
                        ports.append(str(p))
            services.append(ServiceFact(name=name, source_file=rel, ports=ports))
    except Exception:
        pass
    return services, [], []


# Handler registry: (callable, [glob_patterns])
_HANDLERS: list[tuple] = [
    (_parse_docker_compose, ["docker-compose.yml", "docker-compose.yaml",
                              "compose.yml", "compose.yaml"]),
    (_parse_package_json,   ["package.json"]),
    (_parse_makefile,       ["Makefile", "makefile", "GNUmakefile"]),
    (_parse_env_file,       [".env.example", ".env.sample", ".env.template"]),
    (_parse_k8s_manifest,   ["*.yaml", "*.yml"]),   # broad — filtered by content
]
