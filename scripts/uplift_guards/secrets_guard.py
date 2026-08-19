"""Secrets-in-diff guard.

Refuses commits whose staged additions look like API keys, tokens, or
private keys. Uses conservative regex — false positives are tolerable
(commit can be retried with the secret moved out); false negatives are not.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Each pattern is a (label, compiled regex). Patterns match the staged
# *additions* line-by-line, not the whole file (so existing values that
# weren't introduced by this commit are not flagged).
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("Generic OpenRouter / Together / Groq style", re.compile(r"\b(?:sk|gsk)_[A-Za-z0-9]{32,}\b")),
    ("GitHub token", re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")),
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Tavily API key", re.compile(r"tvly-[A-Za-z0-9]{20,}")),
]

# RED-TEAM HARDENING (Strategy 4): tightened allowlist.
# Anchored (^ or $) patterns so adversary can't create tests/foo/
# test_secrets_guard_helper.py to exfiltrate keys, and self-allowlist
# of secrets_guard.py itself removed (was a recursion — the guard could
# leak keys as "comments" in its own file).
ALLOWLIST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^tests/test_uplift_guards\.py$"),
    re.compile(r"^\.env\.template$"),
    re.compile(r"^\.env\.example$"),
    # Redaction fail-closed fixtures: these files exist to prove the helm-context
    # codec REJECTS secret-shaped strings ("sk-proj-abcdefgh…", "AKIAABCD…",
    # fake PRIVATE KEY blocks — all synthetic, none deployable). Same fixture
    # category as tests/test_uplift_guards.py above. Landed on main via the
    # GitHub merge queue (#1414), which never runs local hooks, so every local
    # restack merge re-flags them as staged "additions".
    re.compile(r"^tests/test_helm_context\.py$"),
    re.compile(r"^terminal/tests/helmContextProtocol\.test\.ts$"),
]


def _staged_added_lines(repo_root: Path) -> list[tuple[str, str]]:
    """Return [(path, added_line)] for every line added by the staged diff."""
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--no-color"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    if result.returncode != 0:
        return []
    rows: list[tuple[str, str]] = []
    current_path: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_path = line[6:]
            continue
        if current_path is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            rows.append((current_path, line[1:]))
    return rows


def _is_allowlisted(path: str) -> bool:
    return any(p.search(path) for p in ALLOWLIST_PATTERNS)


def check_no_secrets(repo_root: Path | None = None) -> tuple[bool, str]:
    """Refuse commits whose staged additions contain credential-shaped text."""
    repo_root = repo_root or Path.cwd()
    findings: list[str] = []
    for path, line in _staged_added_lines(repo_root):
        if _is_allowlisted(path):
            continue
        for label, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}: {label} (line excerpt: {line[:60]!r})")

    if findings:
        return False, (
            "SECRETS GUARD blocked the commit.\n"
            "  Suspected credentials in staged additions:\n    "
            + "\n    ".join(findings)
            + "\n  Move the secret to ~/.env or your secret manager and retry."
        )

    return True, "no secret-shaped strings found in staged additions"
