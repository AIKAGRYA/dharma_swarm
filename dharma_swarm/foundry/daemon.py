"""The non-stop engine — a bounded-continuous Foundry loop for an always-on host.

GitHub Actions cron is the light always-on layer (report cadence). Serious
signal needs the inner loop running at volume, continuously — which is what this
daemon does on an always-on host (the VPS shift named in
organism-rewire-2026-07 next-item 4). Each cycle it runs a bounded campaign
against a rotating target, then:

- checks the kill-switch and HALTS if set (operator STOP or holon kill),
- tracks cumulative spend and HALTS when the monthly budget is exhausted,
- computes the standing kill-metrics and HALTS on any KILL verdict (fail-closed
  — a gaming/replication/ban signal stops the engine, it does not grind on),
- writes a kill-metrics snapshot + a walking-brief fragment every cycle so the
  operator's phone always reflects reality,
- sleeps, then repeats.

It never selects on money and never lights a self-modification fuse; it only runs
the external-target refinery. Pure/injectable so it is fully testable without a
host, a clock, a network, or a model key.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from dharma_swarm.foundry import killswitch
from dharma_swarm.foundry.campaign import CampaignConfig, CampaignResult, dry_run_campaign
from dharma_swarm.foundry.kill_metrics import evaluate_kill_metrics, render_walking_brief, snapshot_json
from dharma_swarm.foundry.targets import TARGET_REGISTRY

_STATE_ROOT = Path.home() / ".dharma" / "foundry"

# A cycle runs one bounded campaign against one target and returns its result.
CycleFn = Callable[[str, int, float, "Path | None"], CampaignResult]


@dataclass
class DaemonConfig:
    targets: list[str] = field(default_factory=lambda: list(TARGET_REGISTRY))
    cycle_generations: int = 3
    interval_seconds: float = 300.0
    max_cycles: int = 0            # 0 = run forever (until a HALT condition)
    budget_cap_usd: float = 300.0  # monthly model spend ceiling (free routes are $0)
    survival_floor: float = 0.30
    state_root: Path | None = None
    # Patient idle: for SELF-CLEARING halt conditions (operator STOP file,
    # monthly budget cap) the daemon sleeps and re-checks instead of exiting,
    # so systemd Restart=always doesn't churn and work resumes the moment the
    # condition clears (STOP removed / month rolls over). Kill-metric verdicts
    # and 3-strike failures still HALT hard — those need eyes, not patience.
    idle_on_stop: bool = False


@dataclass
class DaemonState:
    cycles_run: int = 0
    total_proposed: int = 0
    total_ring1_wins: int = 0
    total_ring2_survivors: int = 0
    total_spend_usd: float = 0.0
    stopped_reason: str = ""
    last_snapshot: dict | None = None
    consecutive_failures: int = 0
    last_error: str = ""


def _default_cycle(target_id: str, generations: int, budget_cap: float,
                   state_root: Path | None) -> CampaignResult:
    """Default cycle: a hermetic dry-run campaign (no keys/network).

    Live operation swaps this for a cycle that runs the real army against a
    pinned target under docker isolation; the daemon logic is identical.
    """
    spec = TARGET_REGISTRY[target_id]
    config = CampaignConfig(generations=generations, budget_cap_usd=budget_cap)
    return dry_run_campaign(spec, config=config, state_root=state_root)


def _write_cycle_artifacts(state_root: Path, snapshot_dict: dict, brief: str) -> None:
    root = Path(state_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "kill_metrics.json").write_text(json.dumps(snapshot_dict, indent=2), encoding="utf-8")
    (root / "brief_fragment.md").write_text(brief, encoding="utf-8")


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _load_month_spend(state_root: Path) -> float:
    """Resume this month's spend so a service restart can't reset the budget.

    Without this, ``Restart=always`` + a crash loop would grant a fresh cap
    every restart. The ledger is month-keyed; a new month starts at zero.
    """
    path = Path(state_root) / "spend_ledger.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("month") == _month_key():
            return float(data.get("spend_usd", 0.0))
    except (OSError, ValueError):
        pass
    return 0.0


def _write_month_spend(state_root: Path, spend_usd: float) -> None:
    path = Path(state_root) / "spend_ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "month": _month_key(),
        "spend_usd": round(spend_usd, 6),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")


def run_daemon(
    config: DaemonConfig | None = None,
    *,
    cycle_fn: CycleFn = _default_cycle,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> DaemonState:
    """Run the bounded-continuous engine until a HALT condition."""
    config = config or DaemonConfig()
    state = DaemonState()
    state_root = config.state_root if config.state_root is not None else _STATE_ROOT
    targets = config.targets or list(TARGET_REGISTRY)
    prior_survival: float | None = None
    cycle = 0
    state.total_spend_usd = _load_month_spend(state_root)

    while config.max_cycles == 0 or cycle < config.max_cycles:
        if killswitch.is_stopped(state_root=state_root):
            if config.idle_on_stop:
                sleep_fn(config.interval_seconds)
                state.total_spend_usd = _load_month_spend(state_root)  # month may roll
                continue
            state.stopped_reason = f"kill-switch: {killswitch.stop_reason(state_root=state_root)}"
            break
        remaining = config.budget_cap_usd - state.total_spend_usd
        if remaining <= 0:
            if config.idle_on_stop:
                sleep_fn(config.interval_seconds)
                state.total_spend_usd = _load_month_spend(state_root)  # month may roll
                continue
            state.stopped_reason = "budget exhausted"
            break

        target_id = targets[cycle % len(targets)]
        try:
            result = cycle_fn(target_id, config.cycle_generations, remaining, state_root)
            state.consecutive_failures = 0
        except Exception as exc:  # noqa: BLE001 — one red cycle must not crash-loop the service
            state.consecutive_failures += 1
            state.last_error = f"{type(exc).__name__}: {exc}"
            if state.consecutive_failures >= 3:
                # Fail closed with evidence: three reds in a row is a broken
                # target/oracle, not turbulence. Halt so the operator sees it.
                state.stopped_reason = f"3 consecutive cycle failures; last: {state.last_error}"
                break
            cycle += 1
            if config.max_cycles == 0 or cycle < config.max_cycles:
                sleep_fn(config.interval_seconds)
            continue

        state.cycles_run += 1
        state.total_proposed += result.proposed
        state.total_ring1_wins += result.ring1_wins
        state.total_ring2_survivors += result.ring2_survivors
        state.total_spend_usd = round(state.total_spend_usd + result.spend_usd, 6)
        _write_month_spend(state_root, state.total_spend_usd)

        snapshot = evaluate_kill_metrics(
            cohort_survival=result.mean_survival,
            verified_improvements=result.ring2_survivors,
            prior_cohort_survival=prior_survival,
            survival_floor=config.survival_floor,
        )
        state.last_snapshot = snapshot.to_dict()
        _write_cycle_artifacts(state_root, state.last_snapshot, render_walking_brief(snapshot))

        if snapshot.any_kill():
            state.stopped_reason = "kill-metric verdict: " + ", ".join(
                v.metric for v in snapshot.verdicts if v.status == "kill"
            )
            break

        prior_survival = result.mean_survival
        cycle += 1
        if config.max_cycles == 0 or cycle < config.max_cycles:
            sleep_fn(config.interval_seconds)

    if not state.stopped_reason:
        state.stopped_reason = f"reached max_cycles={config.max_cycles}"
    return state


def state_json(state: DaemonState) -> str:
    return json.dumps(asdict(state), indent=2, default=str)
