from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm import mission_control_bootstrap as bootstrap
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard
from scripts.runtime import sadhana_campaign_bootstrap as cli

_DEPENDENCIES = {
    "G01_DARSHAN_PUBLICATION": ["G05_LOOP_CLOSURE", "G10_SAFETY_TCB"],
    "G02_DHARMAGRAPH_ENGINE": ["G09_TITANIUM_HARDENING", "G10_SAFETY_TCB"],
    "G03_CONSTELLATION_OPERATOR_SURFACE": [
        "G08_ORGANISM_REWIRE",
        "G10_SAFETY_TCB",
    ],
    "G04_HYPERBOLIC_TIME_CHAMBER": [
        "G07_ORCHESTRATION_ARENA",
        "G10_SAFETY_TCB",
    ],
    "G05_LOOP_CLOSURE": ["G08_ORGANISM_REWIRE", "G10_SAFETY_TCB"],
    "G06_MERGE_MASTER_PR_CONVERGENCE": [
        "G09_TITANIUM_HARDENING",
        "G10_SAFETY_TCB",
    ],
    "G07_ORCHESTRATION_ARENA": [
        "G09_TITANIUM_HARDENING",
        "G10_SAFETY_TCB",
    ],
    "G08_ORGANISM_REWIRE": ["G09_TITANIUM_HARDENING", "G10_SAFETY_TCB"],
    "G09_TITANIUM_HARDENING": ["G10_SAFETY_TCB"],
    "G10_SAFETY_TCB": [],
}
_ORDER = (
    "G10_SAFETY_TCB",
    "G09_TITANIUM_HARDENING",
    "G02_DHARMAGRAPH_ENGINE",
    "G06_MERGE_MASTER_PR_CONVERGENCE",
    "G07_ORCHESTRATION_ARENA",
    "G08_ORGANISM_REWIRE",
    "G03_CONSTELLATION_OPERATOR_SURFACE",
    "G04_HYPERBOLIC_TIME_CHAMBER",
    "G05_LOOP_CLOSURE",
    "G01_DARSHAN_PUBLICATION",
)


def _contract_document() -> dict[str, Any]:
    goals = []
    for index, goal_id in enumerate(bootstrap.EXPECTED_GOAL_IDS, start=1):
        goals.append(
            {
                "allowed_actions": ["inspect repository state"],
                "approval_boundaries": ["no external effects"],
                "beneficiary": "SADHANA operator",
                "ceilings": {
                    "attempts": index,
                    "cash_usd": 0,
                    "concurrency": 1,
                    "default_attempt_policy": "portfolio_default",
                },
                "deadline": (
                    "2026-08-24T10:00:00+09:00"
                    if goal_id == "G10_SAFETY_TCB"
                    else "2026-09-02T02:15:12+09:00"
                ),
                "definition_of_done": f"Independently accept {goal_id} evidence.",
                "dependencies": _DEPENDENCIES[goal_id],
                "desired_beneficial_outcome": f"A bounded {goal_id} delta.",
                "evidence_locations": [f"evidence/{goal_id}"],
                "forbidden_actions": ["claim unverified completion"],
                "goal_id": goal_id,
                "independent_verifier": "operator",
                "priority": "P0" if index >= 8 else "P1",
                "recorded_baseline": {
                    "authority": "none",
                    "claim": "unverified",
                    "state": "provisional",
                },
                "rollback": "revert only the scoped delta",
                "scope": {
                    "code": [],
                    "data": [],
                    "external": [],
                    "runtime": [],
                },
                "telos": "beneficial verified progress",
                "terminal_conditions": ["independent acceptance"],
            }
        )
    return {
        "campaign_id": bootstrap.EXPECTED_CAMPAIGN_ID,
        "generated_at": "2026-08-23T02:35:00+09:00",
        "goals": goals,
        "portfolio_policy": {
            "allocation": {
                "fair_goal_coverage_percent": 20,
                "verification_exploration_recovery_percent": 30,
                "verified_value_priority_percent": 50,
            },
            "default_attempt_ceiling": {
                "concurrency": 1,
                "input_tokens": 1000,
                "output_tokens": 500,
                "retries": 0,
                "wall_seconds": 60,
            },
            "external_cash_ceiling_usd_without_new_warrant": 0,
            "fitness_rule": "independent accepted value only",
            "global_concurrency_ceiling": 4,
        },
        "schema": bootstrap.GOAL_CONTRACT_SCHEMA,
        "status": bootstrap.EXPECTED_CONTRACT_STATUS,
    }


def _encoded(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _pinned_portfolio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[bootstrap.GoalPortfolio, Path]:
    raw = _encoded(_contract_document())
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(bootstrap, "EXPECTED_CONTRACT_SHA256", digest)
    monkeypatch.setattr(bootstrap, "EXPECTED_CONTRACT_DIGEST", f"sha256:{digest}")
    contract_path = tmp_path / "goal-contracts.v1.json"
    contract_path.write_bytes(raw)
    contract_path.chmod(0o600)
    return bootstrap.load_goal_contract(contract_path), contract_path


async def _owners(
    tmp_path: Path,
) -> tuple[RuntimeStateStore, TaskBoard, MissionControl]:
    runtime = RuntimeStateStore(
        tmp_path / "state" / "runtime.db",
        include_memory_plane=False,
    )
    await runtime.init_db()
    task_db = tmp_path / "db" / "tasks.db"
    task_db.parent.mkdir(parents=True)
    board = TaskBoard(task_db, runtime_state=runtime)
    await board.init_db()
    return runtime, board, MissionControl(board, runtime)


def test_production_contract_pin_is_frozen() -> None:
    assert bootstrap.EXPECTED_CONTRACT_DIGEST == (
        "sha256:e2891fcb2171563adc87a339d5fca42b155ee8aa5dc96b153ab3515f01051101"
    )
    assert bootstrap.EXPECTED_CAMPAIGN_ID == "sadhana-10-20260823"
    assert bootstrap.GOAL_CONTRACT_SCHEMA == "dharma.sadhana.goal_contracts.v1"


def test_contract_loader_pins_exact_bytes_and_rejects_schema_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio, path = _pinned_portfolio(tmp_path, monkeypatch)
    assert portfolio.dependency_order == _ORDER
    assert portfolio.campaign_id == bootstrap.EXPECTED_CAMPAIGN_ID

    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(bootstrap.GoalContractError, match="digest mismatch"):
        bootstrap.load_goal_contract(path)

    document = _contract_document()
    document["schema"] = "dharma.sadhana.goal_contracts.v2"
    raw = _encoded(document)
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(bootstrap.GoalContractError, match="pinned v1 schema"):
        bootstrap._decode_goal_contract(raw, expected_sha256=digest)

    document = _contract_document()
    document["campaign_id"] = "sadhana-foreign"
    raw = _encoded(document)
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(bootstrap.GoalContractError, match="campaign_id"):
        bootstrap._decode_goal_contract(raw, expected_sha256=digest)


def test_contract_loader_rejects_cycle_symlink_and_unsafe_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _contract_document()
    document["goals"][-1]["dependencies"] = ["G01_DARSHAN_PUBLICATION"]
    raw = _encoded(document)
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(bootstrap.GoalContractError, match="contains a cycle"):
        bootstrap._decode_goal_contract(raw, expected_sha256=digest)

    _, path = _pinned_portfolio(tmp_path, monkeypatch)
    link = tmp_path / "contract-link.json"
    link.symlink_to(path)
    with pytest.raises(bootstrap.GoalContractError, match="securely open"):
        bootstrap.load_goal_contract(link)
    path.chmod(0o622)
    with pytest.raises(bootstrap.GoalContractError, match="group/world writable"):
        bootstrap.load_goal_contract(path)


@pytest.mark.asyncio
async def test_fresh_initialization_seeds_exact_graph_and_authority_neutral_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio, _ = _pinned_portfolio(tmp_path, monkeypatch)
    runtime, board, control = await _owners(tmp_path / "owners")

    result = await bootstrap.initialize_sadhana_campaign(
        portfolio,
        control,
        board,
        operator_id="operator",
    )
    payload = json.loads(result.to_json())
    tasks = await board.list_tasks(limit=20)
    by_goal = {task.metadata["goal_id"]: task for task in tasks}

    assert len(tasks) == 10
    assert set(by_goal) == set(bootstrap.EXPECTED_GOAL_IDS)
    assert payload["mission_id"] == bootstrap.EXPECTED_CAMPAIGN_ID
    assert payload["contract_digest"] == portfolio.digest
    assert payload["dependency_order"] == list(_ORDER)
    assert payload["goal_task_map"] == {
        goal_id: by_goal[goal_id].id for goal_id in bootstrap.EXPECTED_GOAL_IDS
    }
    assert payload["canary_goal_id"] == "G05_LOOP_CLOSURE"
    assert payload["canary_task_id"] == by_goal["G05_LOOP_CLOSURE"].id
    assert payload["dispatch_ready"] is False
    assert payload["dispatch_blocker"] == "authority_unbound"
    assert payload["proves_independent_acceptance"] is False
    assert payload["proves_model_execution"] is False
    assert payload["authority_binding"]["seed_dispatch_fields"] == (
        "immutable_provenance_not_runtime_readiness"
    )
    assert payload["authority_binding"]["correlation_formula"] == (
        "stable_id('mission_dispatch', mission_id, task_id, 'default')"
    )
    assert payload["authority_binding"]["required_actions"] == [
        "mission_control_dispatch",
        "mission_control_workspace",
    ]
    assert payload["authority_binding"]["lease_cash_ceiling_usd"] == 0
    assert (
        await runtime.get_session(f"mission_campaign:{bootstrap.EXPECTED_CAMPAIGN_ID}")
        is None
    )
    for goal in portfolio.goals:
        task = by_goal[goal.goal_id]
        assert task.title == goal.goal_id
        assert task.description == goal.definition_of_done
        assert task.metadata["goal_contract_sha256"] == goal.content_digest
        assert task.metadata["dispatch_ready"] is False
        assert task.metadata["dispatch_blocker"] == "authority_unbound"
        assert sorted(task.depends_on) == sorted(
            by_goal[item].id for item in goal.dependencies
        )


@pytest.mark.asyncio
async def test_second_initialization_is_byte_stable_no_op(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio, _ = _pinned_portfolio(tmp_path, monkeypatch)
    runtime, board, control = await _owners(tmp_path / "owners")
    first = await bootstrap.initialize_sadhana_campaign(portfolio, control, board)

    async def forbidden_write(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("second initialization attempted an owner write")

    monkeypatch.setattr(runtime, "upsert_session", forbidden_write)
    monkeypatch.setattr(board, "create", forbidden_write)
    second = await bootstrap.initialize_sadhana_campaign(portfolio, control, board)

    assert second.to_json().encode() == first.to_json().encode()
    assert len(await board.list_tasks(limit=20)) == 10


@pytest.mark.asyncio
async def test_conflicting_nonclosed_partial_state_has_zero_additional_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio, _ = _pinned_portfolio(tmp_path, monkeypatch)
    runtime, board, control = await _owners(tmp_path / "owners")
    await control.create_mission(
        portfolio.campaign_id,
        title=bootstrap.MISSION_TITLE,
        goal=bootstrap.MISSION_GOAL,
        operator_id="operator",
        metadata=bootstrap._mission_metadata(portfolio),
    )
    goal = portfolio.by_id["G09_TITANIUM_HARDENING"]
    await control.create_task(
        portfolio.campaign_id,
        title=goal.goal_id,
        description=goal.definition_of_done,
        priority=bootstrap._PRIORITY[goal.priority],
        created_by=bootstrap.BOOTSTRAP_CREATED_BY,
        depends_on=[],
        idempotency_key=bootstrap.task_idempotency_key(portfolio, goal.goal_id),
        metadata=bootstrap._task_metadata(portfolio, goal),
    )
    before_tasks = await board.list_tasks(limit=20)
    writes = 0

    async def forbidden_write(*args: Any, **kwargs: Any) -> Any:
        nonlocal writes
        writes += 1
        raise AssertionError("conflict path attempted an owner write")

    monkeypatch.setattr(runtime, "upsert_session", forbidden_write)
    monkeypatch.setattr(board, "create", forbidden_write)
    with pytest.raises(MissionControlError, match="not dependency-closed"):
        await bootstrap.initialize_sadhana_campaign(portfolio, control, board)

    assert writes == 0
    assert await board.list_tasks(limit=20) == before_tasks


@pytest.mark.asyncio
async def test_dependency_closed_crash_prefix_resumes_without_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio, _ = _pinned_portfolio(tmp_path, monkeypatch)
    _, board, control = await _owners(tmp_path / "owners")
    original_create = board.create
    calls = 0

    async def crash_on_fourth(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 4:
            raise RuntimeError("simulated crash")
        return await original_create(*args, **kwargs)

    monkeypatch.setattr(board, "create", crash_on_fourth)
    with pytest.raises(RuntimeError, match="simulated crash"):
        await bootstrap.initialize_sadhana_campaign(portfolio, control, board)
    prefix = await board.list_tasks(limit=20)
    assert {task.metadata["goal_id"] for task in prefix} == set(_ORDER[:3])

    monkeypatch.setattr(board, "create", original_create)
    result = await bootstrap.initialize_sadhana_campaign(portfolio, control, board)
    assert len(await board.list_tasks(limit=20)) == 10
    assert set(dict(result.goal_task_map)) == set(bootstrap.EXPECTED_GOAL_IDS)


@pytest.mark.asyncio
async def test_additive_authority_binding_does_not_corrupt_seed_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio, _ = _pinned_portfolio(tmp_path, monkeypatch)
    _, board, control = await _owners(tmp_path / "owners")
    first = await bootstrap.initialize_sadhana_campaign(portfolio, control, board)
    canary_id = dict(first.goal_task_map)[bootstrap.CANARY_GOAL_ID]
    canary = await board.get(canary_id)
    assert canary is not None
    await board.update_task(
        canary_id,
        metadata={
            **canary.metadata,
            "mission_campaign_authority": {
                "schema": "dharma.mission_campaign_authority.v1",
                "status": "bound",
            },
        },
    )

    second = await bootstrap.initialize_sadhana_campaign(portfolio, control, board)
    rebound = await board.get(canary_id)
    assert second.to_json() == first.to_json()
    assert rebound is not None
    assert rebound.metadata["mission_campaign_authority"]["status"] == "bound"
    assert rebound.metadata["dispatch_ready"] is False
    assert rebound.metadata["dispatch_blocker"] == "authority_unbound"


@pytest.mark.asyncio
async def test_tasks_without_mission_fail_before_mission_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio, _ = _pinned_portfolio(tmp_path, monkeypatch)
    runtime, board, control = await _owners(tmp_path / "owners")
    await board.create(
        title="foreign",
        metadata={"campaign_id": portfolio.campaign_id, "goal_id": "foreign"},
    )
    writes = 0

    async def forbidden_write(*args: Any, **kwargs: Any) -> Any:
        nonlocal writes
        writes += 1
        raise AssertionError("mission write occurred")

    monkeypatch.setattr(runtime, "upsert_session", forbidden_write)
    with pytest.raises(MissionControlError, match="foreign task"):
        await bootstrap.initialize_sadhana_campaign(portfolio, control, board)
    assert writes == 0
    assert await control.get_mission(portfolio.campaign_id) is None


def test_cli_second_run_is_byte_stable_and_uses_supervisor_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    portfolio, contract_path = _pinned_portfolio(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "load_goal_contract", lambda _: portfolio)
    state_dir = tmp_path / "campaign-state"
    arguments = [
        "initialize",
        "--contracts",
        str(contract_path),
        "--state-dir",
        str(state_dir),
        "--operator-id",
        "operator",
    ]

    assert cli.main(arguments) == 0
    first = capsys.readouterr()
    assert cli.main(arguments) == 0
    second = capsys.readouterr()

    assert first.err == second.err == ""
    assert first.out.encode() == second.out.encode()
    assert json.loads(first.out)["task_count"] == 10
    assert (state_dir / "state" / "runtime.db").is_file()
    assert (state_dir / "db" / "tasks.db").is_file()
    assert (state_dir / "locks" / "sadhana-bootstrap.lock").is_file()


def test_cli_contract_mismatch_fails_before_state_effects(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    contract_path = tmp_path / "wrong.json"
    contract_path.write_text("{}", encoding="utf-8")
    contract_path.chmod(0o600)
    state_dir = tmp_path / "must-not-exist"

    assert (
        cli.main(
            [
                "initialize",
                "--contracts",
                str(contract_path),
                "--state-dir",
                str(state_dir),
            ]
        )
        == 2
    )
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["error_type"] == "GoalContractError"
    assert not state_dir.exists()


def test_cli_lock_contention_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    portfolio, contract_path = _pinned_portfolio(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "load_goal_contract", lambda _: portfolio)
    state_dir = tmp_path / "campaign-state"
    lock_path = state_dir / "locks" / "sadhana-bootstrap.lock"
    lock_path.parent.mkdir(parents=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert (
            cli.main(
                [
                    "initialize",
                    "--contracts",
                    str(contract_path),
                    "--state-dir",
                    str(state_dir),
                ]
            )
            == 2
        )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    output = capsys.readouterr()
    assert output.out == ""
    assert "another SADHANA bootstrap is active" in output.err
    assert not (state_dir / "state" / "runtime.db").exists()


@pytest.mark.asyncio
async def test_output_never_claims_dispatch_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio, _ = _pinned_portfolio(tmp_path, monkeypatch)
    _, board, control = await _owners(tmp_path / "owners")
    result = await bootstrap.initialize_sadhana_campaign(portfolio, control, board)
    output = json.loads(result.to_json())
    assert output["dispatch_ready"] is False
    assert output["dispatch_blocker"] == "authority_unbound"
