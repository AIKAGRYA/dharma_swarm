#!/usr/bin/env python3
"""Client-runnable audit kit for the Agentic Code Governance Sprint (v0, first slice).

Point it at ANY repository path and it produces:
  1. a scan receipt (JSON) - the evidence record, and
  2. a ranked slop/provenance report (Markdown) rendered ONLY from that receipt.

Design constraints (docs/offers/agentic-code-governance-sprint.md, Fable 5 Campaign 3):
  - target-repo-agnostic: no dharma_swarm import, stdlib only, degrade gracefully.
  - receipts first: the report is a pure function of the receipt file, so every
    claim in the deliverable traces to sealed scan evidence.
  - extend existing owners: detectors cross-reference the governance hygiene
    pattern registry (docs/governance/hygiene/patterns/*.yaml) when present;
    this kit adds no new pattern ids and no new truth store.

Usage:
  python3 scripts/revenue_wedge/audit_kit.py scan --target-repo /path/to/repo --output-dir out/
  python3 scripts/revenue_wedge/audit_kit.py render --receipt out/audit_receipt.json --output out/slop_report.md
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "revenue_wedge_audit_kit_receipt.v1"
KIT_VERSION = "0.1.0"

SEVERITY_WEIGHTS = {"critical": 100, "high": 40, "medium": 15, "low": 5}

# Cross-references into the governance hygiene registry. Only ids with an exact
# conceptual match are mapped; unknown ids are dropped at runtime unless the
# registry confirms them.
HYGIENE_CROSS_REF = {
    "hardcoded_secret_like": "VC-E2",
    "duplicate_functions": "VC-F2",
    "oversized_module": "VC-C4",
    "missing_annotations_public_api": "VC-J4",
}

SECRET_PATTERNS = [
    (re.compile(r"""(?i)(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*["'][^"']{8,}["']"""), "assignment of a credential-like literal"),
    (re.compile(r"""["'](sk-[A-Za-z0-9_-]{10,})["']"""), "OpenAI/Anthropic-style key literal"),
    (re.compile(r"""["'](ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,})["']"""), "GitHub token literal"),
    (re.compile(r"""["'](AKIA[0-9A-Z]{16})["']"""), "AWS access key literal"),
    (re.compile(r"""["'](xox[baprs]-[A-Za-z0-9-]{10,})["']"""), "Slack token literal"),
]

AI_COMMIT_MARKERS = [
    "co-authored-by: oz",
    "oz-agent@warp.dev",
    "noreply@anthropic.com",
    "co-authored-by: claude",
    "co-authored-by: copilot",
    "co-authored-by: devin",
    "co-authored-by: cursor",
    "[bot]",
    "generated with",
    "ai-assisted",
    "\U0001f916",  # robot-face marker used by several agent CLIs
]

SKIP_DIR_NAMES = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", ".tox", ".mypy_cache", ".ruff_cache", "dist", "build", ".eggs"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iter_python_files(target: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(target.rglob("*.py")):
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(target).parts):
            continue
        files.append(path)
    return files


def target_fingerprint(target: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        rel = path.relative_to(target).as_posix()
        digest.update(rel.encode())
        digest.update(str(path.stat().st_size).encode())
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
    return digest.hexdigest()


def load_hygiene_registry(registry_dir: Path | None) -> dict[str, dict[str, Any]]:
    """Load hygiene pattern metadata if the registry exists (dharma-side runs).

    Client-side runs without the registry simply get detector-local labels.
    """
    registry: dict[str, dict[str, Any]] = {}
    if registry_dir is None or not registry_dir.is_dir():
        return registry
    for path in sorted(registry_dir.glob("*.yaml")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("id"), str):
            registry[payload["id"]] = {
                "title": payload.get("title", ""),
                "severity": payload.get("severity", ""),
            }
    return registry


def make_finding(detector: str, severity: str, path: str, line: int | None, message: str) -> dict[str, Any]:
    return {
        "detector": detector,
        "severity": severity,
        "path": path,
        "line": line,
        "message": message,
        "hygiene_pattern_id": HYGIENE_CROSS_REF.get(detector),
    }


def detect_secrets(target: Path, files: list[Path]) -> list[dict[str, Any]]:
    findings = []
    for path in files:
        rel = path.relative_to(target).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        make_finding(
                            "hardcoded_secret_like", "critical", rel, lineno,
                            f"credential-like literal ({label}); move to environment/config and rotate if real",
                        )
                    )
                    break
    return findings


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None


def detect_missing_annotations(target: Path, files: list[Path]) -> list[dict[str, Any]]:
    findings = []
    for path in files:
        rel = path.relative_to(target).as_posix()
        if rel.startswith("tests/") or Path(rel).name.startswith("test_"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            args = [a for a in node.args.args + node.args.kwonlyargs if a.arg not in {"self", "cls"}]
            unannotated = [a.arg for a in args if a.annotation is None]
            if node.returns is None or unannotated:
                detail = []
                if unannotated:
                    detail.append(f"params without annotations: {', '.join(unannotated)}")
                if node.returns is None:
                    detail.append("no return annotation")
                findings.append(
                    make_finding(
                        "missing_annotations_public_api", "medium", rel, node.lineno,
                        f"public function `{node.name}` on the API surface: {'; '.join(detail)}",
                    )
                )
    return findings


def detect_duplicate_functions(target: Path, files: list[Path]) -> list[dict[str, Any]]:
    bodies: dict[str, list[tuple[str, int, str]]] = {}
    for path in files:
        rel = path.relative_to(target).as_posix()
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
            if len(body) < 2:
                continue
            digest = hashlib.sha256("\n".join(ast.dump(n) for n in body).encode()).hexdigest()
            bodies.setdefault(digest, []).append((rel, node.lineno, node.name))
    findings = []
    for locations in bodies.values():
        if len(locations) < 2:
            continue
        rel, lineno, name = locations[0]
        others = ", ".join(f"{r}:{ln} `{nm}`" for r, ln, nm in locations[1:])
        findings.append(
            make_finding(
                "duplicate_functions", "medium", rel, lineno,
                f"function `{name}` body duplicated at: {others}; extract one owner",
            )
        )
    return findings


def detect_test_gaps(target: Path, files: list[Path]) -> list[dict[str, Any]]:
    test_text = ""
    source_modules = []
    for path in files:
        rel = path.relative_to(target).as_posix()
        if Path(rel).name.startswith("test_") or "/tests/" in f"/{rel}" or rel.startswith("tests/"):
            test_text += path.read_text(encoding="utf-8", errors="replace")
        elif Path(rel).name != "__init__.py":
            source_modules.append((rel, path))
    findings = []
    for rel, path in source_modules:
        stem = Path(rel).stem
        if stem not in test_text:
            loc = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            severity = "high" if loc >= 50 else "medium"
            findings.append(
                make_finding(
                    "test_gap_modules", severity, rel, None,
                    f"module `{stem}` ({loc} lines) is never referenced by any test file",
                )
            )
    return findings


def detect_dead_code_markers(target: Path, files: list[Path]) -> list[dict[str, Any]]:
    codeish = re.compile(r"^\s*#\s*(def |class |import |from |return |if |for |while |\w+\s*=\s*)")
    findings = []
    for path in files:
        rel = path.relative_to(target).as_posix()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        run_start, run_length = None, 0
        for lineno, line in enumerate(lines, 1):
            if codeish.match(line):
                run_start = run_start or lineno
                run_length += 1
            else:
                if run_length >= 3:
                    findings.append(
                        make_finding(
                            "dead_code_markers", "low", rel, run_start,
                            f"{run_length} consecutive commented-out code lines; delete or restore",
                        )
                    )
                run_start, run_length = None, 0
        if run_length >= 3:
            findings.append(
                make_finding(
                    "dead_code_markers", "low", rel, run_start,
                    f"{run_length} consecutive commented-out code lines; delete or restore",
                )
            )
        for lineno, line in enumerate(lines, 1):
            if re.search(r"#\s*(TODO|FIXME|HACK)\b", line):
                findings.append(
                    make_finding(
                        "dead_code_markers", "low", rel, lineno,
                        "unresolved TODO/FIXME/HACK marker",
                    )
                )
    return findings


def detect_oversized_modules(target: Path, files: list[Path], max_lines: int) -> list[dict[str, Any]]:
    findings = []
    for path in files:
        rel = path.relative_to(target).as_posix()
        loc = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        if loc > max_lines:
            findings.append(
                make_finding(
                    "oversized_module", "medium", rel, None,
                    f"module is {loc} lines (> {max_lines}); split along seam boundaries",
                )
            )
    return findings


def git_provenance(target: Path) -> dict[str, Any]:
    if not (target / ".git").exists():
        return {"available": False, "reason": "target is not a git repository"}
    try:
        log = subprocess.run(
            ["git", "-C", str(target), "log", "--pretty=format:%H%x01%an <%ae>%x01%B%x02"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        return {"available": False, "reason": f"git log failed: {exc}"}
    total = 0
    ai_shas: list[str] = []
    for chunk in log.split("\x02"):
        if not chunk.strip():
            continue
        total += 1
        sha = chunk.strip().split("\x01", 1)[0].strip()
        if any(marker in chunk.lower() for marker in AI_COMMIT_MARKERS):
            ai_shas.append(sha)
    ai_files: dict[str, int] = {}
    sampled = ai_shas[:500]
    for sha in sampled:
        try:
            names = subprocess.run(
                ["git", "-C", str(target), "show", "--name-only", "--format=", sha],
                capture_output=True, text=True, timeout=60, check=True,
            ).stdout
        except subprocess.SubprocessError:
            continue
        for name in names.splitlines():
            if name.strip():
                ai_files[name.strip()] = ai_files.get(name.strip(), 0) + 1
    top = sorted(ai_files.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
    return {
        "available": True,
        "total_commits": total,
        "ai_attributed_commits": len(ai_shas),
        "ai_commit_fraction": round(len(ai_shas) / total, 4) if total else 0.0,
        "ai_commits_file_sampled": len(sampled),
        "marker_set": AI_COMMIT_MARKERS,
        "top_ai_touched_files": [{"path": p, "ai_commits": n} for p, n in top],
    }


def scan(target: Path, max_module_lines: int, registry_dir: Path | None) -> dict[str, Any]:
    files = iter_python_files(target)
    findings: list[dict[str, Any]] = []
    findings += detect_secrets(target, files)
    findings += detect_missing_annotations(target, files)
    findings += detect_duplicate_functions(target, files)
    findings += detect_test_gaps(target, files)
    findings += detect_dead_code_markers(target, files)
    findings += detect_oversized_modules(target, files, max_module_lines)

    registry = load_hygiene_registry(registry_dir)
    for finding in findings:
        pattern_id = finding.get("hygiene_pattern_id")
        if pattern_id and registry and pattern_id not in registry:
            finding["hygiene_pattern_id"] = None
        if pattern_id and registry.get(pattern_id):
            finding["hygiene_pattern_title"] = registry[pattern_id]["title"]

    findings.sort(key=lambda f: (-SEVERITY_WEIGHTS.get(f["severity"], 0), f["path"], f["line"] or 0))
    total_loc = sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines()) for p in files)
    weighted = sum(SEVERITY_WEIGHTS.get(f["severity"], 0) for f in findings)
    by_severity: dict[str, int] = {}
    for finding in findings:
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "kit_version": KIT_VERSION,
        "observed_at_utc": _iso_now(),
        "target_repo": str(target),
        "target_fingerprint_sha256": target_fingerprint(target, files),
        "python_files_scanned": len(files),
        "total_python_loc": total_loc,
        "hygiene_registry_loaded": bool(registry),
        "findings": findings,
        "summary": {
            "finding_count": len(findings),
            "by_severity": by_severity,
            "weighted_slop_points": weighted,
            "slop_score_per_kloc": round(weighted / (total_loc / 1000), 2) if total_loc else 0.0,
        },
        "provenance": git_provenance(target),
    }


def render_report(receipt: dict[str, Any]) -> str:
    summary = receipt["summary"]
    prov = receipt["provenance"]
    lines = [
        "# Agentic Code Governance Audit - Ranked Slop & Provenance Report",
        "",
        f"- target: `{receipt['target_repo']}`",
        f"- scanned at: {receipt['observed_at_utc']} (kit v{receipt['kit_version']}, receipt schema `{receipt['schema_version']}`)",
        f"- target fingerprint: `sha256:{receipt['target_fingerprint_sha256']}`",
        f"- python files scanned: {receipt['python_files_scanned']} ({receipt['total_python_loc']} LOC)",
        "",
        "## Score",
        "",
        f"- findings: **{summary['finding_count']}** ("
        + ", ".join(f"{sev}: {n}" for sev, n in sorted(summary["by_severity"].items(), key=lambda kv: -SEVERITY_WEIGHTS.get(kv[0], 0)))
        + ")",
        f"- weighted slop points: **{summary['weighted_slop_points']}**",
        f"- slop score per KLOC: **{summary['slop_score_per_kloc']}**",
        "",
        "## Provenance",
        "",
    ]
    if prov.get("available"):
        lines += [
            f"- commits analysed: {prov['total_commits']}",
            f"- AI-attributed commits: {prov['ai_attributed_commits']} ({prov['ai_commit_fraction'] * 100:.1f}%)",
        ]
        if prov["top_ai_touched_files"]:
            lines.append("- most AI-touched files:")
            lines += [f"  - `{e['path']}` ({e['ai_commits']} AI-attributed commits)" for e in prov["top_ai_touched_files"][:10]]
    else:
        lines.append(f"- provenance unavailable: {prov.get('reason', 'unknown')}")
    lines += ["", "## Ranked Findings", ""]
    if not receipt["findings"]:
        lines.append("No findings. Either the target is clean or the detector set is too narrow for it.")
    for i, f in enumerate(receipt["findings"], 1):
        location = f"`{f['path']}`" + (f":{f['line']}" if f["line"] else "")
        ref = f" [hygiene:{f['hygiene_pattern_id']}]" if f.get("hygiene_pattern_id") else ""
        title = f" ({f['hygiene_pattern_title']})" if f.get("hygiene_pattern_title") else ""
        lines.append(f"{i}. **{f['severity'].upper()}** {f['detector']}{ref}{title} - {location}: {f['message']}")
    lines += [
        "",
        "---",
        "Every line above is rendered from the scan receipt; re-render with "
        "`audit_kit.py render --receipt <receipt.json>` to verify no claim exists outside the evidence.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="scan a target repo and write receipt + report")
    scan_p.add_argument("--target-repo", type=Path, required=True)
    scan_p.add_argument("--output-dir", type=Path, required=True)
    scan_p.add_argument("--max-module-lines", type=int, default=500)
    scan_p.add_argument(
        "--hygiene-registry",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "docs/governance/hygiene/patterns",
        help="hygiene pattern registry dir for cross-references (optional; absent on client machines)",
    )
    scan_p.add_argument("--fail-threshold", type=float, default=None, help="exit 2 if slop_score_per_kloc exceeds this (for client CI gates)")

    render_p = sub.add_parser("render", help="render the ranked report from an existing receipt")
    render_p.add_argument("--receipt", type=Path, required=True)
    render_p.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.command == "scan":
        target = args.target_repo.resolve()
        if not target.is_dir():
            parser.error(f"target repo {target} is not a directory")
        receipt = scan(target, args.max_module_lines, args.hygiene_registry)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = args.output_dir / "audit_receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        report_path = args.output_dir / "slop_report.md"
        report_path.write_text(render_report(receipt), encoding="utf-8")
        print(f"wrote {receipt_path}")
        print(f"wrote {report_path}")
        score = receipt["summary"]["slop_score_per_kloc"]
        if args.fail_threshold is not None and score > args.fail_threshold:
            # Explicit numeric coercion: both operands are floats (a slop ratio
            # and a CLI threshold), never secrets. The cast is also a sanitizer
            # barrier for CodeQL's clear-text-logging taint, which otherwise
            # coarsely treats the whole receipt (built from scanned file text)
            # as sensitive even though detect_secrets stores only labels.
            print(
                f"slop score {float(score):.4f} exceeds threshold "
                f"{float(args.fail_threshold):.4f}"
            )
            return 2
        return 0

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != SCHEMA_VERSION:
        print(f"warning: receipt schema {receipt.get('schema_version')!r} != {SCHEMA_VERSION!r}; rendering anyway")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(receipt), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
