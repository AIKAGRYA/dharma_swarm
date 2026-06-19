#!/usr/bin/env python3
"""Read-only module diet census for dharma_swarm.

This script is the proof gate before deleting or moving modules. It does not
mutate the repository. It classifies Python modules into coarse lifecycle
buckets so humans and agents can shrink the live surface without guesswork.

Intended use:
    python3 scripts/governance/module_diet_census.py --format markdown
    python3 scripts/governance/module_diet_census.py --format json
    python3 scripts/governance/module_diet_census.py \
        --baseline-top-level-count 406 --fail-on-top-level-growth
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DUPLICATE_FAMILY_PATTERNS: dict[str, re.Pattern[str]] = {
    "bridge": re.compile(r"(^|_)bridge($|_)", re.IGNORECASE),
    "adapter": re.compile(r"(^|_)adapter(s)?($|_)", re.IGNORECASE),
    "routing": re.compile(r"(^|_)(routing|router|selector)($|_)", re.IGNORECASE),
    "orchestrator": re.compile(r"(^|_)(orchestrator|orchestrate)($|_)", re.IGNORECASE),
    "director": re.compile(r"(^|_)director($|_)", re.IGNORECASE),
    "provider": re.compile(r"(^|_)provider(s)?($|_)", re.IGNORECASE),
    "terminal": re.compile(r"(^|_)(terminal|tui|swarmlens)($|_)", re.IGNORECASE),
}

# These are not claimed to be the full live set. They are the named core owners
# already present in governance docs, used only to avoid calling obvious cores
# dead when a purely static import count is incomplete.
KNOWN_CORE_MODULES = {
    "dharma_swarm.agent_runner",
    "dharma_swarm.archive",
    "dharma_swarm.config",
    "dharma_swarm.dgc_cli",
    "dharma_swarm.dharma_kernel",
    "dharma_swarm.evolution",
    "dharma_swarm.models",
    "dharma_swarm.orchestrator",
    "dharma_swarm.providers",
    "dharma_swarm.runtime_state",
    "dharma_swarm.stigmergy",
    "dharma_swarm.swarm",
    "dharma_swarm.telos_gates",
}

PROOF_GATE = [
    "python3 scripts/governance/module_diet_census.py --format markdown",
    "python3 -m pytest tests/test_module_diet_census.py -q",
    "python3 -m pytest -q tests/smoke tests/test_import_hygiene.py",
    "make test-fast",
    "make governance-all",
]


@dataclass(frozen=True)
class ModuleRow:
    path: str
    module: str
    lines: int
    top_level: bool
    imported_by_count: int
    test_exists: bool
    manifest_mentioned: bool
    entrypoint: bool
    duplicate_families: list[str]
    classification: str
    proof_required: list[str]
    reasons: list[str]


@dataclass(frozen=True)
class CensusResult:
    rows: list[ModuleRow]
    summary: dict[str, object]

    def to_json_text(self) -> str:
        return json.dumps(
            {
                "summary": self.summary,
                "rows": [asdict(row) for row in self.rows],
            },
            indent=2,
            sort_keys=True,
        ) + "\n"


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def iter_repo_python_files(repo_root: Path) -> Iterable[Path]:
    for dirname in ("dharma_swarm", "api", "scripts", "tests"):
        root = repo_root / dirname
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" not in path.parts:
                yield path


def iter_dharma_modules(repo_root: Path) -> Iterable[Path]:
    root = repo_root / "dharma_swarm"
    if not root.exists():
        return
    for path in root.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path


def module_name(repo_root: Path, path: Path) -> str:
    rel = path.relative_to(repo_root).with_suffix("")
    return ".".join(rel.parts)


def parse_import_targets(path: Path) -> set[str]:
    text = safe_read_text(path)
    if not text.strip():
        return set()
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return set()

    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            base = node.module or ""
            if not base:
                continue
            targets.add(base)
            if base == "dharma_swarm":
                for alias in node.names:
                    if alias.name != "*":
                        targets.add(f"dharma_swarm.{alias.name}")
            elif base.startswith("dharma_swarm."):
                for alias in node.names:
                    if alias.name != "*":
                        targets.add(f"{base}.{alias.name}")
    return targets


def resolve_import_target(target: str, known_modules: set[str]) -> str | None:
    if target in known_modules:
        return target
    parts = target.split(".")
    while len(parts) > 1:
        parts = parts[:-1]
        candidate = ".".join(parts)
        if candidate in known_modules:
            return candidate
    return None


def discover_entrypoints(repo_root: Path) -> set[str]:
    entrypoints = set(KNOWN_CORE_MODULES)
    pyproject = safe_read_text(repo_root / "pyproject.toml")
    for match in re.finditer(r'=\s*"([A-Za-z0-9_\.]+):[^\"]+"', pyproject):
        target = match.group(1)
        if target.startswith("dharma_swarm."):
            entrypoints.add(target)
    return entrypoints


def duplicate_families(path: Path, module: str) -> list[str]:
    haystack = " ".join([path.stem, module, "/".join(path.parts)]).lower()
    families = [
        name
        for name, pattern in DUPLICATE_FAMILY_PATTERNS.items()
        if pattern.search(haystack)
    ]
    return sorted(set(families))


def build_test_name_index(repo_root: Path) -> set[str]:
    tests = repo_root / "tests"
    if not tests.exists():
        return set()
    return {path.name for path in tests.rglob("*.py")}


def has_conventional_test(path: Path, test_names: set[str]) -> bool:
    if path.name == "__init__.py":
        return True
    stem = path.stem
    exact = {f"test_{stem}.py", f"{stem}_test.py"}
    if exact & test_names:
        return True
    needle = f"test_{stem}"
    return any(name.startswith(needle) for name in test_names)


def classify_module(
    *,
    module: str,
    top_level: bool,
    imported_by_count: int,
    test_exists: bool,
    manifest_mentioned: bool,
    entrypoint: bool,
    duplicate_family_names: list[str],
) -> tuple[str, list[str], list[str]]:
    reasons: list[str] = []
    proof_required: list[str] = []

    if entrypoint or manifest_mentioned or module in KNOWN_CORE_MODULES:
        if entrypoint:
            reasons.append("entrypoint_or_named_core")
        if manifest_mentioned:
            reasons.append("manifest_mentioned")
        if duplicate_family_names:
            reasons.append("duplicate_family_review_still_required")
            return "LIVE_DUPLICATE_REVIEW", PROOF_GATE, reasons
        return "LIVE", [], reasons

    if duplicate_family_names:
        reasons.append("duplicate_seam_family")
        proof_required = PROOF_GATE
        if imported_by_count:
            reasons.append("has_importers")
            return "LIVE_DUPLICATE_REVIEW", proof_required, reasons
        return "DUPLICATE_REVIEW", proof_required, reasons

    if imported_by_count:
        reasons.append("has_importers")
        if test_exists:
            reasons.append("has_conventional_test")
        return "LIVE_CANDIDATE", [], reasons

    if test_exists:
        reasons.append("has_conventional_test_but_no_static_importers")
        return "SHADOW_OR_TESTED_SEED", PROOF_GATE[:3], reasons

    proof_required = PROOF_GATE
    if top_level:
        reasons.append("top_level_no_importers_no_conventional_test")
        return "DEAD_CANDIDATE", proof_required, reasons

    reasons.append("nested_no_importers_no_conventional_test")
    return "SEED_OR_DEAD_CANDIDATE", proof_required, reasons


def build_census(repo_root: Path) -> CensusResult:
    repo_root = repo_root.resolve()
    module_paths = sorted(iter_dharma_modules(repo_root))
    module_by_name = {module_name(repo_root, path): path for path in module_paths}
    known_modules = set(module_by_name)

    imported_by: dict[str, set[str]] = defaultdict(set)
    for source in iter_repo_python_files(repo_root):
        source_module = module_name(repo_root, source)
        for target in parse_import_targets(source):
            if not target.startswith("dharma_swarm"):
                continue
            resolved = resolve_import_target(target, known_modules)
            if resolved and resolved != source_module:
                imported_by[resolved].add(str(source.relative_to(repo_root)))

    manifest_text = safe_read_text(repo_root / "ACTIVE_SURFACE_MANIFEST.yaml")
    entrypoints = discover_entrypoints(repo_root)
    test_names = build_test_name_index(repo_root)

    rows: list[ModuleRow] = []
    for path in module_paths:
        module = module_name(repo_root, path)
        rel_path = str(path.relative_to(repo_root))
        top_level = path.parent == repo_root / "dharma_swarm"
        imports = imported_by.get(module, set())
        families = duplicate_families(path.relative_to(repo_root), module)
        text = safe_read_text(path)
        manifest_mentioned = rel_path in manifest_text or module in manifest_text
        test_exists = has_conventional_test(path, test_names)
        entrypoint = module in entrypoints
        classification, proof_required, reasons = classify_module(
            module=module,
            top_level=top_level,
            imported_by_count=len(imports),
            test_exists=test_exists,
            manifest_mentioned=manifest_mentioned,
            entrypoint=entrypoint,
            duplicate_family_names=families,
        )
        rows.append(
            ModuleRow(
                path=rel_path,
                module=module,
                lines=text.count("\n") + (1 if text else 0),
                top_level=top_level,
                imported_by_count=len(imports),
                test_exists=test_exists,
                manifest_mentioned=manifest_mentioned,
                entrypoint=entrypoint,
                duplicate_families=families,
                classification=classification,
                proof_required=proof_required,
                reasons=reasons,
            )
        )

    class_counts = Counter(row.classification for row in rows)
    family_counts: Counter[str] = Counter()
    for row in rows:
        family_counts.update(row.duplicate_families)

    summary: dict[str, object] = {
        "total_modules": len(rows),
        "top_level_modules": sum(1 for row in rows if row.top_level),
        "top_level_ratio": round(
            sum(1 for row in rows if row.top_level) / max(1, len(rows)), 4
        ),
        "classification_counts": dict(sorted(class_counts.items())),
        "duplicate_family_counts": dict(sorted(family_counts.items())),
        "large_files_over_500": sum(1 for row in rows if row.lines > 500),
        "large_files_over_1000": sum(1 for row in rows if row.lines > 1000),
        "large_files_over_3000": sum(1 for row in rows if row.lines > 3000),
        "proof_gate": PROOF_GATE,
    }
    return CensusResult(rows=rows, summary=summary)


def markdown_table(rows: Iterable[ModuleRow], columns: list[str]) -> str:
    rows = list(rows)
    if not rows:
        return "_None found by this static pass._\n"
    out = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        values: list[str] = []
        for column in columns:
            value = getattr(row, column)
            if isinstance(value, list):
                value = ", ".join(value)
            values.append(str(value).replace("|", "\\|"))
        out.append("| " + " | ".join(values) + " |")
    return "\n".join(out) + "\n"


def render_markdown(result: CensusResult) -> str:
    rows = result.rows
    class_counts = result.summary["classification_counts"]
    family_counts = result.summary["duplicate_family_counts"]

    dead_candidates = sorted(
        (row for row in rows if row.classification == "DEAD_CANDIDATE"),
        key=lambda row: (-row.lines, row.path),
    )[:40]
    duplicate_rows = sorted(
        (row for row in rows if "DUPLICATE" in row.classification),
        key=lambda row: (row.duplicate_families, -row.lines, row.path),
    )[:60]
    giant_rows = sorted(
        (row for row in rows if row.lines > 1000),
        key=lambda row: (-row.lines, row.path),
    )[:40]

    lines = [
        "# Module Diet Census",
        "",
        "Status: generated read-only static scan; owns no deletion authority.",
        "",
        "## Summary",
        "",
        f"- total modules: {result.summary['total_modules']}",
        f"- top-level modules: {result.summary['top_level_modules']}",
        f"- top-level ratio: {result.summary['top_level_ratio']}",
        f"- files over 500 lines: {result.summary['large_files_over_500']}",
        f"- files over 1,000 lines: {result.summary['large_files_over_1000']}",
        f"- files over 3,000 lines: {result.summary['large_files_over_3000']}",
        "",
        "## Classification counts",
        "",
        json.dumps(class_counts, indent=2, sort_keys=True),
        "",
        "## Duplicate seam family counts",
        "",
        json.dumps(family_counts, indent=2, sort_keys=True),
        "",
        "## First top-level dead candidates to reverify",
        "",
        markdown_table(dead_candidates, ["path", "lines", "classification", "reasons"]),
        "",
        "## Duplicate seam review queue",
        "",
        markdown_table(
            duplicate_rows,
            ["path", "lines", "classification", "duplicate_families", "imported_by_count"],
        ),
        "",
        "## Large-file pressure queue",
        "",
        markdown_table(giant_rows, ["path", "lines", "classification", "imported_by_count"]),
        "",
        "## Step-5 deletion gate",
        "",
        "No file is safe to delete from this census alone. A deletion PR must prove:",
        "",
        *[f"- `{command}`" for command in PROOF_GATE],
        "",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="repository root, default: cwd")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="write output to this path instead of stdout")
    parser.add_argument(
        "--baseline-top-level-count",
        type=int,
        help="expected maximum top-level dharma_swarm/*.py module count",
    )
    parser.add_argument(
        "--fail-on-top-level-growth",
        action="store_true",
        help="exit non-zero if top-level module count exceeds the baseline",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    result = build_census(Path(args.repo_root))
    text = result.to_json_text() if args.format == "json" else render_markdown(result)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")

    if args.fail_on_top_level_growth and args.baseline_top_level_count is not None:
        top_level = int(result.summary["top_level_modules"])
        if top_level > args.baseline_top_level_count:
            print(
                f"top-level module count grew: {top_level} > {args.baseline_top_level_count}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
