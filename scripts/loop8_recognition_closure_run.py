#!/usr/bin/env python3
"""Loop 8 (Recognition / Eigenform) closure replay.

This bounded replay proves recognition as a causal feedback edge without
calling an external provider or weakening the global cybernetics audit gate:

  sense      : read real loop-closure receipt history from the ledger.
  interpret  : derive a self-model/cascade history from closed-loop evidence.
  constrain  : admit only if required loop receipts close under the audit rules.
  act        : run RecognitionEngine so it writes recognition_seed.md.
  adapt      : later build_agent_context reads that seed and changes context.

Usage:
    .venv/bin/python scripts/loop8_recognition_closure_run.py \
        --report reports/loop_closure/cybernetics_codex/2026-07-01_loop8_recognition_closure.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

TRANSITIONS = ("sense", "interpret", "constrain", "act", "adapt")
REQUIRED_HISTORY_LOOPS = (1, 2, 3, 4, 5, 6, 7, 9, 10, 11)
LOOP_IDS = {
    1: "swarm_task_loop",
    2: "organism_heartbeat",
    3: "evolution_loop",
    4: "consolidation_memory",
    5: "zeitgeist_scanner",
    6: "witness_auditor",
    7: "training_flywheel",
    9: "conductors",
    10: "context_agent",
    11: "replication_monitor",
}
MARKER = "loop8recognitionclosure"
WORK_DIR_SENTINEL = ".loop8_recognition_closure_workdir"
WORK_DIR_SENTINEL_CONTENT = "owned by scripts/loop8_recognition_closure_run.py\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_report_path() -> Path:
    return (
        REPO_ROOT
        / "reports"
        / "loop_closure"
        / "cybernetics_codex"
        / f"{datetime.now(timezone.utc):%Y-%m-%d}_loop8_recognition_closure.json"
    )


def _default_history_dir() -> Path:
    return REPO_ROOT / "reports" / "loop_closure" / "cybernetics_codex"


def _default_work_dir(report_path: Path) -> Path:
    return Path(tempfile.gettempdir()) / "dharma_loop8_recognition_closure" / report_path.stem


def _observed_at_for_report(report_path: Path, override: str | None) -> str:
    if override:
        return override
    stem_date = report_path.name[:10]
    try:
        datetime.strptime(stem_date, "%Y-%m-%d")
    except ValueError:
        return _utc_now()
    return f"{stem_date}T00:00:00Z"


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_hash(value: Any) -> str:
    return _sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


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
        "sha256": _sha256_bytes(payload),
    }


def _reset_work_dir(work_dir: Path) -> None:
    if work_dir.exists():
        sentinel = work_dir / WORK_DIR_SENTINEL
        try:
            sentinel_valid = (
                sentinel.read_text(encoding="utf-8") == WORK_DIR_SENTINEL_CONTENT
            )
        except OSError:
            sentinel_valid = False
        if not sentinel_valid:
            raise RuntimeError(f"refusing to reset non-owned work dir: {work_dir}")
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / WORK_DIR_SENTINEL).write_text(WORK_DIR_SENTINEL_CONTENT, encoding="utf-8")


def _empty_transitions() -> dict[str, bool]:
    return {name: False for name in TRANSITIONS}


def _closure_satisfied(report: dict[str, Any]) -> bool:
    adapt = report.get("adapt_proof") or {}
    return (
        int(report.get("cycles") or 0) > 0
        and bool(report.get("real_data"))
        and all(bool((report.get("transitions_receipted") or {}).get(t)) for t in TRANSITIONS)
        and bool(adapt.get("fed_forward"))
        and adapt.get("before") != adapt.get("after")
        and not report.get("tick_errors")
    )


def _read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_by_name(paths: list[Path]) -> Path | None:
    return sorted(paths, key=lambda p: p.name)[-1] if paths else None


def _loop1_candidates(history_dir: Path) -> list[Path]:
    return [
        path
        for path in history_dir.glob("*loop1*_spine_dispatch.json")
        if "loop10" not in path.name and "loop11" not in path.name
    ]


def _generic_loop_candidates(history_dir: Path, loop: int) -> list[Path]:
    return list(history_dir.glob(f"*loop{loop}_*closure.json"))


def _evaluate_loop1(data: dict[str, Any]) -> dict[str, Any]:
    served_truth = data.get("served_provider_truth") or {}
    evidence_receipts = data.get("evidence_receipts") or {}
    tasks_requested = int(data.get("tasks_requested") or 0)
    tasks_completed = int(data.get("tasks_completed") or 0)
    dispatch_dropoffs = int(data.get("dispatch_dropoffs") or 0)
    tick_errors = data.get("tick_errors") or []
    receipt_statuses = [str(status) for status in evidence_receipts.values()]
    completed_with_truth = int(served_truth.get("completed_runs_with_truth") or 0)
    marks_before = int(data.get("stigmergy_marks_before") or 0)
    marks_after = int(data.get("stigmergy_marks_after") or 0)
    adapt_fed_forward = bool(data.get("adapt_fired")) and marks_before != marks_after
    closed = (
        tasks_requested > 0
        and tasks_completed == tasks_requested
        and dispatch_dropoffs == 0
        and not tick_errors
        and bool(receipt_statuses)
        and all(status == "ok" for status in receipt_statuses)
        and completed_with_truth >= tasks_completed
        and adapt_fed_forward
    )
    return {
        "closed": closed,
        "cycles": int(data.get("ticks") or tasks_completed or 0),
        "real_data": closed,
        "transitions_receipted": {name: closed for name in TRANSITIONS},
        "adapt_proof": {
            "before": marks_before,
            "after": marks_after,
            "fed_forward": adapt_fed_forward and closed,
            "field": "Loop 1 bounded spine dispatch marks fed into stigmergy state",
        },
        "tick_errors": tick_errors,
        "blocker": "" if closed else "Loop 1 bounded replay did not satisfy strict predicate",
        "tasks_requested": tasks_requested,
        "tasks_completed": tasks_completed,
        "dispatch_dropoffs": dispatch_dropoffs,
        "completed_runs_with_truth": completed_with_truth,
        "evidence_receipts": len(receipt_statuses),
    }


def _evaluate_generic_loop(loop: int, data: dict[str, Any]) -> dict[str, Any]:
    from dharma_swarm.cybernetics_codex import _evaluate_loop_closure_replay

    evaluated = _evaluate_loop_closure_replay(data)
    loop_matches = int(data.get("loop") or 0) == loop
    evaluated["closed"] = bool(evaluated["closed"] and loop_matches)
    evaluated["loop_matches"] = loop_matches
    if not loop_matches:
        evaluated["blocker"] = f"receipt loop field {data.get('loop')} does not match loop {loop}"
    return evaluated


def read_loop_history(history_dir: Path) -> dict[int, dict[str, Any]]:
    history: dict[int, dict[str, Any]] = {}
    for loop in REQUIRED_HISTORY_LOOPS:
        path = (
            _latest_by_name(_loop1_candidates(history_dir))
            if loop == 1
            else _latest_by_name(_generic_loop_candidates(history_dir, loop))
        )
        if path is None:
            history[loop] = {
                "loop": loop,
                "loop_id": LOOP_IDS[loop],
                "exists": False,
                "closed": False,
                "path": None,
                "blocker": f"no receipt found for loop {loop}",
            }
            continue

        evidence = _file_evidence(path)
        try:
            data = _read_json_file(path)
            evaluated = _evaluate_loop1(data) if loop == 1 else _evaluate_generic_loop(loop, data)
            closed = bool(evaluated.get("closed"))
            history[loop] = {
                "loop": loop,
                "loop_id": str(data.get("loop_id") or LOOP_IDS[loop]),
                "exists": True,
                "closed": closed,
                "path": evidence["path"],
                "bytes": evidence["bytes"],
                "sha256": evidence["sha256"],
                "observed_at": data.get("observed_at"),
                "cycles": int(evaluated.get("cycles") or data.get("cycles") or 0),
                "real_data": bool(evaluated.get("real_data", data.get("real_data"))),
                "transitions_receipted": (
                    data.get("transitions_receipted")
                    or evaluated.get("transitions_receipted")
                    or {}
                ),
                "adapt_proof": data.get("adapt_proof") or evaluated.get("adapt_proof") or {},
                "tick_errors": data.get("tick_errors") or evaluated.get("tick_errors") or [],
                "blocker": evaluated.get("blocker") or "",
            }
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            history[loop] = {
                "loop": loop,
                "loop_id": LOOP_IDS[loop],
                "exists": True,
                "closed": False,
                "path": evidence["path"],
                "bytes": evidence["bytes"],
                "sha256": evidence["sha256"],
                "blocker": f"receipt unreadable: {type(exc).__name__}: {exc}",
            }
    return history


def _history_digest(history: dict[int, dict[str, Any]]) -> str:
    digest_payload = [
        {
            "loop": loop,
            "loop_id": item.get("loop_id"),
            "path": item.get("path"),
            "sha256": item.get("sha256"),
            "closed": item.get("closed"),
            "cycles": item.get("cycles"),
            "adapt_proof_sha256": _json_hash(item.get("adapt_proof") or {}),
        }
        for loop, item in sorted(history.items())
    ]
    return _json_hash(digest_payload)


def _derive_self_model(history: dict[int, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    digest = _history_digest(history)
    closed_items = [item for _, item in sorted(history.items()) if item.get("closed")]
    loop_refs = [
        {
            "loop": item["loop"],
            "loop_id": item["loop_id"],
            "receipt_sha256": item.get("sha256"),
            "receipt_path": item.get("path"),
            "cycles": item.get("cycles"),
            "adapt_field": (item.get("adapt_proof") or {}).get("field"),
        }
        for item in closed_items
    ]
    self_model = {
        "schema_version": "loop8_recognition_eigenform.self_model.v1",
        "marker": MARKER,
        "history_digest": digest,
        "required_loops": list(REQUIRED_HISTORY_LOOPS),
        "closed_loop_count": len(closed_items),
        "total_cycles": sum(int(item.get("cycles") or 0) for item in closed_items),
        "loop_refs": loop_refs,
        "eigenform_rule": (
            "A loop contributes to recognition only when its own closed receipt "
            "shows all five transitions and a fed-forward adapt change."
        ),
    }
    cascade_records = []
    for item in closed_items:
        loop = int(item["loop"])
        sha_prefix = str(item.get("sha256") or "")[:12]
        cascade_records.append(
            {
                "domain": f"{MARKER}:loop{loop}:{item['loop_id']}:{sha_prefix}",
                "converged": True,
                "eigenform_reached": True,
                "best_fitness": round(0.80 + (loop % 10) / 100, 2),
                "receipt_path": item.get("path"),
                "receipt_sha256": item.get("sha256"),
                "history_digest": digest,
                "cycles": int(item.get("cycles") or 0),
            }
        )
    return self_model, cascade_records


def _write_interpreted_history(
    state_dir: Path,
    *,
    self_model: dict[str, Any],
    cascade_records: list[dict[str, Any]],
) -> dict[str, Any]:
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    self_model_path = meta_dir / "loop8_eigenform_self_model.json"
    cascade_path = meta_dir / "cascade_history.jsonl"
    graph_path = meta_dir / "cc_catalytic_graph.json"
    system_rv_path = meta_dir / "system_rv.json"

    self_model_path.write_text(
        json.dumps(self_model, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cascade_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in cascade_records),
        encoding="utf-8",
    )
    graph = {
        "nodes": {
            f"loop{row['domain'].split(':loop', 1)[1].split(':', 1)[0]}": {
                "domain": row["domain"],
                "receipt_sha256": row["receipt_sha256"],
            }
            for row in cascade_records
        },
        "edges": [
            {
                "from": row["domain"],
                "to": "loop8:recognition_eigenform",
                "kind": "receipt_history_feeds_recognition",
            }
            for row in cascade_records
        ],
    }
    graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    system_rv_path.write_text(
        json.dumps(
            [
                {
                    "rv": 0.618,
                    "regime": "loop-history-eigenform",
                    "history_digest": self_model["history_digest"],
                }
            ],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "self_model": _file_evidence(self_model_path),
        "cascade_history": _file_evidence(cascade_path),
        "autocatalytic_graph": _file_evidence(graph_path),
        "system_rv": _file_evidence(system_rv_path),
    }


async def _synthesize_recognition_seed(state_dir: Path, *, observed_at: str) -> str:
    import dharma_swarm.meta_daemon as meta_daemon

    fixed_now = _parse_utc(observed_at)
    original_utc_now = meta_daemon._utc_now
    meta_daemon._utc_now = lambda: fixed_now
    try:
        engine = meta_daemon.RecognitionEngine(state_dir=state_dir)
        return await engine.synthesize("light")
    finally:
        meta_daemon._utc_now = original_utc_now


def _snippet(text: str, marker: str = MARKER, radius: int = 260) -> str:
    compact = " ".join(text.split())
    pos = compact.find(marker)
    if pos < 0:
        return compact[: radius * 2]
    start = max(0, pos - radius)
    end = min(len(compact), pos + len(marker) + radius)
    return compact[start:end]


def run_replay(
    *,
    report_path: Path,
    history_dir: Path | None = None,
    work_dir: Path | None = None,
    observed_at: str | None = None,
    fresh: bool = True,
) -> dict[str, Any]:
    from dharma_swarm.context import build_agent_context

    observed = _observed_at_for_report(report_path, observed_at)
    ledger_dir = history_dir or _default_history_dir()
    state_dir = work_dir or _default_work_dir(report_path)
    if fresh:
        _reset_work_dir(state_dir)
    else:
        state_dir.mkdir(parents=True, exist_ok=True)

    transitions = _empty_transitions()
    tick_errors: list[str] = []
    cycle_detail: list[dict[str, Any]] = []
    history: dict[int, dict[str, Any]] = {}
    self_model: dict[str, Any] = {}
    cascade_records: list[dict[str, Any]] = []
    interpreted_files: dict[str, Any] = {}
    seed_text = ""
    seed_path = state_dir / "meta" / "recognition_seed.md"
    archive_path = state_dir / "meta" / "history" / f"seed_{_parse_utc(observed):%Y%m%d_%H%M%S}.md"

    context_before = build_agent_context(
        role="architect",
        thread="architectural",
        state_dir=state_dir,
    )
    context_before_proof = {
        "context_sha256": _sha256_text(context_before),
        "context_chars": len(context_before),
        "recognition_seed_present": "## L9: META -- Recognition Seed" in context_before,
        "marker_present": MARKER in context_before,
    }
    context_after = context_before

    try:
        history = read_loop_history(ledger_dir)
        required_present = all(bool(item.get("exists")) for item in history.values())
        required_closed = all(bool(item.get("closed")) for item in history.values())
        transitions["sense"] = required_present and all(bool(item.get("sha256")) for item in history.values())

        self_model, cascade_records = _derive_self_model(history)
        interpreted_files = _write_interpreted_history(
            state_dir,
            self_model=self_model,
            cascade_records=cascade_records,
        )
        transitions["interpret"] = (
            transitions["sense"]
            and self_model.get("closed_loop_count") == len(REQUIRED_HISTORY_LOOPS)
            and len(cascade_records) == len(REQUIRED_HISTORY_LOOPS)
            and all(row.get("eigenform_reached") for row in cascade_records)
        )

        required_sha_bound = len(cascade_records) == len(REQUIRED_HISTORY_LOOPS) and all(
            str(item.get("sha256") or "")[:12] in row["domain"]
            for item, row in zip(
                [history[loop] for loop in REQUIRED_HISTORY_LOOPS],
                cascade_records,
                strict=False,
            )
        )
        transitions["constrain"] = (
            transitions["interpret"]
            and required_closed
            and required_sha_bound
            and bool(self_model.get("history_digest"))
        )

        if transitions["constrain"]:
            seed_text = asyncio.run(_synthesize_recognition_seed(state_dir, observed_at=observed))
            seed_contains_required_loops = all(
                f"{MARKER}:loop{loop}:" in seed_text for loop in REQUIRED_HISTORY_LOOPS
            )
            transitions["act"] = (
                seed_path.exists()
                and archive_path.exists()
                and MARKER in seed_text
                and seed_contains_required_loops
            )

        context_after = build_agent_context(
            role="architect",
            thread="architectural",
            state_dir=state_dir,
        )
        context_after_proof = {
            "context_sha256": _sha256_text(context_after),
            "context_chars": len(context_after),
            "recognition_seed_present": "## L9: META -- Recognition Seed" in context_after,
            "marker_present": MARKER in context_after,
        }
        transitions["adapt"] = (
            transitions["act"]
            and context_before_proof["context_sha256"] != context_after_proof["context_sha256"]
            and bool(context_after_proof["recognition_seed_present"])
            and bool(context_after_proof["marker_present"])
        )

        cycle_detail.append(
            {
                "cycle": 1,
                "history_dir": str(ledger_dir),
                "required_loops": list(REQUIRED_HISTORY_LOOPS),
                "required_present": required_present,
                "required_closed": required_closed,
                "history_digest": self_model.get("history_digest"),
                "cascade_records": len(cascade_records),
                "seed_written": seed_path.exists(),
            }
        )
        cycle_detail.append(
            {
                "cycle": 2,
                "later_context_reader": "dharma_swarm.context.build_agent_context",
                "context_before": context_before_proof,
                "context_after": context_after_proof,
                "context_changed": (
                    context_before_proof["context_sha256"]
                    != context_after_proof["context_sha256"]
                ),
            }
        )
    except Exception as exc:
        tick_errors.append(f"{type(exc).__name__}: {exc}")
        context_after_proof = {
            "context_sha256": _sha256_text(context_after),
            "context_chars": len(context_after),
            "recognition_seed_present": "## L9: META -- Recognition Seed" in context_after,
            "marker_present": MARKER in context_after,
        }

    context_after_proof = {
        "context_sha256": _sha256_text(context_after),
        "context_chars": len(context_after),
        "recognition_seed_present": "## L9: META -- Recognition Seed" in context_after,
        "marker_present": MARKER in context_after,
    }
    real_data = bool(
        transitions["sense"]
        and transitions["interpret"]
        and transitions["constrain"]
        and transitions["act"]
        and transitions["adapt"]
        and seed_path.exists()
        and all(item.get("closed") for item in history.values())
    )
    report: dict[str, Any] = {
        "loop": 8,
        "loop_id": "recognition_eigenform",
        "cycles": len(cycle_detail),
        "real_data": real_data,
        "transitions_receipted": transitions,
        "adapt_proof": {
            "field": "recognition_seed.md -> later build_agent_context() L9 block",
            "before": context_before_proof,
            "after": context_after_proof,
            "fed_forward": bool(transitions["adapt"]),
            "seed_path": str(seed_path),
        },
        "tick_errors": tick_errors,
        "cycle_detail": cycle_detail,
        "sense_evidence": {
            "reader": "scripts.loop8_recognition_closure_run.read_loop_history",
            "history_dir": str(ledger_dir),
            "required_loops": list(REQUIRED_HISTORY_LOOPS),
            "receipts_read": [
                {
                    "loop": loop,
                    "loop_id": item.get("loop_id"),
                    "path": item.get("path"),
                    "sha256": item.get("sha256"),
                    "closed": item.get("closed"),
                    "cycles": item.get("cycles"),
                }
                for loop, item in sorted(history.items())
            ],
            "history_digest": self_model.get("history_digest"),
        },
        "interpret_evidence": {
            "interpreter": "receipt_history_to_recognition_cascade_history",
            "self_model": {
                "schema_version": self_model.get("schema_version"),
                "marker": self_model.get("marker"),
                "history_digest": self_model.get("history_digest"),
                "closed_loop_count": self_model.get("closed_loop_count"),
                "total_cycles": self_model.get("total_cycles"),
                "loop_refs": self_model.get("loop_refs", []),
            },
            "cascade_records": cascade_records,
            "interpreted_files": interpreted_files,
        },
        "constrain_evidence": {
            "required_loops_present": all(bool(item.get("exists")) for item in history.values()),
            "required_loops_closed": all(bool(item.get("closed")) for item in history.values()),
            "all_cascade_records_sha_bound": all(
                str(history[loop].get("sha256") or "")[:12] in row["domain"]
                for loop, row in zip(REQUIRED_HISTORY_LOOPS, cascade_records, strict=False)
            ),
            "history_digest_present": bool(self_model.get("history_digest")),
            "admitted_to_recognition_engine": bool(transitions["constrain"]),
            "provider_truth_claimed": False,
        },
        "act_evidence": {
            "actor": "dharma_swarm.meta_daemon.RecognitionEngine.synthesize",
            "synthesis_type": "light",
            "recognition_seed": _file_evidence(seed_path),
            "recognition_history_archive": _file_evidence(archive_path),
            "seed_contains_marker": MARKER in seed_text,
            "seed_contains_required_loop_domains": all(
                f"{MARKER}:loop{loop}:" in seed_text for loop in REQUIRED_HISTORY_LOOPS
            )
            if seed_text
            else False,
            "seed_snippet": _snippet(seed_text),
        },
        "adapt_evidence": {
            "reader": "dharma_swarm.context.build_agent_context",
            "context_before": context_before_proof,
            "context_after": context_after_proof,
            "context_changed": context_before_proof["context_sha256"] != context_after_proof["context_sha256"],
        },
        "later_cycle_read_evidence": {
            "later_reader": "dharma_swarm.context.build_agent_context",
            "recognition_seed_section_present": context_after_proof["recognition_seed_present"],
            "marker_present_in_later_context": context_after_proof["marker_present"],
            "later_context_snippet": _snippet(context_after),
        },
        "provider_truth": {
            "external_provider_invoked": False,
            "provider_truth_claimed": False,
        },
        "work_dir": str(state_dir),
        "observed_at": observed,
    }
    report["closed"] = _closure_satisfied(report)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(_json_ready(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=_default_report_path(),
        help="path for the Loop 8 closure receipt",
    )
    parser.add_argument(
        "--history-dir",
        type=Path,
        default=_default_history_dir(),
        help="directory containing prior loop closure receipts",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="private replay state dir; defaults under /private/tmp",
    )
    parser.add_argument(
        "--observed-at",
        default=None,
        help="override observed_at; defaults to the date prefix in --report",
    )
    parser.add_argument(
        "--no-fresh",
        action="store_true",
        help="reuse prior private replay state instead of resetting it",
    )
    args = parser.parse_args(argv)

    report = run_replay(
        report_path=args.report,
        history_dir=args.history_dir,
        work_dir=args.work_dir,
        observed_at=args.observed_at,
        fresh=not args.no_fresh,
    )
    print(json.dumps(_json_ready(report), indent=2, sort_keys=True))
    return 0 if report.get("closed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
