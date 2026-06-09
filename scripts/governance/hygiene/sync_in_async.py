#!/usr/bin/env python3
"""Find synchronous blocking calls inside async functions."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BLOCKING_CALLS = {
    "time.sleep",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "subprocess.run",
    "subprocess.call",
}


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def iter_python_files() -> list[Path]:
    roots = [REPO_ROOT / "dharma_swarm", REPO_ROOT / "api", REPO_ROOT / "scripts"]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def main() -> int:
    hits: list[str] = []
    for path in iter_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    name = dotted_name(child.func)
                    if name in BLOCKING_CALLS:
                        rel = path.relative_to(REPO_ROOT).as_posix()
                        hits.append(f"{rel}:{child.lineno}: {name} inside async {node.name}")
    print(f"sync_in_async_sites={len(hits)}")
    for hit in hits[:20]:
        print(hit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
