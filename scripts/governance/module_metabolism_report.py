"""Warn-only module metabolism report.

This script turns broad repository-shape signals into an advisory report. It is
not a gate: high split pressure, duplicate-looking files, cycles, and missing
test references never change the exit code.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_INCLUDE = ("dharma_swarm",)
SIMILARITY_THRESHOLD = 0.75
STOP_TOKENS = {
    "Any", "False", "None", "True", "class", "def", "dict", "from",
    "import", "int", "list", "return", "self", "str", "with",
}
SIDE_EFFECT_PATTERNS: dict[str, re.Pattern[str]] = {
    "open": re.compile(r"\bopen\s*\("),
    "write_text": re.compile(r"\bwrite_text\s*\("),
    "sqlite": re.compile(r"\bsqlite3?\b|\baiosqlite\b|\.db\b"),
    "subprocess": re.compile(r"\bsubprocess\b"),
    "Path.home": re.compile(r"\bPath\.home\s*\("),
    "jsonl": re.compile(r"\bjsonl\b|\.jsonl\b"),
    "emit": re.compile(r"\bemit\s*\("),
    "create_task": re.compile(r"\bcreate_task\s*\("),
    "requests/http": re.compile(r"\brequests\b|\bhttpx\b|https?://"),
    "os.environ": re.compile(r"\bos\.environ\b"),
    ".dharma": re.compile(r"\.dharma"),
    "json_write": re.compile(r"\bjson\.dump\s*\(|\bjson\.dumps\s*\("),
}
BRANCH_NODES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
    ast.BoolOp, ast.IfExp, ast.Match,
)


@dataclass
class FunctionSize:
    name: str
    start_line: int
    line_count: int
    branch_count: int


@dataclass
class ModuleReport:
    path: str
    module: str
    family: str
    line_count: int
    import_count: int
    class_count: int
    function_count: int
    public_api_count: int
    public_api_names: list[str]
    longest_functions: list[FunctionSize]
    branch_count: int
    side_effect_hits: dict[str, int]
    inbound_imports: int = 0
    outbound_imports: int = 0
    no_inbound: bool = False
    cycle_member: bool = False
    test_reference_count: int = 0
    suggested_action: str = "keep"
    flags: list[str] = field(default_factory=list)
    parse_error: str | None = None


@dataclass
class SimilarityPair:
    left: str
    right: str
    score: float


@dataclass
class PortfolioSummary:
    module_count: int
    root_module_count: int
    total_lines: int
    over_500_lines: int
    over_1000_lines: int
    over_3000_lines: int
    no_inbound_count: int
    root_no_inbound_count: int
    cycle_module_count: int
    high_similarity_pair_count: int
    families: dict[str, int]
    global_flags: list[str]


@dataclass
class MetabolismReport:
    summary: PortfolioSummary
    modules: list[ModuleReport]
    similarity_pairs: list[SimilarityPair]


def repo_root_from(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


def iter_python_files(repo_root: Path, targets: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for raw in targets:
        path = (repo_root / raw).resolve()
        if not path.exists():
            continue
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(
                p
                for p in path.rglob("*.py")
                if p.is_file() and "__pycache__" not in p.parts
            )
    return sorted(dict.fromkeys(files))


def module_name(repo_root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(repo_root)
    return ".".join(rel.with_suffix("").parts)


def module_family(repo_root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(repo_root)
    parts = rel.parts
    if len(parts) > 2:
        return parts[1]
    stem = path.stem
    if stem == "__init__":
        return "__init__"
    prefix = stem.split("_", 1)[0]
    return f"root:{prefix}"


def node_line_count(node: ast.AST) -> int:
    start = getattr(node, "lineno", 0)
    end = getattr(node, "end_lineno", start)
    return max(0, end - start + 1)


def branch_count(node: ast.AST) -> int:
    return sum(1 for child in ast.walk(node) if isinstance(child, BRANCH_NODES))


def side_effect_hits(text: str) -> dict[str, int]:
    hits: dict[str, int] = {}
    for name, pattern in SIDE_EFFECT_PATTERNS.items():
        count = len(pattern.findall(text))
        if count:
            hits[name] = count
    return hits


def parse_module(repo_root: Path, path: Path) -> ModuleReport:
    text = path.read_text(encoding="utf-8", errors="ignore")
    report = ModuleReport(
        path=str(path.relative_to(repo_root)),
        module=module_name(repo_root, path),
        family=module_family(repo_root, path),
        line_count=len(text.splitlines()) if text else 0,
        import_count=0,
        class_count=0,
        function_count=0,
        public_api_count=0,
        public_api_names=[],
        longest_functions=[],
        branch_count=0,
        side_effect_hits=side_effect_hits(text),
    )
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        report.parse_error = f"{exc.lineno}:{exc.msg}"
        report.flags.append("parse_error")
        return report

    functions: list[FunctionSize] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            report.import_count += 1
        elif isinstance(node, ast.ClassDef):
            report.class_count += 1
            if not node.name.startswith("_"):
                report.public_api_names.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            report.function_count += 1
            if not node.name.startswith("_"):
                report.public_api_names.append(node.name)
            functions.append(
                FunctionSize(node.name, node.lineno, node_line_count(node), branch_count(node))
            )

    report.public_api_count = len(report.public_api_names)
    report.longest_functions = sorted(
        functions, key=lambda item: item.line_count, reverse=True
    )[:5]
    report.branch_count = branch_count(tree)
    return report


def import_targets(tree: ast.AST, current_module: str, known_modules: set[str]) -> set[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = resolve_import(alias.name, known_modules)
                if target:
                    targets.add(target)
            continue
        if isinstance(node, ast.ImportFrom):
            raw_module = resolve_relative_import(current_module, node)
            if raw_module:
                target = resolve_import(raw_module, known_modules)
                if target:
                    targets.add(target)
    targets.discard(current_module)
    return targets


def resolve_relative_import(current_module: str, node: ast.ImportFrom) -> str:
    module = node.module or ""
    if node.level == 0:
        return module
    base_parts = current_module.split(".")[:-1]
    keep = max(0, len(base_parts) - (node.level - 1))
    prefix = base_parts[:keep]
    if module:
        prefix.extend(module.split("."))
    return ".".join(prefix)


def resolve_import(raw_module: str, known_modules: set[str]) -> str | None:
    if not raw_module.startswith("dharma_swarm"):
        return None
    parts = raw_module.split(".")
    for length in range(len(parts), 1, -1):
        candidate = ".".join(parts[:length])
        if candidate in known_modules:
            return candidate
    return None


def build_import_graph(
    repo_root: Path, files: list[Path], reports_by_module: dict[str, ModuleReport]
) -> dict[str, set[str]]:
    known_modules = set(reports_by_module)
    graph: dict[str, set[str]] = {name: set() for name in known_modules}
    for path in files:
        current = module_name(repo_root, path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        graph[current] = import_targets(tree, current, known_modules)

    inbound: Counter[str] = Counter()
    for source, targets in graph.items():
        reports_by_module[source].outbound_imports = len(targets)
        for target in targets:
            inbound[target] += 1
    for module, report in reports_by_module.items():
        report.inbound_imports = inbound[module]
        report.no_inbound = inbound[module] == 0
    return graph


def cycle_members(graph: dict[str, set[str]]) -> set[str]:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    members: set[str] = set()

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in graph.get(node, set()):
            if target not in indices:
                strongconnect(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1 or node in graph.get(node, set()):
                members.update(component)

    for node in graph:
        if node not in indices:
            strongconnect(node)
    return members


def collect_test_files(repo_root: Path) -> list[tuple[Path, str]]:
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return []
    test_files: list[tuple[Path, str]] = []
    for path in sorted(tests_dir.rglob("*.py")):
        try:
            test_files.append((path, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return test_files


def count_test_references(repo_root: Path, reports: Iterable[ModuleReport]) -> None:
    test_files = collect_test_files(repo_root)
    if not test_files:
        return
    for report in reports:
        stem = Path(report.path).stem
        dotted = report.module
        import_path = report.module.replace(".", "/")
        needles = (
            dotted,
            import_path,
            report.path,
            f"from {dotted} import",
            f"import {dotted}",
            f"from dharma_swarm import {stem}",
        )
        matching_files = 0
        for test_path, text in test_files:
            if any(needle in text for needle in needles) or (
                stem != "__init__" and stem in test_path.name
            ):
                matching_files += 1
        report.test_reference_count = matching_files


def token_set(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        token
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text)
        if token not in STOP_TOKENS and not token.startswith("__")
    }


def similarity_pairs(
    repo_root: Path, files: list[Path], threshold: float
) -> list[SimilarityPair]:
    vectors = [(path, token_set(path)) for path in files]
    vectors = [(path, tokens) for path, tokens in vectors if len(tokens) >= 30]
    pairs: list[SimilarityPair] = []
    for index, (left_path, left_tokens) in enumerate(vectors):
        for right_path, right_tokens in vectors[index + 1 :]:
            union = left_tokens | right_tokens
            if not union:
                continue
            score = len(left_tokens & right_tokens) / len(union)
            if score >= threshold:
                pairs.append(
                    SimilarityPair(
                        left=str(left_path.relative_to(repo_root)),
                        right=str(right_path.relative_to(repo_root)),
                        score=round(score, 4),
                    )
                )
    return sorted(pairs, key=lambda pair: pair.score, reverse=True)


def is_root_package_module(path: str) -> bool:
    return path.startswith("dharma_swarm/") and "/" not in path.removeprefix(
        "dharma_swarm/"
    )


def likely_entrypoint(report: ModuleReport, text: str) -> bool:
    name = Path(report.path).stem
    if 'if __name__ == "__main__"' in text or "if __name__ == '__main__'" in text:
        return True
    entrypoint_terms = ("cli", "daemon", "server", "runner", "supervisor", "main")
    return any(term in name for term in entrypoint_terms)


def add_flags_and_actions(
    repo_root: Path,
    reports: list[ModuleReport],
    pairs: list[SimilarityPair],
) -> None:
    similar_paths = {pair.left for pair in pairs} | {pair.right for pair in pairs}
    family_counts = Counter(report.family for report in reports)
    for report in reports:
        text = (repo_root / report.path).read_text(encoding="utf-8", errors="ignore")
        if likely_entrypoint(report, text):
            report.flags.append("entrypoint_possible")
        if report.test_reference_count == 0:
            report.flags.append("test_signal_missing")
        if report.side_effect_hits:
            report.flags.append("write_surface")
        if report.inbound_imports >= 10:
            report.flags.append("core_hub")
        if report.cycle_member:
            report.flags.append("cycle_member")
        if report.line_count > 1000:
            report.flags.append("large_module")

        if report.path in similar_paths:
            report.suggested_action = "merge-review"
        elif report.inbound_imports >= 10 and report.line_count > 500:
            report.suggested_action = "facade"
        elif report.line_count > 1000 or report.public_api_count >= 30:
            report.suggested_action = "split-review"
        elif is_root_package_module(report.path) and family_counts[report.family] >= 3:
            report.suggested_action = "move-to-package"
        elif report.no_inbound and report.test_reference_count == 0:
            report.suggested_action = "archive-review"
        else:
            report.suggested_action = "keep"


def global_flags(repo_root: Path, reports: list[ModuleReport]) -> list[str]:
    flags: list[str] = []
    manifest = repo_root / "docs" / "governance" / "SOVEREIGN_MANIFEST.md"
    if not manifest.exists():
        return flags
    text = manifest.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"(\d+)\s+files at its top level", text)
    root_count = sum(1 for report in reports if is_root_package_module(report.path))
    if match and int(match.group(1)) != root_count:
        flags.append("doc_claim_stale")
    return flags


def build_report(
    repo_root: Path,
    targets: Iterable[str] = DEFAULT_INCLUDE,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> MetabolismReport:
    files = iter_python_files(repo_root, targets)
    reports = [parse_module(repo_root, path) for path in files]
    reports_by_module = {report.module: report for report in reports}
    graph = build_import_graph(repo_root, files, reports_by_module)
    cycle_set = cycle_members(graph)
    for module in cycle_set:
        reports_by_module[module].cycle_member = True
    count_test_references(repo_root, reports)
    pairs = similarity_pairs(repo_root, files, similarity_threshold)
    add_flags_and_actions(repo_root, reports, pairs)

    root_modules = [report for report in reports if is_root_package_module(report.path)]
    summary = PortfolioSummary(
        module_count=len(reports),
        root_module_count=len(root_modules),
        total_lines=sum(report.line_count for report in reports),
        over_500_lines=sum(1 for report in reports if report.line_count > 500),
        over_1000_lines=sum(1 for report in reports if report.line_count > 1000),
        over_3000_lines=sum(1 for report in reports if report.line_count > 3000),
        no_inbound_count=sum(1 for report in reports if report.no_inbound),
        root_no_inbound_count=sum(1 for report in root_modules if report.no_inbound),
        cycle_module_count=len(cycle_set),
        high_similarity_pair_count=len(pairs),
        families=dict(sorted(Counter(report.family for report in reports).items())),
        global_flags=global_flags(repo_root, reports),
    )
    return MetabolismReport(
        summary=summary,
        modules=sorted(reports, key=lambda report: report.path),
        similarity_pairs=pairs,
    )


def print_text_report(report: MetabolismReport) -> None:
    summary = report.summary
    print("Module Metabolism Report (warn-only)")
    print("=" * 42)
    for label, value in (
        ("Modules", summary.module_count),
        ("Root modules", summary.root_module_count),
        ("Total lines", summary.total_lines),
        (">500 LOC", summary.over_500_lines),
        (">1000 LOC", summary.over_1000_lines),
        (">3000 LOC", summary.over_3000_lines),
        ("No inbound imports", summary.no_inbound_count),
        ("Root no inbound imports", summary.root_no_inbound_count),
        ("Cycle modules", summary.cycle_module_count),
        ("High-similarity pairs", summary.high_similarity_pair_count),
    ):
        print(f"{label}: {value}")
    if summary.global_flags:
        print(f"Global flags: {', '.join(summary.global_flags)}")

    print()
    print("Similarity Pairs")
    print("-" * 42)
    for pair in report.similarity_pairs[:20]:
        print(f"{pair.score:.2f}  {pair.left} <> {pair.right}")
    if not report.similarity_pairs:
        print("None above threshold.")

    print()
    print("Top Metabolism Queue")
    print("-" * 42)
    priority = {"merge-review": 0, "facade": 1, "split-review": 2,
                "move-to-package": 3, "archive-review": 4, "keep": 5}
    ranked = sorted(
        report.modules,
        key=lambda item: (
            priority.get(item.suggested_action, 9),
            -item.line_count,
            item.path,
        ),
    )
    for module in ranked[:40]:
        flags = f" [{', '.join(module.flags)}]" if module.flags else ""
        print(
            f"{module.suggested_action:16} {module.line_count:5} LOC "
            f"in={module.inbound_imports:3} out={module.outbound_imports:3} "
            f"tests={module.test_reference_count:3} {module.path}{flags}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets", nargs="*", default=list(DEFAULT_INCLUDE),
        help="Python files or directories to scan, relative to repo root.",
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    parser.add_argument(
        "--similarity-threshold", type=float, default=SIMILARITY_THRESHOLD,
        help="Jaccard token threshold for merge-review pairs.",
    )
    args = parser.parse_args(argv)

    root = (args.repo_root.resolve() if args.repo_root else repo_root_from())
    report = build_report(
        repo_root=root,
        targets=args.targets,
        similarity_threshold=args.similarity_threshold,
    )
    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
