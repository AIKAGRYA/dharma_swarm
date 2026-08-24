from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from dharma_swarm.forge_lab import unattended_explore as unattended


def test_hash_chain_is_append_only_and_tamper_evident(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    first = unattended.append_chain(
        path,
        {"kind": "one"},
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    second = unattended.append_chain(
        path,
        {"kind": "two"},
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )

    rows = unattended.read_chain(
        path,
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    assert [row["sequence"] for row in rows] == [1, 2]
    assert second["previous_digest"] == first["receipt_digest"]

    payloads = [json.loads(line) for line in path.read_text().splitlines()]
    payloads[0]["kind"] = "tampered"
    path.write_text("".join(json.dumps(row) + "\n" for row in payloads))
    with pytest.raises(unattended.UnattendedError, match="digest mismatch"):
        unattended.read_chain(
            path,
            schema=unattended.RECEIPT_SCHEMA,
            digest_field="receipt_digest",
        )


def test_budget_ledger_reserves_before_run_and_caps_utc_periods(tmp_path: Path) -> None:
    ledger = tmp_path / "budget.jsonl"
    policy = unattended.BudgetPolicy(
        run_usd=0.75,
        run_calls=4,
        daily_usd=1.0,
        monthly_usd=2.0,
        daily_calls=4,
        monthly_calls=8,
    )
    row = unattended.reserve_budget(
        ledger,
        run_id="run-one",
        at="2026-08-25T00:00:00Z",
        policy=policy,
    )
    assert row["reserved_usd"] == 0.75
    assert row["reserved_logical_calls"] == 4
    assert "billing telemetry unavailable" in row["accounting_semantics"]

    with pytest.raises(unattended.UnattendedError) as error:
        unattended.reserve_budget(
            ledger,
            run_id="run-two",
            at="2026-08-25T23:59:59Z",
            policy=policy,
        )
    assert error.value.code == "BUDGET_CAP"

    next_day = unattended.reserve_budget(
        ledger,
        run_id="run-three",
        at="2026-08-26T00:00:00Z",
        policy=policy,
    )
    assert next_day["sequence"] == 2


def test_logical_provider_call_budget_refuses_the_fifth_dispatch() -> None:
    counter = unattended.LogicalCallBudget()
    for index in range(4):
        counter.consume(f"call-{index}")
    assert counter.used == unattended.LOGICAL_PROVIDER_CALL_SLOTS
    with pytest.raises(unattended.UnattendedError) as error:
        counter.consume("fifth")
    assert error.value.code == "LOGICAL_PROVIDER_CALL_CAP"


def _ready_doctor() -> dict[str, object]:
    return {
        "ok": True,
        "checks": {
            "providers": {
                "ready": True,
                "ttl_seconds": unattended.PROVIDER_TTL_SECONDS,
                "receipt": "/unused/provider.json",
            },
            "grader": {"ready": True, "docker_daemon_reachable": True},
            "taskbed": {"ready": True, "next_explore_task_id": "task-fixture"},
        },
    }


def test_admission_requires_halt_absent_exact_state_and_two_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("RSI_LAB_STATE", str(state))
    monkeypatch.setattr(
        unattended,
        "require_execution_source",
        lambda *_args, **_kwargs: {
            "ready": True,
            "repo": str(tmp_path / "release" / "repo"),
            "commit": "a" * 40,
        },
    )
    monkeypatch.setattr(unattended, "doctor", _ready_doctor)
    monkeypatch.setattr(
        unattended,
        "_selected_routes",
        lambda _check: [
            {"provider": "provider-a", "model_id": "model-a"},
            {"provider": "provider-b", "model_id": "model-b"},
        ],
    )

    admitted = unattended.admission_status(state.resolve())
    assert admitted["ready"] is True
    assert len({row["provider"] for row in admitted["routes"]}) == 2

    halt = state / ".dharma" / "forge_lab" / "HALT"
    halt.parent.mkdir(parents=True)
    halt.touch()
    refused = unattended.admission_status(state.resolve())
    assert refused["ready"] is False
    assert any(reason.startswith("HALT_present") for reason in refused["reasons"])


def test_child_config_is_fixed_1x1x1_hard_budget_and_explore_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    run_id = "unattended-test"
    run_dir = (
        state
        / ".dharma"
        / "forge_lab"
        / "unattended_explore"
        / "runs"
        / run_id
    )
    result_path = run_dir / "child_result.json"
    reservation = unattended.reserve_budget(
        state
        / ".dharma"
        / "forge_lab"
        / "unattended_explore"
        / "budget_ledger.jsonl",
        run_id=run_id,
        at="2026-08-25T00:00:00Z",
    )
    source_repo = tmp_path / "release" / "repo"
    spec = {
        "schema": unattended.RUNNER_SCHEMA,
        "run_id": run_id,
        "source_repo": str(source_repo),
        "source_commit": "b" * 40,
        "state_root": str(state),
        "archive_root": str(state / ".dharma" / "evolution_archive"),
        "scratch_root": str(state / ".dharma" / "evolution_worktrees"),
        "result_path": str(result_path),
        "routes": [
            {"provider": "provider-a", "model_id": "model-a"},
            {"provider": "provider-b", "model_id": "model-b"},
        ],
        "task_id": "task-fixture",
        "shape": {"generations": 1, "children": 1, "tasks": 1},
        "limits": {
            "logical_provider_call_slots": unattended.LOGICAL_PROVIDER_CALL_SLOTS,
            "per_call_tokens": unattended.PER_CALL_TOKENS,
            "per_candidate_tokens": unattended.PER_CANDIDATE_TOKENS,
            "per_candidate_usd": unattended.PER_CANDIDATE_USD,
            "max_experiment_tokens": unattended.MAX_EXPERIMENT_TOKENS,
            "external_timeout_seconds": unattended.DEFAULT_TIMEOUT_SECONDS,
        },
        "reservation_digest": reservation["ledger_digest"],
    }
    spec["spec_digest"] = unattended.content_digest(spec)
    spec_path = run_dir / "child_spec.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(json.dumps(spec) + "\n")
    monkeypatch.setenv("RSI_LAB_UNATTENDED_CHILD_RUN_ID", run_id)
    fake_secret = "provider-secret-must-never-enter-child-evidence"
    monkeypatch.setenv("OPENAI_API_KEY", fake_secret)
    monkeypatch.setattr(
        unattended,
        "admission_status",
        lambda _state: {
            "ready": True,
            "reasons": [],
            "source": {"commit": "b" * 40, "repo": str(source_repo)},
            "routes": spec["routes"],
            "task_id": spec["task_id"],
        },
    )
    monkeypatch.setattr(unattended, "_bounded_child_seams", lambda *_args: object())
    captured = {}

    async def fake_run(cfg, *, seams):
        captured["cfg"] = cfg
        captured["seams"] = seams
        return {
            "experiment_id": "experiment-1",
            "closeout_state": "inconclusive_low_power",
            "reasons": [f"provider fixture accidentally included {fake_secret}"],
        }

    monkeypatch.setattr(
        "dharma_swarm.forge_lab.experiment.run_experiment",
        fake_run,
    )

    assert unattended.run_child(spec_path) == 0
    cfg = captured["cfg"]
    assert (cfg.generations, cfg.children, cfg.tasks_per_generation) == (1, 1, 1)
    assert cfg.soft_token_cap is False
    assert cfg.force_single_llm_mutation is True
    assert cfg.budget_cap_tokens == unattended.PER_CANDIDATE_TOKENS
    assert cfg.max_experiment_tokens == unattended.MAX_EXPERIMENT_TOKENS
    result = json.loads(result_path.read_text())
    assert result["positive_rsi_claim"] is False
    assert result["epistemic_modality"] == "EXPLORE_ONLY"
    assert fake_secret not in result_path.read_text()

    tampered = dict(spec)
    tampered["reservation_digest"] = "sha256:" + "0" * 64
    tampered["spec_digest"] = unattended.content_digest(
        {key: value for key, value in tampered.items() if key != "spec_digest"}
    )
    spec_path.write_text(json.dumps(tampered) + "\n")
    with pytest.raises(unattended.UnattendedError) as error:
        unattended.run_child(spec_path)
    assert error.value.code == "CHILD_RESERVATION"


def test_parent_oneshot_reserves_then_seals_admission_and_closeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("RSI_LAB_STATE", str(state))
    routes = [
        {"provider": "provider-a", "model_id": "model-a"},
        {"provider": "provider-b", "model_id": "model-b"},
    ]
    monkeypatch.setattr(
        unattended,
        "admission_status",
        lambda _state: {
            "ready": True,
            "reasons": [],
            "source": {"commit": "c" * 40, "repo": str(tmp_path / "release" / "repo")},
            "routes": routes,
            "task_id": "task-fixture",
            "halt_path": str(state / ".dharma" / "forge_lab" / "HALT"),
        },
    )

    def fake_child(spec_path, *, run_id, timeout_seconds, log_path, halt_path):
        del timeout_seconds, halt_path
        spec = json.loads(spec_path.read_text())
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("bounded child fixture\n")
        child = {
            "schema": unattended.CHILD_SCHEMA,
            "run_id": run_id,
            "experiment_id": "experiment-fixture",
            "closeout_state": "inconclusive_low_power",
            "logical_provider_calls_used": 4,
            "logical_provider_call_limit": 4,
            "positive_rsi_claim": False,
        }
        child["result_digest"] = unattended.content_digest(child)
        unattended.write_json_exclusive(Path(spec["result_path"]), child)
        return 0, False, False, 1

    monkeypatch.setattr(unattended, "_run_child_process", fake_child)
    result = unattended.run_once(state, timeout_seconds=60)
    assert result["ok"] is True
    assert result["positive_rsi_claim"] is False

    control = state / ".dharma" / "forge_lab" / "unattended_explore"
    ledger = unattended.read_chain(
        control / "budget_ledger.jsonl",
        schema=unattended.LEDGER_SCHEMA,
        digest_field="ledger_digest",
    )
    assert ledger[0]["reserved_usd"] == 1.0
    receipts = unattended.read_chain(
        control / "receipts.jsonl",
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    assert len(ledger) == 1
    assert [row["kind"] for row in receipts] == ["run_admitted", "run_closeout"]
    assert receipts[-1]["epistemic_modality"] == "EXPLORE_ONLY"
    assert receipts[-1]["positive_rsi_claim"] is False

    def fake_halted(_spec_path, *, run_id, timeout_seconds, log_path, halt_path):
        del run_id, timeout_seconds, halt_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("halted child fixture\n")
        return -15, False, True, 2

    monkeypatch.setattr(unattended, "_run_child_process", fake_halted)
    halted = unattended.run_once(state, timeout_seconds=60)
    assert halted["ok"] is False
    assert halted["halted"] is True
    receipts = unattended.read_chain(
        control / "receipts.jsonl",
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    assert receipts[-1]["halted"] is True
    assert receipts[-1]["epistemic_modality"] == "InconclusiveOperatorHalt"


def test_external_watchdog_terminates_the_child_process_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TimedProcess:
        pid = 4242

        def wait(self, timeout):
            return -15

    process = TimedProcess()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)
    signals = []
    monkeypatch.setattr(unattended.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    spec = tmp_path / "spec.json"
    spec.write_text("{}\n")

    monotonic = iter((0.0, 61.0, 61.1))
    monkeypatch.setattr(unattended.time, "monotonic", lambda: next(monotonic))
    returncode, timed_out, halted, _wall = unattended._run_child_process(
        spec,
        run_id="watchdog",
        timeout_seconds=60,
        log_path=tmp_path / "child.log",
        halt_path=tmp_path / "HALT",
    )
    assert returncode == -15
    assert timed_out is True
    assert halted is False
    assert signals == [(4242, unattended.signal.SIGTERM)]


def test_halt_latch_terminates_running_child_and_is_typed_inconclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RunningProcess:
        pid = 4343

        def wait(self, timeout):
            return -15

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: RunningProcess())
    signals = []
    monkeypatch.setattr(unattended.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    spec = tmp_path / "spec.json"
    spec.write_text("{}\n")
    halt = tmp_path / "HALT"
    halt.touch()

    returncode, timed_out, halted, _wall = unattended._run_child_process(
        spec,
        run_id="halted-run",
        timeout_seconds=60,
        log_path=tmp_path / "halted.log",
        halt_path=halt,
    )
    assert returncode == -15
    assert timed_out is False
    assert halted is True
    assert signals == [(4343, unattended.signal.SIGTERM)]


def test_unattended_wrapper_and_systemd_timer_are_bounded() -> None:
    root = Path(__file__).resolve().parents[2] / "scripts" / "forge_lab"
    wrapper = (root / "rsi-unattended-explore").read_text()
    service = (root / "systemd" / "rsi-lab-explore.service").read_text()
    timer = (root / "systemd" / "rsi-lab-explore.timer").read_text()

    assert "RSI_LAB_DEV_SOURCE is forbidden" in wrapper
    assert '--state-root "${state}"' in wrapper
    assert "Type=oneshot" in service
    assert "TimeoutStartSec=2800" in service
    assert "ReadWritePaths=/root/rsi-lab/state" in service
    assert "ReadOnlyPaths=/root/rsi-lab/current" in service
    assert "ProtectHome=read-only" in service
    assert "NoNewPrivileges=true" in service
    assert "CapabilityBoundingSet=\n" in service
    assert "AmbientCapabilities=\n" in service
    assert "RestrictNamespaces=true" in service
    assert "ConditionPathExists=!/root/rsi-lab/state/.dharma/forge_lab/HALT" in service
    assert "Persistent=true" in timer
    assert "Unit=rsi-lab-explore.service" in timer
    syntax = subprocess.run(
        ["bash", "-n", str(root / "rsi-unattended-explore")],
        capture_output=True,
        check=False,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
