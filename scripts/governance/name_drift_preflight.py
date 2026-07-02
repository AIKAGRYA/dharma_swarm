#!/usr/bin/env python3
"""Scan naming-drift evidence and route it into DE_BUG_CORRAL.

This is a read-only preflight. It does not decide whether a finding is true;
it locates the latest files that talk about naming drift, alias drift, name
mismatches, and Corral path drift, then tells the operator which numbered
DE_BUG_CORRAL file should own or point to each item.

Default output is human-readable stdout. Cron should write receipts outside
the worktree, for example:

    python3 scripts/governance/name_drift_preflight.py \
      --json-output ~/.dharma/logs/name_drift_preflight_latest.json \
      --markdown-output ~/.dharma/logs/name_drift_preflight_latest.md
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CANONICAL_CORRAL = Path("DE_BUG_CORRAL")
CORRAL_INDEX = CANONICAL_CORRAL / "00.md"

try:
    from scripts.governance.agent_admission import validate_semantic_commons
except Exception:  # pragma: no cover - surfaced in payload
    validate_semantic_commons = None  # type: ignore[assignment]

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "node_modules",
}
SKIP_PATH_PREFIXES = (
    "tests/",
    "DE_BUG_CORRAL/",
    "docs/governance/hygiene/baselines/",
    "reports/governance/name_drift_preflight_",
)
SKIP_EXACT_PATHS = {
    "scripts/governance/agent_onboard.py",
    "scripts/governance/agent_admission.py",
    "scripts/governance/agent_admission_projection.py",
    "scripts/governance/name_drift_preflight.py",
    "reports/governance/active_track_evidence.json",
    "reports/governance/semantic_commons_projection_manifest.json",
    "reports/governance/track_portfolio.json",
}

NAME_DRIFT_RE = re.compile(
    "|".join(
        [
            r"name[-_ ]?drift",
            r"naming drift",
            r"naming inconsisten",
            r"name mismatch",
            r"key-name contract",
            r"hyphen/underscore",
            r"separator[-_ ]?drift",
            r"semantic_aliases",
            r"semantic_objects",
            r"NameDriftPreflight",
            r"alias index",
            r"api_name",
            r"bridge.*adapter.*connector",
        ]
    ),
    re.IGNORECASE,
)

CORRAL_RE = re.compile(r"DE_BUG_CORRAL|debug corral|bug[-_ ]corral", re.IGNORECASE)
MISSING_FILE_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./-]+\.(?:py|md|yaml|yml|json))\s+MISSING",
    re.IGNORECASE,
)

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".py",
    ".sh",
    ".toml",
}


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    text: str
    route: str
    reason: str
    source_kind: str
    last_touched: str


@dataclass(frozen=True)
class CorralState:
    canonical_dir_present: bool
    canonical_index_present: bool
    noncanonical_paths: list[str]
    existing_numbered_files: list[str]


def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _tracked_or_local_files(repo_root: Path) -> list[Path]:
    raw = _run(["git", "ls-files", "-co", "--exclude-standard"], repo_root)
    if raw:
        files = [repo_root / line for line in raw.splitlines()]
    else:
        files = [p for p in repo_root.rglob("*") if p.is_file()]
    filtered: list[Path] = []
    for path in files:
        try:
            rel = path.relative_to(repo_root)
        except ValueError:
            continue
        rel_text = rel.as_posix()
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel_text in SKIP_EXACT_PATHS:
            continue
        if any(rel_text.startswith(prefix) for prefix in SKIP_PATH_PREFIXES):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        filtered.append(path)
    return sorted(filtered)


def _last_touched(repo_root: Path, rel: str, path: Path) -> str:
    git_date = _run(["git", "log", "-1", "--format=%cs", "--", rel], repo_root)
    if git_date:
        return git_date
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()
    except OSError:
        return "unknown"


def _source_kind(rel: str) -> str:
    if rel.startswith("DE_BUG_CORRAL/"):
        return "canonical-corral"
    if rel.startswith("docs/bug-corral") or rel.startswith("docs/bug_corral"):
        return "noncanonical-corral"
    if rel.startswith("docs/governance/ACTIVE_TRACK") or rel.startswith("CLAUDE.md"):
        return "active-track"
    if rel.startswith("reports/governance/active_track_evidence"):
        return "generated-track-evidence"
    if rel.startswith("docs/governance/hygiene/"):
        return "hygiene-doctrine"
    if rel.startswith("docs/research/"):
        return "research-finder"
    if rel == "INTERFACE_MISMATCH_MAP.md":
        return "live-ledger"
    if rel == "docs/governance/REPO_GOVERNANCE_AUDIT.md":
        return "live-ledger"
    return "finder-or-code"


def _is_stale_missing_claim(repo_root: Path, text: str) -> bool:
    """Ignore generated MISSING lines when the file now exists."""
    for match in MISSING_FILE_RE.finditer(text):
        if (repo_root / match.group("path")).exists():
            return True
    return False


def _route(rel: str, text: str) -> tuple[str, str]:
    haystack = f"{rel}\n{text}".lower()
    if "de_bug_corral" in haystack or "bug-corral" in haystack or "debug corral" in haystack:
        return "DE_BUG_CORRAL/09.md", "corral path/provenance drift"
    if "interface_mismatch_map" in haystack or "key-name contract" in haystack:
        return "DE_BUG_CORRAL/01.md", "declared-vs-actual name mismatch"
    if "active_track_evidence" in haystack or "track_portfolio" in haystack:
        return "DE_BUG_CORRAL/04.md", "generated inventory evidence"
    if "active_track" in haystack or "agent_admission" in haystack:
        return "DE_BUG_CORRAL/07.md", "live doctrine or active-track pointer"
    if "hygiene" in haystack or "anti_ai_slop" in haystack:
        return "DE_BUG_CORRAL/02.md", "hygiene or anti-slop naming signal"
    return "DE_BUG_CORRAL/03.md", "repo-wide naming and structural drift"


def inspect_corral(repo_root: Path) -> CorralState:
    canonical = repo_root / CANONICAL_CORRAL
    noncanonical: list[str] = []
    for rel in ("docs/bug-corral", "docs/bug_corral", "docs/bug-corral-arbiter"):
        if (repo_root / rel).exists():
            noncanonical.append(rel)
    existing = []
    if canonical.exists():
        existing = sorted(p.name for p in canonical.glob("[0-9][0-9].md"))
    return CorralState(
        canonical_dir_present=canonical.is_dir(),
        canonical_index_present=(repo_root / CORRAL_INDEX).is_file(),
        noncanonical_paths=noncanonical,
        existing_numbered_files=existing,
    )


def scan_repo(repo_root: Path = REPO_ROOT) -> list[Hit]:
    hits: list[Hit] = []
    seen: set[tuple[str, int, str]] = set()
    for path in _tracked_or_local_files(repo_root):
        try:
            rel = path.relative_to(repo_root).as_posix()
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for idx, raw in enumerate(lines, start=1):
            if not (NAME_DRIFT_RE.search(raw) or CORRAL_RE.search(raw)):
                continue
            text = " ".join(raw.strip().split())
            if not text:
                continue
            if _is_stale_missing_claim(repo_root, text):
                continue
            key = (rel, idx, text)
            if key in seen:
                continue
            seen.add(key)
            route, reason = _route(rel, text)
            hits.append(
                Hit(
                    path=rel,
                    line=idx,
                    text=text[:220],
                    route=route,
                    reason=reason,
                    source_kind=_source_kind(rel),
                    last_touched=_last_touched(repo_root, rel, path),
                )
            )
    hits.sort(key=lambda h: (h.last_touched, h.path, h.line), reverse=True)
    return hits


def inspect_semantic_commons(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    if validate_semantic_commons is None:
        return {
            "available": False,
            "object_count": 0,
            "alias_count": 0,
            "orientation_route_count": 0,
            "error_count": 1,
            "warning_count": 0,
            "errors": [
                {
                    "check": "semantic_commons_import",
                    "severity": "error",
                    "path": "scripts/governance/agent_admission.py",
                    "detail": "could not import Semantic Commons verifier",
                }
            ],
            "warnings": [],
        }
    report = validate_semantic_commons(repo_root)
    return {
        "available": True,
        "object_count": report["object_count"],
        "alias_count": report["alias_count"],
        "orientation_route_count": report["orientation_route_count"],
        "active_agent_uid_count": report["active_agent_uid_count"],
        "a2a_card_uid_count": report["a2a_card_uid_count"],
        "error_count": len(report["errors"]),
        "warning_count": len(report["warnings"]),
        "errors": report["errors"],
        "warnings": report["warnings"],
    }


def build_payload(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    hits = scan_repo(repo_root)
    corral = inspect_corral(repo_root)
    semantic_commons = inspect_semantic_commons(repo_root)
    by_route: dict[str, int] = {}
    for hit in hits:
        by_route[hit.route] = by_route.get(hit.route, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "canonical_corral": CORRAL_INDEX.as_posix(),
        "corral_state": asdict(corral),
        "semantic_commons": semantic_commons,
        "hit_count": len(hits),
        "by_route": dict(sorted(by_route.items())),
        "hits": [asdict(hit) for hit in hits],
    }



def _normalized_hit_key(hit: dict[str, object]) -> str:
    text = re.sub(r"\s+", " ", str(hit.get("text") or "").strip().lower())
    path = str(hit.get("path") or "")
    route = str(hit.get("route") or "")
    return hashlib.sha256(f"{route}\n{path}\n{text}".encode("utf-8")).hexdigest()[:16]


def build_digest(payload: dict[str, object], *, samples_per_route: int = 8) -> dict[str, object]:
    """Build a compact route delta for dashboards/cron.

    The full payload preserves every hit. The digest is the loop artifact: small
    enough for the cockpit and useful enough for KaizenOps to pick one action
    without reading hundreds of repeated generated-report hits.
    """
    hits = payload.get("hits", [])
    assert isinstance(hits, list)
    route_hits: dict[str, list[dict[str, object]]] = defaultdict(list)
    source_counts: Counter[str] = Counter()
    source_kind_counts: Counter[str] = Counter()
    unique_keys: set[str] = set()
    for item in hits:
        assert isinstance(item, dict)
        route = str(item.get("route") or "DE_BUG_CORRAL/03.md")
        route_hits[route].append(item)
        source_counts[str(item.get("path") or "unknown")] += 1
        source_kind_counts[str(item.get("source_kind") or "unknown")] += 1
        unique_keys.add(_normalized_hit_key(item))

    route_deltas = []
    for route, items in sorted(route_hits.items()):
        top_sources = Counter(str(item.get("path") or "unknown") for item in items).most_common(5)
        route_deltas.append(
            {
                "route": route,
                "hit_count": len(items),
                "top_sources": [{"path": path, "count": count} for path, count in top_sources],
                "samples": items[:samples_per_route],
            }
        )

    corral = payload.get("corral_state", {})
    assert isinstance(corral, dict)
    semantic = payload.get("semantic_commons", {})
    assert isinstance(semantic, dict)
    blockers = []
    if not corral.get("canonical_dir_present"):
        blockers.append("canonical_corral_dir_missing")
    if not corral.get("canonical_index_present"):
        blockers.append("canonical_corral_index_missing")
    if corral.get("noncanonical_paths"):
        blockers.append("noncanonical_corral_paths_present")
    if int(semantic.get("error_count") or 0) > 0:
        blockers.append("semantic_commons_errors_present")

    return {
        "schema_version": "name_drift_preflight_digest.v1",
        "generated_at": payload.get("generated_at"),
        "repo_root": payload.get("repo_root"),
        "canonical_corral": payload.get("canonical_corral"),
        "status": "blocked" if blockers else "swept",
        "blockers": blockers,
        "hit_count": payload.get("hit_count", 0),
        "unique_hit_count": len(unique_keys),
        "by_route": payload.get("by_route", {}),
        "top_sources": [{"path": path, "count": count} for path, count in source_counts.most_common(10)],
        "source_kinds": dict(sorted(source_kind_counts.items())),
        "route_deltas": route_deltas,
        "next_action": (
            "Create DE_BUG_CORRAL/00.md and route files before treating the sweep as healthy."
            if blockers
            else "KaizenOps should select one routed item for action; do not count raw hit volume as progress."
        ),
        "corral_state": corral,
        "semantic_commons": semantic,
    }


def render_markdown(payload: dict[str, object], limit: int | None = None) -> str:
    corral = payload["corral_state"]
    assert isinstance(corral, dict)
    hits = payload["hits"]
    assert isinstance(hits, list)
    shown = hits if limit is None else hits[:limit]
    lines = [
        "# Name Drift Preflight",
        "",
        f"Generated: {payload['generated_at']}",
        f"Canonical Corral: `{payload['canonical_corral']}`",
        "",
        "## Corral State",
        "",
        f"- canonical dir present: {corral['canonical_dir_present']}",
        f"- canonical index present: {corral['canonical_index_present']}",
        f"- existing numbered files: {', '.join(corral['existing_numbered_files']) or '(none)'}",
        f"- noncanonical corral paths: {', '.join(corral['noncanonical_paths']) or '(none)'}",
        "",
        "## Semantic Commons",
        "",
    ]
    semantic = payload.get("semantic_commons", {})
    assert isinstance(semantic, dict)
    lines.extend(
        [
            f"- verifier available: {semantic.get('available')}",
            f"- objects: {semantic.get('object_count', 0)}",
            f"- aliases: {semantic.get('alias_count', 0)}",
            f"- orientation routes: {semantic.get('orientation_route_count', 0)}",
            f"- active agent_uid values: {semantic.get('active_agent_uid_count', 0)}",
            f"- A2A card agent_uid values: {semantic.get('a2a_card_uid_count', 0)}",
            f"- errors: {semantic.get('error_count', 0)}",
            f"- warnings: {semantic.get('warning_count', 0)}",
            "",
        ]
    )
    semantic_errors = semantic.get("errors", [])
    assert isinstance(semantic_errors, list)
    for item in semantic_errors[:10]:
        assert isinstance(item, dict)
        lines.append(
            f"- ERROR `{item.get('check')}` {item.get('path')}: {item.get('detail')}"
        )
    semantic_warnings = semantic.get("warnings", [])
    assert isinstance(semantic_warnings, list)
    for item in semantic_warnings[:10]:
        assert isinstance(item, dict)
        lines.append(
            f"- WARN `{item.get('check')}` {item.get('path')}: {item.get('detail')}"
        )
    if semantic_errors or semantic_warnings:
        lines.append("")
    lines.extend(
        [
            "## Route Summary",
            "",
        ]
    )
    by_route = payload["by_route"]
    assert isinstance(by_route, dict)
    if by_route:
        for route, count in by_route.items():
            lines.append(f"- `{route}`: {count}")
    else:
        lines.append("- no name-drift hits found")
    lines.extend(["", "## Hits", ""])
    for item in shown:
        assert isinstance(item, dict)
        lines.append(
            f"- `{item['route']}` <- `{item['path']}:{item['line']}` "
            f"({item['source_kind']}, {item['last_touched']}): {item['text']}"
        )
    if limit is not None and len(hits) > limit:
        lines.append(f"- ... {len(hits) - limit} more")
    return "\n".join(lines) + "\n"


def _write_text(path_text: str, content: str) -> None:
    path = Path(path_text).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    parser.add_argument("--limit", type=int, default=60, help="max hits in text output")
    parser.add_argument("--json-output", help="write JSON receipt to this path")
    parser.add_argument("--markdown-output", help="write Markdown receipt to this path")
    parser.add_argument("--digest-output", help="write compact routed digest JSON to this path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail if canonical Corral paths or Semantic Commons checks fail",
    )
    parser.add_argument(
        "--strict-semantic-commons",
        action="store_true",
        help="fail only on Semantic Commons registry/admission errors",
    )
    args = parser.parse_args(argv)

    payload = build_payload(REPO_ROOT)
    if args.json_output:
        _write_text(args.json_output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.markdown_output:
        _write_text(args.markdown_output, render_markdown(payload, limit=None))
    if args.digest_output:
        _write_text(args.digest_output, json.dumps(build_digest(payload), indent=2, sort_keys=True) + "\n")

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_markdown(payload, limit=args.limit))

    corral = payload["corral_state"]
    assert isinstance(corral, dict)
    semantic = payload["semantic_commons"]
    assert isinstance(semantic, dict)
    semantic_failed = int(semantic.get("error_count") or 0) > 0
    if args.strict_semantic_commons and semantic_failed:
        return 1
    if args.strict and (
        not corral["canonical_dir_present"] or corral["noncanonical_paths"] or semantic_failed
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
