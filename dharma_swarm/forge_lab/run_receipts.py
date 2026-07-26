"""Receipt layer for forge_lab experiments: result rows, closeouts, after-run notes.

Every artifact an experiment leaves behind flows through here so monitors and
successors read stable schemas. EXPLORE closeout states are enforced at write
time: a positive-lift claim is structurally impossible.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPLORE_CLOSEOUTS = ("measured_negative", "inconclusive_low_power", "blocked_with_evidence")
CLOSEOUT_SCHEMA = "forge_lab.closeout.v0"
RESULT_ROW_SCHEMA = "forge_lab.result_observation.v0"
GENERATION_RECEIPT_SCHEMA = "forge_lab.generation_receipt.v0"
AFTER_RUN_NOTES_SCHEMA = "forge_lab.after_run_notes.v0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")


def _result_row(
    *,
    exp_id: str,
    candidate_id: str,
    state: str,
    role: str | None,
    op: str,
    generation: int,
    parent_id: str | None = None,
    pass_rate: float | None = None,
    per_task: list[dict[str, Any]] | None = None,
    budget: dict[str, Any] | None = None,
    reasons: list[str] | tuple[str, ...] | None = None,
    duplicate_of: str | None = None,
) -> dict[str, Any]:
    """Canonical row for ``results.jsonl``.

    Monitors can always read the same top-level keys regardless of whether the
    observation was graded, blocked, errored, or duplicate.
    """
    return {
        "schema": RESULT_ROW_SCHEMA,
        "experiment_id": exp_id,
        "candidate_id": candidate_id,
        "parent_id": parent_id,
        "state": state,
        "role": role,
        "op": op,
        "generation": generation,
        "pass_rate": pass_rate,
        "per_task": list(per_task or []),
        "budget": dict(budget or {}),
        "reasons": list(reasons or []),
        "duplicate_of": duplicate_of,
        "at": _now(),
    }


def _append_result_row(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    _append_jsonl(path, row)
    return row


def _result_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Stable generation-receipt summary derived from a result row."""
    return {
        "schema": row["schema"],
        "candidate_id": row["candidate_id"],
        "parent_id": row["parent_id"],
        "state": row["state"],
        "role": row["role"],
        "op": row["op"],
        "generation": row["generation"],
        "pass_rate": row["pass_rate"],
        "reasons": list(row.get("reasons") or []),
        "duplicate_of": row.get("duplicate_of"),
    }


def _artifact_index(exp_dir: Path) -> dict[str, str]:
    return {
        "run_manifest": "run_manifest.json",
        "results": "results.jsonl",
        "archive": "archive.jsonl",
        "receipts_dir": "receipts/",
        "closeout": "closeout.json",
        "after_run_notes_json": "after_run_notes.json",
        "after_run_notes_md": "after_run_notes.md",
    }


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _after_run_notes_payload(exp_dir: Path, closeout: dict[str, Any]) -> dict[str, Any]:
    stats = closeout.get("stats") if isinstance(closeout.get("stats"), dict) else {}
    receipts = sorted(p.name for p in (exp_dir / "receipts").glob("generation_*.json"))
    return {
        "schema": AFTER_RUN_NOTES_SCHEMA,
        "experiment_id": closeout.get("experiment_id"),
        "generated_at": _now(),
        "closeout_state": closeout.get("closeout_state"),
        "claim_boundary": "L0_legacy_configuration_search_no_paired_lift",
        "honesty_rule": {
            "sample": "fixed_adaptive_search_task_panel",
            "sample_value": stats.get("allocated_task_count"),
            "interpretation": "descriptive_configuration_signal_only_non_causal",
        },
        "evidence_level": stats.get("evidence_level"),
        "research_interpretation": stats.get("research_interpretation"),
        "paired_lift_claim_eligible": stats.get("paired_lift_claim_eligible"),
        "authority_granted": stats.get("authority_granted"),
        "counters": stats.get("counters", {}),
        "seed_pass_rate": stats.get("seed_pass_rate"),
        "best_pass_rate": stats.get("best_pass_rate"),
        "tokens_spent_total": stats.get("tokens_spent_total"),
        "reported_tokens_lower_bound": stats.get("reported_tokens_lower_bound"),
        "usage_completeness": stats.get("usage_completeness"),
        "tokens_spent_total_semantics": stats.get("tokens_spent_total_semantics"),
        "merkle_verified": (closeout.get("merkle") or {}).get("verified")
        if isinstance(closeout.get("merkle"), dict)
        else None,
        "scratch_worktree": closeout.get("scratch_worktree", {}),
        "artifacts": _artifact_index(exp_dir),
        "artifact_counts": {
            "result_rows": _count_jsonl_rows(exp_dir / "results.jsonl"),
            "archive_rows": _count_jsonl_rows(exp_dir / "archive.jsonl"),
            "generation_receipts": len(receipts),
        },
        "generation_receipts": receipts,
        "started_at": closeout.get("started_at"),
        "finished_at": closeout.get("finished_at"),
        "wall_seconds": closeout.get("wall_seconds"),
    }


def _render_after_run_notes(notes: dict[str, Any]) -> str:
    counters = notes.get("counters") or {}
    scratch = notes.get("scratch_worktree") or {}
    artifacts = notes.get("artifacts") or {}
    receipts = notes.get("generation_receipts") or []
    lines = [
        "# Forge Lab After-Run Notes",
        "",
        f"- schema: {notes.get('schema')}",
        f"- experiment_id: {notes.get('experiment_id')}",
        f"- closeout_state: {notes.get('closeout_state')}",
        f"- claim_boundary: {notes.get('claim_boundary')}",
        f"- counters: graded={counters.get('graded', 0)} blocked={counters.get('blocked', 0)} errored={counters.get('errored', 0)} duplicate={counters.get('duplicate', 0)}",
        f"- seed_pass_rate: {notes.get('seed_pass_rate')}",
        f"- best_pass_rate: {notes.get('best_pass_rate')}",
        f"- tokens_spent_total: {notes.get('tokens_spent_total')}",
        f"- reported_tokens_lower_bound: {notes.get('reported_tokens_lower_bound')}",
        f"- usage_completeness: {notes.get('usage_completeness')}",
        f"- merkle_verified: {notes.get('merkle_verified')}",
        f"- scratch_worktree: state={scratch.get('state')} removed={scratch.get('removed')} path={scratch.get('path')}",
        f"- result_rows: {(notes.get('artifact_counts') or {}).get('result_rows', 0)}",
        f"- generation_receipts: {', '.join(receipts) if receipts else 'none'}",
        "",
        "## Artifacts",
    ]
    for key in sorted(artifacts):
        lines.append(f"- {key}: {artifacts[key]}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "- EXPLORE closeouts cannot claim positive lift.",
            "- This is adaptive L0 configuration search, not authentic self-editing.",
            "- Same-panel score differences are descriptive and selection-biased, not paired causal evidence.",
            "- Reported tokens are a lower bound, not a provider billing ceiling.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_after_run_notes(exp_dir: Path, closeout: dict[str, Any]) -> dict[str, Any]:
    notes = _after_run_notes_payload(exp_dir, closeout)
    _write_json(exp_dir / "after_run_notes.json", notes)
    (exp_dir / "after_run_notes.md").write_text(_render_after_run_notes(notes), encoding="utf-8")
    return notes


def _closeout(exp_dir: Path, exp_id: str, state: str, *, reasons: list[str], started_at: str,
              stats: dict[str, Any], merkle_root: Any, wall_seconds: float,
              scratch_worktree: dict[str, Any] | None = None) -> dict[str, Any]:
    assert state in EXPLORE_CLOSEOUTS, f"illegal explore closeout: {state}"
    payload = {
        "schema": CLOSEOUT_SCHEMA,
        "experiment_id": exp_id,
        "closeout_state": state,
        "reasons": reasons,
        "stats": stats,
        "merkle": merkle_root,
        "scratch_worktree": scratch_worktree or {},
        "artifacts": _artifact_index(exp_dir),
        "started_at": started_at,
        "finished_at": _now(),
        "wall_seconds": wall_seconds,
    }
    _write_json(exp_dir / "closeout.json", payload)
    _write_after_run_notes(exp_dir, payload)
    return payload


__all__ = [
    "EXPLORE_CLOSEOUTS",
    "CLOSEOUT_SCHEMA",
    "RESULT_ROW_SCHEMA",
    "GENERATION_RECEIPT_SCHEMA",
    "AFTER_RUN_NOTES_SCHEMA",
]
