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
import math
import os
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache
from typing import Callable

from dharma_swarm.foundry import killswitch
from dharma_swarm.foundry.artifacts import ArtifactReplayError
from dharma_swarm.foundry.campaign import CampaignConfig, CampaignResult, dry_run_campaign
from dharma_swarm.foundry.kill_metrics import evaluate_kill_metrics, render_walking_brief
from dharma_swarm.foundry.runner_isolation import StrongIsolationUnavailable
from dharma_swarm.foundry.targets import TARGET_REGISTRY

_STATE_ROOT = Path.home() / ".dharma" / "foundry"
_SERVICE_STATE_WRITE_LOCK = threading.Lock()

# A cycle runs one bounded campaign against one target and returns its result.
CycleFn = Callable[[str, int, float, "Path | None"], CampaignResult]


@dataclass
class DaemonConfig:
    targets: list[str] = field(default_factory=lambda: list(TARGET_REGISTRY))
    cycle_generations: int = 3
    interval_seconds: float = 300.0
    max_cycles: int = 0            # 0 = run forever (until a HALT condition)
    budget_cap_usd: float = 300.0  # monthly model spend ceiling (free routes are $0)
    # Maximum provider liability admitted by one live/campaign cycle. The
    # daemon reserves this allowance durably before the cycle starts, so a
    # process/host crash cannot reopen spent-but-not-yet-reported capacity.
    cycle_budget_cap_usd: float = 5.0
    survival_floor: float = 0.30
    state_root: Path | None = None
    # Patient idle: for SELF-CLEARING halt conditions (operator STOP file,
    # monthly budget cap) the daemon sleeps and re-checks instead of exiting,
    # so systemd Restart=always doesn't churn and work resumes the moment the
    # condition clears (STOP removed / month rolls over). Kill-metric verdicts
    # and 3-strike failures still HALT hard — those need eyes, not patience.
    idle_on_stop: bool = False
    mode: str = "dry"
    provider_outage_threshold: int = 3
    provider_outage_cooldown_seconds: float = 300.0
    heartbeat_seconds: float = 60.0


@dataclass
class DaemonState:
    cycles_run: int = 0
    total_proposed: int = 0
    total_ring1_wins: int = 0
    total_ring2_survivors: int = 0
    total_provider_failures: int = 0
    total_spend_usd: float = 0.0
    committed_spend_usd: float = 0.0
    reserved_spend_usd: float = 0.0
    unresolved_spend_reservations: int = 0
    stopped_reason: str = ""
    last_snapshot: dict | None = None
    consecutive_failures: int = 0
    consecutive_provider_outages: int = 0
    last_error: str = ""
    terminal_kill: bool = False
    boot_id: str = ""


class FoundryStateError(RuntimeError):
    """Persistent state is unreadable or invalid; proceeding would fail open."""


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


_SPEND_LEDGER_SCHEMA = "foundry_spend_ledger.v2"


def _blank_spend_ledger() -> dict:
    return {
        "schema_version": _SPEND_LEDGER_SCHEMA,
        "month": _month_key(),
        "committed_spend_usd": 0.0,
        "reservations": [],
    }


def _read_spend_ledger(state_root: Path) -> dict:
    """Read/validate the current ledger, including crash-held reservations."""
    path = Path(state_root) / "spend_ledger.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _blank_spend_ledger()
    except OSError as exc:
        raise FoundryStateError(
            f"spend ledger unreadable ({type(exc).__name__})"
        ) from exc
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError("ledger is not an object")
        if data.get("month") != _month_key():
            return _blank_spend_ledger()

        schema = data.get("schema_version")
        if schema in (None, ""):
            # Compatibility read for the pre-reservation v1 ledger.
            committed = float(data.get("spend_usd", 0.0))
            raw_reservations: list[dict] = []
        elif schema == _SPEND_LEDGER_SCHEMA:
            committed = float(data.get("committed_spend_usd", 0.0))
            raw_reservations = data.get("reservations", [])
            if not isinstance(raw_reservations, list):
                raise TypeError("reservations is not a list")
        else:
            raise ValueError("unknown spend ledger schema")

        if not math.isfinite(committed) or committed < 0:
            raise ValueError("committed spend must be finite and non-negative")
        reservations: list[dict] = []
        seen: set[str] = set()
        for raw_reservation in raw_reservations:
            if not isinstance(raw_reservation, dict):
                raise TypeError("reservation is not an object")
            reservation_id = str(raw_reservation.get("reservation_id", ""))
            amount = float(raw_reservation.get("amount_usd", -1.0))
            if not reservation_id or reservation_id in seen:
                raise ValueError("reservation id is missing or duplicated")
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError("reservation must be finite and positive")
            seen.add(reservation_id)
            reservations.append({
                "reservation_id": reservation_id,
                "amount_usd": round(amount, 6),
                "created_at": str(raw_reservation.get("created_at", "")),
                "target_id": str(raw_reservation.get("target_id", "")),
                "boot_id": str(raw_reservation.get("boot_id", "")),
            })

        effective = round(
            committed + sum(item["amount_usd"] for item in reservations), 6
        )
        claimed = float(data.get("spend_usd", effective))
        if not math.isfinite(claimed) or abs(claimed - effective) > 0.000001:
            raise ValueError("spend total does not match committed plus reservations")
    except (ValueError, TypeError) as exc:
        raise FoundryStateError(
            f"spend ledger invalid ({type(exc).__name__})"
        ) from exc
    return {
        "schema_version": _SPEND_LEDGER_SCHEMA,
        "month": _month_key(),
        "committed_spend_usd": round(committed, 6),
        "reservations": reservations,
    }


def spend_ledger_summary(state_root: Path) -> dict:
    """Return conservative spend: committed charges plus unresolved holds."""
    ledger = _read_spend_ledger(state_root)
    reserved = round(
        sum(item["amount_usd"] for item in ledger["reservations"]), 6
    )
    committed = round(float(ledger["committed_spend_usd"]), 6)
    return {
        **ledger,
        "reserved_spend_usd": reserved,
        "spend_usd": round(committed + reserved, 6),
        "unresolved_reservations": len(ledger["reservations"]),
    }


def _load_month_spend(state_root: Path) -> float:
    """Resume this month's spend so a service restart can't reset the budget.

    Without this, ``Restart=always`` + a crash loop would grant a fresh cap
    every restart. The ledger is month-keyed; a new month starts at zero.
    """
    return float(spend_ledger_summary(state_root)["spend_usd"])


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Replace one JSON state file atomically and fsync file + directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temp.unlink(missing_ok=True)


def _write_spend_ledger(state_root: Path, ledger: dict) -> None:
    reservations = list(ledger.get("reservations", []))
    committed = round(float(ledger.get("committed_spend_usd", 0.0)), 6)
    reserved = round(sum(float(item["amount_usd"]) for item in reservations), 6)
    _atomic_write_json(
        Path(state_root) / "spend_ledger.json",
        {
            "schema_version": _SPEND_LEDGER_SCHEMA,
            "month": _month_key(),
            "committed_spend_usd": committed,
            "reservations": reservations,
            # Compatibility/inspection total: this is deliberately
            # conservative and includes unresolved crash reservations.
            "spend_usd": round(committed + reserved, 6),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _write_month_spend(state_root: Path, spend_usd: float) -> None:
    if not math.isfinite(spend_usd) or spend_usd < 0:
        raise FoundryStateError("spend ledger write requires non-negative finite spend")
    _write_spend_ledger(
        state_root,
        {
            "committed_spend_usd": round(spend_usd, 6),
            "reservations": [],
        },
    )


def _reserve_cycle_spend(
    state_root: Path,
    amount_usd: float,
    *,
    target_id: str,
    boot_id: str,
) -> str:
    if not math.isfinite(amount_usd) or amount_usd <= 0:
        raise FoundryStateError("cycle reservation must be finite and positive")
    ledger = _read_spend_ledger(state_root)
    reservation_id = str(uuid.uuid4())
    ledger["reservations"].append({
        "reservation_id": reservation_id,
        "amount_usd": round(amount_usd, 6),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_id": target_id,
        "boot_id": boot_id,
    })
    _write_spend_ledger(state_root, ledger)
    return reservation_id


def _settle_cycle_spend(
    state_root: Path,
    reservation_id: str,
    actual_spend_usd: float,
) -> float:
    if not math.isfinite(actual_spend_usd) or actual_spend_usd < 0:
        raise FoundryStateError("cycle reported invalid spend")
    ledger = _read_spend_ledger(state_root)
    matched = [
        item for item in ledger["reservations"]
        if item["reservation_id"] == reservation_id
    ]
    if len(matched) != 1:
        raise FoundryStateError("cycle spend reservation missing or duplicated")
    allowance = float(matched[0]["amount_usd"])
    ledger["reservations"] = [
        item for item in ledger["reservations"]
        if item["reservation_id"] != reservation_id
    ]
    ledger["committed_spend_usd"] = round(
        float(ledger["committed_spend_usd"]) + actual_spend_usd, 6
    )
    _write_spend_ledger(state_root, ledger)
    return allowance


def _sync_spend_state(state: DaemonState, state_root: Path) -> None:
    summary = spend_ledger_summary(state_root)
    state.committed_spend_usd = float(summary["committed_spend_usd"])
    state.reserved_spend_usd = float(summary["reserved_spend_usd"])
    state.unresolved_spend_reservations = int(summary["unresolved_reservations"])
    state.total_spend_usd = float(summary["spend_usd"])


@lru_cache(maxsize=1)
def _code_sha() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return proc.stdout.strip() or "unknown"


def _write_service_state(
    state_root: Path,
    state: DaemonState,
    *,
    status: str,
    mode: str,
    target_id: str = "",
) -> None:
    root = Path(state_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "foundry_service_state.v1",
        "boot_id": state.boot_id,
        "pid": os.getpid(),
        "code_sha": _code_sha(),
        "status": status,
        "mode": mode,
        "target_id": target_id,
        "cycles_run": state.cycles_run,
        "total_proposed": state.total_proposed,
        "provider_failures": state.total_provider_failures,
        "consecutive_provider_outages": state.consecutive_provider_outages,
        "committed_spend_usd": state.committed_spend_usd,
        "reserved_spend_usd": state.reserved_spend_usd,
        "unresolved_spend_reservations": state.unresolved_spend_reservations,
        "accounted_spend_usd": state.total_spend_usd,
        "terminal_kill": state.terminal_kill,
        "stopped_reason": state.stopped_reason,
        "last_error": state.last_error,
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
    }
    # The heartbeat thread and main loop can pulse at the same boundary. A
    # process-local lock plus UUID temp names prevents their writes racing;
    # file+directory fsync makes the winning snapshot durable across power loss.
    with _SERVICE_STATE_WRITE_LOCK:
        _atomic_write_json(root / "service_state.json", payload)


@contextmanager
def _heartbeat_during_cycle(
    state_root: Path,
    state: DaemonState,
    *,
    mode: str,
    target_id: str,
    interval_seconds: float,
):
    """Keep liveness fresh while a bounded oracle call is still in flight."""
    if interval_seconds <= 0:
        yield
        return
    stopped = threading.Event()

    def pulse() -> None:
        while not stopped.wait(interval_seconds):
            _write_service_state(
                state_root,
                state,
                status="running",
                mode=mode,
                target_id=target_id,
            )

    thread = threading.Thread(target=pulse, name="foundry-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1.0)


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
    state.boot_id = str(uuid.uuid4())
    _sync_spend_state(state, state_root)
    _write_service_state(state_root, state, status="starting", mode=config.mode)

    while config.max_cycles == 0 or cycle < config.max_cycles:
        # Refresh on every boundary so month rollover and any conservative
        # unresolved crash reservation are reflected before capacity opens.
        _sync_spend_state(state, state_root)
        if killswitch.is_stopped(state_root=state_root):
            if config.idle_on_stop and not killswitch.has_terminal_kill(state_root):
                _write_service_state(state_root, state, status="idle", mode=config.mode)
                sleep_fn(config.interval_seconds)
                _sync_spend_state(state, state_root)  # month may roll
                continue
            state.stopped_reason = f"kill-switch: {killswitch.stop_reason(state_root=state_root)}"
            state.terminal_kill = killswitch.has_terminal_kill(state_root)
            break
        remaining = config.budget_cap_usd - state.total_spend_usd
        if remaining <= 0:
            if config.idle_on_stop:
                _write_service_state(state_root, state, status="idle", mode=config.mode)
                sleep_fn(config.interval_seconds)
                _sync_spend_state(state, state_root)  # month may roll
                continue
            state.stopped_reason = "budget exhausted"
            break

        target_id = targets[cycle % len(targets)]
        cycle_budget = remaining
        reservation_id = ""
        if config.mode in {"live", "campaign"}:
            if not math.isfinite(config.cycle_budget_cap_usd) or (
                config.cycle_budget_cap_usd <= 0
            ):
                raise FoundryStateError(
                    "live/campaign cycle_budget_cap_usd must be finite and positive"
                )
            cycle_budget = min(remaining, config.cycle_budget_cap_usd)
            reservation_id = _reserve_cycle_spend(
                state_root,
                cycle_budget,
                target_id=target_id,
                boot_id=state.boot_id,
            )
            _sync_spend_state(state, state_root)
        _write_service_state(
            state_root, state, status="running", mode=config.mode, target_id=target_id
        )
        try:
            with _heartbeat_during_cycle(
                state_root,
                state,
                mode=config.mode,
                target_id=target_id,
                interval_seconds=config.heartbeat_seconds,
            ):
                result = cycle_fn(
                    target_id, config.cycle_generations, cycle_budget, state_root
                )
            state.consecutive_failures = 0
        except (ArtifactReplayError, StrongIsolationUnavailable) as exc:
            if reservation_id:
                # Unknown provider liability stays reserved. It can only be
                # released after an operator reconciles external billing.
                _sync_spend_state(state, state_root)
            state.consecutive_failures += 1
            is_replication = isinstance(exc, ArtifactReplayError)
            error_type = type(exc).__name__
            category = "replication_failure" if is_replication else "isolation_unavailable"
            state.last_error = f"{error_type}: terminal safety prerequisite failed"
            state.stopped_reason = f"terminal {category.replace('_', ' ')}"
            state.terminal_kill = True
            killswitch.persist_terminal_kill(
                state_root,
                category=category,
                reason=(
                    "artifact lineage or seeded replay did not verify"
                    if is_replication
                    else "strong Docker isolation unavailable; host execution refused"
                ),
                evidence={"target_id": target_id, "error_type": error_type},
            )
            break
        except Exception as exc:  # noqa: BLE001 — one red cycle must not crash-loop the service
            if reservation_id:
                _sync_spend_state(state, state_root)
            state.consecutive_failures += 1
            state.last_error = f"{type(exc).__name__}: cycle failed"
            if state.consecutive_failures >= 3:
                # Fail closed with evidence: three reds in a row is a broken
                # target/oracle, not turbulence. Halt so the operator sees it.
                state.stopped_reason = f"3 consecutive cycle failures; last: {state.last_error}"
                state.terminal_kill = True
                killswitch.persist_terminal_kill(
                    state_root,
                    category="cycle_failure",
                    reason="three consecutive campaign cycles failed",
                    evidence={"target_id": target_id, "error_type": type(exc).__name__},
                )
                break
            cycle += 1
            if config.max_cycles == 0 or cycle < config.max_cycles:
                sleep_fn(config.interval_seconds)
            continue

        actual_spend = float(result.spend_usd)
        if reservation_id:
            allowance = _settle_cycle_spend(
                state_root, reservation_id, actual_spend
            )
            _sync_spend_state(state, state_root)
            if actual_spend > allowance + 0.000001:
                state.stopped_reason = "terminal per-cycle budget overrun"
                state.last_error = "BudgetExceeded: actual spend exceeded durable reservation"
                state.terminal_kill = True
                killswitch.persist_terminal_kill(
                    state_root,
                    category="budget_overrun",
                    reason="cycle spend exceeded its pre-call durable allowance",
                    evidence={
                        "target_id": target_id,
                        "allowance_usd": allowance,
                        "actual_spend_usd": actual_spend,
                    },
                )
                break
        else:
            if not math.isfinite(actual_spend) or actual_spend < 0:
                raise FoundryStateError("cycle reported invalid spend")
            _write_month_spend(
                state_root,
                round(state.total_spend_usd + actual_spend, 6),
            )
            _sync_spend_state(state, state_root)

        if result.provider_failures > 0 and result.proposed == 0:
            state.total_provider_failures += result.provider_failures
            state.consecutive_provider_outages += 1
            state.last_error = "ProviderExhausted: no proposal reached evaluation"
            if state.consecutive_provider_outages >= max(
                1, config.provider_outage_threshold
            ):
                state.stopped_reason = "terminal provider outage threshold reached"
                state.terminal_kill = True
                killswitch.persist_terminal_kill(
                    state_root,
                    category="provider_exhausted",
                    reason="all configured provider routes failed across bounded retries",
                    evidence={
                        "target_id": target_id,
                        "consecutive_outages": state.consecutive_provider_outages,
                    },
                )
                break
            _write_service_state(
                state_root,
                state,
                status="degraded_provider_outage",
                mode=config.mode,
                target_id=target_id,
            )
            cycle += 1
            if config.max_cycles == 0 or cycle < config.max_cycles:
                cooldown = max(
                    1.0,
                    min(
                        config.interval_seconds,
                        config.provider_outage_cooldown_seconds,
                    ),
                )
                sleep_fn(cooldown)
            continue

        state.consecutive_provider_outages = 0

        state.cycles_run += 1
        state.total_proposed += result.proposed
        state.total_ring1_wins += result.ring1_wins
        state.total_ring2_survivors += result.ring2_survivors
        state.total_provider_failures += result.provider_failures
        snapshot = evaluate_kill_metrics(
            cohort_survival=result.mean_survival,
            verified_improvements=result.ring2_survivors,
            prior_cohort_survival=prior_survival,
            survival_floor=config.survival_floor,
        )
        state.last_snapshot = snapshot.to_dict()
        _write_cycle_artifacts(state_root, state.last_snapshot, render_walking_brief(snapshot))

        if snapshot.any_kill():
            killed_metrics = [v.metric for v in snapshot.verdicts if v.status == "kill"]
            state.stopped_reason = "kill-metric verdict: " + ", ".join(killed_metrics)
            state.terminal_kill = True
            killswitch.persist_terminal_kill(
                state_root,
                category="kill_metric",
                reason="standing kill metric fired",
                evidence={"metrics": killed_metrics, "target_id": target_id},
            )
            break

        prior_survival = result.mean_survival
        cycle += 1
        if config.max_cycles == 0 or cycle < config.max_cycles:
            sleep_fn(config.interval_seconds)

    if not state.stopped_reason:
        state.stopped_reason = f"reached max_cycles={config.max_cycles}"
    _write_service_state(
        state_root,
        state,
        status="killed" if state.terminal_kill else "stopped",
        mode=config.mode,
    )
    return state


def state_json(state: DaemonState) -> str:
    return json.dumps(asdict(state), indent=2, default=str)
