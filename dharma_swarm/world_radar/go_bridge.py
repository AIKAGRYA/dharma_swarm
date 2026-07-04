"""Bridge Python runtime loops to the Go world scout and signal ingestor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess  # noqa: F401  (tests patch go_bridge.subprocess.run for the go_invoke layer)
import time
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.operator_core.world_radar.receipt_bridge import (
    receipt_paths,
    world_receipts_dir,
)
from dharma_swarm.operator_core.ingest_nats import publish_ingest_receipts_if_enabled
from dharma_swarm.world_radar.go_invoke import (  # noqa: F401  (re-exported; callers and tests patch these here)
    _go_invocation,
    _health_source_errors,
    _merged_source_errors,
    _partial_source_error,
    _run_go_ingestor,
    _run_go_scout,
    _source_counts,
)
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
from dharma_swarm.world_radar.io_utils import (
    acquire_lock as _acquire_lock,
    append_jsonl_once as _append_jsonl_once,
    file_size as _file_size,
    read_json as _read_json,
    read_jsonl as _read_jsonl,
    release_lock as _release_lock,
    utc_now_iso as _utc_now_iso,
    write_json_atomic as _write_json_atomic,
    write_jsonl as _write_jsonl,
    write_text_atomic as _write_text_atomic,
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
    ingest_run_id: str = ""
    ingest_summary_path: str = ""
    ingest_summary_ledger_path: str = ""
    ingest_cost_ledger_path: str = ""
    archive_enabled: bool = False
    archive_count: int = 0
    dedupe_count: int = 0
    archive_dir: str = ""
    archive_index_path: str = ""
    archive_replay_index_path: str = ""
    archive_manifest_path: str = ""
    archive_discovered_count: int = 0
    archive_workers: int = 0
    archive_total_bytes: int = 0
    archive_clean_text_count: int = 0
    archive_clean_text_bytes: int = 0
    archive_error_count: int = 0
    errors: tuple[str, ...] = ()
    source_errors: tuple[dict[str, str], ...] = ()
    scout_invocation_mode: str = ""
    ingestor_invocation_mode: str = ""



def run_world_radar_go_once(
    *,
    state_dir: Path | str | None = None,
    scout_fetch: bool = False,
    min_score: float = 0.45,
    timeout_s: int = 60,
    scout_archive: bool = False,
    scout_archive_dir: Path | str | None = None,
    scout_archive_urls: list[str] | None = None,
    scout_archive_url_files: list[str] | None = None,
    scout_archive_source_specs: list[str] | None = None,
    scout_archive_max_bytes: int = 2_000_000,
    scout_archive_max_pages: int = 100,
    scout_archive_max_depth: int = 0,
    scout_archive_same_domain: bool = True,
    scout_archive_rate_limit_ms: int = 100,
    scout_archive_robots: bool = True,
    scout_archive_default_crawl_delay_ms: int = 0,
    scout_archive_max_retries: int = 1,
    scout_archive_retry_base_delay_ms: int = 250,
    scout_archive_retry_max_delay_ms: int = 2000,
    scout_archive_max_fetch_duration_ms: int = 30000,
    scout_archive_include: list[str] | None = None,
    scout_archive_exclude: list[str] | None = None,
    scout_archive_workers: int = 6,
    scout_archive_discover_llms: bool = False,
    scout_archive_discover_sitemap: bool = False,
    scout_archive_sitemap_max_urls: int = 100,
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
    ingest_summary_path = radar / "ingest_run_summary.json"
    ingest_summary_ledger_path = radar / "ingest_run_summaries.jsonl"
    ingest_cost_ledger_path = radar / "ingest_cost_ledger.jsonl"
    scout_health_path = radar / "world_scout_health.json"
    source_weights_path = radar / "source_weights.json"
    feedback_ledger_path = radar / "source_feedback_ledger.json"
    receipt_dir = world_receipts_dir(state)
    receipt_correlation_id = f"world_radar_go_{time.time_ns()}"
    errors: list[str] = []
    source_errors: list[dict[str, str]] = []
    scout_invocation_mode = ""
    ingestor_invocation_mode = ""
    archive_enabled = False
    archive_count = 0
    dedupe_count = 0
    retry_count = 0
    archive_dir = ""
    archive_index_path = ""
    archive_replay_index_path = ""
    archive_manifest_path = ""
    archive_discovered_count = 0
    archive_workers = 0
    archive_total_bytes = 0
    archive_clean_text_count = 0
    archive_clean_text_bytes = 0
    archive_error_count = 0

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
            archive=scout_archive,
            archive_dir=Path(scout_archive_dir).expanduser() if scout_archive_dir else radar / "archive" / "world_scout",
            archive_urls=scout_archive_urls,
            archive_url_files=scout_archive_url_files,
            archive_source_specs=scout_archive_source_specs,
            archive_max_bytes=scout_archive_max_bytes,
            archive_max_pages=scout_archive_max_pages,
            archive_max_depth=scout_archive_max_depth,
            archive_same_domain=scout_archive_same_domain,
            archive_rate_limit_ms=scout_archive_rate_limit_ms,
            archive_robots=scout_archive_robots,
            archive_default_crawl_delay_ms=scout_archive_default_crawl_delay_ms,
            archive_max_retries=scout_archive_max_retries,
            archive_retry_base_delay_ms=scout_archive_retry_base_delay_ms,
            archive_retry_max_delay_ms=scout_archive_retry_max_delay_ms,
            archive_max_fetch_duration_ms=scout_archive_max_fetch_duration_ms,
            archive_include=scout_archive_include,
            archive_exclude=scout_archive_exclude,
            archive_workers=scout_archive_workers,
            archive_discover_llms=scout_archive_discover_llms,
            archive_discover_sitemap=scout_archive_discover_sitemap,
            archive_sitemap_max_urls=scout_archive_sitemap_max_urls,
        )
        raw_rows.extend(scout_rows)
        successful_sources += int(scout_counts.get("successful_sources", 0) or 0)
        failed_sources += int(scout_counts.get("failed_sources", 0) or 0)
        retry_count += int(scout_counts.get("retry_count", 0) or 0)
        archive_enabled = bool(scout_counts.get("archive_enabled", archive_enabled) or archive_enabled)
        archive_count += int(scout_counts.get("archive_count", 0) or 0)
        dedupe_count += int(scout_counts.get("dedupe_count", 0) or 0)
        archive_dir = str(scout_counts.get("archive_dir", "") or archive_dir)
        archive_index_path = str(scout_counts.get("archive_index_path", "") or archive_index_path)
        archive_replay_index_path = str(scout_counts.get("archive_replay_index_path", "") or archive_replay_index_path)
        archive_manifest_path = str(scout_counts.get("archive_manifest_path", "") or archive_manifest_path)
        archive_discovered_count += int(scout_counts.get("archive_discovered_count", 0) or 0)
        archive_workers = int(scout_counts.get("archive_workers", 0) or archive_workers)
        archive_total_bytes += int(scout_counts.get("archive_total_bytes", 0) or 0)
        archive_clean_text_count += int(scout_counts.get("archive_clean_text_count", 0) or 0)
        archive_clean_text_bytes += int(scout_counts.get("archive_clean_text_bytes", 0) or 0)
        archive_error_count += int(scout_counts.get("archive_error_count", 0) or 0)
        scout_invocation_mode = str(scout_counts.get("invocation_mode", "") or scout_invocation_mode)
        source_errors.extend(
            _merged_source_errors(scout_counts, scout_error, source="world_scout_go", stage="scout")
        )
        if scout_error:
            errors.append(scout_error)
        if archive_index_path:
            raw_rows.extend(_archive_index_to_raw_rows(Path(archive_index_path)))
    _write_jsonl(raw_path, raw_rows)

    ingested_rows, ingest_error, ingestor_invocation_mode = _run_go_ingestor(
        input_path=raw_path,
        output_path=signal_path,
        min_score=min_score,
        timeout_s=timeout_s,
        receipt_dir=receipt_dir,
        correlation_id=receipt_correlation_id,
    )
    if ingest_error:
        errors.append(ingest_error)
        source_errors.append(
            {"source": "world_signal_ingestor_go", "stage": "ingest", "error": ingest_error}
        )
        ingested_rows = _read_jsonl(signal_path)

    board = build_world_signal_board(ingested_rows, source_weights=source_weights)
    if scout_fetch:
        cascade_rows, cascade_errors, cascade_counts, cascade_source_errors = _run_cascade(
            state=state,
            movements=incubating_movements(board),
            output_dir=radar,
            timeout_s=timeout_s,
        )
        if cascade_rows:
            raw_rows.extend(cascade_rows)
            _write_jsonl(raw_path, raw_rows)
            ingested_rows, ingest_error, ingestor_invocation_mode = _run_go_ingestor(
                input_path=raw_path,
                output_path=signal_path,
                min_score=min_score,
                timeout_s=timeout_s,
                receipt_dir=receipt_dir,
                correlation_id=receipt_correlation_id,
            )
            if ingest_error:
                errors.append(ingest_error)
                source_errors.append(
                    {"source": "world_signal_ingestor_go", "stage": "ingest", "error": ingest_error}
                )
                ingested_rows = _read_jsonl(signal_path)
            board = build_world_signal_board(ingested_rows, source_weights=source_weights)
        errors.extend(cascade_errors)
        source_errors.extend(cascade_source_errors)
        successful_sources += cascade_counts.get("successful_sources", 0)
        failed_sources += cascade_counts.get("failed_sources", 0)
        retry_count += cascade_counts.get("retry_count", 0)

    incubation_paths = write_rnd_artifacts(
        incubating_movements(board),
        output_dir=radar / "incubations",
    )
    _write_json_atomic(board_path, board)
    _write_text_atomic(brief_path, render_world_signal_brief(board))
    promotions = promotion_ready_signals(board)
    _write_jsonl(inbox_path, promotions)

    duration_s = round(time.monotonic() - started, 3)
    ingest_summary = _build_ingest_summary(
        run_id=receipt_correlation_id,
        state=state,
        raw_rows=raw_rows,
        ingested_rows=ingested_rows,
        raw_path=raw_path,
        signal_path=signal_path,
        board_path=board_path,
        brief_path=brief_path,
        health_path=health_path,
        inbox_path=inbox_path,
        receipt_dir=receipt_dir,
        summary_path=ingest_summary_path,
        cost_ledger_path=ingest_cost_ledger_path,
        duration_s=duration_s,
        successful_sources=successful_sources,
        failed_sources=failed_sources,
        retry_count=retry_count,
        promotion_count=len(promotions),
        incubation_count=len(incubation_paths),
        archive_enabled=archive_enabled,
        archive_count=archive_count,
        archive_total_bytes=archive_total_bytes,
        archive_error_count=archive_error_count,
        errors=errors,
    )
    cost_event_recorded = _record_ingest_cost_event(ingest_cost_ledger_path, ingest_summary)
    nats_receipt_transport = publish_ingest_receipts_if_enabled(receipt_dir, receipt_correlation_id)
    ingest_summary["nats_receipt_transport"] = nats_receipt_transport
    _write_json_atomic(ingest_summary_path, ingest_summary)
    _append_jsonl_once(ingest_summary_ledger_path, ingest_summary, key_field="run_id")

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
        source_errors=source_errors,
        duration_s=duration_s,
        retry_count=retry_count,
        feedback_events_applied=len(applied_feedback_ids) - applied_before,
        archive_enabled=archive_enabled,
        archive_count=archive_count,
        dedupe_count=dedupe_count,
        archive_dir=archive_dir,
        archive_index_path=archive_index_path,
        archive_replay_index_path=archive_replay_index_path,
        archive_manifest_path=archive_manifest_path,
        archive_discovered_count=archive_discovered_count,
        archive_workers=archive_workers,
        archive_total_bytes=archive_total_bytes,
        archive_clean_text_count=archive_clean_text_count,
        archive_clean_text_bytes=archive_clean_text_bytes,
        archive_error_count=archive_error_count,
    )
    health.update(
        {
            "ingest_run_id": receipt_correlation_id,
            "ingest_summary_path": str(ingest_summary_path),
            "ingest_summary_ledger_path": str(ingest_summary_ledger_path),
            "ingest_cost_ledger_path": str(ingest_cost_ledger_path),
            "receipt_dir": str(receipt_dir),
            "accepted_count": ingest_summary["accepted_count"],
            "rejected_count": ingest_summary["rejected_count"],
            "freshest_receipt": ingest_summary["freshest_receipt"],
            "cost_event_recorded": cost_event_recorded,
            "nats_receipt_transport": nats_receipt_transport,
            "scout_invocation_mode": scout_invocation_mode,
            "ingestor_invocation_mode": ingestor_invocation_mode,
        }
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
        ingest_run_id=receipt_correlation_id,
        ingest_summary_path=str(ingest_summary_path),
        ingest_summary_ledger_path=str(ingest_summary_ledger_path),
        ingest_cost_ledger_path=str(ingest_cost_ledger_path),
        archive_enabled=archive_enabled,
        archive_count=archive_count,
        dedupe_count=dedupe_count,
        archive_dir=archive_dir,
        archive_index_path=archive_index_path,
        archive_replay_index_path=archive_replay_index_path,
        archive_manifest_path=archive_manifest_path,
        archive_discovered_count=archive_discovered_count,
        archive_workers=archive_workers,
        archive_total_bytes=archive_total_bytes,
        archive_clean_text_count=archive_clean_text_count,
        archive_clean_text_bytes=archive_clean_text_bytes,
        archive_error_count=archive_error_count,
        errors=tuple(errors),
        source_errors=tuple(source_errors),
        scout_invocation_mode=scout_invocation_mode,
        ingestor_invocation_mode=ingestor_invocation_mode,
    )


def _run_cascade(
    *,
    state: Path,
    movements: list[dict[str, Any]],
    output_dir: Path,
    timeout_s: int,
) -> tuple[list[dict[str, Any]], list[str], dict[str, int], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    source_errors: list[dict[str, str]] = []
    counts = {"successful_sources": 0, "failed_sources": 0, "retry_count": 0}
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
        counts["successful_sources"] += int(scout_counts.get("successful_sources", 0) or 0)
        counts["failed_sources"] += int(scout_counts.get("failed_sources", 0) or 0)
        counts["retry_count"] += int(scout_counts.get("retry_count", 0) or 0)
        source_errors.extend(
            _merged_source_errors(
                scout_counts, scout_error, source="world_scout_go", stage=f"cascade:{movement_id}"
            )
        )
        if scout_error:
            errors.append(scout_error)
    return rows, errors, counts, source_errors


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


def _archive_index_to_raw_rows(index_path: Path, *, max_rows: int = 200) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in _read_jsonl(index_path)[:max_rows]:
        if not isinstance(entry, dict):
            continue
        if entry.get("dedupe_of"):
            continue
        if str(entry.get("capture_status") or "") not in {"captured", "truncated"}:
            continue
        url = str(entry.get("final_canonical_url") or entry.get("canonical_url") or entry.get("url") or "")
        if not url:
            continue
        text = _archive_clean_text(entry)
        title = str(entry.get("title") or "").strip() or f"Go archive capture: {url}"
        summary = text[:900] if text else f"Archived public evidence capture from {url}"
        content_hash = str(entry.get("content_hash") or "")
        row_id = "go-archive-" + content_hash.replace("sha256:", "")[:24] if content_hash else f"go-archive-{len(rows)}"
        rows.append(
            {
                "id": row_id,
                "source": "go_archive",
                "source_type": str(entry.get("source_kind") or "public_archive"),
                "category": "public_evidence",
                "title": title,
                "description": summary,
                "relevance_score": 0.5,
                "keywords": ["go_archive", "public_evidence", str(entry.get("source_kind") or "")],
                "url": url,
                "metadata": {
                    "trust_state": "untrusted_capture",
                    "authority": "evidence_only",
                    "source_spec_id": entry.get("source_spec_id"),
                    "run_id": entry.get("run_id"),
                    "content_hash": content_hash,
                    "body_path": entry.get("body_path"),
                    "receipt_path": entry.get("receipt_path"),
                    "clean_text_path": entry.get("clean_text_path"),
                    "content_object_path": entry.get("content_object_path"),
                    "capture_status": entry.get("capture_status"),
                    "robots_decision": entry.get("robots_decision"),
                    "no_external_action": True,
                },
            }
        )
    return rows


def _archive_clean_text(entry: dict[str, Any], *, max_chars: int = 4000) -> str:
    for key in ("clean_text_path", "body_path"):
        path_text = str(entry.get(key) or "").strip()
        if not path_text:
            continue
        path = Path(path_text).expanduser()
        if not path.exists() or not path.is_file():
            continue
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    return ""



def _build_ingest_summary(
    *,
    run_id: str,
    state: Path,
    raw_rows: list[dict[str, Any]],
    ingested_rows: list[dict[str, Any]],
    raw_path: Path,
    signal_path: Path,
    board_path: Path,
    brief_path: Path,
    health_path: Path,
    inbox_path: Path,
    receipt_dir: Path,
    summary_path: Path,
    cost_ledger_path: Path,
    duration_s: float,
    successful_sources: int,
    failed_sources: int,
    retry_count: int,
    promotion_count: int,
    incubation_count: int,
    archive_enabled: bool,
    archive_count: int,
    archive_total_bytes: int,
    archive_error_count: int,
    errors: list[str],
) -> dict[str, Any]:
    receipt_summary = _receipt_summary_for_correlation(receipt_dir, run_id)
    receipt_count = int(receipt_summary["receipt_count"])
    accepted_receipts = int(receipt_summary["accepted_receipts"])
    rejected_receipts = int(receipt_summary["rejected_receipts"])
    accepted_count = accepted_receipts if receipt_count else len(ingested_rows)
    rejected_count = rejected_receipts
    source_count = _count_summary_sources(raw_rows, successful_sources, failed_sources)
    input_bytes = _file_size(raw_path)
    output_bytes = _file_size(signal_path)
    receipt_bytes = int(receipt_summary["receipt_bytes"])
    byte_count = input_bytes + output_bytes + receipt_bytes + int(archive_total_bytes)
    provisional_compute_units = max(
        1,
        len(raw_rows)
        + len(ingested_rows)
        + accepted_count
        + rejected_count
        + retry_count
        + archive_count,
    )
    return {
        "schema_version": "world_radar_go_ingest_summary.v1",
        "run_id": run_id,
        "correlation_id": run_id,
        "generated_at": _utc_now_iso(),
        "state_dir": str(state),
        "duration_s": duration_s,
        "source_count": source_count,
        "successful_sources": successful_sources,
        "failed_sources": failed_sources,
        "raw_count": len(raw_rows),
        "signal_count": len(ingested_rows),
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "retry_count": retry_count,
        "byte_count": byte_count,
        "input_bytes": input_bytes,
        "output_bytes": output_bytes,
        "receipt_bytes": receipt_bytes,
        "archive_enabled": archive_enabled,
        "archive_count": archive_count,
        "archive_total_bytes": archive_total_bytes,
        "archive_error_count": archive_error_count,
        "promotion_ready": promotion_count,
        "incubations_written": incubation_count,
        "error_samples": errors[:10],
        "receipt_dir": str(receipt_dir),
        "receipt_count": receipt_count,
        "accepted_receipts": accepted_receipts,
        "rejected_receipts": rejected_receipts,
        "freshest_receipt": receipt_summary["freshest_receipt"],
        "freshest_receipt_observed_at": receipt_summary["freshest_receipt_observed_at"],
        "receipt_ids": receipt_summary["receipt_ids"],
        "raw_path": str(raw_path),
        "signal_path": str(signal_path),
        "board_path": str(board_path),
        "brief_path": str(brief_path),
        "health_path": str(health_path),
        "inbox_path": str(inbox_path),
        "summary_path": str(summary_path),
        "cost_ledger_path": str(cost_ledger_path),
        "provisional_compute_units": provisional_compute_units,
        "cost_model": "neutral_compute_unit_v0_no_usd",
    }


def _receipt_summary_for_correlation(receipt_dir: Path, correlation_id: str) -> dict[str, Any]:
    accepted = 0
    rejected = 0
    total = 0
    receipt_bytes = 0
    receipt_ids: list[str] = []
    freshest_observed_at = ""
    freshest_receipt: dict[str, str] = {}
    for path in receipt_paths(receipt_dir):
        receipt = _read_json(path, default={})
        if not isinstance(receipt, dict):
            continue
        if str(receipt.get("correlation_id") or "") != correlation_id:
            continue
        total += 1
        receipt_bytes += _file_size(path)
        status = str(receipt.get("status") or "").strip().lower()
        if status == "accepted":
            accepted += 1
        elif status == "rejected":
            rejected += 1
        receipt_id = str(receipt.get("receipt_id") or path.stem)
        if receipt_id:
            receipt_ids.append(receipt_id)
        observed_at = str(receipt.get("observed_at") or "")
        if observed_at and observed_at >= freshest_observed_at:
            freshest_observed_at = observed_at
            freshest_receipt = {
                "receipt_id": receipt_id,
                "observed_at": observed_at,
                "path": str(path),
            }
    return {
        "receipt_count": total,
        "accepted_receipts": accepted,
        "rejected_receipts": rejected,
        "receipt_bytes": receipt_bytes,
        "freshest_receipt_observed_at": freshest_observed_at,
        "freshest_receipt": freshest_receipt,
        "receipt_ids": sorted(receipt_ids)[:100],
    }


def _count_summary_sources(raw_rows: list[dict[str, Any]], successful_sources: int, failed_sources: int) -> int:
    measured = successful_sources + failed_sources
    sources = {
        str(row.get("raw_source") or row.get("source") or "").strip()
        for row in raw_rows
        if str(row.get("raw_source") or row.get("source") or "").strip()
    }
    return max(measured, len(sources))


def _record_ingest_cost_event(path: Path, summary: dict[str, Any]) -> bool:
    run_id = str(summary.get("run_id") or "")
    if not run_id:
        raise ValueError("ingest summary missing run_id")
    event = {
        "schema_version": "world_radar_ingest_cost_event.v1",
        "event_id": f"world_radar_ingest_cost:{run_id}",
        "idempotency_key": run_id,
        "recorded_at": _utc_now_iso(),
        "run_id": run_id,
        "correlation_id": str(summary.get("correlation_id") or run_id),
        "agent_id": "world_radar_go_bridge",
        "event_type": "ingest_compute_cost",
        "amount": int(summary.get("provisional_compute_units", 0) or 0),
        "unit": "neutral_compute_unit",
        "pricing_model": "neutral_compute_unit_v0_no_usd",
        "cost_usd": 0.0,
        "token_count": 0,
        "source_count": int(summary.get("source_count", 0) or 0),
        "raw_count": int(summary.get("raw_count", 0) or 0),
        "signal_count": int(summary.get("signal_count", 0) or 0),
        "accepted_count": int(summary.get("accepted_count", 0) or 0),
        "rejected_count": int(summary.get("rejected_count", 0) or 0),
        "retry_count": int(summary.get("retry_count", 0) or 0),
        "byte_count": int(summary.get("byte_count", 0) or 0),
        "receipt_dir": str(summary.get("receipt_dir") or ""),
        "summary_path": str(summary.get("summary_path") or ""),
    }
    return _append_jsonl_once(path, event, key_field="event_id")


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
    source_errors: list[dict[str, str]] | None = None,
    duration_s: float,
    retry_count: int,
    feedback_events_applied: int,
    archive_enabled: bool = False,
    archive_count: int = 0,
    dedupe_count: int = 0,
    archive_dir: str = "",
    archive_index_path: str = "",
    archive_replay_index_path: str = "",
    archive_manifest_path: str = "",
    archive_discovered_count: int = 0,
    archive_workers: int = 0,
    archive_total_bytes: int = 0,
    archive_clean_text_count: int = 0,
    archive_clean_text_bytes: int = 0,
    archive_error_count: int = 0,
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
        "retry_count": retry_count,
        "feedback_events_applied": feedback_events_applied,
        "archive_enabled": archive_enabled,
        "archive_count": archive_count,
        "dedupe_count": dedupe_count,
        "archive_dir": archive_dir,
        "archive_index_path": archive_index_path,
        "archive_replay_index_path": archive_replay_index_path,
        "archive_manifest_path": archive_manifest_path,
        "archive_discovered_count": archive_discovered_count,
        "archive_workers": archive_workers,
        "archive_total_bytes": archive_total_bytes,
        "archive_clean_text_count": archive_clean_text_count,
        "archive_clean_text_bytes": archive_clean_text_bytes,
        "archive_error_count": archive_error_count,
        "errors": errors[:10],
        "source_errors": list(source_errors or [])[:20],
    }


def _render_health_markdown(health: dict[str, Any]) -> str:
    source_errors = health.get("source_errors") if isinstance(health.get("source_errors"), list) else []
    source_error_lines = "".join(
        f"  - [{entry.get('stage', '')}] {entry.get('source', '')}: {entry.get('error', '')}\n"
        for entry in source_errors
        if isinstance(entry, dict)
    )
    return (
        "# World Radar Health\n\n"
        f"- status: {health.get('status')}\n"
        f"- ingest_run_id: {health.get('ingest_run_id', '')}\n"
        f"- scout_invocation_mode: {health.get('scout_invocation_mode', '')}\n"
        f"- ingestor_invocation_mode: {health.get('ingestor_invocation_mode', '')}\n"
        f"- fetch_enabled: {health.get('fetch_enabled')}\n"
        f"- successful_sources: {health.get('successful_sources')}\n"
        f"- failed_sources: {health.get('failed_sources')}\n"
        f"- consecutive_failures: {health.get('consecutive_failures')}\n"
        f"- last_successful_scan: {health.get('last_successful_scan')}\n"
        f"- duration_s: {health.get('duration_s')}\n"
        f"- retry_count: {health.get('retry_count', 0)}\n"
        f"- accepted_count: {health.get('accepted_count', 0)}\n"
        f"- rejected_count: {health.get('rejected_count', 0)}\n"
        f"- ingest_summary_path: {health.get('ingest_summary_path', '')}\n"
        f"- ingest_cost_ledger_path: {health.get('ingest_cost_ledger_path', '')}\n"
        f"- feedback_events_applied: {health.get('feedback_events_applied')}\n"
        f"- archive_enabled: {health.get('archive_enabled', False)}\n"
        f"- archive_count: {health.get('archive_count', 0)}\n"
        f"- archive_index_path: {health.get('archive_index_path', '')}\n"
        f"- archive_replay_index_path: {health.get('archive_replay_index_path', '')}\n"
        f"- archive_discovered_count: {health.get('archive_discovered_count', 0)}\n"
        f"- archive_total_bytes: {health.get('archive_total_bytes', 0)}\n"
        f"- archive_clean_text_count: {health.get('archive_clean_text_count', 0)}\n"
        f"- archive_error_count: {health.get('archive_error_count', 0)}\n"
        f"- signals: {health.get('signals')}\n"
        f"- promotion_ready: {health.get('promotion_ready')}\n"
        f"- source_errors: {len(source_errors)}\n"
        f"{source_error_lines}"
    )
