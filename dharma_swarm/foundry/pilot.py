"""Bounded five-cycle supervisor pilot with simulation-only receipts."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.foundry.campaign import CampaignConfig, dry_run_campaign
from dharma_swarm.foundry.daemon import DaemonConfig, run_daemon
from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.targets import TARGET_REGISTRY


def _code_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return proc.stdout.strip()


def _write_exclusive(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_five_cycle_pilot(
    *,
    state_root: Path,
    repo_root: Path,
    runs: int = 5,
    max_proposals_per_run: int = 2,
    max_spend_usd: float = 0.0,
) -> dict:
    if runs < 5 or runs > 20:
        raise ValueError("pilot runs must be between 5 and 20")
    if max_proposals_per_run < 1 or max_proposals_per_run > 10:
        raise ValueError("max proposals per run must be between 1 and 10")
    if max_spend_usd < 0:
        raise ValueError("max spend must be non-negative")

    pilot_id = f"pilot-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"
    pilot_root = Path(state_root) / "pilot_runs" / pilot_id
    receipts_root = pilot_root / "cycle_receipts"
    checkout_sha = _code_sha(Path(repo_root))
    target_id = "openevolve-circle-packing"
    previous = "genesis"
    cycle_receipts: list[str] = []
    cycle_payloads: list[dict] = []

    def cycle(target, generations, budget_cap, runtime_root):  # noqa: ARG001
        nonlocal previous
        result = dry_run_campaign(
            TARGET_REGISTRY[target_id],
            config=CampaignConfig(
                generations=1,
                per_generation=max_proposals_per_run,
                budget_cap_usd=0.0,
            ),
            state_root=pilot_root,
        )
        sequence = len(cycle_receipts) + 1
        payload = {
            "schema_version": "foundry_pilot_cycle.v1",
            "pilot_id": pilot_id,
            "sequence": sequence,
            "simulation_only": True,
            "promotion_allowed": False,
            "external_claim": False,
            "network_calls": 0,
            "code_sha": checkout_sha,
            "target_id": target_id,
            "proposed": result.proposed,
            "provider_failures": result.provider_failures,
            "ring1_wins": result.ring1_wins,
            "ring2_promotion_blocked": result.ring2_promotion_blocked,
            "spend_usd": result.spend_usd,
            "prev_digest": previous,
            "ran_at": datetime.now(timezone.utc).isoformat(),
        }
        if payload["proposed"] > max_proposals_per_run:
            raise RuntimeError("pilot proposal bound exceeded")
        if payload["spend_usd"] > max_spend_usd:
            raise RuntimeError("pilot spend bound exceeded")
        payload["digest"] = canonical_digest(payload)
        path = receipts_root / f"{sequence:08d}__{payload['digest'][7:23]}.json"
        _write_exclusive(path, payload)
        previous = payload["digest"]
        cycle_receipts.append(str(path.relative_to(pilot_root)))
        cycle_payloads.append(payload)
        return result

    state = run_daemon(
        DaemonConfig(
            targets=[target_id],
            cycle_generations=1,
            interval_seconds=0,
            max_cycles=runs,
            # The supervisor needs positive remaining capacity to enter a
            # cycle; the injected simulation campaign itself is hard-capped 0.
            budget_cap_usd=max(max_spend_usd, 0.000001),
            state_root=pilot_root,
            mode="pilot_simulation",
            heartbeat_seconds=0,
            # Dry runs intentionally cannot promote, so a zero survival value
            # is "unproven simulation", not a production cohort collapse.
            survival_floor=0.0,
        ),
        cycle_fn=cycle,
        sleep_fn=lambda seconds: None,
    )
    if state.terminal_kill or state.cycles_run != runs:
        raise RuntimeError(
            f"pilot supervisor did not complete cleanly: cycles={state.cycles_run} "
            f"terminal={state.terminal_kill} reason={state.stopped_reason}"
        )
    summary = {
        "schema_version": "foundry_pilot_summary.v1",
        "pilot_id": pilot_id,
        "simulation_only": True,
        "promotion_allowed": False,
        "network_calls": 0,
        "code_sha": checkout_sha,
        "runs_requested": runs,
        "runs_completed": state.cycles_run,
        "max_proposals_per_run": max_proposals_per_run,
        "max_spend_usd": max_spend_usd,
        "total_proposed": sum(item["proposed"] for item in cycle_payloads),
        "total_provider_failures": sum(
            item["provider_failures"] for item in cycle_payloads
        ),
        "total_spend_usd": sum(item["spend_usd"] for item in cycle_payloads),
        "cycle_receipts": cycle_receipts,
        "receipt_chain_head": previous,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    summary["digest"] = canonical_digest(summary)
    summary_path = pilot_root / "pilot_summary.json"
    _write_exclusive(summary_path, summary)
    summary["summary_path"] = str(summary_path)
    return summary
