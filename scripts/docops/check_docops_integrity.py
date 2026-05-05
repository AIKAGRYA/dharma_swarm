#!/usr/bin/env python3
"""DocOps integrity checks for machine-verifiable documentation claims.

The config file is intentionally a JSON-compatible YAML subset. That keeps the
gate stdlib-only while preserving the requested docs/docops/assertions.yaml
location and extension.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CONFIG = Path("docs/docops/assertions.yaml")
IGNORE_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
AUTHORITY_TERMS = (
    "source of truth",
    "canonical",
    "authoritative",
    "ground truth",
)
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
CODE_PATH_RE = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:md|py|yaml|yml|json|toml|sh|ts|tsx|js|jsx|txt)(?::\d+)?)`"
)
AUTO_START_RE = re.compile(r"<!--\s*DOCOPS:START\s+([^>]+?)\s*-->")
AUTO_END = "<!-- DOCOPS:END -->"


@dataclass(frozen=True)
class Finding:
    severity: str
    check: str
    message: str

    def render(self) -> str:
        return f"{self.severity}: {self.check}: {self.message}"


@dataclass(frozen=True)
class PathReference:
    doc: Path
    target: str
    line: int


def repo_relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def is_ignored(path: Path, repo_root: Path) -> bool:
    rel_parts = path.resolve().relative_to(repo_root.resolve()).parts
    return any(part in IGNORE_DIR_NAMES for part in rel_parts)


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        config = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{path}: DocOps v0 expects JSON-compatible YAML: {exc}"
        ) from exc
    if not isinstance(config, dict):
        raise SystemExit(f"{path}: top-level config must be an object")
    return config


def iter_files(repo_root: Path, patterns: Iterable[str]) -> list[Path]:
    paths: set[Path] = set()
    for pattern in patterns:
        for path in repo_root.glob(pattern):
            if path.is_file() and not is_ignored(path, repo_root):
                paths.add(path)
    return sorted(paths)


def count_files(repo_root: Path, pattern: str) -> int:
    return sum(
        1
        for path in repo_root.glob(pattern)
        if path.is_file() and not is_ignored(path, repo_root)
    )


def count_paths_containing(repo_root: Path, pattern: str, needle: str) -> int:
    return sum(
        1
        for path in repo_root.glob(pattern)
        if path.is_file()
        and not is_ignored(path, repo_root)
        and needle.lower() in path.as_posix().lower()
    )


def count_regex(repo_root: Path, pattern: str, regex: str) -> int:
    compiled = re.compile(regex)
    count = 0
    for path in repo_root.glob(pattern):
        if path.is_file() and not is_ignored(path, repo_root):
            count += len(compiled.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return count


def total_lines(repo_root: Path, pattern: str) -> int:
    total = 0
    for path in repo_root.glob(pattern):
        if path.is_file() and not is_ignored(path, repo_root):
            total += path.read_bytes().count(b"\n")
    return total


def count_frontmatter(repo_root: Path, pattern: str) -> int:
    count = 0
    for path in repo_root.glob(pattern):
        if path.is_file() and not is_ignored(path, repo_root):
            if path.read_text(encoding="utf-8", errors="ignore").startswith("---\n"):
                count += 1
    return count


def count_authority_candidate_docs(repo_root: Path) -> int:
    count = 0
    for path in repo_root.glob("**/*.md"):
        if path.is_file() and not is_ignored(path, repo_root):
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if any(term in text for term in AUTHORITY_TERMS):
                count += 1
    return count


def collect_metrics(repo_root: Path) -> dict[str, int]:
    return {
        "dharma_python_modules": count_files(repo_root, "dharma_swarm/**/*.py"),
        "dharma_top_level_python_modules": count_files(repo_root, "dharma_swarm/*.py"),
        "total_python_loc": total_lines(repo_root, "dharma_swarm/**/*.py"),
        "test_files": count_files(repo_root, "tests/**/*.py"),
        "test_def_occurrences": count_regex(repo_root, "tests/**/*.py", r"def test_"),
        "markdown_files": count_files(repo_root, "**/*.md"),
        "markdown_total_lines": total_lines(repo_root, "**/*.md"),
        "bridge_files": count_files(repo_root, "dharma_swarm/**/*bridge*.py"),
        "adapter_files": count_paths_containing(repo_root, "dharma_swarm/**/*.py", "adapter"),
        "orchestrator_files": count_files(repo_root, "dharma_swarm/**/*orchestrat*.py"),
        "router_files": count_paths_containing(repo_root, "dharma_swarm/**/*.py", "rout"),
        "frontmatter_markdown_files": count_frontmatter(repo_root, "**/*.md"),
        "architecture_markdown_files": count_files(repo_root, "docs/architecture/*.md"),
        "authority_candidate_docs": count_authority_candidate_docs(repo_root),
    }


def check_assertions(
    repo_root: Path, config: dict[str, Any], metrics: dict[str, int]
) -> list[Finding]:
    findings: list[Finding] = []
    for assertion in config.get("assertions", []):
        assertion_id = assertion.get("id", "<missing-id>")
        doc_path = repo_root / assertion["doc"]
        if not doc_path.exists():
            findings.append(
                Finding("FAIL", "assertion", f"{assertion_id}: missing doc {doc_path}")
            )
            continue
        metric_name = assertion["metric"]
        expected = metrics.get(metric_name)
        if expected is None:
            findings.append(
                Finding("FAIL", "assertion", f"{assertion_id}: unknown metric {metric_name}")
            )
            continue
        text = doc_path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(assertion["regex"], text, flags=re.MULTILINE)
        if not match:
            findings.append(
                Finding(
                    "FAIL",
                    "assertion",
                    f"{assertion_id}: regex did not match {assertion['doc']}",
                )
            )
            continue
        observed = match.group(1).replace(",", "")
        if str(expected) != observed:
            verify = assertion.get("verify", metric_name)
            findings.append(
                Finding(
                    "FAIL",
                    "assertion",
                    (
                        f"{assertion_id}: doc says {observed}, "
                        f"{metric_name} is {expected}; verify with `{verify}`"
                    ),
                )
            )
    return findings


def should_ignore_target(target: str, ignore_patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(target, pattern) for pattern in ignore_patterns)


def strip_target(target: str) -> str:
    target = target.strip().strip("<>").strip()
    if "#" in target:
        target = target.split("#", 1)[0]
    target = re.sub(r":\d+$", "", target)
    return target.strip()


def extract_path_references(doc: Path) -> list[PathReference]:
    refs: list[PathReference] = []
    lines = doc.read_text(encoding="utf-8", errors="ignore").splitlines()
    for lineno, line in enumerate(lines, start=1):
        for match in MARKDOWN_LINK_RE.finditer(line):
            refs.append(PathReference(doc=doc, target=match.group(1), line=lineno))
        for match in CODE_PATH_RE.finditer(line):
            refs.append(PathReference(doc=doc, target=match.group(1), line=lineno))
    return refs


def target_exists(repo_root: Path, doc: Path, target: str) -> bool:
    stripped = strip_target(target)
    if not stripped:
        return True
    if any(char in stripped for char in "*?{}$"):
        return True
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", stripped):
        return True

    prefix = "/Users/dhyana/dharma_swarm/"
    if stripped.startswith(prefix):
        stripped = stripped.removeprefix(prefix)

    candidates: list[Path] = []
    if stripped.startswith("/"):
        candidates.append(repo_root / stripped.lstrip("/"))
    else:
        candidates.extend(
            [
                doc.parent / stripped,
                repo_root / stripped,
                repo_root / "dharma_swarm" / stripped,
                repo_root / "scripts" / stripped,
                repo_root / "docs" / stripped,
                repo_root / "docs" / "governance" / stripped,
                repo_root / "docs" / "architecture" / stripped,
                repo_root / "docs" / "plans" / stripped,
                repo_root / "specs" / stripped,
            ]
        )
    return any(candidate.exists() for candidate in candidates)


def check_path_guards(repo_root: Path, config: dict[str, Any]) -> list[Finding]:
    path_config = config.get("path_guards", {})
    docs = iter_files(repo_root, path_config.get("include", []))
    ignore_targets = path_config.get("ignore_targets", [])
    findings: list[Finding] = []
    for doc in docs:
        for ref in extract_path_references(doc):
            if should_ignore_target(ref.target, ignore_targets):
                continue
            if not target_exists(repo_root, doc, ref.target):
                findings.append(
                    Finding(
                        "FAIL",
                        "path",
                        (
                            f"{repo_relative(doc, repo_root)}:{ref.line}: "
                            f"missing referenced path `{ref.target}`"
                        ),
                    )
                )
    return findings


def doc_contains_authority_claim(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return any(term in text for term in AUTHORITY_TERMS)


def check_canonical_guard(
    repo_root: Path,
    config: dict[str, Any],
    changed_files: list[str] | None,
) -> list[Finding]:
    guard = config.get("canonical_guard", {})
    registered = set(guard.get("registered", []))
    patterns = guard.get("managed_include", [])
    files = {repo_relative(path, repo_root): path for path in iter_files(repo_root, patterns)}

    if changed_files:
        changed_patterns = guard.get("changed_include", ["**/*.md"])
        for rel in changed_files:
            if not rel.endswith(".md"):
                continue
            if any(fnmatch.fnmatch(rel, pattern) for pattern in changed_patterns):
                path = repo_root / rel
                if path.exists() and path.is_file():
                    files[rel] = path

    findings: list[Finding] = []
    for rel, path in sorted(files.items()):
        if rel in registered:
            continue
        if doc_contains_authority_claim(path):
            findings.append(
                Finding(
                    "FAIL",
                    "canonical",
                    (
                        f"{rel} contains an authority term but is not registered "
                        "in docs/governance/CANONICAL_DOC_STACK.md"
                    ),
                )
            )
    return findings


def git_changed_files(repo_root: Path, base_ref: str | None) -> list[str]:
    if not base_ref:
        return []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{base_ref}...HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def doc_review_candidates(
    repo_root: Path, config: dict[str, Any], changed_files: list[str]
) -> list[Finding]:
    changed_python = [rel for rel in changed_files if rel.endswith(".py")]
    if not changed_python:
        return []

    doc_patterns = config.get("change_review", {}).get("doc_include", ["**/*.md"])
    docs = iter_files(repo_root, doc_patterns)
    findings: list[Finding] = []
    for py_file in changed_python:
        basename = Path(py_file).name
        matches: list[str] = []
        for doc in docs:
            text = doc.read_text(encoding="utf-8", errors="ignore")
            if py_file in text or basename in text:
                matches.append(repo_relative(doc, repo_root))
        if matches:
            rendered = ", ".join(matches[:8])
            extra = "" if len(matches) <= 8 else f", +{len(matches) - 8} more"
            findings.append(
                Finding(
                    "WARN",
                    "change-review",
                    f"{py_file} is referenced by docs: {rendered}{extra}",
                )
            )
    return findings


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def check_staleness(config: dict[str, Any], today: date) -> list[Finding]:
    verified_at = config.get("verified_at")
    ttl_days = int(config.get("ttl_days", 0) or 0)
    if not verified_at or ttl_days <= 0:
        return []
    verified = parse_iso_date(verified_at)
    expires = verified + timedelta(days=ttl_days)
    if today > expires:
        return [
            Finding(
                "FAIL",
                "staleness",
                (
                    f"DocOps assertions expired on {expires.isoformat()} "
                    f"(verified_at={verified_at}, ttl_days={ttl_days})"
                ),
            )
        ]
    return []


def parse_attrs(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for part in raw.split():
        if "=" in part:
            key, value = part.split("=", 1)
            attrs[key.strip()] = value.strip().strip('"')
    return attrs


def render_repo_inventory(metrics: dict[str, int]) -> str:
    rows = [
        ("Dharma Python modules", "dharma_python_modules"),
        ("Top-level Dharma Python modules", "dharma_top_level_python_modules"),
        ("Dharma Python LOC", "total_python_loc"),
        ("Test files", "test_files"),
        ("Test function occurrences", "test_def_occurrences"),
        ("Markdown files", "markdown_files"),
        ("Markdown total lines", "markdown_total_lines"),
        ("Bridge files", "bridge_files"),
        ("Adapter files", "adapter_files"),
        ("Orchestrator files", "orchestrator_files"),
        ("Router files", "router_files"),
        ("Authority candidate docs", "authority_candidate_docs"),
    ]
    lines = ["| Metric | Value |", "|---|---:|"]
    for label, key in rows:
        lines.append(f"| {label} | {metrics[key]:,} |")
    return "\n".join(lines)


def generated_section(attrs: dict[str, str], metrics: dict[str, int]) -> str:
    metric = attrs.get("metric")
    if metric == "repo_inventory":
        return render_repo_inventory(metrics)
    raise ValueError(f"unknown auto section metric: {metric}")


def rewrite_auto_sections(text: str, metrics: dict[str, int]) -> tuple[str, bool]:
    output: list[str] = []
    pos = 0
    changed = False
    while True:
        start = AUTO_START_RE.search(text, pos)
        if not start:
            output.append(text[pos:])
            break
        end = text.find(AUTO_END, start.end())
        if end == -1:
            output.append(text[pos:])
            break
        end_content = end + len(AUTO_END)
        attrs = parse_attrs(start.group(1))
        generated = generated_section(attrs, metrics)
        replacement = f"{start.group(0)}\n{generated}\n{AUTO_END}"
        output.append(text[pos : start.start()])
        output.append(replacement)
        if text[start.start() : end_content] != replacement:
            changed = True
        pos = end_content
    return "".join(output), changed


def check_or_write_auto_sections(
    repo_root: Path, config: dict[str, Any], metrics: dict[str, int], write: bool
) -> list[Finding]:
    findings: list[Finding] = []
    patterns = config.get("auto_sections", {}).get("include", [])
    for doc in iter_files(repo_root, patterns):
        text = doc.read_text(encoding="utf-8", errors="ignore")
        try:
            rewritten, changed = rewrite_auto_sections(text, metrics)
        except ValueError as exc:
            findings.append(
                Finding("FAIL", "auto-section", f"{repo_relative(doc, repo_root)}: {exc}")
            )
            continue
        if not changed:
            continue
        if write:
            doc.write_text(rewritten, encoding="utf-8")
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "auto-section",
                    (
                        f"{repo_relative(doc, repo_root)} has stale generated content; "
                        "rerun with --write-auto-sections"
                    ),
                )
            )
    return findings


def run_checks(
    repo_root: Path,
    config_path: Path,
    changed_from: str | None,
    today: date,
    write_auto_sections: bool,
) -> tuple[list[Finding], dict[str, int]]:
    config = load_config(config_path)
    metrics = collect_metrics(repo_root)
    changed_files = git_changed_files(repo_root, changed_from)

    findings: list[Finding] = []
    findings.extend(check_staleness(config, today))
    findings.extend(check_assertions(repo_root, config, metrics))
    findings.extend(check_path_guards(repo_root, config))
    findings.extend(check_canonical_guard(repo_root, config, changed_files))
    findings.extend(check_or_write_auto_sections(repo_root, config, metrics, write_auto_sections))
    findings.extend(doc_review_candidates(repo_root, config, changed_files))
    return findings, metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--assertions", default=DEFAULT_CONFIG, type=Path)
    parser.add_argument("--changed-from")
    parser.add_argument("--today")
    parser.add_argument("--write-auto-sections", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    config_path = args.assertions
    if not config_path.is_absolute():
        config_path = repo_root / config_path
    today = parse_iso_date(args.today) if args.today else date.today()

    findings, metrics = run_checks(
        repo_root=repo_root,
        config_path=config_path,
        changed_from=args.changed_from,
        today=today,
        write_auto_sections=args.write_auto_sections,
    )
    for key in sorted(metrics):
        print(f"metric {key}={metrics[key]}")
    for finding in findings:
        print(finding.render())
    failures = [finding for finding in findings if finding.severity == "FAIL"]
    if failures:
        return 1
    print("DocOps integrity checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
