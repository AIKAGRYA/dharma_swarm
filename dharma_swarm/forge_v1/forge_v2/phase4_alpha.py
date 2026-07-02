"""Phase 4 dual-evolution alpha archive and safety primitives.

The RSI Lab v2.2 objective splits evolution into two tracks:

* Track A: scaffold/genome evolution (prompt/arm/context policy only)
* Track B: isolated code evolution (DGM-style source patches)

This module is deliberately narrow.  It does not generate model proposals, run
grades, open promotion gates, apply patches, or mutate the live Darwin archive.
It only creates receipt-backed archive rows for candidates that were already
evaluated by a caller and fail-closes code candidates that touch forbidden
measurement/gate/oracle surfaces.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.archive import ArchiveEntry, FitnessScore
from dharma_swarm.daemon_config import dharma_state_dir

from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.phase4_dual_evolution_alpha.v1"
DEFAULT_ARCHIVE_ROOT = dharma_state_dir() / "forge_v1" / "phase4_alpha"
LIVE_ARCHIVE = dharma_state_dir() / "evolution" / "archive.jsonl"

TRACK_A_SCAFFOLD = "scaffold_genome"
TRACK_B_CODE = "code_child"

# Objective-specified early Track-B write surface.  ``runner.py`` is allowed only
# for adapter/context code by policy; that nuance is carried in the receipt so a
# reviewer can reject overly broad runner edits before any grade budget is spent.
ALLOWED_CODE_EVOLUTION_PATHS = frozenset(
    {
        "dharma_swarm/forge_v1/forge_v2/arms.py",
        "dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py",
        "dharma_swarm/forge_v1/forge_v2/runner.py",
        "dharma_swarm/forge_v1/forge_v2/budget.py",
        "dharma_swarm/forge_v1/forge_v2/stats.py",
    }
)

FORBIDDEN_CODE_EVOLUTION_PATHS = frozenset(
    {
        "dharma_swarm/forge_v1/forge_v2/verify_promotion.py",
        "dharma_swarm/forge_v1/forge_v2/packet_guard.py",
        "dharma_swarm/forge_v1/forge_v2/fresh_task_oracle.py",
        "dharma_swarm/forge_v1/forge_v2/pr_suite_validator.py",
        "dharma_swarm/forge_v1/forge_v2/taskbed_ledger.py",
        "scripts/governance/check_forge_bypass.py",
    }
)

FORBIDDEN_PREFIXES = (
    "tests/",
    "dharma_swarm/forge_v1/forge_v2/tests/",
)

_DIFF_PATH_RE = re.compile(r"^(?:diff --git a/|--- a/|\+\+\+ b/)(\S+)")


class Phase4SafetyError(RuntimeError):
    """Raised by strict callers when a Phase 4 candidate violates a safety gate."""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _normal_path(path: str | Path) -> str:
    text = str(path).strip()
    if text.startswith("a/") or text.startswith("b/"):
        text = text[2:]
    return text.lstrip("./")


def paths_from_diff(diff_text: str) -> list[str]:
    """Extract touched paths from a unified diff without trusting caller labels."""
    paths: list[str] = []
    for line in (diff_text or "").splitlines():
        match = _DIFF_PATH_RE.match(line.strip())
        if not match:
            continue
        path = _normal_path(match.group(1))
        if path and path != "/dev/null":
            paths.append(path)
    return sorted(set(paths))


def _code_path_findings(paths: Iterable[str]) -> tuple[list[str], list[str]]:
    forbidden: list[str] = []
    outside_allowed: list[str] = []
    for raw in paths:
        path = _normal_path(raw)
        if path in FORBIDDEN_CODE_EVOLUTION_PATHS or any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            forbidden.append(path)
        elif path not in ALLOWED_CODE_EVOLUTION_PATHS:
            outside_allowed.append(path)
    return sorted(set(forbidden)), sorted(set(outside_allowed))


def evaluate_code_candidate_safety(
    *,
    patch: str,
    changed_paths: Iterable[str] = (),
    isolated_worktree: str | Path = "",
    strict: bool = False,
) -> dict[str, Any]:
    """Return a fail-closed safety receipt for a Track-B code candidate.

    The receipt is independent of model self-report: paths are read from the diff
    and merged with caller-supplied changed paths.  A candidate may be archived as
    refused, but may never be treated as eligible if it touches forbidden paths,
    tests, or unapproved surfaces.
    """
    paths = sorted(set(paths_from_diff(patch)) | {_normal_path(p) for p in changed_paths if str(p).strip()})
    forbidden, outside_allowed = _code_path_findings(paths)
    blockers: list[str] = []
    blockers.extend(f"forbidden_path:{path}" for path in forbidden)
    blockers.extend(f"outside_allowed_surface:{path}" for path in outside_allowed)
    if not paths:
        blockers.append("no_changed_paths_detected")
    if not str(isolated_worktree).strip():
        blockers.append("missing_isolated_worktree")

    decision = "pass" if not blockers else "refused"
    receipt = {
        "schema": f"{SCHEMA_VERSION}.code_candidate_safety",
        "generated_at": utc_now(),
        "decision": decision,
        "changed_paths": paths,
        "allowed_surfaces": sorted(ALLOWED_CODE_EVOLUTION_PATHS),
        "forbidden_surfaces": sorted(FORBIDDEN_CODE_EVOLUTION_PATHS),
        "forbidden_prefixes": list(FORBIDDEN_PREFIXES),
        "forbidden_hits": forbidden,
        "outside_allowed_hits": outside_allowed,
        "isolated_worktree": str(isolated_worktree),
        "patch_sha256": canonical_sha256({"patch": patch or ""}),
        "blockers": blockers,
        "live_apply_allowed": False,
        "promotion_gate": "verify_promotion_only",
        "runner_scope_note": "runner.py allowed only for adapter/context code; reviewer must confirm scope before grading",
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    if strict and blockers:
        raise Phase4SafetyError("; ".join(blockers))
    return receipt


def _fitness_from_evaluation(evaluation: dict[str, Any], safety: float = 1.0) -> FitnessScore:
    resolved = float(evaluation.get("resolved_count", 0) or 0)
    total = float(evaluation.get("task_count", evaluation.get("n_pairs", 0)) or 0)
    correctness = resolved / total if total > 0 else 0.0
    lift = max(0.0, float((evaluation.get("ci") or {}).get("mean", evaluation.get("fitness", 0.0)) or 0.0))
    cost = float(evaluation.get("cost_usd", 0.0) or 0.0)
    return FitnessScore(
        correctness=max(0.0, min(1.0, correctness or lift)),
        dharmic_alignment=1.0,
        performance=0.0,
        utilization=0.0,
        economic_value=max(0.0, min(1.0, 1.0 - cost)) if cost else 0.0,
        elegance=0.0,
        efficiency=0.0,
        safety=safety,
    )


def _entry_json(entry: ArchiveEntry) -> str:
    if hasattr(entry, "model_dump_json"):
        return entry.model_dump_json()
    return entry.json()


def _append_jsonl(path: Path, row: dict[str, Any] | ArchiveEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        if isinstance(row, ArchiveEntry):
            fh.write(_entry_json(row) + "\n")
        else:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _archive_paths(root: Path | str) -> dict[str, Path]:
    base = Path(root).expanduser()
    return {
        "root": base,
        "scaffold": base / "scaffold_genomes.jsonl",
        "code": base / "code_children.jsonl",
        "refusals": base / "refusals.jsonl",
        "summary": base / "latest_summary.json",
    }


def archive_scaffold_candidate(
    *,
    genome: dict[str, Any],
    evaluation: dict[str, Any],
    archive_root: Path | str = DEFAULT_ARCHIVE_ROOT,
    parent_id: str | None = None,
    mutation_description: str,
    receipt_links: Iterable[str] = (),
    reason: str = "",
) -> dict[str, Any]:
    """Archive one Track-A scaffold/genome candidate as shadow evidence."""
    paths = _archive_paths(archive_root)
    accepted = str(evaluation.get("closeout") or "") not in {"invalid_budget", "blocked_with_evidence"}
    decision = "accepted_for_archive" if accepted else "rejected_for_archive"
    payload = {
        "schema": f"{SCHEMA_VERSION}.scaffold_candidate",
        "track": TRACK_A_SCAFFOLD,
        "generated_at": utc_now(),
        "parent_id": parent_id,
        "genome": dict(genome),
        "mutation_description": mutation_description,
        "evaluation": dict(evaluation),
        "task_results": dict(evaluation.get("task_results") or {}),
        "budget": dict(evaluation.get("budget") or {}),
        "receipt_links": list(receipt_links),
        "decision": decision,
        "reason": reason or str(evaluation.get("closeout") or ""),
        "live_apply_allowed": False,
        "promotion_gate": "verify_promotion_only",
    }
    payload["candidate_id"] = "scaffold_" + canonical_sha256(payload)[:16]
    payload["receipt_sha256"] = canonical_sha256(payload)

    entry = ArchiveEntry(
        parent_id=parent_id,
        component=f"forge_scaffold::{genome.get('arm', 'unknown')}",
        change_type="scaffold_genome_mutation",
        description=mutation_description,
        spec_ref=payload["candidate_id"],
        requirement_refs=["RSI_V22_PHASE4_TRACK_A"],
        diff="",
        fitness=_fitness_from_evaluation(evaluation),
        test_results=payload,
        evidence_tier="unvalidated",
        promotion_state="candidate",
        gates_passed=["static_sanity", "shadow_only_archive"],
        gates_failed=[] if accepted else [str(evaluation.get("closeout") or "rejected")],
        agent_id="forge_phase4_alpha",
        model=str(genome.get("generator") or ""),
        tokens_used=int((evaluation.get("budget") or {}).get("spent_tokens", 0) or 0),
        status="proposed" if accepted else "gated",
    )
    _append_jsonl(paths["scaffold"], entry)
    return {
        "candidate_id": payload["candidate_id"],
        "decision": decision,
        "archive_path": str(paths["scaffold"]),
        "archive_entry_id": entry.id,
        "live_archive_touched": False,
    }


def archive_code_candidate(
    *,
    patch: str,
    evaluation: dict[str, Any],
    archive_root: Path | str = DEFAULT_ARCHIVE_ROOT,
    parent_id: str | None = None,
    mutation_description: str,
    isolated_worktree: str | Path,
    changed_paths: Iterable[str] = (),
    receipt_links: Iterable[str] = (),
) -> dict[str, Any]:
    """Archive one Track-B code child, or receipt its safety refusal."""
    paths = _archive_paths(archive_root)
    safety = evaluate_code_candidate_safety(
        patch=patch,
        changed_paths=changed_paths,
        isolated_worktree=isolated_worktree,
    )
    evaluation_blockers: list[str] = []
    if evaluation.get("static_checks_passed") is not True:
        evaluation_blockers.append(
            "static_checks_failed" if "static_checks_passed" in evaluation else "missing_static_check_result"
        )
    if evaluation.get("unit_tests_passed") is not True:
        evaluation_blockers.append(
            "unit_tests_failed" if "unit_tests_passed" in evaluation else "missing_unit_test_result"
        )
    base_payload = {
        "schema": f"{SCHEMA_VERSION}.code_candidate",
        "track": TRACK_B_CODE,
        "generated_at": utc_now(),
        "parent_id": parent_id,
        "mutation_description": mutation_description,
        "evaluation": dict(evaluation),
        "receipt_links": list(receipt_links),
        "safety_receipt": safety,
        "evaluation_blockers": evaluation_blockers,
        "live_apply_allowed": False,
        "promotion_gate": "verify_promotion_only",
    }
    base_payload["candidate_id"] = "code_" + canonical_sha256(base_payload)[:16]
    base_payload["receipt_sha256"] = canonical_sha256(base_payload)

    if safety["decision"] != "pass" or evaluation_blockers:
        reason = "safety_gate_failed" if safety["decision"] != "pass" else "evaluation_gate_failed"
        refused = {**base_payload, "decision": "refused", "reason": reason}
        _append_jsonl(paths["refusals"], refused)
        return {
            "candidate_id": base_payload["candidate_id"],
            "decision": "refused",
            "archive_path": str(paths["refusals"]),
            "blockers": [*list(safety["blockers"]), *evaluation_blockers],
            "live_archive_touched": False,
        }

    entry = ArchiveEntry(
        parent_id=parent_id,
        component="forge_code_child",
        change_type="isolated_code_patch",
        description=mutation_description,
        spec_ref=base_payload["candidate_id"],
        requirement_refs=["RSI_V22_PHASE4_TRACK_B"],
        diff="",  # live archive diff stays empty; patch hash is in safety receipt
        shadow_diff=patch,
        fitness=_fitness_from_evaluation(evaluation, safety=1.0),
        test_results={**base_payload, "decision": "accepted_for_archive"},
        evidence_tier="unvalidated",
        promotion_state="candidate",
        gates_passed=["forbidden_path_guard", "isolated_worktree_present", "shadow_only_archive"],
        gates_failed=[],
        agent_id="forge_phase4_alpha",
        model=str(evaluation.get("model") or ""),
        tokens_used=int(evaluation.get("tokens_used", 0) or 0),
        status="proposed",
    )
    _append_jsonl(paths["code"], entry)
    return {
        "candidate_id": base_payload["candidate_id"],
        "decision": "accepted_for_archive",
        "archive_path": str(paths["code"]),
        "archive_entry_id": entry.id,
        "blockers": [],
        "live_archive_touched": False,
    }


def summarize_phase4_archive(*, archive_root: Path | str = DEFAULT_ARCHIVE_ROOT) -> dict[str, Any]:
    """Return and persist a compact archive summary for receipt use."""
    paths = _archive_paths(archive_root)

    def count(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    summary = {
        "schema": f"{SCHEMA_VERSION}.summary",
        "generated_at": utc_now(),
        "archive_root": str(paths["root"]),
        "scaffold_candidates": count(paths["scaffold"]),
        "code_children": count(paths["code"]),
        "refusals": count(paths["refusals"]),
        "live_archive": str(LIVE_ARCHIVE),
        "live_archive_touched": False,
    }
    paths["summary"].parent.mkdir(parents=True, exist_ok=True)
    tmp = paths["summary"].with_suffix(paths["summary"].suffix + ".tmp")
    tmp.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, paths["summary"])
    return summary


__all__ = [
    "ALLOWED_CODE_EVOLUTION_PATHS",
    "FORBIDDEN_CODE_EVOLUTION_PATHS",
    "Phase4SafetyError",
    "archive_code_candidate",
    "archive_scaffold_candidate",
    "evaluate_code_candidate_safety",
    "paths_from_diff",
    "summarize_phase4_archive",
]
