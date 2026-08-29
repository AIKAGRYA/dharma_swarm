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
import hashlib
import math
import os
import shutil
import re
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
from dharma_swarm.foundry.live import ProviderUsageUnverifiable
from dharma_swarm.foundry.runner_isolation import StrongIsolationUnavailable
from dharma_swarm.foundry.targets import TARGET_REGISTRY

_STATE_ROOT = Path.home() / ".dharma" / "foundry"
_SERVICE_STATE_WRITE_LOCK = threading.Lock()
_CYCLE_ACCOUNTING = threading.local()

# A cycle runs one bounded campaign against one target and returns its result.
CycleFn = Callable[[str, int, float, "Path | None"], CampaignResult]


def current_cycle_accounting_context() -> dict[str, object]:
    """Secret-free reservation binding consumed by the campaign receipt."""
    return dict(getattr(_CYCLE_ACCOUNTING, "binding", {}) or {})


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
    # Patient idle applies only to the self-clearing monthly budget cap. STOP,
    # HALT, KILL, quarantine, kill metrics, and repeated failures remain durable
    # operator-bound stops; marker deletion never resumes them.
    idle_on_stop: bool = False
    mode: str = "dry"
    provider_outage_threshold: int = 3
    provider_outage_cooldown_seconds: float = 300.0
    heartbeat_seconds: float = 60.0
    plateau_cycle_threshold: int = 5
    min_free_disk_bytes: int = 2 * 1024 * 1024 * 1024
    max_state_bytes: int = 20 * 1024 * 1024 * 1024


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
    writer_fence: int = 0
    restart_churn_24h: int = 0
    last_completed_cycle_at: str = ""
    total_valid_candidates: int = 0
    verified_receipts: int = 0
    comparable_fitness: float = 0.0
    no_op_ratio: float = 0.0
    spend_rate_usd_per_hour: float = 0.0
    target_quarantine: dict[str, dict] = field(default_factory=dict)


class FoundryStateError(RuntimeError):
    """Persistent state is unreadable or invalid; proceeding would fail open."""


class WriterLeaseContended(FoundryStateError):
    """Another process owns the canonical state-root writer fence."""


@dataclass
class CanonicalWriterLease:
    """Process-held flock plus durable monotonically increasing fence token."""

    state_root: Path
    boot_id: str
    fence: int
    token: str
    lock_handle: object = field(repr=False)
    released: bool = False

    @classmethod
    def acquire(cls, state_root: Path, *, boot_id: str) -> "CanonicalWriterLease":
        import fcntl

        root = Path(state_root)
        root.mkdir(parents=True, exist_ok=True)
        handle = (root / ".canonical-writer.lock").open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise WriterLeaseContended(
                f"canonical Foundry writer already owns {root}"
            ) from exc
        fence_path = root / "writer_fence.json"
        control_path = root / "control_state.json"
        try:
            control = _read_control_state(root)
            control_fence = int(control.get("writer_fence", 0))
        except FoundryStateError:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
            raise
        try:
            prior = json.loads(fence_path.read_text(encoding="utf-8"))
            if (
                not isinstance(prior, dict)
                or prior.get("schema_version") != "foundry_writer_fence.v1"
                or isinstance(prior.get("fence"), bool)
                or not isinstance(prior.get("fence"), int)
                or prior["fence"] < 1
            ):
                raise ValueError("invalid fence projection")
            prior_fence = prior["fence"]
            if prior_fence < control_fence:
                raise ValueError("fence projection rolled back below control high-watermark")
        except FileNotFoundError:
            if control_path.exists() or control_fence:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()
                raise FoundryStateError(
                    "writer fence projection missing after durable control state"
                )
            prior_fence = 0
        except (OSError, ValueError, TypeError) as exc:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
            raise FoundryStateError("writer fence is unreadable or invalid") from exc
        lease = cls(
            state_root=root,
            boot_id=boot_id,
            fence=prior_fence + 1,
            token=uuid.uuid4().hex,
            lock_handle=handle,
        )
        lease.renew(status="acquired")
        return lease

    def _payload(self, *, status: str) -> dict:
        return {
            "schema_version": "foundry_writer_fence.v1",
            "fence": self.fence,
            "token_digest": "sha256:" + hashlib.sha256(
                self.token.encode("ascii")
            ).hexdigest(),
            "boot_id": self.boot_id,
            "pid": os.getpid(),
            "status": status,
            "renewed_at": datetime.now(timezone.utc).isoformat(),
        }

    def renew(self, *, status: str = "held") -> None:
        if self.released:
            raise FoundryStateError("writer fence was already released")
        _atomic_write_json(self.state_root / "writer_fence.json", self._payload(status=status))

    def assert_current(self) -> None:
        try:
            payload = json.loads(
                (self.state_root / "writer_fence.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError, TypeError) as exc:
            raise FoundryStateError("writer fence disappeared or became invalid") from exc
        expected = self._payload(status="held")["token_digest"]
        if int(payload.get("fence", -1)) != self.fence or payload.get("token_digest") != expected:
            raise FoundryStateError("writer fence superseded; stale writer refused")

    def close(self) -> None:
        import fcntl

        if self.released:
            return
        try:
            self.renew(status="released")
        finally:
            self.released = True
            fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_UN)
            self.lock_handle.close()

    def __enter__(self) -> "CanonicalWriterLease":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


_CONTROL_SCHEMA = "foundry_control_state.v2"


def _blank_control_state() -> dict:
    return {
        "schema_version": _CONTROL_SCHEMA,
        "prior_survival": None,
        "consecutive_failures": 0,
        "consecutive_provider_outages": 0,
        "total_proposed": 0,
        "total_valid_candidates": 0,
        "total_ring1_wins": 0,
        "total_ring2_survivors": 0,
        "total_provider_failures": 0,
        "no_op_count": 0,
        "last_completed_cycle_at": "",
        "comparable_fitness": 0.0,
        "target_quarantine": {},
        "boot_history": [],
        "writer_fence": 0,
    }


def _validate_timestamp(raw: object, *, field: str, allow_empty: bool = True) -> str:
    value = str(raw)
    if not value and allow_empty:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise FoundryStateError(f"control state {field} invalid") from exc
    if parsed.tzinfo is None:
        raise FoundryStateError(f"control state {field} must be timezone-aware")
    normalized = parsed.astimezone(timezone.utc)
    if (normalized - datetime.now(timezone.utc)).total_seconds() > 300:
        raise FoundryStateError(f"control state {field} is implausibly future-dated")
    return normalized.isoformat()


def _reject_nonfinite(value: object, *, field: str = "state") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise FoundryStateError(f"{field} contains a non-finite number")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_nonfinite(item, field=f"{field}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_nonfinite(item, field=f"{field}[{index}]")


def _read_control_state(state_root: Path) -> dict:
    path = Path(state_root) / "control_state.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _blank_control_state()
    except (OSError, ValueError, TypeError) as exc:
        raise FoundryStateError("control state unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != _CONTROL_SCHEMA:
        raise FoundryStateError("control state schema invalid")
    _reject_nonfinite(payload, field="control state")
    base = _blank_control_state()
    base.update(payload)
    if not isinstance(base.get("target_quarantine"), dict) or not isinstance(base.get("boot_history"), list):
        raise FoundryStateError("control state collections invalid")
    for key in (
        "consecutive_failures", "consecutive_provider_outages", "total_proposed",
        "total_valid_candidates", "total_ring1_wins", "total_ring2_survivors",
        "total_provider_failures", "no_op_count",
    ):
        value = base[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise FoundryStateError(f"control state {key} invalid")
        if value < 0:
            raise FoundryStateError(f"control state {key} negative")
        base[key] = value
    writer_fence = base.get("writer_fence", 0)
    if isinstance(writer_fence, bool) or not isinstance(writer_fence, int) or writer_fence < 0:
        raise FoundryStateError("control state writer_fence invalid")
    base["writer_fence"] = writer_fence
    prior_survival = base.get("prior_survival")
    if prior_survival is not None:
        if isinstance(prior_survival, bool) or not isinstance(prior_survival, (int, float)):
            raise FoundryStateError("control state prior_survival invalid")
        prior_survival = float(prior_survival)
        if not math.isfinite(prior_survival) or not 0.0 <= prior_survival <= 1.0:
            raise FoundryStateError("control state prior_survival out of range")
        base["prior_survival"] = prior_survival
    comparable = base.get("comparable_fitness", 0.0)
    if isinstance(comparable, bool) or not isinstance(comparable, (int, float)):
        raise FoundryStateError("control state comparable_fitness invalid")
    comparable = float(comparable)
    if not math.isfinite(comparable):
        raise FoundryStateError("control state comparable_fitness non-finite")
    base["comparable_fitness"] = comparable
    base["last_completed_cycle_at"] = _validate_timestamp(
        base.get("last_completed_cycle_at", ""), field="last_completed_cycle_at"
    )
    history = base["boot_history"]
    if len(history) > 10_000:
        raise FoundryStateError("control state boot_history is oversized")
    base["boot_history"] = [
        _validate_timestamp(item, field="boot_history", allow_empty=False)
        for item in history
    ]
    allowed_progress = {
        "best_comparable_fitness", "plateau_cycles", "last_cycle_at",
        "quarantined", "reason", "quarantined_at",
    }
    normalized_quarantine: dict[str, dict] = {}
    for target, raw in base["target_quarantine"].items():
        if not isinstance(target, str) or not target or len(target) > 200:
            raise FoundryStateError("control state target quarantine id invalid")
        if not isinstance(raw, dict) or set(raw) - allowed_progress:
            raise FoundryStateError("control state target quarantine entry invalid")
        best = raw.get("best_comparable_fitness", 0.0)
        plateau = raw.get("plateau_cycles", 0)
        quarantined = raw.get("quarantined", False)
        if isinstance(best, bool) or not isinstance(best, (int, float)) or not math.isfinite(float(best)):
            raise FoundryStateError("control state target fitness invalid")
        if isinstance(plateau, bool) or not isinstance(plateau, int) or plateau < 0:
            raise FoundryStateError("control state plateau counter invalid")
        if not isinstance(quarantined, bool):
            raise FoundryStateError("control state quarantine flag invalid")
        reason = raw.get("reason", "")
        if not isinstance(reason, str) or len(reason) > 1000:
            raise FoundryStateError("control state quarantine reason invalid")
        normalized = {
            "best_comparable_fitness": float(best),
            "plateau_cycles": plateau,
            "quarantined": quarantined,
        }
        if raw.get("last_cycle_at", ""):
            normalized["last_cycle_at"] = _validate_timestamp(
                raw["last_cycle_at"], field="target last_cycle_at", allow_empty=False
            )
        if reason:
            normalized["reason"] = reason
        if raw.get("quarantined_at", ""):
            normalized["quarantined_at"] = _validate_timestamp(
                raw["quarantined_at"], field="target quarantined_at", allow_empty=False
            )
        normalized_quarantine[target] = normalized
    base["target_quarantine"] = normalized_quarantine
    if base["no_op_count"] > base["total_proposed"]:
        raise FoundryStateError("control state no-op count exceeds proposals")
    if base["total_valid_candidates"] > base["total_proposed"]:
        raise FoundryStateError("control state valid candidates exceed proposals")
    return base


def _write_control_state(state_root: Path, payload: dict, lease: CanonicalWriterLease) -> None:
    lease.assert_current()
    body = {**payload, "schema_version": _CONTROL_SCHEMA, "writer_fence": lease.fence}
    _atomic_write_json(Path(state_root) / "control_state.json", body)


def _state_tree_bytes(
    root: Path,
    *,
    max_entries: int = 100_000,
    max_scan_seconds: float = 2.0,
) -> tuple[int, bool, int]:
    """Return bounded storage evidence without following symlinks."""
    total = 0
    scanned = 0
    complete = True
    started = time.monotonic()
    stack = [Path(root)]
    while stack:
        if scanned >= max_entries or time.monotonic() - started >= max_scan_seconds:
            complete = False
            break
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    scanned += 1
                    if scanned > max_entries or (
                        time.monotonic() - started >= max_scan_seconds
                    ):
                        complete = False
                        break
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        complete = False
                if not complete:
                    break
        except OSError:
            complete = False
            break
    return total, complete, scanned


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
    _atomic_write_json(root / "kill_metrics.json", snapshot_dict)
    _atomic_write_text(root / "brief_fragment.md", brief)


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
        ledger_month = str(data.get("month", ""))
        current_month = _month_key()
        if not re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", ledger_month):
            raise ValueError("spend ledger month is invalid")
        if ledger_month > current_month:
            raise ValueError("spend ledger is future-dated")

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
                "origin_month": str(
                    raw_reservation.get("origin_month", ledger_month)
                ),
            })
            if not re.fullmatch(
                r"[0-9]{4}-(?:0[1-9]|1[0-2])",
                reservations[-1]["origin_month"],
            ):
                raise ValueError("reservation origin month is invalid")

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
        # Prior-month committed spend does not consume the new monthly cap,
        # but unresolved holds do: a call crossing UTC month end must remain
        # conservatively reserved until settlement/operator reconciliation.
        "committed_spend_usd": (
            round(committed, 6) if ledger_month == _month_key() else 0.0
        ),
        "reservations": reservations,
        "rollover_from_month": (
            ledger_month if ledger_month != _month_key() else ""
        ),
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
    try:
        encoded = (
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    except (TypeError, ValueError) as exc:
        raise FoundryStateError("refusing non-canonical/non-finite JSON state") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
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


def _atomic_write_text(path: Path, payload: str) -> None:
    """Replace one UTF-8 text projection atomically and durably."""
    if not isinstance(payload, str):
        raise FoundryStateError("text state payload must be a string")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
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


def _archive_prior_spend_ledger(state_root: Path) -> None:
    """Content-seal an old-month ledger before replacing its projection."""
    root = Path(state_root)
    path = root / "spend_ledger.json"
    try:
        raw = path.read_bytes()
        prior = json.loads(raw)
    except FileNotFoundError:
        return
    except (OSError, ValueError, TypeError) as exc:
        raise FoundryStateError("prior spend ledger cannot be archived") from exc
    if not isinstance(prior, dict):
        raise FoundryStateError("prior spend ledger cannot be archived")
    prior_month = str(prior.get("month", ""))
    if prior_month == _month_key():
        return
    if not re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", prior_month):
        raise FoundryStateError("prior spend ledger month is invalid")
    raw_digest = hashlib.sha256(raw).hexdigest()
    archive_root = root / "spend_archives"
    archive = archive_root / f"{prior_month}__{raw_digest}.json"
    if archive.exists():
        try:
            existing = json.loads(archive.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise FoundryStateError("prior spend archive is unreadable") from exc
        if existing.get("prior_ledger_sha256") != "sha256:" + raw_digest:
            raise FoundryStateError("prior spend archive digest mismatch")
        return
    body = {
        "schema_version": "foundry_spend_archive.v1",
        "archived_month": prior_month,
        "successor_month": _month_key(),
        "prior_ledger_sha256": "sha256:" + raw_digest,
        "prior_ledger": prior,
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        body["digest"] = "sha256:" + hashlib.sha256(
            json.dumps(
                body, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        ).hexdigest()
        encoded = (
            json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FoundryStateError("prior spend ledger contains non-canonical data") from exc
    archive_root.mkdir(parents=True, exist_ok=True)
    try:
        with archive.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        return
    directory = os.open(archive_root, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _write_spend_ledger(state_root: Path, ledger: dict) -> None:
    reservations = list(ledger.get("reservations", []))
    committed = round(float(ledger.get("committed_spend_usd", 0.0)), 6)
    reserved = round(sum(float(item["amount_usd"]) for item in reservations), 6)
    _archive_prior_spend_ledger(state_root)
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
        "origin_month": _month_key(),
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


def _write_cycle_settlement(
    state_root: Path,
    *,
    result: CampaignResult,
    reservation_id: str,
    allowance_usd: float,
    actual_spend_usd: float,
    lease: CanonicalWriterLease,
) -> Path:
    lease.assert_current()
    campaign_id = result.campaign_id or f"cycle-{uuid.uuid4().hex}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", campaign_id):
        raise FoundryStateError("campaign accounting id is unsafe")
    body = {
        "schema_version": "foundry_cycle_settlement.v1",
        "campaign_id": campaign_id,
        "target_id": result.target_id,
        "reservation_id": reservation_id,
        "allowance_usd": allowance_usd,
        "actual_spend_usd": actual_spend_usd,
        "provider_accounting_digest": result.provider_accounting_digest,
        "provider_accounting_path": result.provider_accounting_path,
        "writer_fence": lease.fence,
        "boot_id": lease.boot_id,
        "settled_at": datetime.now(timezone.utc).isoformat(),
    }
    body["digest"] = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    root = Path(state_root) / "cycle_settlements"
    path = root / f"{campaign_id}.json"
    encoded = (json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    root.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise FoundryStateError("duplicate campaign settlement refused") from exc
    directory = os.open(root, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return path


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
    lease: CanonicalWriterLease | None = None,
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
        "writer_fence": state.writer_fence,
        "restart_churn_24h": state.restart_churn_24h,
        "last_completed_cycle_at": state.last_completed_cycle_at,
        "total_valid_candidates": state.total_valid_candidates,
        "verified_receipts": state.verified_receipts,
        "comparable_fitness": state.comparable_fitness,
        "no_op_ratio": state.no_op_ratio,
        "spend_rate_usd_per_hour": state.spend_rate_usd_per_hour,
        "target_quarantine": state.target_quarantine,
    }
    # The heartbeat thread and main loop can pulse at the same boundary. A
    # process-local lock plus UUID temp names prevents their writes racing;
    # file+directory fsync makes the winning snapshot durable across power loss.
    with _SERVICE_STATE_WRITE_LOCK:
        if lease is not None:
            lease.assert_current()
        _atomic_write_json(root / "service_state.json", payload)


def _sd_notify(message: str) -> bool:
    """Best-effort systemd notification; absence is normal outside the unit."""
    import socket

    address = os.environ.get("NOTIFY_SOCKET", "")
    if not address:
        return False
    if address.startswith("@"):
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(address)
            sock.sendall(message.encode("utf-8"))
        return True
    except OSError:
        return False


@contextmanager
def _heartbeat_during_cycle(
    state_root: Path,
    state: DaemonState,
    *,
    mode: str,
    target_id: str,
    interval_seconds: float,
    lease: CanonicalWriterLease | None = None,
):
    """Keep liveness fresh while a bounded oracle call is still in flight."""
    if interval_seconds <= 0:
        yield
        return
    stopped = threading.Event()

    def pulse() -> None:
        while not stopped.wait(interval_seconds):
            if lease is not None:
                lease.renew(status="running")
            _write_service_state(
                state_root,
                state,
                status="running",
                mode=mode,
                target_id=target_id,
                lease=lease,
            )
            _sd_notify(f"WATCHDOG=1\nSTATUS=running target={target_id}")

    thread = threading.Thread(target=pulse, name="foundry-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1.0)


def _run_daemon_owned(
    config: DaemonConfig | None = None,
    *,
    cycle_fn: CycleFn = _default_cycle,
    sleep_fn: Callable[[float], None] = time.sleep,
    lease: CanonicalWriterLease,
) -> DaemonState:
    """Run the bounded-continuous engine until a HALT condition."""
    config = config or DaemonConfig()
    state = DaemonState()
    state_root = config.state_root if config.state_root is not None else _STATE_ROOT
    targets = config.targets or list(TARGET_REGISTRY)
    control = _read_control_state(state_root)
    prior_survival_raw = control.get("prior_survival")
    prior_survival: float | None = (
        None if prior_survival_raw is None else float(prior_survival_raw)
    )
    cycle = 0
    state.boot_id = lease.boot_id
    state.writer_fence = lease.fence
    state.consecutive_failures = int(control["consecutive_failures"])
    state.consecutive_provider_outages = int(
        control["consecutive_provider_outages"]
    )
    state.total_proposed = int(control["total_proposed"])
    state.total_valid_candidates = int(control["total_valid_candidates"])
    state.total_ring1_wins = int(control["total_ring1_wins"])
    state.total_ring2_survivors = int(control["total_ring2_survivors"])
    state.verified_receipts = state.total_ring2_survivors
    state.total_provider_failures = int(control["total_provider_failures"])
    state.last_completed_cycle_at = str(control["last_completed_cycle_at"])
    state.comparable_fitness = float(control["comparable_fitness"])
    state.target_quarantine = dict(control["target_quarantine"])
    boot_history = []
    now = datetime.now(timezone.utc)
    for raw in control["boot_history"]:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if (now - parsed.astimezone(timezone.utc)).total_seconds() <= 86_400:
            boot_history.append(parsed.astimezone(timezone.utc).isoformat())
    boot_history.append(now.isoformat())
    control["boot_history"] = boot_history
    state.restart_churn_24h = len(boot_history)
    if state.total_proposed:
        state.no_op_ratio = round(
            int(control["no_op_count"]) / state.total_proposed, 6
        )

    def checkpoint() -> None:
        control.update({
            "prior_survival": prior_survival,
            "consecutive_failures": state.consecutive_failures,
            "consecutive_provider_outages": state.consecutive_provider_outages,
            "total_proposed": state.total_proposed,
            "total_valid_candidates": state.total_valid_candidates,
            "total_ring1_wins": state.total_ring1_wins,
            "total_ring2_survivors": state.total_ring2_survivors,
            "total_provider_failures": state.total_provider_failures,
            "last_completed_cycle_at": state.last_completed_cycle_at,
            "comparable_fitness": state.comparable_fitness,
            "target_quarantine": state.target_quarantine,
        })
        _write_control_state(state_root, control, lease)

    def supervised_sleep(seconds: float, *, status: str = "sleeping") -> None:
        """Keep both the writer fence and systemd watchdog alive while idle."""
        remaining = max(0.0, float(seconds))
        if sleep_fn is not time.sleep:
            sleep_fn(remaining)
            lease.renew(status=status)
            _write_service_state(
                state_root, state, status=status, mode=config.mode, lease=lease
            )
            _sd_notify(f"WATCHDOG=1\nSTATUS={status}")
            return
        pulse_every = max(1.0, min(config.heartbeat_seconds, 60.0))
        while remaining > 0:
            step = min(pulse_every, remaining)
            sleep_fn(step)
            remaining -= step
            lease.renew(status=status)
            _write_service_state(
                state_root, state, status=status, mode=config.mode, lease=lease
            )
            _sd_notify(f"WATCHDOG=1\nSTATUS={status}")

    checkpoint()
    _sync_spend_state(state, state_root)
    _write_service_state(
        state_root, state, status="starting", mode=config.mode, lease=lease
    )
    lease.renew(status="starting")
    _sd_notify("READY=1\nWATCHDOG=1\nSTATUS=Foundry starting")

    while config.max_cycles == 0 or cycle < config.max_cycles:
        # Refresh on every boundary so month rollover and any conservative
        # unresolved crash reservation are reflected before capacity opens.
        _sync_spend_state(state, state_root)
        lease.renew(status="boundary")
        free_bytes = shutil.disk_usage(state_root).free
        state_bytes, scan_complete, scanned_entries = _state_tree_bytes(state_root)
        if (
            not scan_complete
            or free_bytes < config.min_free_disk_bytes
            or state_bytes > config.max_state_bytes
        ):
            state.stopped_reason = "terminal disk threshold"
            state.last_error = (
                "DiskPressure: state scan incomplete"
                if not scan_complete
                else "DiskPressure: Foundry storage safety threshold crossed"
            )
            state.terminal_kill = True
            killswitch.persist_terminal_kill(
                state_root,
                category=("state_scan_incomplete" if not scan_complete else "disk_pressure"),
                reason=(
                    "bounded Foundry state scan could not prove storage safety"
                    if not scan_complete
                    else "free disk or Foundry state size crossed configured threshold"
                ),
                evidence={
                    "free_bytes": free_bytes,
                    "min_free_bytes": config.min_free_disk_bytes,
                    "state_bytes": state_bytes,
                    "max_state_bytes": config.max_state_bytes,
                    "scan_complete": scan_complete,
                    "scanned_entries": scanned_entries,
                },
            )
            checkpoint()
            break
        if killswitch.is_stopped(state_root=state_root):
            killswitch.latch_current_stop(state_root=state_root)
            state.stopped_reason = f"kill-switch: {killswitch.stop_reason(state_root=state_root)}"
            state.terminal_kill = killswitch.has_terminal_kill(state_root)
            checkpoint()
            break
        remaining = config.budget_cap_usd - state.total_spend_usd
        if remaining <= 0:
            if config.idle_on_stop:
                _write_service_state(
                    state_root, state, status="idle", mode=config.mode, lease=lease
                )
                _sd_notify("WATCHDOG=1\nSTATUS=idle budget exhausted")
                supervised_sleep(config.interval_seconds, status="idle")
                _sync_spend_state(state, state_root)  # month may roll
                continue
            state.stopped_reason = "budget exhausted"
            break

        eligible_targets = [
            target for target in targets
            if not bool((state.target_quarantine.get(target) or {}).get("quarantined"))
        ]
        if not eligible_targets:
            state.stopped_reason = "terminal all vetted targets quarantined"
            state.terminal_kill = True
            killswitch.persist_terminal_kill(
                state_root,
                category="targets_exhausted",
                reason="all configured vetted targets reached durable quarantine",
                evidence={"targets": targets},
            )
            checkpoint()
            break
        target_id = eligible_targets[cycle % len(eligible_targets)]
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
            state_root, state, status="running", mode=config.mode,
            target_id=target_id, lease=lease,
        )
        cycle_started = time.monotonic()
        try:
            _CYCLE_ACCOUNTING.binding = {
                "reservation_id": reservation_id,
                "reserved_usd": cycle_budget if reservation_id else 0.0,
                "writer_fence": lease.fence,
                "boot_id": lease.boot_id,
                "target_id": target_id,
            }
            try:
                with _heartbeat_during_cycle(
                    state_root,
                    state,
                    mode=config.mode,
                    target_id=target_id,
                    interval_seconds=config.heartbeat_seconds,
                    lease=lease,
                ):
                    result = cycle_fn(
                        target_id, config.cycle_generations, cycle_budget, state_root
                    )
            finally:
                _CYCLE_ACCOUNTING.binding = {}
            state.consecutive_failures = 0
        except (
            ArtifactReplayError,
            StrongIsolationUnavailable,
            ProviderUsageUnverifiable,
        ) as exc:
            if reservation_id:
                # Unknown provider liability stays reserved. It can only be
                # released after an operator reconciles external billing.
                _sync_spend_state(state, state_root)
            state.consecutive_failures += 1
            is_replication = isinstance(exc, ArtifactReplayError)
            is_usage = isinstance(exc, ProviderUsageUnverifiable)
            error_type = type(exc).__name__
            category = (
                "replication_failure" if is_replication
                else ("usage_unverifiable" if is_usage else "isolation_unavailable")
            )
            state.last_error = f"{error_type}: terminal safety prerequisite failed"
            state.stopped_reason = f"terminal {category.replace('_', ' ')}"
            state.terminal_kill = True
            killswitch.persist_terminal_kill(
                state_root,
                category=category,
                reason=(
                    "artifact lineage or seeded replay did not verify"
                    if is_replication
                    else (
                        "provider usage was not actual or conservatively bounded"
                        if is_usage
                        else "strong Docker isolation unavailable; host execution refused"
                    )
                ),
                evidence={"target_id": target_id, "error_type": error_type},
            )
            checkpoint()
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
                checkpoint()
                break
            checkpoint()
            cycle += 1
            if config.max_cycles == 0 or cycle < config.max_cycles:
                supervised_sleep(config.interval_seconds)
            continue

        actual_spend = float(result.spend_usd)
        if reservation_id:
            allowance = _settle_cycle_spend(
                state_root, reservation_id, actual_spend
            )
            _sync_spend_state(state, state_root)
            _write_cycle_settlement(
                state_root,
                result=result,
                reservation_id=reservation_id,
                allowance_usd=allowance,
                actual_spend_usd=actual_spend,
                lease=lease,
            )
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
                checkpoint()
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
                checkpoint()
                break
            _write_service_state(
                state_root,
                state,
                status="degraded_provider_outage",
                mode=config.mode,
                target_id=target_id,
                lease=lease,
            )
            checkpoint()
            cycle += 1
            if config.max_cycles == 0 or cycle < config.max_cycles:
                cooldown = max(
                    1.0,
                    min(
                        config.interval_seconds,
                        config.provider_outage_cooldown_seconds,
                    ),
                )
                supervised_sleep(cooldown, status="provider_cooldown")
            continue

        state.consecutive_provider_outages = 0

        state.cycles_run += 1
        state.total_proposed += result.proposed
        state.total_ring1_wins += result.ring1_wins
        state.total_ring2_survivors += result.ring2_survivors
        state.total_provider_failures += result.provider_failures
        no_ops = int(result.trip_reasons.get("no_op_diff", 0))
        control["no_op_count"] = int(control["no_op_count"]) + no_ops
        valid_candidates = max(0, result.proposed - result.tripwire_trips)
        state.total_valid_candidates += valid_candidates
        state.verified_receipts = state.total_ring2_survivors
        state.comparable_fitness = max(state.comparable_fitness, result.best_fitness)
        state.no_op_ratio = (
            round(int(control["no_op_count"]) / state.total_proposed, 6)
            if state.total_proposed else 0.0
        )
        elapsed = max(0.001, time.monotonic() - cycle_started)
        state.spend_rate_usd_per_hour = round(actual_spend * 3600.0 / elapsed, 6)
        state.last_completed_cycle_at = datetime.now(timezone.utc).isoformat()

        target_progress = dict(state.target_quarantine.get(target_id) or {})
        prior_best = float(target_progress.get("best_comparable_fitness", 0.0))
        improved = (
            result.ring2_survivors > 0
            and result.best_fitness > prior_best + 1e-12
        )
        target_progress["best_comparable_fitness"] = max(
            prior_best, result.best_fitness
        )
        target_progress["plateau_cycles"] = (
            0 if improved else int(target_progress.get("plateau_cycles", 0)) + 1
        )
        target_progress["last_cycle_at"] = state.last_completed_cycle_at
        if target_progress["plateau_cycles"] >= max(
            1, config.plateau_cycle_threshold
        ):
            target_progress.update({
                "quarantined": True,
                "reason": "target plateau threshold reached without a reproduced survivor",
                "quarantined_at": state.last_completed_cycle_at,
            })
        state.target_quarantine[target_id] = target_progress
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
            checkpoint()
            break

        prior_survival = result.mean_survival
        checkpoint()
        cycle += 1
        if config.max_cycles == 0 or cycle < config.max_cycles:
            supervised_sleep(config.interval_seconds)

    if not state.stopped_reason:
        state.stopped_reason = f"reached max_cycles={config.max_cycles}"
    _write_service_state(
        state_root,
        state,
        status="killed" if state.terminal_kill else "stopped",
        mode=config.mode,
        lease=lease,
    )
    checkpoint()
    _sd_notify(
        "STOPPING=1\nSTATUS="
        + ("terminal safety halt" if state.terminal_kill else state.stopped_reason)
    )
    return state


def run_daemon(
    config: DaemonConfig | None = None,
    *,
    cycle_fn: CycleFn = _default_cycle,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> DaemonState:
    """Acquire the sole canonical writer fence, then run the daemon."""
    effective = config or DaemonConfig()
    root = effective.state_root if effective.state_root is not None else _STATE_ROOT
    boot_id = str(uuid.uuid4())
    with CanonicalWriterLease.acquire(Path(root), boot_id=boot_id) as lease:
        return _run_daemon_owned(
            effective,
            cycle_fn=cycle_fn,
            sleep_fn=sleep_fn,
            lease=lease,
        )


def state_json(state: DaemonState) -> str:
    return json.dumps(asdict(state), indent=2, default=str, allow_nan=False)
