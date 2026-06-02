from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/runtime/autonomy_spine.py"


def load_module():
    spec = importlib.util.spec_from_file_location("autonomy_spine", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_init_creates_mission_tasks_receipts_and_brief(tmp_path: Path, capsys) -> None:
    module = load_module()

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "demo",
        "--goal",
        "Build the autonomy spine smoke test",
    ])
    root = Path(capsys.readouterr().out.strip())

    assert rc == 0
    assert root == tmp_path / "demo"
    assert (root / "mission.json").exists()
    assert (root / "tasks.jsonl").exists()
    assert (root / "receipts.jsonl").exists()
    assert (root / "brief.md").exists()

    mission = json.loads((root / "mission.json").read_text(encoding="utf-8"))
    tasks = [json.loads(line) for line in (root / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    receipts = [json.loads(line) for line in (root / "receipts.jsonl").read_text(encoding="utf-8").splitlines()]

    assert mission["schema"] == module.SCHEMA_MISSION
    assert mission["mission_id"] == "demo"
    assert mission["nats_authority"] == "blocked_until_ack_proof"
    assert len(tasks) == 5
    assert {task["role"] for task in tasks} == {"planner", "builder", "adversary", "verifier", "reporter"}
    assert all(task["receipt_required"] for task in tasks)
    assert receipts[0]["status"] == "initialized"


def test_claim_sets_lease_and_status(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "claim-demo",
        "--goal",
        "Claim a task",
    ]) == 0
    capsys.readouterr()

    task_id = "claim-demo-t02-builder"
    rc = module.main([
        "--state-root",
        str(tmp_path),
        "claim",
        "--mission-id",
        "claim-demo",
        "--task-id",
        task_id,
        "--agent",
        "codex_composer",
        "--json",
    ])
    task = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert task["status"] == "claimed"
    assert task["lease"]["claimed_by"] == "codex_composer"
    assert task["lease"]["expires_at"]


def test_completed_receipt_requires_evidence(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "receipt-demo",
        "--goal",
        "Require proof",
    ]) == 0
    capsys.readouterr()

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "record",
        "--mission-id",
        "receipt-demo",
        "--task-id",
        "receipt-demo-t01-planner",
        "--agent",
        "opus_composer",
        "--status",
        "completed",
    ])
    assert rc == 2
    capsys.readouterr()

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "record",
        "--mission-id",
        "receipt-demo",
        "--task-id",
        "receipt-demo-t01-planner",
        "--agent",
        "opus_composer",
        "--status",
        "completed",
        "--evidence",
        "acceptance contract written",
        "--json",
    ])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert receipt["status"] == "completed"
    assert receipt["evidence"] == "acceptance contract written"


def test_progress_receipt_does_not_close_task(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "progress-demo",
        "--goal",
        "Record progress without closing the task",
    ]) == 0
    capsys.readouterr()

    task_id = "progress-demo-t05-reporter"
    rc = module.main([
        "--state-root",
        str(tmp_path),
        "progress",
        "--mission-id",
        "progress-demo",
        "--task-id",
        task_id,
        "--agent",
        "codex_composer",
        "--status",
        "verified",
        "--evidence",
        "loop 03 packet rendered",
        "--artifact",
        "reports/venture_operator_os/run/03_operator_surface_receipt.md",
        "--json",
    ])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert receipt["status"] == "verified"
    assert receipt["task_id"] == task_id
    assert receipt["role"] == "reporter"

    root = tmp_path / "progress-demo"
    tasks = [json.loads(line) for line in (root / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    reporter = next(task for task in tasks if task["task_id"] == task_id)
    assert reporter["status"] == "open"
    brief = (root / "brief.md").read_text(encoding="utf-8")
    assert "`verified` `progress-demo-t05-reporter`" in brief

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "verify",
        "--mission-id",
        "progress-demo",
        "--phase",
        "complete",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 3
    assert "task_not_closed:progress-demo-t05-reporter" in payload["blockers"]


def test_verify_complete_requires_all_tasks_closed_with_receipts(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "complete-demo",
        "--goal",
        "Close every task",
    ]) == 0
    capsys.readouterr()

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "verify",
        "--mission-id",
        "complete-demo",
        "--phase",
        "complete",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 3
    assert "task_not_closed:complete-demo-t01-planner" in payload["blockers"]

    for role in ["planner", "builder", "adversary", "verifier", "reporter"]:
        index = ["planner", "builder", "adversary", "verifier", "reporter"].index(role) + 1
        assert module.main([
            "--state-root",
            str(tmp_path),
            "record",
            "--mission-id",
            "complete-demo",
            "--task-id",
            f"complete-demo-t{index:02d}-{role}",
            "--agent",
            "codex_composer",
            "--status",
            "completed",
            "--evidence",
            f"{role} proof",
        ]) == 0
        capsys.readouterr()

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "verify",
        "--mission-id",
        "complete-demo",
        "--phase",
        "complete",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["complete_valid"] is True
    assert payload["blockers"] == []


def test_brief_renders_operator_handoff(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "brief-demo",
        "--goal",
        "Write a useful brief",
    ]) == 0
    capsys.readouterr()

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "brief",
        "--mission-id",
        "brief-demo",
    ])
    brief = capsys.readouterr().out

    assert rc == 0
    assert "Autonomy Spine Brief: brief-demo" in brief
    assert "NATS remains blocked until ack proof exists" in brief


def test_run_once_dispatches_open_tasks_and_writes_runner_state(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "run-demo",
        "--goal",
        "Run the mission supervisor once",
    ]) == 0
    capsys.readouterr()

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "run",
        "--mission-id",
        "run-demo",
        "--once",
        "--dispatch-mode",
        "ledger",
        "--json",
    ])
    state = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert state["cycle"] == 1
    assert state["dispatches"] == 5
    assert state["verifier_runs"] == 1
    root = tmp_path / "run-demo"
    assert (root / "runner.json").exists()
    assert (root / "artifacts" / "prompts" / "run-demo-t02-builder.prompt.md").exists()

    tasks = [json.loads(line) for line in (root / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    receipts = [json.loads(line) for line in (root / "receipts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {task["status"] for task in tasks} == {"claimed"}
    assert sum(1 for receipt in receipts if receipt["status"] == "dispatched") == 5
    assert any(receipt["status"] == "heartbeat" for receipt in receipts)


def test_run_respects_agent_filter(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "filter-demo",
        "--goal",
        "Only dispatch codex work",
    ]) == 0
    capsys.readouterr()

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "run",
        "--mission-id",
        "filter-demo",
        "--once",
        "--agents",
        "codex",
        "--json",
    ])
    state = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert state["dispatches"] == 1
    tasks = [
        json.loads(line)
        for line in (tmp_path / "filter-demo" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    claimed = [task for task in tasks if task["status"] == "claimed"]
    assert [task["task_id"] for task in claimed] == ["filter-demo-t02-builder"]


def test_receipt_foldback_reports_venturecell_completed_and_blocked_counts(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "venturecell-demo",
        "--goal",
        "Reconcile terminal receipts",
    ]) == 0
    capsys.readouterr()
    root = tmp_path / "venturecell-demo"
    roles = ["planner", "builder", "adversary", "verifier", "reporter"]
    terminal = {
        "planner": "completed",
        "builder": "blocked",
        "adversary": "completed",
        "verifier": "completed",
        "reporter": "completed",
    }
    for index, role in enumerate(roles, start=1):
        task_id = f"venturecell-demo-t{index:02d}-{role}"
        module.append_jsonl(
            root / "receipts.jsonl",
            {
                "schema": module.SCHEMA_RECEIPT,
                "receipt_id": f"r-{role}",
                "mission_id": "venturecell-demo",
                "task_id": task_id,
                "agent_uid": "codex_composer",
                "role": role,
                "status": terminal[role],
                "evidence": f"{role} proof",
                "artifact_path": f"reports/venture_operator_os/{role}.md",
                "notes": None,
                "test_command": None,
                "created_at": "2026-06-02T12:32:48Z",
            },
        )

    raw_tasks = [
        json.loads(line)
        for line in (root / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert module.task_counts(raw_tasks)["completed"] == 0
    assert module.task_counts(raw_tasks)["blocked"] == 0

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "status",
        "--mission-id",
        "venturecell-demo",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["raw_counts"]["completed"] == 0
    assert payload["raw_counts"]["blocked"] == 0
    assert payload["reconciled_counts"]["completed"] == 4
    assert payload["reconciled_counts"]["blocked"] == 1
    assert payload["raw_reconciled_mismatch"] is True
    assert "COMPLETED_BY_RECEIPT" in payload["artifact_progress_status"]
    assert "BLOCKED_BY_RECEIPT" in payload["artifact_progress_status"]

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "reconcile",
        "--mission-id",
        "venturecell-demo",
        "--json",
    ])
    summary = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert (root / "reconciled_summary.json").exists()
    assert summary["reconciled_counts"]["completed"] == 4
    assert summary["reconciled_counts"]["blocked"] == 1
    assert len(summary["changed_task_ids"]) == 5

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "reconcile",
        "--mission-id",
        "venturecell-demo",
        "--json",
    ])
    summary_again = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert summary_again["idempotency_key"] == summary["idempotency_key"]
    assert len(summary_again["changed_task_ids"]) == 5


def test_receipt_foldback_does_not_close_superseded_terminal_receipt(tmp_path: Path, capsys) -> None:
    module = load_module()
    assert module.main([
        "--state-root",
        str(tmp_path),
        "init",
        "--mission-id",
        "superseded-demo",
        "--goal",
        "Do not close reopened work",
    ]) == 0
    capsys.readouterr()
    root = tmp_path / "superseded-demo"
    task_id = "superseded-demo-t02-builder"
    for status, receipt_id in [("blocked", "r-blocked"), ("lease_reopened", "r-reopen"), ("dispatched", "r-dispatch")]:
        module.append_jsonl(
            root / "receipts.jsonl",
            {
                "schema": module.SCHEMA_RECEIPT,
                "receipt_id": receipt_id,
                "mission_id": "superseded-demo",
                "task_id": task_id,
                "agent_uid": "codex_composer",
                "role": "builder",
                "status": status,
                "evidence": "builder blocker" if status == "blocked" else "builder reopened",
                "artifact_path": "reports/venture_operator_os/builder.md",
                "created_at": "2026-06-02T12:32:48Z",
            },
        )

    rc = module.main([
        "--state-root",
        str(tmp_path),
        "status",
        "--mission-id",
        "superseded-demo",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["reconciled_counts"]["blocked"] == 0
    superseded = payload["reconciled_summary"]["superseded_terminal_receipts"]
    assert superseded[0]["task_id"] == task_id
    assert superseded[0]["superseded_by_status"] == "dispatched"
