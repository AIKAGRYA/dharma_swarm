#!/usr/bin/env python3
"""check_provider_credits.py — Diagnose provider API key health.

Reports which provider keys are:
  - Present (env var set)
  - Missing (env var unset)
  - Likely exhausted (based on recent cron error logs)

Designed to run quickly without making actual API calls — it checks
environment variables and parses recent log files for credit errors.

Usage:
  python3 scripts/check_provider_credits.py

  # Also attempt a cheap validation call per provider
  python3 scripts/check_provider_credits.py --ping

  # JSON output for automation
  python3 scripts/check_provider_credits.py --json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.api_keys import PROVIDER_API_KEY_ENV_KEYS, PROVIDER_BASE_URL_ENV_KEYS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

PROVIDERS: dict[str, dict[str, str]] = {
    provider: {
        "key_env": key_env,
        "base_env": PROVIDER_BASE_URL_ENV_KEYS.get(provider, ""),
    }
    for provider, key_env in PROVIDER_API_KEY_ENV_KEYS.items()
}

# Patterns that indicate credit exhaustion in log files.
# 2026-07-03: extended with wordings providers ACTUALLY emit — the live
# ollama-cloud failure ("you have reached your weekly usage limit") matched
# nothing here, so likely_exhausted read 0 while the chain-head was hard
# capped. Keep this list aligned with observed provider error strings.
CREDIT_ERROR_PATTERNS = [
    re.compile(r"credit balance.*too low", re.IGNORECASE),
    re.compile(r"insufficient.*credits?", re.IGNORECASE),
    re.compile(r"rate.limit.*exceeded", re.IGNORECASE),
    re.compile(r"quota.*exceeded", re.IGNORECASE),
    re.compile(r"billing.*error", re.IGNORECASE),
    re.compile(r"payment.*required", re.IGNORECASE),
    re.compile(r"402", re.IGNORECASE),
    re.compile(r"\b429\b"),
    re.compile(r"too many requests", re.IGNORECASE),
    re.compile(r"usage limit", re.IGNORECASE),
    re.compile(r"resource[_ ]exhausted", re.IGNORECASE),
]

# Only log files touched within this window count as exhaustion evidence.
# Before 2026-07-03 ANY historical match flagged a provider "likely
# exhausted" forever — one stale 402 read as "low on api keys" for weeks.
DEFAULT_WINDOW_HOURS = 72.0

SENSITIVE_LOG_PATTERNS = [
    (
        re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)((?:api[_-]?key|token|secret|password)=)[^\s&]+"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"\b(?:sk|gsk|csk|nvapi)[-_][A-Za-z0-9._-]{8,}"),
        "[REDACTED_KEY]",
    ),
    (
        re.compile(r"(https?://)([^/\s:@]+):([^/\s@]+)@"),
        r"\1[REDACTED]@",
    ),
]

DHARMA_HOME = Path(os.environ.get("DHARMA_HOME", Path.home() / ".dharma"))
LOG_DIRS = [
    DHARMA_HOME / "logs",
    DHARMA_HOME / "sessions" / "logs",
    DHARMA_HOME / "cron" / "logs",
]


def redact_log_excerpt(text: str, *, limit: int = 120) -> str:
    """Redact likely credentials before persisting a diagnostic log excerpt."""

    redacted = text
    for pattern, replacement in SENSITIVE_LOG_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted[:limit]


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_env_keys() -> dict[str, dict[str, Any]]:
    """Check which provider API keys are set in the environment."""
    results: dict[str, dict[str, Any]] = {}
    for provider, config in PROVIDERS.items():
        key_env = config["key_env"]
        key_val = os.environ.get(key_env, "")
        results[provider] = {
            "key_env": key_env,
            "key_present": bool(key_val),
            "key_hint": "present" if key_val else "missing",
            "credit_errors": [],
        }
    return results


def _recent_files(
    log_dir: Path,
    pattern: str,
    limit: int,
    window_hours: float,
    *,
    now: float | None = None,
) -> list[Path]:
    """Newest `limit` files matching `pattern`, restricted to the mtime window."""
    import time

    current = time.time() if now is None else now
    cutoff = current - window_hours * 3600.0
    candidates: list[tuple[float, Path]] = []
    for path in log_dir.rglob(pattern):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime >= cutoff:
            candidates.append((mtime, path))
    candidates.sort()
    return [path for _, path in candidates[-limit:]]


def scan_logs_for_credit_errors(
    results: dict[str, dict[str, Any]],
    *,
    log_dirs: list[Path] | None = None,
    window_hours: float = DEFAULT_WINDOW_HOURS,
    now: float | None = None,
) -> None:
    """Scan recent (windowed) log files for credit/quota exhaustion errors."""
    dirs = LOG_DIRS if log_dirs is None else log_dirs
    for log_dir in dirs:
        if not log_dir.exists():
            continue
        for log_file in _recent_files(log_dir, "*.log", 20, window_hours, now=now):
            try:
                text = log_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines()[-200:]:  # Last 200 lines per file
                for pattern in CREDIT_ERROR_PATTERNS:
                    if pattern.search(line):
                        # Try to identify which provider
                        for provider in results:
                            if provider.lower() in line.lower():
                                results[provider]["credit_errors"].append(
                                    f"{log_file.name}: {redact_log_excerpt(line)}"
                                )
                                break

    # Also scan JSONL logs
    for log_dir in dirs:
        if not log_dir.exists():
            continue
        for log_file in _recent_files(log_dir, "*.jsonl", 10, window_hours, now=now):
            try:
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines[-100:]:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                msg = str(entry.get("message", "") or entry.get("error", ""))
                for pattern in CREDIT_ERROR_PATTERNS:
                    if pattern.search(msg):
                        provider_hit = entry.get("provider", "")
                        if provider_hit and provider_hit in results:
                            results[provider_hit]["credit_errors"].append(
                                f"{log_file.name}: {redact_log_excerpt(msg)}"
                            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check provider API key health and credit status."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--ping",
        action="store_true",
        help="Attempt cheap validation calls (not yet implemented)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write output to this file instead of stdout (supports ~ expansion)",
    )
    parser.add_argument(
        "--window-hours",
        type=float,
        default=DEFAULT_WINDOW_HOURS,
        help="Only log files modified within this window count as exhaustion "
        f"evidence (default: {DEFAULT_WINDOW_HOURS})",
    )
    args = parser.parse_args()

    results = check_env_keys()
    scan_logs_for_credit_errors(results, window_hours=args.window_hours)

    # Compute summary
    present = [p for p, r in results.items() if r["key_present"]]
    missing = [p for p, r in results.items() if not r["key_present"]]
    exhausted = [p for p, r in results.items() if r["credit_errors"]]

    if args.json:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            # Honesty header: consumers (and agents reading this file) must
            # know this is NOT a live balance check. "missing" = env var
            # unset in THIS process; "likely_exhausted" = a credit-error
            # regex matched a recent log line naming the provider.
            "method": "env-presence + windowed log-scan (heuristic; no live API calls)",
            "window_hours": args.window_hours,
            "writer": "scripts/check_provider_credits.py",
            "summary": {
                "present": len(present),
                "missing": len(missing),
                "likely_exhausted": len(exhausted),
            },
            "providers": results,
        }
        text = json.dumps(output, indent=2)
        if args.output:
            from pathlib import Path
            out_path = Path(args.output).expanduser()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
    else:
        print("=" * 60)
        print("PROVIDER CREDIT STATUS")
        print("=" * 60)
        print(f"\n{'Provider':<15} {'Key':<10} {'Status'}")
        print("-" * 50)
        for provider, info in sorted(results.items()):
            key_status = "✓ SET" if info["key_present"] else "✗ MISSING"
            credit_status = ""
            if info["credit_errors"]:
                credit_status = f" ⚠ {len(info['credit_errors'])} credit error(s)"
            print(f"{provider:<15} {key_status:<10} {credit_status}")

        print(f"\nSummary: {len(present)} present, {len(missing)} missing, {len(exhausted)} with credit errors")

        if missing:
            print(f"\nMissing keys: {', '.join(sorted(missing))}")
        if exhausted:
            print(f"\nLikely exhausted: {', '.join(sorted(exhausted))}")
            print("\nRecent credit errors:")
            for provider in exhausted:
                for err in results[provider]["credit_errors"][:3]:
                    print(f"  [{provider}] {err}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
