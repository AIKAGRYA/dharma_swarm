"""Deterministic supervisor state machine and safety envelope."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from .adapters import BoundedCommandRunner, LabAdapter, RunFunction
from .config import LabConfig, SupervisorConfig
from .models import (
    ActionKind,
    ActionResult,
    LabAssessment,
    LabRuntimeState,
    LabSnapshot,
    LabState,
    ResourceStatus,
    TickReport,
)
from .receipts import ReceiptChain


STATE_SCHEMA = "dharma.lab_supervisor.runtime_state.v1"
TICK_SCHEMA = "dharma.lab_supervisor.tick.v1"


def _utc_date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


def _rfc3339(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _state_precedence(states: list[LabState]) -> LabState:
    for candidate in (LabState.HALTED, LabState.BLOCKED, LabState.DEGRADED):
        if candidate in states:
            return candidate
    return LabState.HEALTHY


class RuntimeStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, lab_names: list[str]) -> dict[str, LabRuntimeState]:
        raw: dict[str, Any] = {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if loaded.get("schema") == STATE_SCHEMA and isinstance(loaded.get("labs"), dict):
                raw = loaded["labs"]
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            pass
        result: dict[str, LabRuntimeState] = {}
        allowed = set(LabRuntimeState.__dataclass_fields__)
        for name in lab_names:
            row = raw.get(name, {})
            if not isinstance(row, dict):
                row = {}
            values = {key: value for key, value in row.items() if key in allowed}
            try:
                result[name] = LabRuntimeState(**values)
            except (TypeError, ValueError):
                result[name] = LabRuntimeState()
        return result

    def write(self, states: dict[str, LabRuntimeState], *, observed_at: float) -> None:
        payload = {
            "schema": STATE_SCHEMA,
            "observed_at": _rfc3339(observed_at),
            "labs": {name: asdict(state) for name, state in sorted(states.items())},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)


class Supervisor:
    """One bounded supervision tick.

    A recurring timer owns cadence.  This object owns one lock-protected
    inspect/assess/act/receipt transaction and never sleeps indefinitely.
    """

    def __init__(
        self,
        config: SupervisorConfig,
        *,
        state_root: Path,
        clock: Callable[[], float] = time.time,
        load_fn: Callable[[], tuple[float, float, float]] = os.getloadavg,
        cpu_count_fn: Callable[[], int | None] = os.cpu_count,
        disk_usage_fn: Callable[[str | os.PathLike[str]], shutil._ntuple_diskusage] = shutil.disk_usage,
        run_fn: RunFunction | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.state_root = Path(state_root).expanduser()
        self.clock = clock
        self.load_fn = load_fn
        self.cpu_count_fn = cpu_count_fn
        self.disk_usage_fn = disk_usage_fn
        self.run_fn = run_fn
        self.sleep_fn = sleep_fn
        self.receipts = ReceiptChain(self.state_root / "receipts.jsonl")
        self.runtime_store = RuntimeStore(self.state_root / "state.json")
        self.lock_path = self.state_root / "supervisor.lock"

    @contextmanager
    def _lock(self) -> Iterator[bool]:
        self.state_root.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        acquired = False
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                yield False
                return
            yield True
        finally:
            if acquired:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _resources(self) -> ResourceStatus:
        reasons: list[str] = []
        try:
            free = int(self.disk_usage_fn(self.state_root).free)
        except OSError:
            free = 0
            reasons.append("disk_probe_failed")
        if free < self.config.policy.min_free_disk_bytes:
            reasons.append("free_disk_floor_breached")
        cpus = max(1, int(self.cpu_count_fn() or 1))
        try:
            load_per_cpu = float(self.load_fn()[0]) / cpus
        except OSError:
            load_per_cpu = float("inf")
            reasons.append("load_probe_failed")
        if load_per_cpu > self.config.policy.max_load_per_cpu:
            reasons.append("load_floor_breached")
        return ResourceStatus(not reasons, free, load_per_cpu, tuple(reasons))

    def _assess(
        self,
        lab: LabConfig,
        snapshot: LabSnapshot,
        runtime: LabRuntimeState,
        *,
        now: float,
        resources: ResourceStatus,
    ) -> LabAssessment:
        reasons: list[str] = []
        # This exact branch is a governed negative-control marker.  There is no
        # inverse transition anywhere in supervisor code.
        if snapshot.halt_evidence:
            runtime.halt_latched = True
            runtime.halt_reasons = sorted(set(runtime.halt_reasons + list(snapshot.halt_evidence)))
        if runtime.halt_latched:
            reasons.extend(runtime.halt_reasons or ["historical_halt_latched"])
            state = LabState.HALTED
        elif snapshot.blockers:
            reasons.extend(snapshot.blockers)
            state = LabState.BLOCKED
        elif runtime.circuit_open_until > now:
            reasons.append(f"circuit_open_until:{_rfc3339(runtime.circuit_open_until)}")
            state = LabState.BLOCKED
        else:
            if lab.require_evidence and snapshot.latest_evidence_at is not None:
                age = max(0.0, now - snapshot.latest_evidence_at)
                if age > lab.max_stale_seconds:
                    reasons.append(f"stale_evidence_seconds:{int(age)}")
            reasons.extend(snapshot.provider_failures)
            reasons.extend(snapshot.warnings)
            state = LabState.DEGRADED if reasons else LabState.HEALTHY
        if not resources.safe and state is not LabState.HALTED:
            state = LabState.BLOCKED
            reasons.extend(resources.reasons)
        return LabAssessment(
            lab=lab.name,
            state=state,
            reasons=tuple(sorted(set(reasons))),
            observed_at=now,
            latest_evidence_at=snapshot.latest_evidence_at,
            halt_latched=runtime.halt_latched,
            evidence=snapshot.evidence,
        )

    def _action_budget(
        self,
        runtime: LabRuntimeState,
        action: ActionKind,
    ) -> tuple[bool, str]:
        policy = self.config.policy
        if runtime.actions_today >= policy.max_actions_per_lab_per_day:
            return False, "daily_action_budget_exhausted"
        if action is ActionKind.RUN_BOUNDED_TRIAL:
            if runtime.trials_today >= policy.max_trials_per_lab_per_day:
                return False, "daily_trial_budget_exhausted"
        if action in {ActionKind.QUARANTINE_PROVIDER, ActionKind.ROTATE_PROVIDER}:
            if runtime.provider_actions_today >= policy.max_provider_actions_per_lab_per_day:
                return False, "daily_provider_action_budget_exhausted"
        if action is ActionKind.PRUNE_DISPOSABLE:
            if runtime.cleanup_actions_today >= policy.max_cleanup_actions_per_lab_per_day:
                return False, "daily_cleanup_action_budget_exhausted"
        return True, ""

    @staticmethod
    def _record_action_budget(runtime: LabRuntimeState, action: ActionKind) -> None:
        runtime.actions_today += 1
        if action is ActionKind.RUN_BOUNDED_TRIAL:
            runtime.trials_today += 1
        elif action in {ActionKind.QUARANTINE_PROVIDER, ActionKind.ROTATE_PROVIDER}:
            runtime.provider_actions_today += 1
        elif action is ActionKind.PRUNE_DISPOSABLE:
            runtime.cleanup_actions_today += 1

    def _run_action(
        self,
        adapter: LabAdapter,
        runtime: LabRuntimeState,
        action: ActionKind,
        runner: BoundedCommandRunner,
        *,
        now: float,
        dry_run: bool,
    ) -> ActionResult:
        allowed, reason = self._action_budget(runtime, action)
        if not allowed:
            return ActionResult(adapter.config.name, action, "skipped", detail=reason)
        if action is ActionKind.PRUNE_DISPOSABLE:
            result = adapter.prune_disposable(now, dry_run=dry_run)
        else:
            result = adapter.run_declared_action(action, runner, dry_run=dry_run)
        if not dry_run and result.status not in {"unavailable", "skipped"}:
            self._record_action_budget(runtime, action)
            if action is ActionKind.RUN_BOUNDED_TRIAL:
                runtime.last_trial_at = now
        return result

    def _actions_for(
        self,
        adapter: LabAdapter,
        assessment: LabAssessment,
        snapshot: LabSnapshot,
        runtime: LabRuntimeState,
        runner: BoundedCommandRunner,
        *,
        now: float,
        dry_run: bool,
        resources: ResourceStatus,
    ) -> tuple[ActionResult, ...]:
        results = [ActionResult(adapter.config.name, ActionKind.INSPECT, "succeeded")]
        if assessment.state is LabState.HALTED:
            results.append(
                self._run_action(
                    adapter,
                    runtime,
                    ActionKind.KEEP_HALTED,
                    runner,
                    now=now,
                    dry_run=dry_run,
                )
            )
            return tuple(results)
        if not resources.safe:
            if adapter.config.disposable_paths:
                results.append(
                    self._run_action(
                        adapter,
                        runtime,
                        ActionKind.PRUNE_DISPOSABLE,
                        runner,
                        now=now,
                        dry_run=dry_run,
                    )
                )
            return tuple(results)
        if assessment.state is LabState.DEGRADED and snapshot.provider_failures:
            for action in (ActionKind.QUARANTINE_PROVIDER, ActionKind.ROTATE_PROVIDER):
                results.append(
                    self._run_action(
                        adapter,
                        runtime,
                        action,
                        runner,
                        now=now,
                        dry_run=dry_run,
                    )
                )
            return tuple(results)
        stale_only = assessment.state is LabState.DEGRADED and all(
            reason.startswith("stale_evidence_seconds:") for reason in assessment.reasons
        )
        if (
            assessment.state is LabState.HEALTHY or stale_only
        ) and adapter.config.bounded_trial is not None:
            due = now - runtime.last_trial_at >= adapter.config.trial_interval_seconds
            if due:
                results.append(
                    self._run_action(
                        adapter,
                        runtime,
                        ActionKind.RUN_BOUNDED_TRIAL,
                        runner,
                        now=now,
                        dry_run=dry_run,
                    )
                )
        return tuple(results)

    def _update_circuit(
        self,
        assessment: LabAssessment,
        snapshot: LabSnapshot,
        runtime: LabRuntimeState,
        *,
        now: float,
    ) -> None:
        # An open circuit is a fixed cooldown, not a sliding window.  Evidence
        # is still inspected while open, but cannot extend the deadline until
        # a fresh probe is permitted at or after expiry.
        if runtime.circuit_open_until > now:
            return
        if assessment.state is LabState.HEALTHY:
            runtime.consecutive_failures = 0
            runtime.circuit_open_until = 0.0
            return
        if assessment.state is LabState.HALTED:
            return
        probe_failed = snapshot.probe is not None and not snapshot.probe.succeeded
        actual_failure = bool(snapshot.provider_failures) or probe_failed
        if not actual_failure:
            if snapshot.probe is not None and snapshot.probe.succeeded:
                runtime.consecutive_failures = 0
                runtime.circuit_open_until = 0.0
            return
        runtime.consecutive_failures += 1
        if runtime.consecutive_failures >= self.config.policy.circuit_failure_threshold:
            runtime.circuit_open_until = max(
                runtime.circuit_open_until,
                now + self.config.policy.circuit_cooldown_seconds,
            )

    def run_tick(self, *, allow_actions: bool = False) -> TickReport:
        now = float(self.clock())
        tick_id = f"tick-{int(now)}-{uuid.uuid4().hex[:12]}"
        dry_run = self.config.policy.dry_run or not allow_actions
        with self._lock() as acquired:
            if not acquired:
                return TickReport(
                    TICK_SCHEMA,
                    tick_id,
                    now,
                    LabState.BLOCKED,
                    dry_run,
                    lock_contended=True,
                    internal_failure=True,
                    notes=("supervisor_lock_contended",),
                )
            chain_status = self.receipts.verify()
            if not chain_status.valid:
                return TickReport(
                    TICK_SCHEMA,
                    tick_id,
                    now,
                    LabState.BLOCKED,
                    dry_run,
                    internal_failure=True,
                    notes=("receipt_chain_invalid", *chain_status.errors),
                )
            names = [lab.name for lab in self.config.labs]
            runtimes = self.runtime_store.load(names)
            for lab, reasons in self.receipts.latched_labs().items():
                if lab in runtimes:
                    runtimes[lab].halt_latched = True
                    runtimes[lab].halt_reasons = sorted(
                        set(runtimes[lab].halt_reasons + reasons)
                    )
            resources = self._resources()
            runner_kwargs: dict[str, Any] = {"sleep_fn": self.sleep_fn}
            if self.run_fn is not None:
                runner_kwargs["run_fn"] = self.run_fn
            runner = BoundedCommandRunner(
                self.config.policy.max_subprocess_calls_per_tick,
                **runner_kwargs,
            )
            assessments: list[LabAssessment] = []
            date = _utc_date(now)
            for lab in self.config.labs:
                runtime = runtimes[lab.name]
                runtime.reset_daily_budget(date)
                circuit_open = runtime.circuit_open_until > now
                adapter = LabAdapter(lab)
                snapshot = adapter.observe(
                    now,
                    runner,
                    retry_attempts=self.config.policy.probe_retry_attempts,
                    skip_probe=circuit_open,
                )
                assessment = self._assess(
                    lab,
                    snapshot,
                    runtime,
                    now=now,
                    resources=resources,
                )
                actions = self._actions_for(
                    adapter,
                    assessment,
                    snapshot,
                    runtime,
                    runner,
                    now=now,
                    dry_run=dry_run,
                    resources=resources,
                )
                assessment = replace(assessment, actions=actions)
                assessments.append(assessment)
                self._update_circuit(assessment, snapshot, runtime, now=now)
            self.runtime_store.write(runtimes, observed_at=now)
            overall = _state_precedence([assessment.state for assessment in assessments])
            receipt_payload = {
                "tick_id": tick_id,
                "observed_at": _rfc3339(now),
                "state": overall,
                "dry_run": dry_run,
                "config_sha256": self.config.config_sha256,
                "cadence_seconds": self.config.policy.cadence_seconds,
                "resource_status": asdict(resources),
                "assessments": [asdict(assessment) for assessment in assessments],
                "subprocess_calls": runner.calls,
            }
            record_hash = self.receipts.append(receipt_payload)
            return TickReport(
                TICK_SCHEMA,
                tick_id,
                now,
                overall,
                dry_run,
                tuple(assessments),
                resources,
                record_hash,
            )

    def status(self) -> dict[str, Any]:
        chain = self.receipts.verify()
        names = [lab.name for lab in self.config.labs]
        runtimes = self.runtime_store.load(names)
        return {
            "schema": "dharma.lab_supervisor.status.v1",
            "state_root": str(self.state_root),
            "config_dry_run": self.config.policy.dry_run,
            "config_sha256": self.config.config_sha256,
            "cadence_seconds": self.config.policy.cadence_seconds,
            "labs": {name: asdict(runtime) for name, runtime in sorted(runtimes.items())},
            "receipt_chain": asdict(chain),
        }
