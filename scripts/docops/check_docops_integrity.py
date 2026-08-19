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
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CONFIG = Path("docs/docops/assertions.yaml")
CANONICAL_ROOT_AGENTS_BYTES = (
    b"# Agent entrypoint\n"
    b"\n"
    b"Run `make onboard` before non-trivial work.\n"
    b"It reports session status; it does not grant permission to edit.\n"
    b"Use `make agent-build-preflight PACKET=<path>` for exact edit admission.\n"
    b"The canonical behavioral contract is `CLAUDE.md`; this file must never duplicate it.\n"
    b"For purpose/vision context when designing (optional): `make vision`. It grants nothing.\n"
    b"Return the startup readback printed by onboarding before editing.\n"
)
IGNORE_DIR_NAMES = {
    ".git",
    ".claude",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
IGNORE_REL_PATTERNS = (
    "AGENTS.md",
    "reports/docops/**",
    # Machine-generated loop/forge output (gitignored 2026-06-10; 500k+ files).
    # Runtime metabolism, not repo docs — excluded so doc metrics measure the
    # genome (code + curated docs), not the fleet's report exhaust.
    "reports/revenue_wedge/**",
    "reports/forge/**",
)
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
ABSOLUTE_REPO_PATH_RE = re.compile(r"/Users/dhyana/dharma_swarm/[A-Za-z0-9_./:-]+")
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


@lru_cache(maxsize=8)
def git_tracked_paths(repo_root: str) -> frozenset[str] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return frozenset(path for path in result.stdout.split("\0") if path)


def is_ignored(path: Path, repo_root: Path) -> bool:
    rel = path.resolve().relative_to(repo_root.resolve())
    rel_parts = rel.parts
    rel_text = rel.as_posix()
    tracked = git_tracked_paths(str(repo_root.resolve()))
    if tracked is not None and rel_text not in tracked:
        return True
    if any(fnmatch.fnmatch(rel_text, pattern) for pattern in IGNORE_REL_PATTERNS):
        return True
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
    needle_lower = needle.lower()
    return sum(
        1
        for path in repo_root.glob(pattern)
        if path.is_file()
        and not is_ignored(path, repo_root)
        and needle_lower in path.relative_to(repo_root).as_posix().lower()
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
    repo_root: Path,
    config: dict[str, Any],
    metrics: dict[str, int],
    counts_advisory: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []
    value_severity = "WARN" if counts_advisory else "FAIL"
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
        matches = list(re.finditer(assertion["regex"], text, flags=re.MULTILINE))
        if not matches:
            findings.append(
                Finding(
                    value_severity,
                    "assertion",
                    f"{assertion_id}: regex did not match {assertion['doc']}",
                )
            )
            continue
        # Duplicate-token tripwire: an asserted count must appear EXACTLY once.
        # Refreshes that append instead of replace duplicated the SOVEREIGN
        # MANIFEST count table row-by-row until 2026-07-03 (rows quadruplicated
        # while the checker happily validated the first match). Duplicates are
        # manufactured decay — flag them even when the values agree.
        if len(matches) > 1:
            findings.append(
                Finding(
                    value_severity,
                    "assertion-duplicate",
                    (
                        f"{assertion_id}: asserted token appears {len(matches)}x in "
                        f"{assertion['doc']} — refreshes must REPLACE the row, never "
                        "append; dedupe to exactly one occurrence"
                    ),
                )
            )
        match = matches[0]
        observed = match.group(1).replace(",", "")
        if str(expected) != observed:
            verify = assertion.get("verify", metric_name)
            findings.append(
                Finding(
                    value_severity,
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


def authority_terms_in_text(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in AUTHORITY_TERMS if term in lowered]


def check_canonical_guard(
    repo_root: Path,
    config: dict[str, Any],
    changed_files: list[tuple[str, str]] | None,
) -> list[Finding]:
    guard = config.get("canonical_guard", {})
    registered = set(guard.get("registered", []))
    ignore_patterns = guard.get("ignore", [])
    patterns = guard.get("managed_include", [])
    files = {repo_relative(path, repo_root): path for path in iter_files(repo_root, patterns)}
    findings: list[Finding] = []

    for rel in sorted(registered):
        path = repo_root / rel
        if not path.is_file():
            findings.append(
                Finding(
                    "FAIL",
                    "canonical",
                    f"registered canonical file is missing: {rel}",
                )
            )

    agents_path = repo_root / "AGENTS.md"
    if "AGENTS.md" in registered and agents_path.is_file():
        try:
            agents_bytes = agents_path.read_bytes()
        except OSError as exc:
            findings.append(
                Finding(
                    "FAIL",
                    "canonical",
                    f"registered canonical file is unreadable: AGENTS.md ({exc})",
                )
            )
        else:
            if agents_bytes != CANONICAL_ROOT_AGENTS_BYTES:
                findings.append(
                    Finding(
                        "FAIL",
                        "canonical",
                        (
                            "AGENTS.md must be the byte-exact root pointer; it may not "
                            "duplicate or extend the behavioral contract in CLAUDE.md"
                        ),
                    )
                )

    changed_doc_statuses: dict[str, str] = {}
    if changed_files:
        changed_patterns = guard.get("changed_include", ["**/*.md"])
        for status, rel in changed_files:
            if not rel.endswith(".md"):
                continue
            if any(fnmatch.fnmatch(rel, pattern) for pattern in ignore_patterns):
                continue
            if any(fnmatch.fnmatch(rel, pattern) for pattern in changed_patterns):
                path = repo_root / rel
                if path.exists() and path.is_file():
                    files[rel] = path
                    changed_doc_statuses[rel] = status

    for rel, path in sorted(files.items()):
        if any(fnmatch.fnmatch(rel, pattern) for pattern in ignore_patterns):
            continue
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


def git_changed_file_statuses(
    repo_root: Path, base_ref: str | None
) -> list[tuple[str, str]]:
    if not base_ref:
        return []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", "--diff-filter=ACMRTUXB", f"{base_ref}...HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    statuses: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        rel = parts[-1]
        statuses.append((status, rel))
    return statuses


def git_changed_files(repo_root: Path, base_ref: str | None) -> list[str]:
    return [rel for _status, rel in git_changed_file_statuses(repo_root, base_ref)]


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
    repo_root: Path,
    config: dict[str, Any],
    metrics: dict[str, int],
    write: bool,
    counts_advisory: bool = False,
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
                    "WARN" if counts_advisory else "FAIL",
                    "auto-section",
                    (
                        f"{repo_relative(doc, repo_root)} has stale generated content; "
                        "rerun with --write-auto-sections"
                    ),
                )
            )
    return findings


def _format_count(value: int, sample: str) -> str:
    """Render ``value`` preserving the comma style of the matched ``sample``."""
    return f"{value:,}" if "," in sample else str(value)


def _replace_capture_group(match: re.Match[str], new_value: str) -> str:
    """Return ``match.group(0)`` with capture group 1 replaced by ``new_value``."""
    whole = match.group(0)
    rel_start = match.start(1) - match.start(0)
    rel_end = match.end(1) - match.start(0)
    return whole[:rel_start] + new_value + whole[rel_end:]


def _collapse_duplicate_assertion_lines(
    text: str, assertions: list[dict[str, Any]]
) -> tuple[str, int]:
    """Collapse byte-identical full lines that carry an asserted count token to a
    single occurrence, preserving order (first wins).

    A ``merge=union`` merge appends a whole managed count row a second time; the
    per-match value rewrite above then corrects BOTH copies' values but leaves
    two identical rows, which the ``assertion-duplicate`` tripwire rejects — so
    the writer was not actually idempotent and every doc-touching merge needed a
    hand dedupe. Only exact full-line duplicates that match an assertion regex
    are removed (a distinct row with a coincidentally equal count is never a
    byte-identical line), and an asserted token is required to appear exactly
    once anyway (that is what the tripwire enforces), so collapsing to one is
    consistent with the gate, not a weakening of it.
    """
    patterns = [re.compile(a["regex"]) for a in assertions]
    seen: set[str] = set()
    kept: list[str] = []
    removed = 0
    for line in text.split("\n"):
        if line.strip() and any(p.search(line) for p in patterns):
            if line in seen:
                removed += 1
                continue
            seen.add(line)
        kept.append(line)
    return "\n".join(kept), removed


def write_assertion_counts(
    repo_root: Path, config: dict[str, Any], metrics: dict[str, int]
) -> list[Finding]:
    """Rewrite every asserted count token in place to match live metrics, then
    collapse any merge-duplicated count rows to a single occurrence.

    Driven by the same ``assertions`` config that ``check_assertions`` reads, so
    the writer can never drift from the gate. Each assertion's regex capture
    group is replaced with the live metric value (comma style preserved) for
    every non-overlapping match; then byte-identical duplicate count lines
    (``merge=union`` artifacts) are collapsed. Idempotent and merge-healing.
    """
    findings: list[Finding] = []
    by_doc: dict[Path, list[dict[str, Any]]] = {}
    for assertion in config.get("assertions", []):
        by_doc.setdefault(repo_root / assertion["doc"], []).append(assertion)

    for doc_path, assertions in by_doc.items():
        if not doc_path.exists():
            findings.append(
                Finding("FAIL", "assertion-write", f"missing doc: {doc_path}")
            )
            continue
        text = doc_path.read_text(encoding="utf-8")
        original = text
        for assertion in assertions:
            metric_name = assertion["metric"]
            if metric_name not in metrics:
                findings.append(
                    Finding(
                        "FAIL",
                        "assertion-write",
                        f"{assertion.get('id')}: unknown metric {metric_name}",
                    )
                )
                continue
            expected = metrics[metric_name]
            pattern = re.compile(assertion["regex"], flags=re.MULTILINE)

            def _sub(m: re.Match[str], _expected: int = expected) -> str:
                return _replace_capture_group(m, _format_count(_expected, m.group(1)))

            text = pattern.sub(_sub, text)
        text, collapsed = _collapse_duplicate_assertion_lines(text, assertions)
        if collapsed:
            findings.append(
                Finding(
                    "INFO",
                    "assertion-dedupe",
                    f"{doc_path.name}: collapsed {collapsed} merge-duplicated count "
                    "row(s) to a single occurrence",
                )
            )
        if text != original:
            doc_path.write_text(text, encoding="utf-8")
    return findings


def run_checks(
    repo_root: Path,
    config_path: Path,
    changed_from: str | None,
    today: date,
    write_auto_sections: bool,
    write_manifest_counts: bool = False,
    counts_advisory: bool = False,
) -> tuple[list[Finding], dict[str, int]]:
    config = load_config(config_path)
    metrics = collect_metrics(repo_root)
    changed_file_statuses = git_changed_file_statuses(repo_root, changed_from)
    changed_files = [rel for _status, rel in changed_file_statuses]

    findings: list[Finding] = []
    findings.extend(check_staleness(config, today))
    if write_manifest_counts:
        findings.extend(write_assertion_counts(repo_root, config, metrics))
    findings.extend(check_assertions(repo_root, config, metrics, counts_advisory))
    findings.extend(check_path_guards(repo_root, config))
    findings.extend(check_canonical_guard(repo_root, config, changed_file_statuses))
    findings.extend(
        check_or_write_auto_sections(
            repo_root, config, metrics, write_auto_sections, counts_advisory
        )
    )
    findings.extend(doc_review_candidates(repo_root, config, changed_files))
    return findings, metrics


def finding_to_dict(finding: Finding) -> dict[str, str]:
    return {
        "severity": finding.severity,
        "check": finding.check,
        "message": finding.message,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_report_payload(
    findings: list[Finding], metrics: dict[str, int], today: date
) -> dict[str, Any]:
    failures = [finding for finding in findings if finding.severity == "FAIL"]
    warnings = [finding for finding in findings if finding.severity == "WARN"]
    return {
        "date": today.isoformat(),
        "passed": not failures,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "metrics": metrics,
        "findings": [finding_to_dict(finding) for finding in findings],
    }


def scan_doc_inventory(
    repo_root: Path,
    config: dict[str, Any],
    patterns: Iterable[str],
    missing_limit: int = 200,
) -> dict[str, Any]:
    registered = set(config.get("canonical_guard", {}).get("registered", []))
    ignore_targets = config.get("path_guards", {}).get("ignore_targets", [])
    docs = iter_files(repo_root, patterns)

    authority_docs: list[dict[str, Any]] = []
    frontmatter_docs: list[str] = []
    absolute_path_refs: list[dict[str, Any]] = []
    missing_refs: list[dict[str, Any]] = []
    path_reference_count = 0

    for doc in docs:
        rel = repo_relative(doc, repo_root)
        text = doc.read_text(encoding="utf-8", errors="ignore")
        terms = authority_terms_in_text(text)
        if terms:
            authority_docs.append(
                {
                    "path": rel,
                    "terms": terms,
                    "registered": rel in registered,
                }
            )
        if text.startswith("---\n"):
            frontmatter_docs.append(rel)

        for match in ABSOLUTE_REPO_PATH_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            absolute_path_refs.append(
                {
                    "path": rel,
                    "line": line,
                    "target": match.group(0),
                }
            )

        for ref in extract_path_references(doc):
            if should_ignore_target(ref.target, ignore_targets):
                continue
            path_reference_count += 1
            if len(missing_refs) >= missing_limit:
                continue
            if not target_exists(repo_root, doc, ref.target):
                missing_refs.append(
                    {
                        "path": rel,
                        "line": ref.line,
                        "target": ref.target,
                    }
                )

    unregistered_authority = [
        item for item in authority_docs if not bool(item.get("registered"))
    ]
    return {
        "markdown_files_scanned": len(docs),
        "authority_docs": authority_docs,
        "authority_doc_count": len(authority_docs),
        "unregistered_authority_doc_count": len(unregistered_authority),
        "frontmatter_doc_count": len(frontmatter_docs),
        "frontmatter_docs": frontmatter_docs[:200],
        "absolute_path_ref_count": len(absolute_path_refs),
        "absolute_path_refs": absolute_path_refs[:200],
        "path_reference_count": path_reference_count,
        "missing_reference_count_capped": len(missing_refs),
        "missing_reference_limit": missing_limit,
        "missing_references": missing_refs,
    }


def render_inventory_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# DocOps Corpus Inventory",
        "",
        "This is a non-blocking inventory for doc cleanup agents. The blocking gate",
        "remains `scripts/docops/check_docops_integrity.py` without report flags.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Markdown files scanned | {inventory['markdown_files_scanned']:,} |",
        f"| Authority candidate docs | {inventory['authority_doc_count']:,} |",
        f"| Unregistered authority docs | {inventory['unregistered_authority_doc_count']:,} |",
        f"| Frontmatter docs | {inventory['frontmatter_doc_count']:,} |",
        f"| Absolute repo path references | {inventory['absolute_path_ref_count']:,} |",
        f"| Path references scanned | {inventory['path_reference_count']:,} |",
        f"| Missing references reported | {inventory['missing_reference_count_capped']:,} |",
        "",
        "## Unregistered Authority Docs",
        "",
    ]
    unregistered = [
        item for item in inventory["authority_docs"] if not bool(item.get("registered"))
    ]
    if not unregistered:
        lines.append("None found.")
    else:
        lines.extend(["| Path | Terms |", "|---|---|"])
        for item in unregistered[:80]:
            terms = ", ".join(item["terms"])
            lines.append(f"| `{item['path']}` | {terms} |")

    lines.extend(["", "## Absolute Repo Path References", ""])
    if not inventory["absolute_path_refs"]:
        lines.append("None found.")
    else:
        lines.extend(["| Path | Line | Target |", "|---|---:|---|"])
        for item in inventory["absolute_path_refs"][:80]:
            lines.append(f"| `{item['path']}` | {item['line']} | `{item['target']}` |")

    lines.extend(["", "## Missing References", ""])
    if not inventory["missing_references"]:
        lines.append("None found.")
    else:
        lines.extend(["| Path | Line | Target |", "|---|---:|---|"])
        for item in inventory["missing_references"][:80]:
            lines.append(f"| `{item['path']}` | {item['line']} | `{item['target']}` |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--assertions", default=DEFAULT_CONFIG, type=Path)
    parser.add_argument("--changed-from")
    parser.add_argument("--today")
    parser.add_argument("--write-auto-sections", action="store_true")
    parser.add_argument(
        "--write-manifest-counts",
        action="store_true",
        help=(
            "Rewrite asserted count tokens (e.g. SOVEREIGN_MANIFEST counts) in "
            "place to match live metrics. Used by the push:main reconcile job."
        ),
    )
    parser.add_argument(
        "--counts-advisory",
        action="store_true",
        help=(
            "Downgrade generated-count drift (SOVEREIGN_MANIFEST count assertions "
            "and AUTO_INVENTORY auto-sections) from FAIL to WARN. Counts are "
            "reconciled on main by docops-reconcile-main.yml, so PRs and the "
            "merge queue never gate on them. Structural problems (missing doc, "
            "unknown metric, bad auto-section config) still FAIL."
        ),
    )
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--inventory-json", type=Path)
    parser.add_argument("--inventory-markdown", type=Path)
    parser.add_argument(
        "--inventory-glob",
        action="append",
        default=[],
        help="Markdown glob for non-blocking corpus inventory; defaults to **/*.md.",
    )
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
        write_manifest_counts=args.write_manifest_counts,
        counts_advisory=args.counts_advisory,
    )
    if args.report_json:
        report_path = args.report_json
        if not report_path.is_absolute():
            report_path = repo_root / report_path
        write_json(report_path, check_report_payload(findings, metrics, today))

    if args.inventory_json or args.inventory_markdown:
        config = load_config(config_path)
        patterns = args.inventory_glob or ["**/*.md"]
        inventory = scan_doc_inventory(repo_root, config, patterns)
        if args.inventory_json:
            inventory_json = args.inventory_json
            if not inventory_json.is_absolute():
                inventory_json = repo_root / inventory_json
            write_json(inventory_json, inventory)
        if args.inventory_markdown:
            inventory_markdown = args.inventory_markdown
            if not inventory_markdown.is_absolute():
                inventory_markdown = repo_root / inventory_markdown
            inventory_markdown.parent.mkdir(parents=True, exist_ok=True)
            inventory_markdown.write_text(
                render_inventory_markdown(inventory), encoding="utf-8"
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
