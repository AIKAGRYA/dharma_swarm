from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from dharma_swarm.forge_lab import unattended_explore as unattended
from dharma_swarm.forge_lab import unattended_ledger
from dharma_swarm.forge_lab import provider_selftest


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


def test_first_chain_append_fsyncs_its_parent_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synced: list[Path] = []
    monkeypatch.setattr(
        unattended_ledger,
        "_fsync_directory",
        lambda path: synced.append(path),
    )
    path = tmp_path / "chain" / "receipts.jsonl"

    unattended.append_chain(
        path,
        {"kind": "durable"},
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )

    assert synced == [path.parent]


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


def test_logical_provider_call_budget_refuses_after_the_fixed_dispatch_shape() -> None:
    counter = unattended.LogicalCallBudget()
    for index in range(unattended.LOGICAL_PROVIDER_CALL_SLOTS):
        counter.consume(f"call-{index}")
    assert counter.used == unattended.LOGICAL_PROVIDER_CALL_SLOTS
    with pytest.raises(unattended.UnattendedError) as error:
        counter.consume("sixth")
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


def _role_bindings() -> dict[str, dict[str, str]]:
    return {
        "mutator": {
            "role": "mutator",
            "provider": "provider-a",
            "model_id": "model-a",
        },
        "solver": {
            "role": "solver",
            "provider": "provider-a",
            "model_id": "model-a",
        },
        "verifier": {
            "role": "verifier",
            "provider": "provider-b",
            "model_id": "model-b",
        },
    }


def _model_evidence() -> dict[str, object]:
    return {
        "role_bindings": _role_bindings(),
        "routes": [
            {"provider": "provider-a", "model_id": "model-a"},
            {"provider": "provider-b", "model_id": "model-b"},
        ],
        "model_profile_digest": "sha256:" + "a" * 64,
        "provider_receipt_digest": "sha256:" + "b" * 64,
    }


def test_admission_rejects_symlinked_state_substrate_before_control_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = (tmp_path / "state").resolve()
    outside = tmp_path / "outside"
    state.mkdir()
    outside.mkdir()
    (state / ".dharma").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("RSI_LAB_STATE", str(state))

    status = unattended.admission_status(state)

    assert status["ready"] is False
    assert status["reasons"][0].startswith("STATE_ROOT_UNSAFE:")
    assert list(outside.iterdir()) == []


def test_model_evidence_requires_receipt_bound_to_exact_active_roles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "provider.json"
    activation_bindings = list(_role_bindings().values())
    policy = {
        "configuration": {
            "model_selection": {
                "source": "active_model_role_profile",
                "activation_profile_digest": "sha256:" + "a" * 64,
                "role_bindings": activation_bindings,
            }
        }
    }
    payload = {
        "schema": provider_selftest.PROVIDER_SELFTEST_SCHEMA,
        "profile": "staged",
        "live": True,
        "ok": True,
        "policy": policy,
        "policy_digest": unattended.content_digest(policy),
        "rows": [
            {
                "callable": True,
                "provider": "provider-a",
                "requested_model": "model-a",
            },
            {
                "callable": True,
                "provider": "provider-b",
                "requested_model": "model-b",
            },
        ],
        "receipt": str(receipt),
        "cached": False,
    }
    payload["receipt_digest"] = provider_selftest._receipt_digest(payload)
    receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        unattended,
        "activation_status",
        lambda: {
            "active": True,
            "integrity": "verified",
            "current_profile_digest": "sha256:" + "a" * 64,
            "role_bindings": activation_bindings,
        },
    )

    evidence = unattended._selected_model_evidence({"receipt": str(receipt)})

    assert evidence["role_bindings"] == _role_bindings()
    assert evidence["model_profile_digest"] == "sha256:" + "a" * 64
    assert evidence["provider_receipt_digest"] == payload["receipt_digest"]

    payload["policy"]["configuration"]["model_selection"][
        "activation_profile_digest"
    ] = "sha256:" + "c" * 64
    payload["policy_digest"] = unattended.content_digest(payload["policy"])
    payload["receipt_digest"] = provider_selftest._receipt_digest(payload)
    receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(unattended.UnattendedError) as error:
        unattended._selected_model_evidence({"receipt": str(receipt)})
    assert error.value.code == "PROVIDER_RECEIPT_PROFILE_MISMATCH"


def test_admission_requires_halt_absent_exact_state_and_two_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    logical_state = tmp_path / "state-current"
    logical_state.symlink_to(state, target_is_directory=True)
    monkeypatch.setenv("RSI_LAB_STATE", str(logical_state))
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
        "reconciliation_status",
        lambda: {"ok": True, "read_only": True, "findings": []},
    )
    monkeypatch.setattr(
        unattended,
        "_selected_model_evidence",
        lambda _check: _model_evidence(),
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


def test_admission_refuses_unreconciled_control_plane_before_spend(
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
        "reconciliation_status",
        lambda: {
            "ok": False,
            "read_only": True,
            "findings": [
                {
                    "code": "ACTIVE_CAMPAIGN_MISSING_RUN",
                    "campaign": "stale-campaign",
                }
            ],
        },
    )
    monkeypatch.setattr(
        unattended,
        "_selected_model_evidence",
        lambda _check: _model_evidence(),
    )

    refused = unattended.admission_status(state.resolve())

    assert refused["ready"] is False
    assert "control_plane_reconciliation_required" in refused["reasons"]
    assert refused["reconciliation"]["findings"][0]["campaign"] == "stale-campaign"


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
        "role_bindings": _role_bindings(),
        "model_profile_digest": "sha256:" + "a" * 64,
        "provider_receipt_digest": "sha256:" + "b" * 64,
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
            "role_bindings": spec["role_bindings"],
            "model_profile_digest": spec["model_profile_digest"],
            "provider_receipt_digest": spec["provider_receipt_digest"],
            "task_id": spec["task_id"],
        },
    )
    def fake_seams(_spec, counter):
        for label in (
            "candidate_generation",
            "candidate_generation",
            "mutation",
            "candidate_solver",
            "candidate_verifier",
        ):
            counter.consume(label)
        return object()

    monkeypatch.setattr(unattended, "_bounded_child_seams", fake_seams)
    captured = {}

    async def fake_run(cfg, *, seams):
        captured["cfg"] = cfg
        captured["seams"] = seams
        return {
            "experiment_id": "experiment-1",
            "closeout_state": "inconclusive_low_power",
            "reasons": [f"provider fixture accidentally included {fake_secret}"],
            "stats": {
                "counters": {"graded": 2, "paired_controls": 1, "blocked": 0}
            },
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
    assert cfg.mutator_model == "model-a"
    assert cfg.solver_model == "model-a"
    assert cfg.verifier_model == "model-b"
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
            "role_bindings": _role_bindings(),
            "model_profile_digest": "sha256:" + "a" * 64,
            "provider_receipt_digest": "sha256:" + "b" * 64,
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
            "logical_provider_calls_used": unattended.LOGICAL_PROVIDER_CALL_SLOTS,
            "logical_provider_call_limit": unattended.LOGICAL_PROVIDER_CALL_SLOTS,
            "logical_provider_calls_by_role": {
                "candidate_generation": 2,
                "mutation": 1,
                "candidate_solver": 1,
                "candidate_verifier": 1,
            },
            "expected_provider_calls_by_role": {
                "candidate_generation": 2,
                "mutation": 1,
                "candidate_solver": 1,
                "candidate_verifier": 1,
            },
            "execution_shape_ok": True,
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
    assert ledger[0]["reserved_usd"] == unattended.RUN_USD_RESERVATION
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
    assert 'state="$(cd -- "${state}" && pwd -P)"' in wrapper
    assert 'export RSI_LAB_PYDEPS="${pydeps}"' in wrapper
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
