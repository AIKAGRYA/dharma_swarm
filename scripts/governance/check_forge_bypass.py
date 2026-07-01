#!/usr/bin/env python3
"""Guard against Forge/DGM promotion bypasses.

The RSI Lab live-apply path must go through forge_v2.verify_promotion.  This
guard checks RSI-sensitive source files for direct live-apply calls such as
``auto_evolve(..., shadow=False)`` or ``DGMLoop(..., shadow_mode=False)``.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENSITIVE_DIRS = (
    ROOT / "dharma_swarm" / "forge_v1" / "forge_v2",
)
SENSITIVE_FILES = (
    ROOT / "dharma_swarm" / "dgm_loop.py",
)
FALSE_KEYWORDS = {"shadow", "shadow_mode"}
LIVE_APPLY_CALLS = {"auto_evolve", "apply_sealed_packet", "apply_diff_and_test", "DGMLoop"}


def _iter_sensitive_files(root: Path = ROOT) -> list[Path]:
    files = [path for path in SENSITIVE_FILES if path.exists()]
    for directory in SENSITIVE_DIRS:
        if directory.exists():
            files.extend(sorted(directory.glob("*.py")))
    return sorted(set(files))


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_false_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def check_file(path: Path) -> list[str]:
    findings: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path
    if rel.as_posix() == "dharma_swarm/dgm_loop.py" and "DHARMA_EVOLUTION_SHADOW" in text:
        findings.append(f"{rel}: env live-unlock DHARMA_EVOLUTION_SHADOW is forbidden")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        findings.append(f"{rel}: syntax error while scanning: {exc}")
        return findings
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in LIVE_APPLY_CALLS:
            continue
        for kw in node.keywords:
            if kw.arg in FALSE_KEYWORDS and _is_false_constant(kw.value):
                findings.append(
                    f"{rel}:{node.lineno}: direct live apply via {name}(..., {kw.arg}=False)"
                )
    return findings


def check_paths(paths: list[Path] | None = None) -> list[str]:
    findings: list[str] = []
    for path in paths or _iter_sensitive_files():
        findings.extend(check_file(Path(path)))
    return findings


def main() -> int:
    findings = check_paths()
    if findings:
        print("FORGE_BYPASS_GUARD_FAILED")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("FORGE_BYPASS_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
