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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider registry (from dharma_swarm/api_keys.py)
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict[str, str]] = {
    "anthropic": {"key_env": "ANTHROPIC_API_KEY", "base_env": ""},
    "openai": {"key_env": "OPENAI_API_KEY", "base_env": "OPENAI_BASE_URL"},
    "openrouter": {"key_env": "OPENROUTER_API_KEY", "base_env": "OPENROUTER_BASE_URL"},
    "groq": {"key_env": "GROQ_API_KEY", "base_env": "GROQ_BASE_URL"},
    "cerebras": {"key_env": "CEREBRAS_API_KEY", "base_env": "CEREBRAS_BASE_URL"},
    "nvidia_nim": {"key_env": "NVIDIA_NIM_API_KEY", "base_env": "NVIDIA_NIM_BASE_URL"},
    "together": {"key_env": "TOGETHER_API_KEY", "base_env": "TOGETHER_BASE_URL"},
    "fireworks": {"key_env": "FIREWORKS_API_KEY", "base_env": "FIREWORKS_BASE_URL"},
    "google_ai": {"key_env": "GOOGLE_AI_API_KEY", "base_env": "GOOGLE_AI_BASE_URL"},
    "sambanova": {"key_env": "SAMBANOVA_API_KEY", "base_env": "SAMBANOVA_BASE_URL"},
    "mistral": {"key_env": "MISTRAL_API_KEY", "base_env": "MISTRAL_BASE_URL"},
    "siliconflow": {"key_env": "SILICONFLOW_API_KEY", "base_env": "SILICONFLOW_BASE_URL"},
    "ollama": {"key_env": "OLLAMA_API_KEY", "base_env": "OLLAMA_BASE_URL"},
}

# Patterns that indicate credit exhaustion in log files
CREDIT_ERROR_PATTERNS = [
    re.compile(r"credit balance.*too low", re.IGNORECASE),
    re.compile(r"insufficient.*credits?", re.IGNORECASE),
    re.compile(r"rate.limit.*exceeded", re.IGNORECASE),
    re.compile(r"quota.*exceeded", re.IGNORECASE),
    re.compile(r"billing.*error", re.IGNORECASE),
    re.compile(r"payment.*required", re.IGNORECASE),
    re.compile(r"402", re.IGNORECASE),
]

DHARMA_HOME = Path(os.environ.get("DHARMA_HOME", Path.home() / ".dharma"))
LOG_DIRS = [
    DHARMA_HOME / "logs",
    DHARMA_HOME / "sessions" / "logs",
    DHARMA_HOME / "cron" / "logs",
]


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
            "key_prefix": key_val[:8] + "..." if len(key_val) > 8 else ("(empty)" if not key_val else "***"),
            "credit_errors": [],
        }
    return results


def scan_logs_for_credit_errors(results: dict[str, dict[str, Any]]) -> None:
    """Scan recent log files for credit/quota exhaustion errors."""
    for log_dir in LOG_DIRS:
        if not log_dir.exists():
            continue
        for log_file in sorted(log_dir.rglob("*.log"))[-20:]:  # Last 20 log files
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
                                    f"{log_file.name}: {line[:120]}"
                                )
                                break

    # Also scan JSONL logs
    for log_dir in LOG_DIRS:
        if not log_dir.exists():
            continue
        for log_file in sorted(log_dir.rglob("*.jsonl"))[-10:]:
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
                                f"{log_file.name}: {msg[:120]}"
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
    args = parser.parse_args()

    results = check_env_keys()
    scan_logs_for_credit_errors(results)

    # Compute summary
    present = [p for p, r in results.items() if r["key_present"]]
    missing = [p for p, r in results.items() if not r["key_present"]]
    exhausted = [p for p, r in results.items() if r["credit_errors"]]

    if args.json:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "present": len(present),
                "missing": len(missing),
                "likely_exhausted": len(exhausted),
            },
            "providers": results,
        }
        print(json.dumps(output, indent=2))
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
