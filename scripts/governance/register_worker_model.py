#!/usr/bin/env python3
"""register_worker_model.py — identity-as-attribution shim for free worker models.

Mirrors the existing registration-desk pattern: writes
~/.dharma/external_agents/worker-<model>/registration.json so that
delegation runs and archive entries can be grouped by (daemon_version, model).

This is ATTRIBUTION ONLY. It grants no authority: every registered worker is
external_worker_evidence_only, cannot write source, cannot approve PRs, cannot
mutate kernel/telos/meta. The registration desk is a projection, not a gate.

Usage:
    python3 scripts/governance/register_worker_model.py \
        --model qwen3-coder-480b --provider ollama_cloud
    python3 scripts/governance/register_worker_model.py --all   # the 7 free models
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

STATE_ROOT = Path(os.environ.get("DHARMA_STATE_DIR", "~/.dharma")).expanduser()
EXTERNAL_AGENTS = STATE_ROOT / "external_agents"

# The free worker fleet (per CLAUDE.md model routing canon).
FREE_WORKERS: tuple[tuple[str, str], ...] = (
    ("qwen3-coder-480b", "ollama_cloud"),
    ("kimi-k2.5", "ollama_cloud"),
    ("glm-5.1", "ollama_cloud"),
    ("deepseek-v4", "ollama_cloud"),
    ("minimax", "ollama_cloud"),
    ("mistral", "ollama_cloud"),
    ("nvidia-nim", "nvidia_nim"),
)


def _slug(model: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", model.strip().lower()).strip("-")


def build_registration(model: str, provider: str, daemon_version: str) -> dict:
    return {
        "agent_uid": f"worker-{_slug(model)}",
        "callsign": f"worker-{_slug(model)}",
        "display_name": f"Worker: {model}",
        "harness": "evolution_worker",
        "model_identity": model,
        "provider": provider,
        "free_tier": True,
        "role": "evolution_worker",
        "authority": "external_worker_evidence_only",
        "daemon_version": daemon_version,
        "registered_at": datetime.now(UTC).isoformat(),
        "autonomy_policy": {
            "mode": "manual",
            "requires_approval": True,
            "can_approve_prs": False,
            "can_write_source": False,
            "can_mutate_meta_dharma": False,
            "can_mutate_telos": False,
            "can_mutate_dharma_kernel": False,
            "explicit_task_assignment_required": True,
        },
    }


def register(model: str, provider: str, daemon_version: str, root: Path | None = None) -> Path:
    desk = (root or EXTERNAL_AGENTS) / f"worker-{_slug(model)}"
    desk.mkdir(parents=True, exist_ok=True)
    path = desk / "registration.json"
    payload = build_registration(model, provider, daemon_version)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _resolve_daemon_version() -> str:
    try:
        from dharma_swarm.versioning.daemon_version import daemon_version

        return daemon_version()
    except Exception:
        return "0.0.0+unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model")
    ap.add_argument("--provider")
    ap.add_argument("--all", action="store_true", help="register the 7 free workers")
    ap.add_argument("--root", type=Path, default=None, help="override desk root (tests)")
    args = ap.parse_args(argv)

    dv = _resolve_daemon_version()
    written: list[str] = []
    if args.all:
        for model, provider in FREE_WORKERS:
            written.append(str(register(model, provider, dv, args.root)))
    elif args.model:
        provider = args.provider or "ollama_cloud"
        written.append(str(register(args.model, provider, dv, args.root)))
    else:
        ap.error("provide --model <name> or --all")

    print(json.dumps({"daemon_version": dv, "registered": written}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
