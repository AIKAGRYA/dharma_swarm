#!/usr/bin/env python3
"""Deterministic module naming/coherence inventory.

This gate is intentionally narrow.  It does not grade architecture taste; it
guards against concrete sloppy surfaces: generated directories leaking into the
scan and duplicate module basenames inside the same package directory.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SOURCE_ROOTS = ("dharma_swarm", "api", "scripts")
SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".worktrees",
    "__pycache__",
    "artifacts",
    "build",
    "build_artifacts",
    "dist",
    "external",
    "generated",
    "node_modules",
    "reports",
    "results",
    "vendor",
}
SKIP_PREFIXES = (".dharma",)
NAMING_FAMILIES = ("bridge", "adapter", "router", "orchestrator", "gateway")


@dataclass(frozen=True)
class ModuleCoherenceReport:
    repo_root: str
    scanned_files: int
    source_roots: list[str]
    family_counts: dict[str, int]
    family_examples: dict[str, list[str]]
    duplicate_modules_same_package: list[dict[str, Any]]
    status: str

    @property
    def ok(self) -> bool:
        return self.status == "pass"


def _skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or any(name.startswith(prefix) for prefix in SKIP_PREFIXES)


def iter_source_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root_name in SOURCE_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            rel_parts = path.relative_to(repo_root).parts
            if any(_skip_dir(part) for part in rel_parts):
                continue
            files.append(path)
    return files


def analyze_module_coherence(repo_root: Path) -> ModuleCoherenceReport:
    repo_root = repo_root.resolve()
    files = iter_source_files(repo_root)

    family_paths: dict[str, list[str]] = {}
    for family in NAMING_FAMILIES:
        family_paths[family] = [
            path.relative_to(repo_root).as_posix()
            for path in files
            if family in path.stem.lower()
        ]

    by_package_and_stem: dict[tuple[str, str], list[str]] = defaultdict(list)
    for path in files:
        rel = path.relative_to(repo_root)
        by_package_and_stem[(rel.parent.as_posix(), path.stem)].append(rel.as_posix())

    duplicates = [
        {"package": package, "module": module, "paths": sorted(paths)}
        for (package, module), paths in sorted(by_package_and_stem.items())
        if len(paths) > 1
    ]

    family_counts = dict(Counter({family: len(paths) for family, paths in family_paths.items()}))
    status = "fail" if duplicates else "pass"
    return ModuleCoherenceReport(
        repo_root=str(repo_root),
        scanned_files=len(files),
        source_roots=[root for root in SOURCE_ROOTS if (repo_root / root).exists()],
        family_counts=family_counts,
        family_examples={family: paths[:12] for family, paths in family_paths.items()},
        duplicate_modules_same_package=duplicates,
        status=status,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root to scan")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--report-json", default="", help="Optional path to write JSON report")
    args = parser.parse_args(argv)

    report = analyze_module_coherence(Path(args.repo_root))
    payload = asdict(report)

    if args.report_json:
        out = Path(args.report_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status={report.status}")
        print(f"scanned_files={report.scanned_files}")
        print("family_counts=" + json.dumps(report.family_counts, sort_keys=True))
        if report.duplicate_modules_same_package:
            print("duplicate_modules_same_package=" + json.dumps(report.duplicate_modules_same_package, sort_keys=True))

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
