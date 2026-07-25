#!/usr/bin/env python3
"""Loop 4 + Loop 10 closure replay for memory/context feedback.

This replay proves two bounded cybernetic loops without provider claims:

Loop 4 (consolidation_memory)
  sense      completed work with concrete repo evidence
  interpret  reduce it into durable memory facts
  constrain  admit only completed work with an existing evidence path
  act        write real StrangeLoopMemory rows to SQLite
  adapt      consolidate witness rows into META memory

Loop 10 (context_agent)
  sense      read the durable memory through the context memory reader
  interpret  assemble agent context that contains that memory
  constrain  require the memory section and budget guard before serving
  act        write a context package built from the assembled context
  adapt      read the package and re-assemble later context with the memory

Usage:
    .venv/bin/python scripts/loop4_10_memory_context_closure_run.py \
        --receipt-dir reports/loop_closure/cybernetics_codex
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

TRANSITIONS = ("sense", "interpret", "constrain", "act", "adapt")
MARKER = "loop410memorycontextclosure"
WORK_ID = "loop4_10_memory_context_closure_replay_v1"
DEFAULT_STATE_DIR = Path(tempfile.gettempdir()) / "dharma_loop4_10_memory_context_closure_state"
STATE_SENTINEL = ".loop4_10_memory_context_closure_state"
STATE_SENTINEL_CONTENT = "owned by scripts/loop4_10_memory_context_closure_run.py\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _receipt_date(observed_at: str) -> str:
    return observed_at[:10]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_evidence(path: Path) -> dict[str, Any]:
    try:
        rel_path = str(path.relative_to(REPO_ROOT))
    except ValueError:
        rel_path = str(path)
    if not path.exists():
        return {
            "path": rel_path,
            "exists": False,
            "bytes": 0,
            "sha256": None,
        }
    payload = path.read_bytes()
    return {
        "path": rel_path,
        "exists": True,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


def _memory_db_path(state_dir: Path) -> Path:
    return state_dir / "db" / "memory.db"


def _context_package_path(state_dir: Path) -> Path:
    return state_dir / "context" / "packages" / "loop4_10_memory_context.md"


def _prepare_state_dir(state_dir: Path, *, reset_state: bool) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    sentinel = state_dir / STATE_SENTINEL
    reset_targets = (
        _memory_db_path(state_dir),
        Path(f"{_memory_db_path(state_dir)}-wal"),
        Path(f"{_memory_db_path(state_dir)}-shm"),
        _context_package_path(state_dir),
    )
    if reset_state:
        try:
            sentinel_valid = sentinel.read_text(encoding="utf-8") == STATE_SENTINEL_CONTENT
        except OSError:
            sentinel_valid = False
        if any(path.exists() for path in reset_targets) and not sentinel_valid:
            raise RuntimeError(f"refusing to reset non-owned state dir: {state_dir}")
        for path in reset_targets:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    sentinel.write_text(STATE_SENTINEL_CONTENT, encoding="utf-8")


def _memory_count(state_dir: Path, layer: str | None = None) -> int:
    db_path = _memory_db_path(state_dir)
    if not db_path.exists():
        return 0
    with sqlite3.connect(str(db_path)) as conn:
        if layer is None:
            row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE layer = ?",
                (layer,),
            ).fetchone()
    return int(row[0] if row else 0)


def _snippet(text: str, marker: str = MARKER, radius: int = 240) -> str:
    compact = " ".join(text.split())
    pos = compact.find(marker)
    if pos < 0:
        return compact[: radius * 2]
    start = max(0, pos - radius)
    end = min(len(compact), pos + len(marker) + radius)
    return compact[start:end]


def _empty_transitions() -> dict[str, bool]:
    return {name: False for name in TRANSITIONS}


def _closed(report: dict[str, Any]) -> bool:
    adapt = report.get("adapt_proof") or {}
    return (
        int(report.get("cycles") or 0) > 0
        and bool(report.get("real_data"))
        and all(bool((report.get("transitions_receipted") or {}).get(t)) for t in TRANSITIONS)
        and bool(adapt.get("fed_forward"))
        and adapt.get("before") != adapt.get("after")
        and not report.get("tick_errors")
    )


async def run_loop4(state_dir: Path, *, observed_at: str) -> dict[str, Any]:
    """Drive Loop 4 through the real StrangeLoopMemory persistence path."""

    from dharma_swarm.context import read_recent_memories
    from dharma_swarm.memory import StrangeLoopMemory

    memory_db = _memory_db_path(state_dir)
    evidence_path = Path(__file__).resolve()
    test_path = REPO_ROOT / "tests" / "test_loop4_10_memory_context_closure_run.py"
    artifacts = [_file_evidence(evidence_path), _file_evidence(test_path)]
    work_event = {
        "work_id": WORK_ID,
        "status": "completed",
        "evidence_path": artifacts[0]["path"],
        "evidence_exists": artifacts[0]["exists"],
        "artifacts": artifacts,
        "marker": MARKER,
    }

    transitions = _empty_transitions()
    tick_errors: list[str] = []
    cycle_detail: list[dict[str, Any]] = []
    inserted_ids: list[str] = []
    meta_entry_id: str | None = None
    later_memory_context = ""
    later_recent_memories = ""
    meta_before = _memory_count(state_dir, "meta")
    memory_before = _memory_count(state_dir)

    async with StrangeLoopMemory(memory_db) as memory:
        try:
            transitions["sense"] = (
                work_event["status"] == "completed"
                and all(bool(item["exists"]) and bool(item["sha256"]) for item in artifacts)
            )

            interpreted = (
                f"{MARKER} completed work {WORK_ID} is ready for durable "
                f"memory consolidation; evidence file path {work_event['evidence_path']} "
                f"sha256 {artifacts[0]['sha256']}"
            )
            transitions["interpret"] = transitions["sense"] and WORK_ID in interpreted

            admitted = (
                transitions["interpret"]
                and work_event["status"] == "completed"
                and all(bool(item["exists"]) and bool(item["sha256"]) for item in artifacts)
                and "provider" not in work_event
            )
            transitions["constrain"] = admitted

            if admitted:
                for index in range(3):
                    entry = await memory.witness(
                        f"{MARKER} completed work {WORK_ID} witness sample {index + 1} "
                        f"with file path {work_event['evidence_path']} and real count evidence"
                    )
                    inserted_ids.append(entry.id)
                development = await memory.mark_development(
                    f"{MARKER} completed work consolidated into durable memory",
                    f"file path {work_event['evidence_path']}; witness_rows=3",
                )
                inserted_ids.append(development.id)
                transitions["act"] = True

            meta_entry = await memory.consolidate_patterns()
            if meta_entry is not None:
                meta_entry_id = meta_entry.id

            meta_after = _memory_count(state_dir, "meta")
            memory_after = _memory_count(state_dir)
            later_memory_context = await memory.get_context(max_chars=8000)
            later_recent_memories = read_recent_memories(
                state_dir=state_dir,
                max_entries=8,
            )
            later_read_ok = (
                MARKER in later_memory_context
                and MARKER in later_recent_memories
            )
            fed_forward = bool(meta_entry_id) and meta_after > meta_before and later_read_ok
            transitions["adapt"] = fed_forward

            cycle_detail.append(
                {
                    "cycle": 1,
                    "sensed_work_id": WORK_ID,
                    "admitted": admitted,
                    "witness_rows_inserted": 3 if admitted else 0,
                    "development_rows_inserted": 1 if admitted else 0,
                    "meta_before": meta_before,
                    "meta_after": meta_after,
                    "memory_before": memory_before,
                    "memory_after": memory_after,
                }
            )
            cycle_detail.append(
                {
                    "cycle": 2,
                    "later_cycle_read": later_read_ok,
                    "memory_get_context_contains_marker": MARKER in later_memory_context,
                    "read_recent_memories_contains_marker": MARKER in later_recent_memories,
                }
            )
        except Exception as exc:  # a tick error honestly blocks closure
            tick_errors.append(f"{type(exc).__name__}: {exc}")
            meta_after = _memory_count(state_dir, "meta")
            memory_after = _memory_count(state_dir)

    later_read_ok = (
        MARKER in later_memory_context
        and MARKER in later_recent_memories
    )
    fed_forward = (
        bool(meta_entry_id)
        and _memory_count(state_dir, "meta") > meta_before
        and later_read_ok
    )

    return {
        "loop": 4,
        "loop_id": "consolidation_memory",
        "cycles": len(cycle_detail),
        "real_data": bool(inserted_ids and later_read_ok and memory_db.exists()),
        "transitions_receipted": transitions,
        "adapt_proof": {
            "field": "StrangeLoopMemory META consolidation count, then later memory/context readers",
            "before": meta_before,
            "after": _memory_count(state_dir, "meta"),
            "fed_forward": fed_forward,
            "meta_entry_id": meta_entry_id,
            "memory_rows_before": memory_before,
            "memory_rows_after": _memory_count(state_dir),
        },
        "tick_errors": tick_errors,
        "cycle_detail": cycle_detail,
        "sense_evidence": work_event,
        "interpret_evidence": {
            "interpreted_summary": (
                f"{MARKER} completed work {WORK_ID} -> durable memory candidate"
            ),
            "contains_work_id": True,
        },
        "constrain_evidence": {
            "required_status": "completed",
            "evidence_path_exists": bool(work_event["evidence_exists"]),
            "artifacts_hashed": all(bool(item["sha256"]) for item in artifacts),
            "provider_truth_claimed": False,
            "admitted_to_memory": bool(transitions["constrain"]),
        },
        "act_evidence": {
            "memory_db": str(memory_db),
            "inserted_memory_ids": inserted_ids,
            "memory_rows_after": _memory_count(state_dir),
        },
        "adapt_evidence": {
            "meta_entry_id": meta_entry_id,
            "meta_before": meta_before,
            "meta_after": _memory_count(state_dir, "meta"),
        },
        "later_cycle_read_evidence": {
            "memory_get_context_contains_marker": MARKER in later_memory_context,
            "read_recent_memories_contains_marker": MARKER in later_recent_memories,
            "memory_get_context_snippet": _snippet(later_memory_context),
            "recent_memories_snippet": _snippet(later_recent_memories),
        },
        "observed_at": observed_at,
    }


def run_loop10(state_dir: Path, *, observed_at: str) -> dict[str, Any]:
    """Drive Loop 10 through actual context assembly over Loop 4 memory."""

    from dharma_swarm.context import CONTEXT_BUDGET, build_agent_context, read_memory_context

    transitions = _empty_transitions()
    tick_errors: list[str] = []
    cycle_detail: list[dict[str, Any]] = []
    package_path = _context_package_path(state_dir)
    package_before = (
        _sha256_text(package_path.read_text(encoding="utf-8"))
        if package_path.exists()
        else "missing"
    )
    context_text = ""
    later_context_text = ""
    package_text = ""

    try:
        memory_context = read_memory_context(
            state_dir=state_dir,
            limit=8,
            allow_semantic_search=False,
            consumer="loop4_10_memory_context_closure.loop10",
            task_id=WORK_ID,
        )
        transitions["sense"] = MARKER in memory_context

        context_text = build_agent_context(
            role="surgeon",
            thread="mechanistic",
            state_dir=state_dir,
        )
        has_recent_memory_section = "## Recent Session Memories" in context_text
        transitions["interpret"] = has_recent_memory_section and MARKER in context_text

        context_over_budget = "context budget exceeded" in context_text
        within_budget = len(context_text) <= CONTEXT_BUDGET + 128
        transitions["constrain"] = (
            transitions["interpret"]
            and within_budget
            and not context_over_budget
        )

        if transitions["constrain"]:
            package_path.parent.mkdir(parents=True, exist_ok=True)
            package_text = (
                f"# Loop 10 Memory-Aware Context Package\n"
                f"observed_at: {observed_at}\n"
                f"source_marker: {MARKER}\n\n"
                f"{context_text}\n"
            )
            package_path.write_text(package_text, encoding="utf-8")
            transitions["act"] = package_path.exists() and MARKER in package_text

        package_after = (
            _sha256_text(package_path.read_text(encoding="utf-8"))
            if package_path.exists()
            else "missing"
        )

        later_context_text = build_agent_context(
            role="surgeon",
            thread="mechanistic",
            state_dir=state_dir,
        )
        package_read_text = package_path.read_text(encoding="utf-8") if package_path.exists() else ""
        later_read_ok = MARKER in later_context_text and MARKER in package_read_text
        fed_forward = package_before != package_after and later_read_ok
        transitions["adapt"] = fed_forward

        cycle_detail.append(
            {
                "cycle": 1,
                "memory_reader_contains_marker": MARKER in memory_context,
                "assembled_context_contains_marker": MARKER in context_text,
                "has_recent_memory_section": has_recent_memory_section,
                "context_chars": len(context_text),
                "within_budget": within_budget,
                "package_written": package_path.exists(),
            }
        )
        cycle_detail.append(
            {
                "cycle": 2,
                "later_context_assembly_contains_marker": MARKER in later_context_text,
                "later_package_read_contains_marker": MARKER in package_read_text,
                "package_checksum_before": package_before,
                "package_checksum_after": package_after,
            }
        )
    except Exception as exc:
        tick_errors.append(f"{type(exc).__name__}: {exc}")
        package_after = (
            _sha256_text(package_path.read_text(encoding="utf-8"))
            if package_path.exists()
            else "missing"
        )

    package_read_text = package_path.read_text(encoding="utf-8") if package_path.exists() else ""
    later_read_ok = MARKER in later_context_text and MARKER in package_read_text
    fed_forward = package_before != package_after and later_read_ok

    return {
        "loop": 10,
        "loop_id": "context_agent",
        "cycles": len(cycle_detail),
        "real_data": bool(MARKER in context_text and later_read_ok and package_path.exists()),
        "transitions_receipted": transitions,
        "adapt_proof": {
            "field": "memory-aware context package checksum, then later context/package read",
            "before": package_before,
            "after": package_after,
            "fed_forward": fed_forward,
            "package_path": str(package_path),
        },
        "tick_errors": tick_errors,
        "cycle_detail": cycle_detail,
        "sense_evidence": {
            "reader": "dharma_swarm.context.read_memory_context",
            "memory_db": str(_memory_db_path(state_dir)),
            "contains_marker": MARKER in read_memory_context(
                state_dir=state_dir,
                limit=8,
                allow_semantic_search=False,
                consumer="loop4_10_memory_context_closure.loop10.evidence",
                task_id=WORK_ID,
            ),
        },
        "interpret_evidence": {
            "assembler": "dharma_swarm.context.build_agent_context",
            "role": "surgeon",
            "thread": "mechanistic",
            "context_contains_marker": MARKER in context_text,
            "context_snippet": _snippet(context_text),
        },
        "constrain_evidence": {
            "context_budget": CONTEXT_BUDGET,
            "context_chars": len(context_text),
            "budget_exceeded_marker_present": "context budget exceeded" in context_text,
            "recent_memory_section_required": True,
            "admitted_to_package": bool(transitions["constrain"]),
        },
        "act_evidence": {
            "package_path": str(package_path),
            "package_exists": package_path.exists(),
            "package_checksum": package_after,
        },
        "adapt_evidence": {
            "package_checksum_before": package_before,
            "package_checksum_after": package_after,
            "package_read_contains_marker": MARKER in package_read_text,
        },
        "later_cycle_read_evidence": {
            "later_context_assembly_contains_marker": MARKER in later_context_text,
            "later_context_snippet": _snippet(later_context_text),
            "later_package_read_contains_marker": MARKER in package_read_text,
        },
        "observed_at": observed_at,
    }


async def run_replay(
    *,
    receipt_dir: Path,
    state_dir: Path = DEFAULT_STATE_DIR,
    observed_at: str | None = None,
    reset_state: bool = True,
) -> dict[str, Any]:
    observed = observed_at or _utc_now()
    _prepare_state_dir(state_dir, reset_state=reset_state)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    loop4 = await run_loop4(state_dir, observed_at=observed)
    loop10 = run_loop10(state_dir, observed_at=observed)

    date = _receipt_date(observed)
    loop4_path = receipt_dir / f"{date}_loop4_memory_context_closure.json"
    loop10_path = receipt_dir / f"{date}_loop10_context_agent_closure.json"
    loop4_path.write_text(json.dumps(_json_ready(loop4), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    loop10_path.write_text(json.dumps(_json_ready(loop10), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "state_dir": str(state_dir),
        "receipt_dir": str(receipt_dir),
        "loop4": loop4,
        "loop10": loop10,
        "receipt_paths": {
            "loop4": str(loop4_path),
            "loop10": str(loop10_path),
        },
        "closed": {
            "loop4": _closed(loop4),
            "loop10": _closed(loop10),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        required=True,
        help="directory for loop4 and loop10 closure receipts",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=DEFAULT_STATE_DIR,
        help="private replay state dir; reset by default; defaults to /private/tmp",
    )
    parser.add_argument(
        "--no-reset-state",
        action="store_true",
        help="reuse prior replay state instead of resetting private replay artifacts",
    )
    parser.add_argument(
        "--observed-at",
        default=None,
        help="override observed_at for deterministic tests",
    )
    args = parser.parse_args(argv)

    result = asyncio.run(
        run_replay(
            receipt_dir=args.receipt_dir,
            state_dir=args.state_dir,
            observed_at=args.observed_at,
            reset_state=not args.no_reset_state,
        )
    )
    print(json.dumps(_json_ready(result), indent=2, sort_keys=True))
    return 0 if all(result["closed"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
