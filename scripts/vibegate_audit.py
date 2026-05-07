#!/usr/bin/env python3
"""VibeGate launch-hardening audit for AI-built apps."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


IGNORE_DIRS = {
    ".git", ".next", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__",
    "build", "coverage", "dist", "node_modules", "out", "target", "vendor",
}
TEXT_SUFFIXES = {
    "", ".cjs", ".conf", ".css", ".env", ".html", ".js", ".json", ".jsx",
    ".mjs", ".md", ".py", ".sh", ".sql", ".toml", ".ts", ".tsx", ".txt",
    ".yaml", ".yml",
}

MAX_FILE_BYTES = 512_000
MAX_FINDING_SNIPPET = 220


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    path: str
    line: int
    title: str
    evidence: str
    recommendation: str

@dataclass(frozen=True)
class VibeGateReport:
    target_repo: str
    generated_at: str
    repo_fingerprint: str
    scanned_files: int
    skipped_files: int
    generated_app_signals: list[str]
    severity_counts: dict[str, int]
    launch_verdict: str
    launch_score: int
    findings: list[Finding]
    next_actions: list[str]

def _is_ignored(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)

def _walk_text_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if not path.is_file() or _is_ignored(path.relative_to(root)):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Procfile"}:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _clean_snippet(text: str) -> str:
    snippet = " ".join(text.strip().split())
    if len(snippet) <= MAX_FINDING_SNIPPET:
        return snippet
    return snippet[: MAX_FINDING_SNIPPET - 3] + "..."


def _finding(
    *,
    rule_id: str,
    severity: str,
    root: Path,
    path: Path,
    line: int,
    title: str,
    evidence: str,
    recommendation: str,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        path=path.relative_to(root).as_posix(),
        line=line,
        title=title,
        evidence=_clean_snippet(evidence),
        recommendation=recommendation,
    )


def _scan_file(root: Path, path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    suffix = path.suffix.lower()
    rel = path.relative_to(root).as_posix()

    secret_patterns = [
        ("secret.private-key", "critical", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----")),
        ("secret.github-token", "critical", re.compile(r"ghp_[A-Za-z0-9_]{20,}")),
        ("secret.openai-key", "critical", re.compile(r"sk-[A-Za-z0-9]{24,}")),
        ("secret.aws-access-key", "critical", re.compile(r"AKIA[0-9A-Z]{16}")),
    ]
    for rule_id, severity, pattern in secret_patterns:
        for match in pattern.finditer(text):
            findings.append(
                _finding(
                    rule_id=rule_id,
                    severity=severity,
                    root=root,
                    path=path,
                    line=_line_for_offset(text, match.start()),
                    title="Possible committed secret",
                    evidence=match.group(0)[:24] + "...",
                    recommendation="Rotate the secret if real, remove it from git history, and load it from environment or a secrets manager.",
                )
            )

    if path.name == ".env" or rel.endswith("/.env"):
        findings.append(
            _finding(
                rule_id="secret.env-file",
                severity="high",
                root=root,
                path=path,
                line=1,
                title="Environment file is committed in the app tree",
                evidence=rel,
                recommendation="Keep only .env.example in source control; move real values to local environment or hosting secrets.",
            )
        )

    if suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html"}:
        js_rules = [
            (
                "web.xss-dangerous-html",
                "high",
                re.compile(r"\b(?:innerHTML|outerHTML|insertAdjacentHTML)\s*="),
                "Raw HTML assignment can turn model/user text into XSS.",
                "Render text safely or sanitize through a reviewed HTML sanitizer before insertion.",
            ),
            (
                "web.eval",
                "critical",
                re.compile(r"\beval\s*\("),
                "Dynamic JavaScript execution is a code-execution sink.",
                "Replace eval with a typed dispatch table or a safe parser for the intended expression language.",
            ),
            (
                "web.cors-wildcard",
                "high",
                re.compile(r"Access-Control-Allow-Origin['\"]?\s*[:,=]\s*['\"]\*['\"]"),
                "Wildcard CORS can expose private API responses.",
                "Restrict CORS to the production origin and handle credentials explicitly.",
            ),
            (
                "web.localstorage-token",
                "medium",
                re.compile(r"localStorage\.(?:setItem|getItem)\s*\([^)]*(?:token|jwt|secret)", re.IGNORECASE),
                "Long-lived auth material in localStorage is exposed to XSS.",
                "Use httpOnly secure cookies or short-lived in-memory tokens with refresh flow.",
            ),
        ]
        for rule_id, severity, pattern, title, recommendation in js_rules:
            for match in pattern.finditer(text):
                findings.append(
                    _finding(
                        rule_id=rule_id,
                        severity=severity,
                        root=root,
                        path=path,
                        line=_line_for_offset(text, match.start()),
                        title=title,
                        evidence=text[match.start() : match.end() + 80],
                        recommendation=recommendation,
                    )
                )

    if suffix == ".py":
        py_rules = [
            (
                "python.eval",
                "critical",
                re.compile(r"\beval\s*\("),
                "Python eval is a code-execution sink.",
                "Replace eval with a typed dispatch table, JSON parsing, or ast.literal_eval for trusted literals only.",
            ),
            (
                "python.subprocess-shell",
                "high",
                re.compile(r"subprocess\.(?:run|Popen|call|check_call|check_output)\s*\([^)]*shell\s*=\s*True", re.DOTALL),
                "subprocess shell=True can create command injection paths.",
                "Pass a list of arguments with shell=False and validate user-controlled path pieces.",
            ),
        ]
        for rule_id, severity, pattern, title, recommendation in py_rules:
            for match in pattern.finditer(text):
                findings.append(
                    _finding(
                        rule_id=rule_id,
                        severity=severity,
                        root=root,
                        path=path,
                        line=_line_for_offset(text, match.start()),
                        title=title,
                        evidence=text[match.start() : match.end() + 80],
                        recommendation=recommendation,
                    )
                )

    if suffix == ".sql":
        if re.search(r"create\s+policy", text, re.IGNORECASE) is None and re.search(r"create\s+table", text, re.IGNORECASE):
            findings.append(
                _finding(
                    rule_id="supabase.rls-missing-policy",
                    severity="high",
                    root=root,
                    path=path,
                    line=1,
                    title="SQL creates tables without visible row-level security policy",
                    evidence=rel,
                    recommendation="Add explicit RLS enablement and policies before launch if this backs a Supabase app.",
                )
            )

    return findings


def detect_generated_app_signals(root: Path, file_text: dict[Path, str]) -> list[str]:
    signals: set[str] = set()
    package_json = root / "package.json"
    if package_json.exists():
        signals.add("node-app")
        try:
            package = json.loads(_read_text(package_json))
        except json.JSONDecodeError:
            package = {}
        deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        if "vite" in deps:
            signals.add("vite")
        if "next" in deps:
            signals.add("nextjs")
        if "@supabase/supabase-js" in deps:
            signals.add("supabase")
        if "stripe" in deps or "@stripe/stripe-js" in deps:
            signals.add("stripe")
    if (root / "src").exists() and (root / "package.json").exists():
        signals.add("frontend-app")
    joined = "\n".join(file_text.values()).lower()
    for needle, signal in [
        ("generated by lovable", "lovable-generated"),
        ("lovable.dev", "lovable-generated"),
        ("bolt.new", "bolt-generated"),
        ("generated by bolt", "bolt-generated"),
        ("v0.dev", "v0-generated"),
        ("replit agent", "replit-agent"),
        ("cursor", "cursor-touched"),
        ("windsurf", "windsurf-touched"),
    ]:
        if needle in joined:
            signals.add(signal)
    return sorted(signals)


def _project_findings(root: Path, file_text: dict[Path, str], signals: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    package_path = root / "package.json"
    package: dict[str, object] = {}
    if not file_text:
        findings.append(Finding("project.empty-repo", "high", ".", 1, "No scannable app files found",
                                "0 text files", "Do not treat an empty or binary-only repo as launchable."))
        return findings
    if signals and package_path not in file_text:
        findings.append(Finding("project.no-app-manifest", "medium", ".", 1, "Generated-app signal but no package manifest",
                                ", ".join(signals), "Find the real app root before calling this launch-ready."))
    if package_path in file_text:
        try:
            package = json.loads(file_text[package_path])
        except json.JSONDecodeError:
            findings.append(Finding("project.package-json-invalid", "high", "package.json", 1,
                                    "package.json is invalid JSON", "json decode failed",
                                    "Fix package.json before dependency or deploy checks."))
        scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
        deps = {}
        if isinstance(package, dict):
            deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        if isinstance(scripts, dict) and "test" not in scripts:
            findings.append(Finding("project.no-test-script", "medium", "package.json", 1,
                                    "No npm test script", "scripts.test missing",
                                    "Add at least one smoke or unit test before selling this as launch-ready."))
        lockfiles = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock"}
        if not any((root / name).exists() for name in lockfiles):
            findings.append(Finding("project.no-lockfile", "medium", "package.json", 1,
                                    "No dependency lockfile", "lockfile missing",
                                    "Commit exactly one lockfile so installs are reproducible."))
        env_deps = {"@supabase/supabase-js", "stripe", "@stripe/stripe-js", "firebase", "openai"}
        if env_deps.intersection(deps) and not (root / ".env.example").exists():
            findings.append(Finding("project.no-env-example", "medium", "package.json", 1,
                                    "Env-dependent app has no .env.example", ", ".join(sorted(env_deps.intersection(deps))),
                                    "Add .env.example with variable names and no secrets."))
        if "@supabase/supabase-js" in deps:
            joined = "\n".join(file_text.values()).lower()
            has_policy = "create policy" in joined or "enable row level security" in joined
            if not has_policy:
                findings.append(Finding("supabase.no-policy-evidence", "high", "package.json", 1,
                                        "Supabase dependency with no RLS policy evidence",
                                        "@supabase/supabase-js present",
                                        "Add migrations or docs showing RLS is enabled and policies cover user data."))
    return findings


def repo_fingerprint(root: Path, file_text: dict[Path, str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(file_text, key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(file_text[path].encode("utf-8", errors="ignore")).hexdigest().encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _severity_counts(findings: Sequence[Finding]) -> dict[str, int]:
    counts = Counter(f.severity for f in findings)
    return {key: counts.get(key, 0) for key in ("critical", "high", "medium", "low")}


def _launch_verdict(counts: dict[str, int]) -> tuple[str, int]:
    score = 100
    score -= counts["critical"] * 35
    score -= counts["high"] * 18
    score -= counts["medium"] * 7
    score = max(score, 0)
    if counts["critical"]:
        return "do_not_launch", score
    if counts["high"] >= 3:
        return "blocked_until_hardened", score
    if counts["high"]:
        return "launch_with_fix_pr_first", score
    if counts["medium"]:
        return "acceptable_for_private_beta", score
    return "launch_ready_static_pass", score


def _next_actions(findings: Sequence[Finding], verdict: str) -> list[str]:
    actions: list[str] = []
    if verdict == "do_not_launch":
        actions.append("Fix critical findings before any public launch or customer demo.")
    elif verdict == "blocked_until_hardened":
        actions.append("Batch high-severity findings into one hardening PR, then rescan.")
    elif verdict == "launch_with_fix_pr_first":
        actions.append("Open a small fix PR for the high-severity findings before sharing the app.")
    else:
        actions.append("Run a smoke test against the deployed app and collect real user-flow evidence.")

    by_rule = Counter(f.rule_id for f in findings)
    for rule_id, _count in by_rule.most_common(3):
        actions.append(f"Prioritize `{rule_id}` because it appears in the top finding cluster.")
    actions.append("If this is an owned repo, run dependency and browser smoke checks next.")
    return actions


def build_report(root: Path, *, generated_at: str | None = None) -> VibeGateReport:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"target repo does not exist or is not a directory: {root}")

    file_text: dict[Path, str] = {}
    skipped = 0
    findings: list[Finding] = []
    for path in _walk_text_files(root):
        try:
            text = _read_text(path)
        except OSError:
            skipped += 1
            continue
        file_text[path] = text
        findings.extend(_scan_file(root, path, text))

    signals = detect_generated_app_signals(root, file_text)
    findings.extend(_project_findings(root, file_text, signals))
    findings = sorted(findings, key=lambda f: (f.severity, f.path, f.line, f.rule_id))
    counts = _severity_counts(findings)
    verdict, score = _launch_verdict(counts)
    report = VibeGateReport(
        target_repo=str(root),
        generated_at=generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        repo_fingerprint=repo_fingerprint(root, file_text),
        scanned_files=len(file_text),
        skipped_files=skipped,
        generated_app_signals=signals,
        severity_counts=counts,
        launch_verdict=verdict,
        launch_score=score,
        findings=findings,
        next_actions=_next_actions(findings, verdict),
    )
    return report


def report_to_dict(report: VibeGateReport) -> dict[str, object]:
    return asdict(report)


def render_markdown(report: VibeGateReport) -> str:
    lines = [
        "# VibeGate Launch Hardening Report",
        "",
        f"- Target repo: `{report.target_repo}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Repo fingerprint: `{report.repo_fingerprint}`",
        f"- Scanned files: `{report.scanned_files}`",
        f"- Skipped files: `{report.skipped_files}`",
        f"- Generated-app signals: `{', '.join(report.generated_app_signals) if report.generated_app_signals else 'none'}`",
        f"- Launch verdict: `{report.launch_verdict}`",
        f"- Launch score: `{report.launch_score}`",
        "",
        "## Severity Counts",
        "",
    ]
    for severity, count in report.severity_counts.items():
        lines.append(f"- `{severity}`: `{count}`")

    lines.extend(["", "## Findings", ""])
    if not report.findings:
        lines.append("- No static launch-hardening findings from built-in rules.")
    else:
        for finding in report.findings:
            lines.extend(
                [
                    f"### {finding.severity.upper()} — {finding.rule_id}",
                    "",
                    f"- Location: `{finding.path}:{finding.line}`",
                    f"- Issue: {finding.title}",
                    f"- Evidence: `{finding.evidence}`",
                    f"- Fix: {finding.recommendation}",
                    "",
                ]
            )

    lines.extend(["## Next Actions", ""])
    lines.extend(f"- {action}" for action in report.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: VibeGateReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(report.target_repo).name or "repo"
    json_path = output_dir / f"{safe_name}_vibegate.json"
    md_path = output_dir / f"{safe_name}_vibegate.md"
    json_path.write_text(json.dumps(report_to_dict(report), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit an AI-built app repo for launch-hardening blockers.")
    parser.add_argument("target_repo", type=Path, help="Path to the app repo to scan.")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/vibegate"),
                        help="Directory for JSON/Markdown reports (default: reports/vibegate).")
    parser.add_argument("--json-only", action="store_true", help="Print JSON to stdout instead of writing report files.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report(args.target_repo)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.json_only:
        print(json.dumps(report_to_dict(report), ensure_ascii=True, indent=2))
        return 0 if report.launch_verdict != "do_not_launch" else 2

    json_path, md_path = write_outputs(report, args.output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0 if report.launch_verdict != "do_not_launch" else 2


if __name__ == "__main__":
    raise SystemExit(main())
