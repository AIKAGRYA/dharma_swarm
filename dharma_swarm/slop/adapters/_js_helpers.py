"""Shared helpers for JS/TS detector adapters.

JS/TS projects are package.json-rooted, not file-rooted. Most TS/JS
tools (knip, jscpd, dependency-cruiser, tsc, eslint) run at the project
root and emit findings against repo-relative paths. These helpers keep
that discipline consistent across adapters.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

JS_TS_SUFFIXES: frozenset[str] = frozenset(
    {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
)
PYTHON_SUFFIXES: frozenset[str] = frozenset({".py"})

JS_PROJECT_MARKER = "package.json"
TS_PROJECT_MARKER = "tsconfig.json"
EXCLUDE_DIRS: frozenset[str] = frozenset(
    {"node_modules", ".next", "dist", "build", ".turbo", ".git", "__pycache__"}
)


def filter_python_paths(paths: Iterable[Path]) -> list[Path]:
    return [p for p in paths if p.suffix in PYTHON_SUFFIXES]


def filter_js_ts_paths(paths: Iterable[Path]) -> list[Path]:
    return [p for p in paths if p.suffix in JS_TS_SUFFIXES]


def find_js_projects(paths: Iterable[Path], *, repo_root: Path) -> list[Path]:
    """Find package.json-rooted projects that contain any input path.

    Walks each input path's ancestors to find the nearest package.json,
    deduplicates, and returns project roots in the order discovered.
    Skips package.json files inside node_modules/dist/build.
    """
    roots: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        p = raw if raw.is_absolute() else (repo_root / raw)
        if not p.exists():
            continue
        for ancestor in [p, *p.parents]:
            if ancestor == repo_root.parent:
                break
            if any(part in EXCLUDE_DIRS for part in ancestor.parts):
                continue
            candidate = ancestor / JS_PROJECT_MARKER
            if candidate.is_file():
                resolved = ancestor.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    roots.append(resolved)
                break
    return roots


def find_ts_projects(paths: Iterable[Path], *, repo_root: Path) -> list[Path]:
    """Find tsconfig.json-rooted projects (a superset of JS projects)."""
    roots: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        p = raw if raw.is_absolute() else (repo_root / raw)
        if not p.exists():
            continue
        for ancestor in [p, *p.parents]:
            if ancestor == repo_root.parent:
                break
            if any(part in EXCLUDE_DIRS for part in ancestor.parts):
                continue
            candidate = ancestor / TS_PROJECT_MARKER
            if candidate.is_file():
                resolved = ancestor.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    roots.append(resolved)
                break
    return roots


__all__ = [
    "EXCLUDE_DIRS",
    "JS_PROJECT_MARKER",
    "JS_TS_SUFFIXES",
    "PYTHON_SUFFIXES",
    "TS_PROJECT_MARKER",
    "filter_js_ts_paths",
    "filter_python_paths",
    "find_js_projects",
    "find_ts_projects",
]
