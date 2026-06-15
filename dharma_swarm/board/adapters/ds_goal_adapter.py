"""Read-only BoardStore projection for ds-goal mission ledgers.

The ds-goal ledger remains the domain truth. This adapter projects
`mission.json` + `tasks.jsonl` rows into BoardStore Card objects so operator
surfaces can show the work in the same kanban/card shape as other stores.
It does not mutate ds-goal state and does not create a second task store.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from dharma_swarm.board.models import (
    AcceptanceCriterion,
    Card,
    CardId,
    CardStatus,
    ObjectiveId,
    ReceiptRef,
    RenderHints,
    Version,
)
from dharma_swarm.operator_core.runtime_truth import sha256_file, stable_payload_hash


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _identifier(value: str) -> str:
    chars: list[str] = []
    for char in str(value or ""):
        if char.isalnum() or char in {"-", "_"}:
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or stable_payload_hash(value)[:18].replace(":", "_")


def _has_kernel_result_ref(task: dict[str, Any]) -> bool:
    ref = task.get("kernel_result_ref")
    if not isinstance(ref, dict):
        return False
    return bool(ref.get("run_id") or ref.get("receipt_id") or ref.get("proof_entry_hash"))


def _task_status(task: dict[str, Any]) -> CardStatus:
    has_kernel_ref = _has_kernel_result_ref(task)
    result_status = str(task.get("kernel_result_status") or "").strip().lower()
    if result_status == "completed":
        return "done" if has_kernel_ref else "review"
    if result_status == "failed":
        return "failed"
    if result_status == "blocked":
        return "blocked"
    if result_status == "review":
        return "review"

    status = str(task.get("status") or "").strip().lower()
    if status in {"done", "completed", "closed"}:
        return "done" if has_kernel_ref else "review"
    if status in {"failed", "error"}:
        return "failed"
    if status in {"blocked"}:
        return "blocked"
    if status in {"running"}:
        return "running"
    if status in {"claimed", "assigned", "leased"}:
        return "claimed"
    if status in {"cancelled", "canceled"}:
        return "cancelled"
    return "claimable"


def _agent_kind(agent_uid: str) -> str:
    raw = agent_uid.lower()
    if "codex" in raw:
        return "codex"
    if "devin" in raw:
        return "devin"
    if "cursor" in raw:
        return "cursor"
    if "fable" in raw or "claude" in raw or "opus" in raw:
        return "claude_code"
    if "hermes" in raw or "daemon" in raw:
        return "daemon"
    return "unknown"


def _weight(task: dict[str, Any], status: CardStatus) -> float:
    if status in {"blocked", "failed"}:
        return 0.95
    if status in {"claimed", "running", "review"}:
        return 0.85
    if status == "done":
        return 0.25
    role = str(task.get("role") or "").lower()
    if role in {"verifier", "reviewer"}:
        return 0.9
    if role in {"builder", "implementer"}:
        return 0.8
    return 0.7


def _time_from(mission: dict[str, Any], task: dict[str, Any]) -> str:
    lease = task.get("lease") if isinstance(task.get("lease"), dict) else {}
    return str(
        task.get("kernel_closeback_at")
        or lease.get("claimed_at")
        or mission.get("created_at")
        or ""
    )


def _receipt_refs(mission_dir: Path, mission: dict[str, Any], task: dict[str, Any]) -> list[ReceiptRef]:
    created_at = _time_from(mission, task)
    refs: list[ReceiptRef] = []
    mission_path = mission_dir / "mission.json"
    tasks_path = mission_dir / "tasks.jsonl"
    for label, path in (("ds_goal_mission", mission_path), ("ds_goal_tasks", tasks_path)):
        if not path.exists():
            continue
        refs.append(
            ReceiptRef(
                receipt_id=f"{label}:{stable_payload_hash(str(path))[-16:]}",
                kind=label,
                store="external",
                uri=str(path),
                checksum=sha256_file(path),
                created_at=created_at,
                summary=f"{label} ledger file",
            )
        )

    kernel_result = task.get("kernel_result_ref") if isinstance(task.get("kernel_result_ref"), dict) else {}
    if kernel_result:
        run_id = str(kernel_result.get("run_id") or "kernel_result")
        proof_hash = str(kernel_result.get("proof_entry_hash") or "")
        refs.append(
            ReceiptRef(
                receipt_id=f"kernel_result:{run_id}",
                kind="living_agent_kernel_result",
                store="external",
                uri=run_id,
                checksum=proof_hash,
                created_at=created_at,
                summary=str(kernel_result.get("status") or task.get("kernel_result_status") or ""),
            )
        )
    return refs


def ds_goal_task_to_card(task: dict[str, Any], *, mission: dict[str, Any], mission_dir: Path) -> Card:
    """Project one ds-goal task row into a BoardStore Card."""
    mission_id = str(task.get("mission_id") or mission.get("mission_id") or mission_dir.name)
    task_id = str(task.get("task_id") or task.get("id") or mission_id)
    status = _task_status(task)
    agent_uid = str(task.get("agent_uid") or "")
    created_at = _time_from(mission, task)
    title = str(task.get("title") or mission.get("title") or mission.get("goal") or task_id)
    return_address = str(task.get("return_address") or "")
    verifier = str(task.get("verifier_command") or "")
    criteria: list[AcceptanceCriterion] = []
    if verifier:
        criteria.append(
            AcceptanceCriterion(
                id="verifier_command",
                text="Verifier command exits 0",
                kind="test",
                verifier=verifier,
                evidence_ref=str(task.get("kernel_result_ref", {}).get("proof_entry_hash") or ""),
            )
        )
    if task.get("receipt_required"):
        criteria.append(
            AcceptanceCriterion(
                id="kernel_closeback",
                text="LivingAgentKernel records kernel_result_ref on the ds-goal task",
                kind="receipt",
                verifier="ds-goal run --max-wakes 1",
                evidence_ref=str(task.get("kernel_result_ref", {}).get("run_id") or ""),
            )
        )

    return Card(
        id=CardId(f"dsg_{_identifier(mission_id)}_{_identifier(task_id)}"),
        parent_objective=ObjectiveId(f"dsg_{_identifier(mission_id)}"),
        title=title,
        body="\n".join(
            line
            for line in [
                f"mission_id: {mission_id}",
                f"task_id: {task_id}",
                f"role: {task.get('role') or ''}",
                f"return_address: {return_address}",
                f"mission_goal: {mission.get('goal') or ''}",
            ]
            if line.strip()
        ),
        status=status,
        assignee_kind=_agent_kind(agent_uid),
        capability_required=["ds_goal", "living_agent_kernel"],
        acceptance_criteria=criteria,
        receipt_refs=_receipt_refs(mission_dir, mission, task),
        cost_ceiling_usd=Decimal("0.00"),
        version=Version(1),
        idempotency_key=f"ds_goal:{stable_payload_hash({'mission_id': mission_id, 'task_id': task_id})}",
        arjuna_weight=_weight(task, status),
        created_by=agent_uid or "ds-goal",
        created_at=created_at,
        updated_at=created_at,
        last_transitioned_at=created_at,
        source_surface="cli",
        render_hints=RenderHints(
            column_hint=status,
            lane_hint="ds_goal",
            thread_hint=return_address,
            map_node_kind="ds_goal_task",
        ),
    )


def mission_cards(mission_dir: Path) -> list[Card]:
    """Project every task in one ds-goal mission directory."""
    mission_root = mission_dir.expanduser().resolve()
    mission = _read_json(mission_root / "mission.json")
    tasks = _jsonl_rows(mission_root / "tasks.jsonl")
    return [
        ds_goal_task_to_card(task, mission=mission, mission_dir=mission_root)
        for task in tasks
    ]


class DsGoalBoardAdapter:
    """Read-only adapter over a ds-goal state root."""

    def __init__(self, state_root: Path | str) -> None:
        self.state_root = Path(state_root).expanduser().resolve()

    def mission_dirs(self) -> list[Path]:
        if not self.state_root.exists():
            return []
        return sorted(
            path
            for path in self.state_root.iterdir()
            if path.is_dir() and (path / "mission.json").exists() and (path / "tasks.jsonl").exists()
        )

    def list_cards(self, *, mission_id: str = "") -> list[Card]:
        roots = [self.state_root / mission_id] if mission_id else self.mission_dirs()
        cards: list[Card] = []
        for mission_dir in roots:
            if mission_dir.exists():
                cards.extend(mission_cards(mission_dir))
        return cards


def load_ds_goal_cards(state_root: Path | str, *, mission_id: str = "") -> list[Card]:
    """Convenience projection for CLI and dashboards."""
    return DsGoalBoardAdapter(state_root).list_cards(mission_id=mission_id)
