from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import unattended_explore as unattended
from dharma_swarm.forge_lab import unattended_child_support
from dharma_swarm.forge_lab import unattended_ledger
from dharma_swarm.forge_lab import unattended_scratch
from dharma_swarm.forge_lab import provider_selftest
from dharma_swarm.forge_lab.experiment import Seams

_CONTEXT_DIGEST = "sha256:" + "d" * 64


@pytest.fixture(autouse=True)
def _admitted_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        unattended,
        "load_admitted_task_context",
        lambda task_id, *, state_root: (
            {"task_id": task_id},
            {"fixture.py": "fixture\n"},
            {"task_id": task_id, "binding_digest": _CONTEXT_DIGEST},
        ),
    )


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


def test_admission_rejects_world_writable_state_before_control_writes(
    tmp_path: Path,
) -> None:
    state = (tmp_path / "state").resolve()
    state.mkdir(mode=0o777)
    state.chmod(0o777)

    status = unattended.admission_status(state)

    assert status["ready"] is False
    assert status["reasons"][0].startswith("STATE_ROOT_UNSAFE:")
    assert list(state.iterdir()) == []


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


def test_judge_cache_refusal_is_receipted_before_budget_or_child_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = (tmp_path / "state").resolve()
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
        lambda: {"ok": True, "read_only": True, "findings": []},
    )
    monkeypatch.setattr(
        unattended,
        "_selected_model_evidence",
        lambda _check: _model_evidence(),
    )

    def refuse_judge_cache(_task_id: str, *, state_root: Path):
        del state_root
        raise unattended.UnattendedContextError(
            "JUDGE_CACHE_DIGEST_MISMATCH",
            "release-bound judge cache digest mismatch",
        )

    budget_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    child_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def unexpected_budget(*args, **kwargs):
        budget_calls.append((args, kwargs))
        raise AssertionError("budget reservation must follow admitted context")

    def unexpected_child(*args, **kwargs):
        child_calls.append((args, kwargs))
        raise AssertionError("child/provider dispatch must follow admitted context")

    monkeypatch.setattr(unattended, "load_admitted_task_context", refuse_judge_cache)
    monkeypatch.setattr(unattended, "reserve_budget", unexpected_budget)
    monkeypatch.setattr(unattended, "_run_child_process", unexpected_child)

    with pytest.raises(unattended.UnattendedError) as error:
        unattended.run_once(state, timeout_seconds=60)

    assert error.value.code == "ADMISSION_REFUSED"
    assert budget_calls == []
    assert child_calls == []
    control = state / ".dharma" / "forge_lab" / "unattended_explore"
    assert not (control / "budget_ledger.jsonl").exists()
    receipts = unattended.read_chain(
        control / "receipts.jsonl",
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    assert len(receipts) == 1
    refusal = receipts[0]
    assert refusal["kind"] == "admission_refusal"
    assert refusal["reasons"] == [
        "JUDGE_CACHE_DIGEST_MISMATCH:release-bound judge cache digest mismatch"
    ]
    assert refusal["provider_calls"] == 0
    assert refusal["usd_reserved"] == 0.0
    assert refusal["positive_rsi_claim"] is False


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
        "scratch_root": str(
            state
            / ".dharma"
            / "evolution_worktrees"
            / "unattended"
            / run_id
        ),
        "result_path": str(result_path),
        "routes": [
            {"provider": "provider-a", "model_id": "model-a"},
            {"provider": "provider-b", "model_id": "model-b"},
        ],
        "role_bindings": _role_bindings(),
        "model_profile_digest": "sha256:" + "a" * 64,
        "provider_receipt_digest": "sha256:" + "b" * 64,
        "task_id": "task-fixture",
        "task_context_binding_digest": _CONTEXT_DIGEST,
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
    scratch_create = unattended.create_run_scratch(
        state,
        run_id,
        source_commit="b" * 40,
        spec_digest=spec["spec_digest"],
        created_at="2026-08-25T00:00:00Z",
    )
    monkeypatch.setenv("RSI_LAB_UNATTENDED_CHILD_RUN_ID", run_id)
    monkeypatch.setenv(
        "RSI_LAB_UNATTENDED_SCRATCH_DEVICE",
        str(scratch_create["root_identity"]["device"]),
    )
    monkeypatch.setenv(
        "RSI_LAB_UNATTENDED_SCRATCH_INODE",
        str(scratch_create["root_identity"]["inode"]),
    )
    monkeypatch.setenv(
        "RSI_LAB_UNATTENDED_SCRATCH_MARKER_DIGEST",
        str(scratch_create["marker_digest"]),
    )
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
            "task_context_binding": {
                "task_id": spec["task_id"],
                "binding_digest": _CONTEXT_DIGEST,
            },
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
        return Seams(
            make_worktree=lambda **_kwargs: tmp_path / "unused-scratch",
            remove_worktree=lambda **_kwargs: None,
        )

    monkeypatch.setattr(unattended, "_bounded_child_seams", fake_seams)
    captured = {}

    async def fake_run(cfg, *, seams):
        captured["runs"] = int(captured.get("runs", 0)) + 1
        captured["cfg"] = cfg
        captured["seams"] = seams
        return {
            "experiment_id": "experiment-1",
            "closeout_state": "inconclusive_low_power",
            "reasons": [f"provider fixture accidentally included {fake_secret}"],
            "scratch_worktree": {
                "path": str(Path(spec["scratch_root"]) / "experiment-1" / "repo"),
                "state": "removed",
                "removed": True,
            },
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

    spec_path.write_text(json.dumps(spec) + "\n")
    marker_path = Path(spec["scratch_root"]) / unattended_scratch.SCRATCH_MARKER
    original_marker = marker_path.read_bytes()
    drifted_marker = json.loads(original_marker)
    drifted_marker["created_at"] = "2026-08-25T00:00:01Z"
    drifted_marker["marker_digest"] = unattended.content_digest(
        {
            key: value
            for key, value in drifted_marker.items()
            if key != "marker_digest"
        }
    )
    marker_path.write_text(json.dumps(drifted_marker) + "\n")
    os.chmod(marker_path, 0o600)
    with pytest.raises(unattended.UnattendedError) as marker_error:
        unattended.run_child(spec_path)
    assert marker_error.value.code == "SCRATCH_MARKER_MISMATCH"
    assert captured["runs"] == 1
    assert unattended._lexists(Path(spec["scratch_root"]))
    assert marker_path.is_file()

    marker_path.write_bytes(original_marker)
    os.chmod(marker_path, 0o600)
    unattended.cleanup_run_scratch(
        state,
        run_id,
        source_commit="b" * 40,
        spec_digest=spec["spec_digest"],
        expected_root_identity=scratch_create["root_identity"],
        expected_marker_digest=scratch_create["marker_digest"],
    )


def test_scratch_custody_cleans_an_aborted_child_clone(tmp_path: Path) -> None:
    source_repo = tmp_path / "source"
    archive_path = tmp_path / "archive" / "archive.jsonl"
    scratch_repo = tmp_path / "scratch" / "experiment-1" / "repo"
    removals: list[tuple[Path, Path, str]] = []

    def make_worktree(**_kwargs) -> Path:
        scratch_repo.mkdir(parents=True)
        return scratch_repo

    def remove_worktree(
        *, source_repo: Path, repo: Path, experiment_id: str
    ) -> None:
        removals.append((source_repo, repo, experiment_id))
        repo.rmdir()
        repo.parent.rmdir()

    def abort(seams: Seams) -> None:
        created = seams.make_worktree(
            source_repo=source_repo,
            experiment_id="experiment-1",
            archive_path=archive_path,
            category="agent_evolution",
        )
        assert created == scratch_repo
        raise RuntimeError("simulated child failure")

    with pytest.raises(RuntimeError, match="simulated child failure"):
        unattended._run_with_scratch_custody(
            Seams(
                make_worktree=make_worktree,
                remove_worktree=remove_worktree,
            ),
            abort,
        )

    assert removals == [(source_repo, scratch_repo, "experiment-1")]
    assert not scratch_repo.parent.exists()


def test_scratch_custody_refuses_unconfirmed_cleanup(tmp_path: Path) -> None:
    scratch_repo = tmp_path / "scratch" / "experiment-1" / "repo"

    def make_worktree(**_kwargs) -> Path:
        scratch_repo.mkdir(parents=True)
        return scratch_repo

    def refuse_remove(**_kwargs) -> None:
        raise RuntimeError("cleanup refused")

    seams, cleanup = unattended_child_support.with_scratch_custody(
        Seams(
            make_worktree=make_worktree,
            remove_worktree=refuse_remove,
        )
    )
    seams.make_worktree(
        source_repo=tmp_path / "source",
        experiment_id="experiment-1",
        archive_path=tmp_path / "archive.jsonl",
        category="agent_evolution",
    )

    with pytest.raises(unattended.UnattendedError) as error:
        cleanup()

    assert error.value.code == "SCRATCH_CLEANUP_FAILED"
    assert scratch_repo.exists()


def test_clone_scratch_rolls_back_when_creation_fails_after_side_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    scratch_root = tmp_path / "scratch-run"
    scratch_root.mkdir()
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(scratch_root))
    monkeypatch.setattr(
        unattended_child_support,
        "require_execution_source",
        lambda _source: {"commit": "d" * 40},
    )
    calls = 0

    def fail_after_clone(argv, *, cwd=None, timeout=300):
        del cwd, timeout
        nonlocal calls
        calls += 1
        if calls == 1:
            Path(argv[-1]).mkdir(parents=True)
            return
        raise unattended.UnattendedError("SCRATCH_GIT_FAILED", "checkout failed")

    monkeypatch.setattr(unattended_child_support, "_run_git", fail_after_clone)

    with pytest.raises(unattended.UnattendedError, match="checkout failed"):
        unattended._clone_scratch(
            source_repo=source_repo,
            experiment_id="experiment-1",
            archive_path=tmp_path / "archive.jsonl",
            category="agent_evolution",
        )

    assert not (scratch_root / "experiment-1").exists()


def test_parent_cleanup_removes_a_real_clone_left_by_killed_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    subprocess.run(["git", "init", "-q", str(source_repo)], check=True)
    (source_repo / "fixture.py").write_text("VALUE = 1\n")
    subprocess.run(["git", "-C", str(source_repo), "add", "fixture.py"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source_repo),
            "-c",
            "user.name=RSI Test",
            "-c",
            "user.email=rsi@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(source_repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    state = tmp_path / "state"
    state.mkdir()
    run_id = "unattended-real-clone"
    spec_digest = "sha256:" + "e" * 64
    scratch_create = unattended.create_run_scratch(
        state,
        run_id,
        source_commit=commit,
        spec_digest=spec_digest,
        created_at="2026-08-28T00:00:00Z",
    )
    root = unattended.unattended_scratch_root(state, run_id)
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(root))
    monkeypatch.setattr(
        unattended_child_support,
        "require_execution_source",
        lambda _source: {"commit": commit},
    )

    repo = unattended._clone_scratch(
        source_repo=source_repo,
        experiment_id="experiment-1",
        archive_path=tmp_path / "archive.jsonl",
        category="agent_evolution",
    )

    assert (repo / "fixture.py").read_text() == "VALUE = 1\n"
    proof = unattended.cleanup_run_scratch(
        state,
        run_id,
        source_commit=commit,
        spec_digest=spec_digest,
        expected_root_identity=scratch_create["root_identity"],
        expected_marker_digest=scratch_create["marker_digest"],
    )
    assert proof["ok"] is True
    assert proof["inventory"]["regular_files"] > 10
    assert not unattended._lexists(root)


def test_scratch_custody_detects_dangling_symlink_after_remove(
    tmp_path: Path,
) -> None:
    scratch_repo = tmp_path / "scratch" / "experiment-1" / "repo"

    def make_worktree(**_kwargs) -> Path:
        scratch_repo.mkdir(parents=True)
        return scratch_repo

    def leave_dangling_link(**_kwargs) -> None:
        scratch_repo.rmdir()
        scratch_repo.symlink_to(tmp_path / "missing", target_is_directory=True)

    seams, _cleanup = unattended_child_support.with_scratch_custody(
        Seams(
            make_worktree=make_worktree,
            remove_worktree=leave_dangling_link,
        )
    )
    repo = seams.make_worktree(
        source_repo=tmp_path / "source",
        experiment_id="experiment-1",
        archive_path=tmp_path / "archive.jsonl",
        category="agent_evolution",
    )

    with pytest.raises(unattended.UnattendedError) as error:
        seams.remove_worktree(
            source_repo=tmp_path / "source",
            repo=repo,
            experiment_id="experiment-1",
        )

    assert error.value.code == "SCRATCH_REMOVE_UNCONFIRMED"
    assert repo.exists() is False
    assert repo.is_symlink() is True


def _stale_run_fixture(
    state: Path,
    *,
    run_id: str,
    receipt: bool,
) -> tuple[Path, dict[str, object], dict[str, object]]:
    control = state / ".dharma" / "forge_lab" / "unattended_explore"
    spec_path = control / "runs" / run_id / "child_spec.json"
    scratch_root = unattended.unattended_scratch_root(state, run_id)
    spec: dict[str, object] = {
        "schema": unattended.RUNNER_SCHEMA,
        "run_id": run_id,
        "state_root": str(state),
        "scratch_root": str(scratch_root),
        "source_commit": "f" * 40,
        "positive_rsi_claim": False,
    }
    spec["spec_digest"] = unattended.content_digest(spec)
    unattended.write_json_exclusive(spec_path, spec)
    created = unattended.create_run_scratch(
        state,
        run_id,
        source_commit=str(spec["source_commit"]),
        spec_digest=str(spec["spec_digest"]),
        created_at="2026-08-28T00:00:00Z",
    )
    repo = scratch_root / "experiment-stale" / "repo"
    repo.mkdir(parents=True)
    (repo / "partial.py").write_text("partial\n")
    if receipt:
        unattended.append_chain(
            control / "receipts.jsonl",
            {
                "kind": "run_admitted",
                "at": "2026-08-28T00:00:00Z",
                "run_id": run_id,
                "source_commit": spec["source_commit"],
                "spec": str(spec_path),
                "spec_digest": spec["spec_digest"],
                "scratch_custody_create": created,
                "positive_rsi_claim": False,
            },
            schema=unattended.RECEIPT_SCHEMA,
            digest_field="receipt_digest",
        )
    return control, spec, created


def test_stale_marker_bound_root_is_recovered_before_new_spend(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    run_id = "unattended-stale"
    control, _spec, created = _stale_run_fixture(
        state,
        run_id=run_id,
        receipt=True,
    )

    recovered = unattended._recover_stale_scratch(state, control)

    assert len(recovered) == 1
    assert recovered[0]["kind"] == "stale_scratch_recovered"
    assert recovered[0]["provider_calls"] == 0
    assert recovered[0]["usd_reserved"] == 0.0
    assert unattended.validate_parent_scratch_proofs(
        created,
        recovered[0]["scratch_custody"]["cleanup"],
        state_root=state,
        run_id=run_id,
    )
    assert unattended_scratch.list_run_scratch_ids(state) == []
    assert not (control / "budget_ledger.jsonl").exists()


def test_stale_recovery_refuses_recomputed_marker_drift_without_deleting(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    run_id = "unattended-stale-drift"
    control, _spec, _created = _stale_run_fixture(
        state,
        run_id=run_id,
        receipt=True,
    )
    root = unattended.unattended_scratch_root(state, run_id)
    marker_path = root / unattended_scratch.SCRATCH_MARKER
    marker = json.loads(marker_path.read_text())
    marker["created_at"] = "2026-08-28T00:00:01Z"
    marker["marker_digest"] = unattended.content_digest(
        {key: value for key, value in marker.items() if key != "marker_digest"}
    )
    marker_path.write_text(json.dumps(marker) + "\n")
    os.chmod(marker_path, 0o600)

    with pytest.raises(unattended.UnattendedError) as error:
        unattended._recover_stale_scratch(state, control)

    assert error.value.code == "STALE_SCRATCH_REFUSED"
    assert unattended_scratch.list_run_scratch_ids(state) == [run_id]
    assert marker_path.is_file()
    assert not (control / "budget_ledger.jsonl").exists()
    receipts = unattended.read_chain(
        control / "receipts.jsonl",
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    assert receipts[-1]["kind"] == "stale_scratch_refusal"
    assert receipts[-1]["error_code"] == "SCRATCH_MARKER_MISMATCH"


def test_unknown_stale_root_blocks_run_before_admission_or_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    control, _spec, _created = _stale_run_fixture(
        state,
        run_id="unattended-unknown",
        receipt=False,
    )
    admission_called = False
    budget_called = False

    def unexpected_admission(_state):
        nonlocal admission_called
        admission_called = True
        raise AssertionError("stale audit must precede admission")

    def unexpected_budget(*_args, **_kwargs):
        nonlocal budget_called
        budget_called = True
        raise AssertionError("stale audit must precede reservation")

    monkeypatch.setattr(unattended, "admission_status", unexpected_admission)
    monkeypatch.setattr(unattended, "reserve_budget", unexpected_budget)

    with pytest.raises(unattended.UnattendedError) as error:
        unattended.run_once(state, timeout_seconds=60)

    assert error.value.code == "STALE_SCRATCH_REFUSED"
    assert admission_called is False
    assert budget_called is False
    assert unattended_scratch.list_run_scratch_ids(state) == ["unattended-unknown"]
    assert not (control / "budget_ledger.jsonl").exists()
    receipts = unattended.read_chain(
        control / "receipts.jsonl",
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    assert receipts[-1]["kind"] == "stale_scratch_refusal"
    assert receipts[-1]["error_code"] == "STALE_SCRATCH_AUTHORITY_MISSING"


def test_live_orphan_child_lease_blocks_stale_recovery(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    run_id = "unattended-live-child"
    control, spec, created = _stale_run_fixture(
        state,
        run_id=run_id,
        receipt=True,
    )
    lease = unattended.acquire_run_scratch_lease(
        state,
        run_id,
        source_commit=str(spec["source_commit"]),
        spec_digest=str(spec["spec_digest"]),
        expected_root_identity=created["root_identity"],
        expected_marker_digest=created["marker_digest"],
    )
    try:
        with pytest.raises(unattended.UnattendedError) as error:
            unattended._recover_stale_scratch(state, control)
        assert error.value.code == "STALE_SCRATCH_REFUSED"
        assert unattended_scratch.list_run_scratch_ids(state) == [run_id]
    finally:
        lease.close()


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
            "task_context_binding": {
                "task_id": "task-fixture",
                "binding_digest": _CONTEXT_DIGEST,
            },
            "halt_path": str(state / ".dharma" / "forge_lab" / "HALT"),
        },
    )

    def fake_child(
        spec_path,
        *,
        run_id,
        timeout_seconds,
        log_path,
        halt_path,
        scratch_root_identity,
        scratch_marker_digest,
    ):
        del timeout_seconds, halt_path
        spec = json.loads(spec_path.read_text())
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("bounded child fixture\n")
        attestation = unattended_scratch.attest_run_scratch(
            state,
            run_id,
            source_commit=spec["source_commit"],
            spec_digest=spec["spec_digest"],
            expected_root_identity=scratch_root_identity,
            expected_marker_digest=scratch_marker_digest,
        )
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
            "scratch_cleanup_ok": True,
            "scratch_custody_attestation": attestation,
            "experiment_closeout": {
                "schema": "forge_lab.closeout.v0",
                "experiment_id": "experiment-fixture",
                "closeout_state": "inconclusive_low_power",
                "scratch_worktree": {
                    "path": str(
                        Path(spec["scratch_root"])
                        / "experiment-fixture"
                        / "repo"
                    ),
                    "state": "removed",
                    "removed": True,
                },
                "stats": {
                    "counters": {
                        "graded": 2,
                        "paired_controls": 1,
                        "blocked": 0,
                    }
                },
            },
            "epistemic_modality": "EXPLORE_ONLY",
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

    halted_scratch: list[Path] = []

    def fake_halted(
        spec_path,
        *,
        run_id,
        timeout_seconds,
        log_path,
        halt_path,
        scratch_root_identity,
        scratch_marker_digest,
    ):
        del (
            run_id,
            timeout_seconds,
            halt_path,
            scratch_root_identity,
            scratch_marker_digest,
        )
        spec = json.loads(spec_path.read_text())
        scratch_root = Path(spec["scratch_root"])
        repo = scratch_root / "killed-experiment" / "repo"
        repo.mkdir(parents=True)
        (repo / "partial.py").write_text("partial\n")
        halted_scratch.append(scratch_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("halted child fixture\n")
        return -15, False, True, 2

    monkeypatch.setattr(unattended, "_run_child_process", fake_halted)
    halted = unattended.run_once(state, timeout_seconds=60)
    assert halted["ok"] is False
    assert halted["halted"] is True
    assert halted["scratch_cleanup_ok"] is True
    assert len(halted_scratch) == 1
    assert not unattended._lexists(halted_scratch[0])
    receipts = unattended.read_chain(
        control / "receipts.jsonl",
        schema=unattended.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    assert receipts[-1]["halted"] is True
    assert receipts[-1]["epistemic_modality"] == "InconclusiveOperatorHalt"
    assert receipts[-1]["scratch_custody"]["cleanup"]["ok"] is True
    assert receipts[-1]["scratch_custody"]["cleanup"]["inventory"][
        "regular_files"
    ] == 2


def test_external_watchdog_terminates_the_child_process_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TimedProcess:
        pid = 4242

        def wait(self, timeout):
            return -15

    process = TimedProcess()
    child_argv: list[str] = []

    def fake_popen(argv, **_kwargs):
        child_argv.extend(argv)
        return process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    signals = []
    monkeypatch.setattr(unattended.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    spec = tmp_path / "spec.json"
    spec.write_text("{}\n")

    monotonic = iter((0.0, 61.0, 61.1))
    monkeypatch.setattr(
        unattended_child_support.time,
        "monotonic",
        lambda: next(monotonic),
    )
    returncode, timed_out, halted, _wall = unattended._run_child_process(
        spec,
        run_id="watchdog",
        timeout_seconds=60,
        log_path=tmp_path / "child.log",
        halt_path=tmp_path / "HALT",
        scratch_root_identity={"device": 1, "inode": 2},
        scratch_marker_digest="sha256:" + "a" * 64,
    )
    assert returncode == -15
    assert timed_out is True
    assert halted is False
    assert signals == [(4242, unattended_child_support.signal.SIGTERM)]
    assert child_argv == [
        unattended.sys.executable,
        "-m",
        "dharma_swarm.forge_lab.unattended_explore",
        "--child-spec",
        str(spec),
    ]


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
        scratch_root_identity={"device": 1, "inode": 2},
        scratch_marker_digest="sha256:" + "a" * 64,
    )
    assert returncode == -15
    assert timed_out is False
    assert halted is True
    assert signals == [(4343, unattended_child_support.signal.SIGTERM)]


def test_unattended_wrapper_and_systemd_timer_are_bounded() -> None:
    root = Path(__file__).resolve().parents[2] / "scripts" / "forge_lab"
    wrapper = (root / "rsi-unattended-explore").read_text()
    service = (root / "systemd" / "rsi-lab-explore.service").read_text()
    timer = (root / "systemd" / "rsi-lab-explore.timer").read_text()

    assert "RSI_LAB_DEV_SOURCE is forbidden" in wrapper
    assert 'state="$(cd -- "${state}" && pwd -P)"' in wrapper
    assert 'export RSI_LAB_PYDEPS="${pydeps}"' in wrapper
    assert 'export RSI_LAB_SWEBENCH_PYDEPS="${swebench_pydeps}"' in wrapper
    assert 'export RSI_LAB_REQUIRE_SWEBENCH_PYDEPS="1"' in wrapper
    assert 'docker_context="default"' in wrapper
    assert 'docker_context="colima-forge-swebench"' in wrapper
    assert 'docker_host="unix:///var/run/docker.sock"' in wrapper
    assert 'export DOCKER_CONTEXT="${docker_context}"' in wrapper
    assert 'export FORGE_DOCKER_CONTEXT="${docker_context}"' in wrapper
    assert 'export DOCKER_HOST="${docker_host}"' in wrapper
    assert "export HF_DATASETS_OFFLINE=1" in wrapper
    assert "export HF_HUB_OFFLINE=1" in wrapper
    assert 'export HF_HOME="${hf_home}"' in wrapper
    assert 'export HF_DATASETS_CACHE="${hf_home}/datasets"' in wrapper
    assert 'export HF_HUB_CACHE="${hf_home}/hub"' in wrapper
    assert '--state-root "${state}"' in wrapper
    assert "Type=oneshot" in service
    assert "TimeoutStartSec=2800" in service
    assert "ReadWritePaths=/root/rsi-lab/state" in service
    assert "ReadWritePaths=/root/.cache/huggingface/datasets" in service
    assert "ReadWritePaths=/root/.cache/huggingface/hub" in service
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
