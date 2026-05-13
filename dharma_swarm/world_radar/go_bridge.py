"""Bridge Python runtime loops to the Go world scout and signal ingestor."""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.world_radar.analysis import (
    build_world_signal_board,
    incubating_movements,
    load_source_feedback_ledger,
    load_source_weights,
    promotion_ready_signals,
    render_world_signal_brief,
    save_source_feedback_ledger,
    save_source_weights,
    update_source_weights_from_opportunities,
)
from dharma_swarm.world_radar.rnd import write_rnd_artifacts


@dataclass(frozen=True)
class WorldRadarGoResult:
    ok: bool
    raw_observations: int
    emitted_signals: int
    promotion_ready: int
    incubations_written: int
    board_path: str
    brief_path: str
    health_path: str
    errors: tuple[str, ...] = ()


def run_world_radar_go_once(
    *,
    state_dir: Path | str | None = None,
    scout_fetch: bool = False,
    min_score: float = 0.45,
    timeout_s: int = 60,
) -> WorldRadarGoResult:
    """Run one world-radar pass and publish board, brief, health, and promotions."""
    started = time.monotonic()
    state = Path(state_dir).expanduser() if state_dir is not None else dharma_state_dir()
    meta = state / "meta"
    radar = meta / "world_radar"
    radar.mkdir(parents=True, exist_ok=True)
    lock_handle = _acquire_lock(radar / ".world_radar.lock")
    raw_path = radar / "raw_observations.jsonl"
    signal_path = meta / "world_signal_feed.jsonl"
    inbox_path = meta / "world_zeitgeist_inbox.jsonl"
    board_path = meta / "world_signal_board.json"
    brief_path = meta / "world_signal_brief.md"
    health_path = radar / "world_radar_health.json"
    health_md_path = radar / "world_radar_health.md"
    scout_health_path = radar / "world_scout_health.json"
    source_weights_path = radar / "source_weights.json"
    feedback_ledger_path = radar / "source_feedback_ledger.json"
    errors: list[str] = []

    source_weights = load_source_weights(source_weights_path)
    applied_feedback_ids = load_source_feedback_ledger(feedback_ledger_path)
    applied_before = len(applied_feedback_ids)
    opportunity_rows = _read_json(meta / "opportunity_board.json", default=[])
    if not isinstance(opportunity_rows, list):
        opportunity_rows = []
    source_weights = update_source_weights_from_opportunities(
        source_weights,
        opportunity_rows,
        applied_event_ids=applied_feedback_ids,
    )
    save_source_weights(source_weights_path, source_weights)
    if len(applied_feedback_ids) != applied_before:
        save_source_feedback_ledger(feedback_ledger_path, applied_feedback_ids)

    raw_rows = _collect_raw_rows(meta)
    successful_sources = 0
    failed_sources = 0
    if scout_fetch:
        scout_rows, scout_error, scout_counts = _run_go_scout(
            state=state,
            output_path=radar / "world_scout_observations.jsonl",
            health_path=scout_health_path,
            timeout_s=timeout_s,
        )
        raw_rows.extend(scout_rows)
        successful_sources += scout_counts.get("successful_sources", 0)
        failed_sources += scout_counts.get("failed_sources", 0)
        if scout_error:
            errors.append(scout_error)
    _write_jsonl(raw_path, raw_rows)

    ingested_rows, ingest_error = _run_go_ingestor(
        input_path=raw_path,
        output_path=signal_path,
        min_score=min_score,
        timeout_s=timeout_s,
    )
    if ingest_error:
        errors.append(ingest_error)
        ingested_rows = _read_jsonl(signal_path)

    board = build_world_signal_board(ingested_rows, source_weights=source_weights)
    if scout_fetch:
        cascade_rows, cascade_errors, cascade_counts = _run_cascade(
            state=state,
            movements=incubating_movements(board),
            output_dir=radar,
            timeout_s=timeout_s,
        )
        if cascade_rows:
            raw_rows.extend(cascade_rows)
            _write_jsonl(raw_path, raw_rows)
            ingested_rows, ingest_error = _run_go_ingestor(
                input_path=raw_path,
                output_path=signal_path,
                min_score=min_score,
                timeout_s=timeout_s,
            )
            if ingest_error:
                errors.append(ingest_error)
                ingested_rows = _read_jsonl(signal_path)
            board = build_world_signal_board(ingested_rows, source_weights=source_weights)
        errors.extend(cascade_errors)
        successful_sources += cascade_counts.get("successful_sources", 0)
        failed_sources += cascade_counts.get("failed_sources", 0)

    incubation_paths = write_rnd_artifacts(
        incubating_movements(board),
        output_dir=radar / "incubations",
    )
    _write_json_atomic(board_path, board)
    _write_text_atomic(brief_path, render_world_signal_brief(board))
    promotions = promotion_ready_signals(board)
    _write_jsonl(inbox_path, promotions)

    health = _build_health(
        previous=_read_json(health_path, default={}),
        ok=not errors,
        scout_fetch=scout_fetch,
        successful_sources=successful_sources,
        failed_sources=failed_sources,
        raw_count=len(raw_rows),
        signal_count=len(ingested_rows),
        promotion_count=len(promotions),
        incubation_count=len(incubation_paths),
        errors=errors,
        duration_s=round(time.monotonic() - started, 3),
        feedback_events_applied=len(applied_feedback_ids) - applied_before,
    )
    _write_json_atomic(health_path, health)
    _write_text_atomic(health_md_path, _render_health_markdown(health))
    _release_lock(lock_handle)

    return WorldRadarGoResult(
        ok=not errors,
        raw_observations=len(raw_rows),
        emitted_signals=len(ingested_rows),
        promotion_ready=len(promotions),
        incubations_written=len(incubation_paths),
        board_path=str(board_path),
        brief_path=str(brief_path),
        health_path=str(health_path),
        errors=tuple(errors),
    )


def _run_cascade(
    *,
    state: Path,
    movements: list[dict[str, Any]],
    output_dir: Path,
    timeout_s: int,
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    counts = {"successful_sources": 0, "failed_sources": 0}
    for movement in movements[:5]:
        movement_id = str(movement.get("movement_id") or "")
        queries = [str(q) for q in movement.get("cascade_queries", []) if str(q).strip()][:5]
        if not movement_id or not queries:
            continue
        out_path = output_dir / f"cascade_{movement_id}.jsonl"
        health_path = output_dir / f"cascade_{movement_id}.health.json"
        scout_rows, scout_error, scout_counts = _run_go_scout(
            state=state,
            output_path=out_path,
            health_path=health_path,
            timeout_s=timeout_s,
            queries=queries,
            cascade_for=movement_id,
        )
        rows.extend(scout_rows)
        counts["successful_sources"] += scout_counts.get("successful_sources", 0)
        counts["failed_sources"] += scout_counts.get("failed_sources", 0)
        if scout_error:
            errors.append(scout_error)
    return rows, errors, counts


def _collect_raw_rows(meta: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in (
        meta / "world_operator_drops.jsonl",
        meta / "world_scout_observations.jsonl",
        meta / "world_radar_observations.jsonl",
        meta / "world_radar" / "raw_observations.jsonl",
        meta / "world_radar" / "world_scout_observations.jsonl",
    ):
        rows.extend(_read_jsonl(path))
    feed_dir = meta / "world_feeds"
    if feed_dir.exists():
        for path in sorted(feed_dir.glob("*.jsonl")):
            rows.extend(_read_jsonl(path))
    return rows


def _run_go_scout(
    *,
    state: Path,
    output_path: Path,
    health_path: Path,
    timeout_s: int,
    queries: list[str] | None = None,
    cascade_for: str = "",
) -> tuple[list[dict[str, Any]], str | None, dict[str, int]]:
    module_dir = _repo_root() / "tools" / "world_scout_go"
    if not module_dir.exists():
        return [], f"missing Go scout module: {module_dir}", {}
    cmd = [
        "go",
        "run",
        ".",
        "--state-dir",
        str(state),
        "--output",
        str(output_path),
        "--health",
        str(health_path),
        "--fetch",
    ]
    if cascade_for:
        cmd.extend(["--cascade-for", cascade_for])
    for query in queries or []:
        cmd.extend(["--query", query])
    try:
        proc = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        return [], f"world_scout_go could not start: {exc}", {}
    except subprocess.TimeoutExpired:
        health = _read_json(health_path, default={})
        return [], f"world_scout_go timed out after {timeout_s}s", _source_counts(health)
    health = _read_json(health_path, default={})
    counts = _source_counts(health)
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or "world_scout_go failed").strip()[:1000], counts
    return _read_jsonl(output_path), _partial_source_error(health), counts


def _run_go_ingestor(
    *,
    input_path: Path,
    output_path: Path,
    min_score: float,
    timeout_s: int,
) -> tuple[list[dict[str, Any]], str | None]:
    module_dir = _repo_root() / "tools" / "world_signal_ingestor_go"
    if not module_dir.exists():
        return [], f"missing Go ingestor module: {module_dir}"
    cmd = [
        "go",
        "run",
        ".",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--min-score",
        str(min_score),
    ]
    try:
        proc = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        return [], f"world_signal_ingestor_go could not start: {exc}"
    except subprocess.TimeoutExpired:
        return [], f"world_signal_ingestor_go timed out after {timeout_s}s"
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or "world_signal_ingestor_go failed").strip()[:1000]
    return _read_jsonl(output_path), None


def _build_health(
    *,
    previous: Any,
    ok: bool,
    scout_fetch: bool,
    successful_sources: int,
    failed_sources: int,
    raw_count: int,
    signal_count: int,
    promotion_count: int,
    incubation_count: int,
    errors: list[str],
    duration_s: float,
    feedback_events_applied: int,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    previous = previous if isinstance(previous, dict) else {}
    checked_at = datetime.now(timezone.utc).isoformat()
    consecutive_failures = 0 if ok else int(float(previous.get("consecutive_failures", 0) or 0)) + 1
    last_successful_scan = (
        checked_at
        if ok and (successful_sources > 0 or not scout_fetch)
        else str(previous.get("last_successful_scan", ""))
    )
    return {
        "ok": ok,
        "status": "ok" if ok else "degraded",
        "checked_at": checked_at,
        "fetch_enabled": scout_fetch,
        "successful_sources": successful_sources,
        "failed_sources": failed_sources,
        "consecutive_failures": consecutive_failures,
        "last_successful_scan": last_successful_scan,
        "raw_observations": raw_count,
        "signals": signal_count,
        "promotion_ready": promotion_count,
        "incubations_written": incubation_count,
        "duration_s": duration_s,
        "feedback_events_applied": feedback_events_applied,
        "errors": errors[:10],
    }


def _render_health_markdown(health: dict[str, Any]) -> str:
    return (
        "# World Radar Health\n\n"
        f"- status: {health.get('status')}\n"
        f"- fetch_enabled: {health.get('fetch_enabled')}\n"
        f"- successful_sources: {health.get('successful_sources')}\n"
        f"- failed_sources: {health.get('failed_sources')}\n"
        f"- consecutive_failures: {health.get('consecutive_failures')}\n"
        f"- last_successful_scan: {health.get('last_successful_scan')}\n"
        f"- duration_s: {health.get('duration_s')}\n"
        f"- feedback_events_applied: {health.get('feedback_events_applied')}\n"
        f"- signals: {health.get('signals')}\n"
        f"- promotion_ready: {health.get('promotion_ready')}\n"
    )


def _source_counts(health: Any) -> dict[str, int]:
    if not isinstance(health, dict):
        return {"successful_sources": 0, "failed_sources": 0}
    return {
        "successful_sources": int(float(health.get("successful_sources", 0) or 0)),
        "failed_sources": int(float(health.get("failed_sources", 0) or 0)),
    }


def _partial_source_error(health: Any) -> str | None:
    if not isinstance(health, dict):
        return None
    failed = int(float(health.get("failed_sources", 0) or 0))
    if failed <= 0:
        return None
    errors = health.get("errors") if isinstance(health.get("errors"), list) else []
    detail = "; ".join(str(item) for item in errors[:3])
    if detail:
        return f"world_scout_go partial source failures={failed}: {detail}"[:1000]
    return f"world_scout_go partial source failures={failed}"


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8") or "null")
    except (OSError, json.JSONDecodeError):
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    lines: list[str] = []
    for row in rows:
        key = str(row.get("id") or row.get("url") or row.get("title") or json.dumps(row, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        lines.append(json.dumps(row, sort_keys=True))
    _write_text_atomic(path, ("\n".join(lines) + "\n") if lines else "")


def _write_json_atomic(path: Path, payload: Any) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _acquire_lock(path: Path) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _release_lock(handle: Any) -> None:
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
