"""Warn-only capsule coherence report for Python modules.

This is an advisory script. It prints objective module-shape signals and never
turns split pressure into a pass/fail gate.

Usage:
    python3 scripts/governance/capsule_coherence_report.py path/to/module.py
    python3 scripts/governance/capsule_coherence_report.py --json path/to/module.py
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence, TextIO

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LONGEST_LIMIT = 5

SIDE_EFFECT_PATTERNS: dict[str, re.Pattern[str]] = {
    "open": re.compile(r"\bopen\s*\("),
    "write_text": re.compile(r"\.write_text\s*\("),
    "sqlite": re.compile(r"\bsqlite(?:3)?\b", re.IGNORECASE),
    "subprocess": re.compile(r"\bsubprocess\b"),
    "Path.home": re.compile(r"\bPath\.home\s*\("),
    "jsonl": re.compile(r"(?:\.jsonl\b|\bjsonl\b)", re.IGNORECASE),
    "emit": re.compile(r"\bemit\b"),
    "create_task": re.compile(r"\bcreate_task\s*\("),
    "requests/http": re.compile(
        r"\b(?:requests|httpx|aiohttp|urllib)\b|https?://", re.IGNORECASE
    ),
    "os.environ": re.compile(r"\bos\.environ\b"),
}

BRANCH_NODE_TYPES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.ExceptHandler,
    ast.IfExp,
    ast.BoolOp,
    ast.Match,
)


@dataclass(frozen=True)
class FunctionMetric:
    name: str
    line_count: int
    branch_count: int
    lineno: int


@dataclass(frozen=True)
class CapsuleReport:
    path: str
    line_count: int
    import_count: int
    class_count: int
    function_count: int
    public_api: list[str]
    likely_public_api_size: int
    longest_functions: list[FunctionMetric]
    branch_count_by_function: dict[str, int]
    side_effect_hits: dict[str, int]
    side_effect_total: int
    test_reference_count: int
    test_reference_files: int
    suggested_split_pressure: str
    split_pressure_score: int
    split_pressure_reasons: list[str]
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _line_count(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def _node_line_count(node: ast.AST) -> int:
    start = getattr(node, "lineno", 0)
    end = getattr(node, "end_lineno", start)
    if not start or not end:
        return 0
    return end - start + 1


def _public_names(tree: ast.Module) -> list[str]:
    top_level_names = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    explicit_exports = _literal_all_exports(tree)
    if explicit_exports is not None:
        top_level_name_set = set(top_level_names)
        return [name for name in explicit_exports if name in top_level_name_set]

    return [name for name in top_level_names if not name.startswith("_")]


def _literal_all_exports(tree: ast.Module) -> list[str] | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (SyntaxError, ValueError):
            return None
        if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
            return list(value)
        return None
    return None


def _qualified_function_metrics(tree: ast.Module) -> list[FunctionMetric]:
    metrics: list[FunctionMetric] = []

    def visit_body(body: Iterable[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                visit_body(node.body, f"{prefix}{node.name}.")
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{node.name}"
                metrics.append(
                    FunctionMetric(
                        name=name,
                        line_count=_node_line_count(node),
                        branch_count=_branch_count(node),
                        lineno=getattr(node, "lineno", 0),
                    )
                )
                visit_body(node.body, f"{name}.")

    visit_body(tree.body)
    return metrics


def _branch_count(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    count = 0

    def visit(node: ast.AST, *, root: bool = False) -> None:
        nonlocal count
        if not root and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, BRANCH_NODE_TYPES):
            count += 1
        if isinstance(node, ast.comprehension):
            count += len(node.ifs)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(function_node, root=True)
    return count


def _side_effect_hits(text: str) -> dict[str, int]:
    return {
        name: len(pattern.findall(text))
        for name, pattern in SIDE_EFFECT_PATTERNS.items()
    }


def _repo_root_for(path: Path) -> Path:
    for candidate in (path.resolve().parent, *path.resolve().parents):
        if (candidate / ".git").exists():
            return candidate
    return REPO_ROOT


def _module_tokens(path: Path, repo_root: Path) -> set[str]:
    tokens = {path.stem}
    try:
        relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        relative = None
    if relative is not None and relative.suffix == ".py":
        tokens.add(".".join(relative.with_suffix("").parts))
    return {token for token in tokens if token}


def _test_reference_counts(path: Path, tests_dir: Path | None) -> tuple[int, int]:
    if tests_dir is None:
        repo_root = _repo_root_for(path)
        tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return 0, 0

    repo_root = tests_dir.parent
    tokens = _module_tokens(path, repo_root)
    if not tokens:
        return 0, 0

    token_pattern = re.compile("|".join(re.escape(token) for token in sorted(tokens, key=len, reverse=True)))
    matching_lines = 0
    matching_files = 0
    for test_path in sorted(tests_dir.rglob("*.py")):
        if not test_path.is_file():
            continue
        file_matched = path.stem in test_path.name
        try:
            lines = test_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            if token_pattern.search(line):
                matching_lines += 1
                file_matched = True
        if file_matched:
            matching_files += 1
    return matching_lines, matching_files


def _split_pressure(
    *,
    line_count: int,
    import_count: int,
    class_count: int,
    function_count: int,
    public_api_size: int,
    function_metrics: Sequence[FunctionMetric],
    side_effect_total: int,
    test_reference_count: int,
) -> tuple[str, int, list[str]]:
    score = 0
    reasons: list[str] = []

    if line_count >= 1000:
        score += 3
        reasons.append("line_count >= 1000")
    elif line_count >= 600:
        score += 2
        reasons.append("line_count >= 600")
    elif line_count >= 300:
        score += 1
        reasons.append("line_count >= 300")

    shape_count = class_count + function_count
    if shape_count >= 50:
        score += 2
        reasons.append("function_count + class_count >= 50")
    elif shape_count >= 25:
        score += 1
        reasons.append("function_count + class_count >= 25")

    if public_api_size >= 20:
        score += 2
        reasons.append("likely_public_api_size >= 20")
    elif public_api_size >= 10:
        score += 1
        reasons.append("likely_public_api_size >= 10")

    if import_count >= 30:
        score += 2
        reasons.append("import_count >= 30")
    elif import_count >= 15:
        score += 1
        reasons.append("import_count >= 15")

    if side_effect_total >= 15:
        score += 2
        reasons.append("side_effect_total >= 15")
    elif side_effect_total >= 5:
        score += 1
        reasons.append("side_effect_total >= 5")

    max_function_lines = max((metric.line_count for metric in function_metrics), default=0)
    if max_function_lines >= 150:
        score += 2
        reasons.append("longest_function_lines >= 150")
    elif max_function_lines >= 80:
        score += 1
        reasons.append("longest_function_lines >= 80")

    max_branches = max((metric.branch_count for metric in function_metrics), default=0)
    if max_branches >= 25:
        score += 2
        reasons.append("max_function_branch_count >= 25")
    elif max_branches >= 12:
        score += 1
        reasons.append("max_function_branch_count >= 12")

    if line_count >= 200 and test_reference_count == 0:
        score += 1
        reasons.append("line_count >= 200 and test_reference_count == 0")

    if score >= 7:
        pressure = "high"
    elif score >= 4:
        pressure = "medium"
    else:
        pressure = "low"
    return pressure, score, reasons


def analyze_file(path: Path | str, *, tests_dir: Path | None = None, longest_limit: int = DEFAULT_LONGEST_LIMIT) -> CapsuleReport:
    module_path = Path(path)
    display_path = str(module_path)
    try:
        text = module_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CapsuleReport(
            path=display_path,
            line_count=0,
            import_count=0,
            class_count=0,
            function_count=0,
            public_api=[],
            likely_public_api_size=0,
            longest_functions=[],
            branch_count_by_function={},
            side_effect_hits={name: 0 for name in SIDE_EFFECT_PATTERNS},
            side_effect_total=0,
            test_reference_count=0,
            test_reference_files=0,
            suggested_split_pressure="low",
            split_pressure_score=0,
            split_pressure_reasons=[],
            error=str(exc),
        )

    try:
        tree = ast.parse(text, filename=str(module_path))
    except SyntaxError as exc:
        return CapsuleReport(
            path=display_path,
            line_count=_line_count(text),
            import_count=0,
            class_count=0,
            function_count=0,
            public_api=[],
            likely_public_api_size=0,
            longest_functions=[],
            branch_count_by_function={},
            side_effect_hits=_side_effect_hits(text),
            side_effect_total=sum(_side_effect_hits(text).values()),
            test_reference_count=0,
            test_reference_files=0,
            suggested_split_pressure="low",
            split_pressure_score=0,
            split_pressure_reasons=[],
            error=f"syntax error: {exc.msg} at line {exc.lineno}",
        )

    import_count = sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
    class_count = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    function_count = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
    public_api = _public_names(tree)
    function_metrics = _qualified_function_metrics(tree)
    longest_functions = sorted(
        function_metrics,
        key=lambda metric: (metric.line_count, metric.branch_count, metric.name),
        reverse=True,
    )[:longest_limit]
    branch_counts = {metric.name: metric.branch_count for metric in function_metrics}
    side_effect_hits = _side_effect_hits(text)
    side_effect_total = sum(side_effect_hits.values())
    test_reference_count, test_reference_files = _test_reference_counts(
        module_path,
        tests_dir,
    )
    split_pressure, split_score, split_reasons = _split_pressure(
        line_count=_line_count(text),
        import_count=import_count,
        class_count=class_count,
        function_count=function_count,
        public_api_size=len(public_api),
        function_metrics=function_metrics,
        side_effect_total=side_effect_total,
        test_reference_count=test_reference_count,
    )

    return CapsuleReport(
        path=display_path,
        line_count=_line_count(text),
        import_count=import_count,
        class_count=class_count,
        function_count=function_count,
        public_api=public_api,
        likely_public_api_size=len(public_api),
        longest_functions=longest_functions,
        branch_count_by_function=branch_counts,
        side_effect_hits=side_effect_hits,
        side_effect_total=side_effect_total,
        test_reference_count=test_reference_count,
        test_reference_files=test_reference_files,
        suggested_split_pressure=split_pressure,
        split_pressure_score=split_score,
        split_pressure_reasons=split_reasons,
    )


def analyze_files(paths: Sequence[str], *, longest_limit: int = DEFAULT_LONGEST_LIMIT) -> list[CapsuleReport]:
    return [analyze_file(path, longest_limit=longest_limit) for path in paths]


def _print_text(reports: Sequence[CapsuleReport], stdout: TextIO) -> None:
    for index, report in enumerate(reports):
        if index:
            print("", file=stdout)
        print(f"Capsule coherence report: {report.path}", file=stdout)
        print("-" * 72, file=stdout)
        if report.error:
            print(f"error: {report.error}", file=stdout)
        print(f"lines: {report.line_count}", file=stdout)
        print(f"imports: {report.import_count}", file=stdout)
        print(f"classes: {report.class_count}", file=stdout)
        print(f"functions: {report.function_count}", file=stdout)
        print(f"likely public API size: {report.likely_public_api_size}", file=stdout)
        public_api = ", ".join(report.public_api) if report.public_api else "(none)"
        print(f"public functions/classes: {public_api}", file=stdout)
        print(
            f"test references: {report.test_reference_count} lines across "
            f"{report.test_reference_files} files",
            file=stdout,
        )
        print(
            f"suggested split pressure: {report.suggested_split_pressure} "
            f"(score {report.split_pressure_score})",
            file=stdout,
        )
        if report.split_pressure_reasons:
            print(f"split pressure reasons: {', '.join(report.split_pressure_reasons)}", file=stdout)

        print("side-effect keyword hits:", file=stdout)
        for name, count in report.side_effect_hits.items():
            print(f"  {name}: {count}", file=stdout)

        print("longest functions:", file=stdout)
        if report.longest_functions:
            for metric in report.longest_functions:
                print(
                    f"  {metric.name}: {metric.line_count} lines, "
                    f"{metric.branch_count} branches (line {metric.lineno})",
                    file=stdout,
                )
        else:
            print("  (none)", file=stdout)

        print("branch counts by function:", file=stdout)
        if report.branch_count_by_function:
            for name, count in sorted(
                report.branch_count_by_function.items(),
                key=lambda item: (-item[1], item[0]),
            ):
                print(f"  {name}: {count}", file=stdout)
        else:
            print("  (none)", file=stdout)


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Python files to inspect.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--longest-limit",
        type=int,
        default=DEFAULT_LONGEST_LIMIT,
        help=f"Number of longest functions to report (default: {DEFAULT_LONGEST_LIMIT}).",
    )
    args = parser.parse_args(argv)

    reports = analyze_files(args.paths, longest_limit=max(0, args.longest_limit))
    if args.json:
        json.dump([report.to_dict() for report in reports], stdout, indent=2, sort_keys=True)
        print(file=stdout)
    else:
        _print_text(reports, stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
