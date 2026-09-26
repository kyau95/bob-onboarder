"""Language detection — maps file extensions and special filenames to Language enum."""
from __future__ import annotations

from pathlib import Path

from app.models.facts import Language

# Extension → Language
_EXT_MAP: dict[str, Language] = {
    ".py":    Language.PYTHON,
    ".pyi":   Language.PYTHON,
    ".js":    Language.JAVASCRIPT,
    ".mjs":   Language.JAVASCRIPT,
    ".cjs":   Language.JAVASCRIPT,
    ".jsx":   Language.JAVASCRIPT,
    ".ts":    Language.TYPESCRIPT,
    ".tsx":   Language.TYPESCRIPT,
    ".go":    Language.GO,
    ".java":  Language.JAVA,
    ".kt":    Language.JAVA,       # Kotlin — close enough for graph purposes
    ".rs":    Language.RUST,
    ".rb":    Language.RUBY,
    ".cs":    Language.CSHARP,
    ".cpp":   Language.CPP,
    ".cc":    Language.CPP,
    ".cxx":   Language.CPP,
    ".c":     Language.C,
    ".h":     Language.C,
    ".hpp":   Language.CPP,
    ".yaml":  Language.YAML,
    ".yml":   Language.YAML,
    ".json":  Language.JSON,
    ".sh":    Language.SHELL,
    ".bash":  Language.SHELL,
    ".zsh":   Language.SHELL,
    ".proto": Language.PROTO,
}

# Exact filename (stem or full) → Language
_NAME_MAP: dict[str, Language] = {
    "Dockerfile":        Language.DOCKERFILE,
    "dockerfile":        Language.DOCKERFILE,
    "Makefile":          Language.SHELL,
    "makefile":          Language.SHELL,
    "GNUmakefile":       Language.SHELL,
    ".env":              Language.SHELL,
    ".env.example":      Language.SHELL,
}

# Directories to skip entirely during file walks
SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".venv", "venv", "env", "ENV",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "dist", "build", "target", ".next", ".nuxt",
    "coverage", "htmlcov", ".tox",
})

# File extensions to skip (binary / generated)
SKIP_EXTENSIONS: frozenset[str] = frozenset({
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".class",
    ".jar", ".war", ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff",
    ".woff2", ".ttf", ".eot", ".pdf", ".lock",
})

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB — skip files larger than this


def detect_language(path: Path) -> Language:
    """Return the Language for a given file path."""
    name = path.name
    if name in _NAME_MAP:
        return _NAME_MAP[name]
    # Dockerfile variants: Dockerfile.dev, Dockerfile.prod …
    if name.startswith("Dockerfile"):
        return Language.DOCKERFILE
    ext = path.suffix.lower()
    return _EXT_MAP.get(ext, Language.UNKNOWN)


def is_skippable(path: Path) -> bool:
    """Return True if this file should be excluded from analysis."""
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return True
    except OSError:
        return True
    return False


def walk_repo(root: Path) -> list[Path]:
    """
    Walk the repository and return all analysable source files.
    Skips SKIP_DIRS and SKIP_EXTENSIONS.
    """
    results: list[Path] = []
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        # Skip any file whose path contains a skipped directory
        if any(part in SKIP_DIRS for part in item.parts):
            continue
        if is_skippable(item):
            continue
        results.append(item)
    return results
