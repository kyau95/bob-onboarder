"""
2a — Source code analyzer.

Uses Tree-sitter for multi-language parsing and Python's ast module for
deeper Python-specific analysis.  Produces ImportFact, FunctionFact,
ClassFact, APIEndpointFact, and DependencyFact records.
"""
from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import Any

from tree_sitter import Language, Node, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

from app.models.facts import (
    APIEndpointFact,
    ClassFact,
    DependencyFact,
    FileInfo,
    FunctionFact,
    ImportFact,
)
from app.models.facts import Language as Lang
from app.services.language_detector import detect_language, walk_repo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parser setup (built once at import time)
# ---------------------------------------------------------------------------

_PY_PARSER  = Parser(Language(tspython.language()))
_JS_PARSER  = Parser(Language(tsjavascript.language()))
_TS_PARSER  = Parser(Language(tstypescript.language_typescript()))
_TSX_PARSER = Parser(Language(tstypescript.language_tsx()))

# HTTP method decorators used by popular frameworks
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

# Known dependency manifest files
_MANIFEST_PARSERS: dict[str, str] = {
    "requirements.txt": "requirements_txt",
    "requirements-dev.txt": "requirements_txt",
    "requirements-test.txt": "requirements_txt",
    "pyproject.toml": "pyproject_toml",
    "setup.cfg": "setup_cfg",
    "package.json": "package_json",
    "go.mod": "go_mod",
    "pom.xml": "pom_xml",
    "build.gradle": "gradle",
}

# Standard-library top-level packages (common subset — good enough for is_external)
_STDLIB_TOPS: frozenset[str] = frozenset({
    "os", "sys", "re", "io", "abc", "ast", "dis", "gc", "inspect",
    "itertools", "functools", "operator", "pathlib", "typing", "types",
    "collections", "dataclasses", "enum", "copy", "pprint", "random",
    "math", "statistics", "decimal", "datetime", "time", "calendar",
    "string", "textwrap", "struct", "codecs", "unicodedata",
    "json", "csv", "configparser", "toml", "xml", "html",
    "http", "urllib", "email", "smtplib", "ftplib",
    "socket", "ssl", "asyncio", "concurrent", "threading", "multiprocessing",
    "subprocess", "shutil", "tempfile", "glob", "fnmatch", "stat",
    "hashlib", "hmac", "secrets", "base64", "binascii", "uuid",
    "logging", "warnings", "traceback", "contextlib", "atexit",
    "argparse", "getopt", "getpass", "readline",
    "unittest", "doctest", "pdb", "profile", "cProfile",
    "platform", "signal", "ctypes", "struct",
    "zipfile", "tarfile", "gzip", "bz2", "lzma", "zlib",
    "pickle", "shelve", "sqlite3", "dbm",
    "tkinter", "curses",
    "builtins", "__future__",
})


def _is_external(name: str) -> bool:
    top = name.split(".")[0].lstrip("_")
    return top not in _STDLIB_TOPS and not name.startswith(".")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyse_sources(repo_path: Path) -> dict:
    """
    Walk the repository and extract all source facts.
    Returns a dict with keys: files, imports, functions, classes,
    api_endpoints, dependencies.
    """
    files: list[FileInfo] = []
    imports: list[ImportFact] = []
    functions: list[FunctionFact] = []
    classes: list[ClassFact] = []
    api_endpoints: list[APIEndpointFact] = []
    dependencies: list[DependencyFact] = []

    all_files = walk_repo(repo_path)

    for abs_path in all_files:
        rel = str(abs_path.relative_to(repo_path))
        lang = detect_language(abs_path)

        try:
            stat = abs_path.stat()
            text = abs_path.read_bytes()
            line_count = text.count(b"\n") + 1
        except OSError:
            continue

        files.append(FileInfo(
            path=rel,
            language=lang,
            size_bytes=stat.st_size,
            line_count=line_count,
        ))

        # --- Source parsing ---
        try:
            if lang == Lang.PYTHON:
                r = _analyse_python(abs_path, rel, text)
            elif lang in (Lang.JAVASCRIPT,):
                r = _analyse_js(abs_path, rel, text, _JS_PARSER)
            elif lang == Lang.TYPESCRIPT:
                parser = _TSX_PARSER if abs_path.suffix == ".tsx" else _TS_PARSER
                r = _analyse_js(abs_path, rel, text, parser)
            else:
                r = None

            if r:
                imports.extend(r.get("imports", []))
                functions.extend(r.get("functions", []))
                classes.extend(r.get("classes", []))
                api_endpoints.extend(r.get("api_endpoints", []))
        except Exception as exc:
            logger.debug("Source parse error %s: %s", rel, exc)

        # --- Dependency manifests ---
        fname = abs_path.name
        if fname in _MANIFEST_PARSERS:
            try:
                deps = _parse_manifest(abs_path, rel, _MANIFEST_PARSERS[fname])
                dependencies.extend(deps)
            except Exception as exc:
                logger.debug("Manifest parse error %s: %s", rel, exc)

    return {
        "files": files,
        "imports": imports,
        "functions": functions,
        "classes": classes,
        "api_endpoints": api_endpoints,
        "dependencies": dependencies,
    }


# ---------------------------------------------------------------------------
# Python analysis (tree-sitter + ast fallback)
# ---------------------------------------------------------------------------

def _analyse_python(path: Path, rel: str, source: bytes) -> dict:
    imports: list[ImportFact] = []
    functions: list[FunctionFact] = []
    classes: list[ClassFact] = []
    api_endpoints: list[APIEndpointFact] = []

    try:
        tree = ast.parse(source.decode("utf-8", errors="replace"))
    except SyntaxError:
        # Fall back to tree-sitter only
        return _analyse_with_treesitter(_PY_PARSER, source, rel)

    for node in ast.walk(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportFact(
                    source_file=rel,
                    line=node.lineno,
                    imported_name=alias.name,
                    is_external=_is_external(alias.name),
                ))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.append(ImportFact(
                source_file=rel,
                line=node.lineno,
                imported_name=mod or ".",
                is_external=_is_external(mod) if mod else False,
            ))

        # Functions / methods
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = [_decorator_name(d) for d in node.decorator_list]
            class_name = _enclosing_class(tree, node)
            functions.append(FunctionFact(
                file=rel,
                line=node.lineno,
                name=node.name,
                class_name=class_name,
                is_async=isinstance(node, ast.AsyncFunctionDef),
                decorators=decorators,
            ))
            # Detect API routes from decorators
            for dec_name in decorators:
                endpoint = _route_from_decorator(dec_name, node, rel)
                if endpoint:
                    api_endpoints.append(endpoint)

        # Classes
        elif isinstance(node, ast.ClassDef):
            bases = [_name_of(b) for b in node.bases]
            methods = [
                n.name for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n is not node
            ]
            classes.append(ClassFact(
                file=rel,
                line=node.lineno,
                name=node.name,
                bases=bases,
                methods=methods,
            ))

    return {
        "imports": imports,
        "functions": functions,
        "classes": classes,
        "api_endpoints": api_endpoints,
    }


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name_of(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _name_of(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name_of(node.value)}.{node.attr}"
    return ""


def _enclosing_class(tree: ast.Module, func: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.walk(node):
                if child is func:
                    return node.name
    return None


def _route_from_decorator(dec: str, func: ast.FunctionDef | ast.AsyncFunctionDef, rel: str) -> APIEndpointFact | None:
    """Detect @app.get("/path"), @router.post("/path"), @bp.route("/path") etc."""
    parts = dec.lower().split(".")
    method = parts[-1] if parts else ""
    if method not in _HTTP_METHODS and method != "route":
        return None

    # Grab the first string argument from the decorator call in the AST
    for d in func.decorator_list:
        if not isinstance(d, ast.Call):
            continue
        if _decorator_name(d.func).lower().endswith(("." + method, method)):
            path_arg = ""
            if d.args and isinstance(d.args[0], ast.Constant):
                path_arg = str(d.args[0].value)
            return APIEndpointFact(
                file=rel,
                line=func.lineno,
                method=method.upper() if method != "route" else "GET",
                path=path_arg,
                handler=func.name,
                framework=_guess_framework(dec),
            )
    return None


def _guess_framework(decorator: str) -> str:
    d = decorator.lower()
    if "router" in d or "fastapi" in d:
        return "fastapi"
    if "bp" in d or "blueprint" in d or "flask" in d:
        return "flask"
    if "app" in d:
        return "flask/fastapi"
    return ""


# ---------------------------------------------------------------------------
# JavaScript / TypeScript analysis via Tree-sitter
# ---------------------------------------------------------------------------

def _analyse_js(path: Path, rel: str, source: bytes, parser: Parser) -> dict:
    tree = parser.parse(source)
    imports: list[ImportFact] = []
    functions: list[FunctionFact] = []
    classes: list[ClassFact] = []
    api_endpoints: list[APIEndpointFact] = []

    def visit(node: Node) -> None:
        t = node.type
        line = node.start_point[0] + 1

        # import / require
        if t == "import_statement":
            src_node = node.child_by_field_name("source")
            if src_node:
                name = _node_text(src_node, source).strip("'\"")
                imports.append(ImportFact(
                    source_file=rel, line=line,
                    imported_name=name,
                    is_external=not name.startswith("."),
                ))

        elif t == "call_expression":
            fn = node.child_by_field_name("function")
            if fn and _node_text(fn, source) == "require":
                args = node.child_by_field_name("arguments")
                if args and args.child_count >= 3:
                    arg = args.child(1)
                    if arg:
                        name = _node_text(arg, source).strip("'\"")
                        imports.append(ImportFact(
                            source_file=rel, line=line,
                            imported_name=name,
                            is_external=not name.startswith("."),
                        ))

        # function declarations
        elif t in ("function_declaration", "function", "arrow_function", "method_definition"):
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source) if name_node else "<anonymous>"
            is_async = any(
                c.type == "async" for c in node.children
            )
            functions.append(FunctionFact(file=rel, line=line, name=name, is_async=is_async))

        # class declarations
        elif t == "class_declaration":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source) if name_node else "<anonymous>"
            classes.append(ClassFact(file=rel, line=line, name=name))

        # Express-style route registration: app.get('/path', handler)
        elif t == "call_expression":
            _check_express_route(node, source, rel, api_endpoints)

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return {"imports": imports, "functions": functions, "classes": classes, "api_endpoints": api_endpoints}


def _check_express_route(node: Node, source: bytes, rel: str, out: list) -> None:
    fn = node.child_by_field_name("function")
    if not fn or fn.type != "member_expression":
        return
    prop = fn.child_by_field_name("property")
    if not prop:
        return
    method = _node_text(prop, source).lower()
    if method not in _HTTP_METHODS:
        return
    args = node.child_by_field_name("arguments")
    if not args or args.child_count < 2:
        return
    path_node = args.child(1)  # first real arg (index 0 is "(")
    path_str = _node_text(path_node, source).strip("'\"") if path_node else ""
    out.append(APIEndpointFact(
        file=rel,
        line=node.start_point[0] + 1,
        method=method.upper(),
        path=path_str,
        handler="",
        framework="express",
    ))


def _analyse_with_treesitter(parser: Parser, source: bytes, rel: str) -> dict:
    """Minimal tree-sitter fallback when ast.parse fails."""
    tree = parser.parse(source)
    imports: list[ImportFact] = []

    def visit(node: Node) -> None:
        if node.type == "import_statement":
            src = node.child_by_field_name("name")
            if src:
                name = _node_text(src, source)
                imports.append(ImportFact(source_file=rel, line=node.start_point[0] + 1,
                                          imported_name=name, is_external=_is_external(name)))
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return {"imports": imports, "functions": [], "classes": [], "api_endpoints": []}


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Dependency manifest parsers
# ---------------------------------------------------------------------------

def _parse_manifest(path: Path, rel: str, parser_name: str) -> list[DependencyFact]:
    fn = globals().get(f"_manifest_{parser_name}")
    if fn is None:
        return []
    return fn(path, rel)


def _manifest_requirements_txt(path: Path, rel: str) -> list[DependencyFact]:
    deps: list[DependencyFact] = []
    is_dev = "dev" in path.name or "test" in path.name
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r"([A-Za-z0-9_\-\.]+)(.*)", line)
        if m:
            deps.append(DependencyFact(
                manifest_file=rel, name=m.group(1),
                version_spec=m.group(2).strip(), is_dev=is_dev,
            ))
    return deps


def _manifest_package_json(path: Path, rel: str) -> list[DependencyFact]:
    deps: list[DependencyFact] = []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return deps
    for section, is_dev in [("dependencies", False), ("devDependencies", True)]:
        for name, version in (data.get(section) or {}).items():
            deps.append(DependencyFact(
                manifest_file=rel, name=name,
                version_spec=str(version), is_dev=is_dev,
            ))
    return deps


def _manifest_pyproject_toml(path: Path, rel: str) -> list[DependencyFact]:
    """Parse [project] dependencies from pyproject.toml using regex (no toml lib needed)."""
    deps: list[DependencyFact] = []
    text = path.read_text(errors="replace")
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in ("[project.dependencies]", "dependencies = [") or stripped.startswith("dependencies"):
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("[") and not stripped.startswith('"'):
                in_deps = False
                continue
            m = re.match(r'"?([A-Za-z0-9_\-\.]+)([^"]*)"?', stripped.strip('", '))
            if m:
                deps.append(DependencyFact(
                    manifest_file=rel, name=m.group(1),
                    version_spec=m.group(2).strip(), is_dev=False,
                ))
    return deps


def _manifest_go_mod(path: Path, rel: str) -> list[DependencyFact]:
    deps: list[DependencyFact] = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("require ") or (line and not line.startswith("//")):
            parts = line.split()
            if len(parts) == 2 and "/" in parts[0]:
                deps.append(DependencyFact(
                    manifest_file=rel, name=parts[0], version_spec=parts[1],
                ))
    return deps


def _manifest_setup_cfg(path: Path, rel: str) -> list[DependencyFact]:
    deps: list[DependencyFact] = []
    in_install = False
    for line in path.read_text(errors="replace").splitlines():
        s = line.strip()
        if s == "install_requires =":
            in_install = True
            continue
        if in_install:
            if s.startswith("[") or (s and not s[0].isspace() and "=" in s):
                in_install = False
                continue
            if s:
                m = re.match(r"([A-Za-z0-9_\-\.]+)(.*)", s)
                if m:
                    deps.append(DependencyFact(
                        manifest_file=rel, name=m.group(1),
                        version_spec=m.group(2).strip(),
                    ))
    return deps


def _manifest_pom_xml(path: Path, rel: str) -> list[DependencyFact]:
    deps: list[DependencyFact] = []
    text = path.read_text(errors="replace")
    for m in re.finditer(
        r"<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>"
        r"(?:\s*<version>([^<]*)</version>)?",
        text,
    ):
        name = f"{m.group(1)}:{m.group(2)}"
        deps.append(DependencyFact(
            manifest_file=rel, name=name,
            version_spec=m.group(3) or "",
        ))
    return deps


def _manifest_gradle(path: Path, rel: str) -> list[DependencyFact]:
    deps: list[DependencyFact] = []
    pattern = re.compile(r"""(?:implementation|api|testImplementation|compile)\s+['"]([^'"]+)['"]""")
    for m in pattern.finditer(path.read_text(errors="replace")):
        parts = m.group(1).split(":")
        if len(parts) >= 2:
            name = f"{parts[0]}:{parts[1]}"
            version = parts[2] if len(parts) > 2 else ""
            deps.append(DependencyFact(manifest_file=rel, name=name, version_spec=version))
    return deps
