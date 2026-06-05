#!/usr/bin/env python3
"""Prevent new memory-authority sprawl outside the Memory Kernel boundary."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

AUTHORITY_EXACT_NAMES = {
    "MemoryKernel",
    "MemoryPlane",
}
AUTHORITY_SUFFIXES = (
    "MemoryStore",
    "MemoryRouter",
    "MemoryRegistry",
    "MemorySubstrate",
)
AUTHORITY_MODULE_NAMES = {
    "memory_kernel.py",
    "memory_plane.py",
    "memory_router.py",
    "memory_registry.py",
    "memory_substrate.py",
}
AUTHORITY_MODULE_SUFFIXES = (
    "_memory_store.py",
    "_memory_router.py",
    "_memory_registry.py",
    "_memory_substrate.py",
)
ALLOWLIST_PATTERNS = (
    "dharma_swarm/memory_kernel/**",
    "dharma_swarm/contracts/intelligence.py",
    "dharma_swarm/contracts/intelligence_adapters.py",
    "dharma_swarm/contracts/intelligence_evaluation_services.py",
    "dharma_swarm/contracts/intelligence_stack.py",
    "dharma_swarm/runtime_state.py",
    "dharma_swarm/memory_lattice.py",
    "dharma_swarm/memory_palace.py",
    "dharma_swarm/routing_memory.py",
    "dharma_swarm/engine/event_memory.py",
    "dharma_swarm/engine/conversation_memory.py",
    "dharma_swarm/engine/knowledge_store.py",
    "scripts/governance/check_memory_kernel_canonical.py",
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    name: str
    reason: str

    def render(self) -> str:
        if self.line:
            return f"  {self.path}:{self.line}  {self.name} ({self.reason})"
        return f"  {self.path}  {self.name} ({self.reason})"


def path_matches(rel_path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return rel_path.startswith(pattern[:-3])
    return fnmatch.fnmatch(rel_path, pattern)


def is_allowlisted(rel_path: str) -> bool:
    return any(path_matches(rel_path, pattern) for pattern in ALLOWLIST_PATTERNS)


def is_test_path(rel_path: str) -> bool:
    path = Path(rel_path)
    return rel_path.startswith("tests/") or "/tests/" in rel_path or path.name.startswith("test_")


def looks_authoritative_name(name: str) -> bool:
    return name in AUTHORITY_EXACT_NAMES or name.endswith(AUTHORITY_SUFFIXES)


def looks_authoritative_module(path: Path) -> bool:
    name = path.name
    return name in AUTHORITY_MODULE_NAMES or name.endswith(AUTHORITY_MODULE_SUFFIXES)


def scan_text(rel_path: str, text: str) -> list[Finding]:
    if is_test_path(rel_path) or is_allowlisted(rel_path):
        return []

    findings: list[Finding] = []
    path = Path(rel_path)
    if looks_authoritative_module(path):
        findings.append(
            Finding(
                path=rel_path,
                line=0,
                name=path.name,
                reason="authority-looking module outside Memory Kernel allowlist",
            )
        )

    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and looks_authoritative_name(node.name):
            findings.append(
                Finding(
                    path=rel_path,
                    line=node.lineno,
                    name=node.name,
                    reason="authority-looking class outside Memory Kernel allowlist",
                )
            )
    return findings


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_paths(base_ref: str, head_ref: str, include_worktree: bool) -> list[Path]:
    rel_paths: set[str] = set()
    for rel in run_git(
        ["diff", "--name-only", "--diff-filter=AM", f"{base_ref}...{head_ref}", "--", "*.py"]
    ):
        rel_paths.add(rel)
    if include_worktree:
        for rel in run_git(["diff", "--name-only", "--diff-filter=AM", "--", "*.py"]):
            rel_paths.add(rel)
        for rel in run_git(["ls-files", "--others", "--exclude-standard", "--", "*.py"]):
            rel_paths.add(rel)
    return sorted(REPO_ROOT / rel for rel in rel_paths)


def scan_paths(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        if not rel.endswith(".py"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(scan_text(rel, text))
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--no-worktree", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = changed_paths(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        include_worktree=not args.no_worktree,
    )
    findings = scan_paths(paths)

    print("Memory Kernel canonicality gate")
    print("-" * 60)
    print(f"Scanned changed Python files: {len(paths)}")

    if not findings:
        print()
        print("No new memory-authority surfaces found outside the allowlist.")
        return 0

    print()
    print("New memory-authority-looking surfaces must be Memory Kernel adapters, projections, or backends:")
    for finding in findings:
        print(finding.render())
    print()
    print("Move the surface under `dharma_swarm/memory_kernel/` or add a reviewed allowlist entry.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
