#!/usr/bin/env python3
"""orientation_graph.py — one-command, whole-system orientation view.

Renders the organism AT ONCE — identity (why), organs, active tracks,
canon custody, liveness, and broken register — as one typed, queryable
packet. A fresh agent should be able to answer "what is this system,
what lives inside it, what is live, what is broken, and what is canon"
from this single command.

This command does NOT own any fact. It projects from the existing owners:

    identity   -> foundations/THE_ORGANISM.md + docs/vision_maps/NORTH_STAR.md
    organs     -> docs/governance/VENTURE_CELL_PORTFOLIO.yaml
    tracks     -> docs/governance/ACTIVE_TRACK.yaml
    custody    -> docs/docops/assertions.yaml (canonical_guard.registered) + git
    liveness   -> live ops census receipt (scripts/runtime/live_ops_census.py)
    broken     -> docs/state/BROKEN_REGISTER.md

Doctrine line that must hold (same as the reconciliation track's):
    Read models project truth from owners; they do not become authority.

Usage:
    python3 scripts/governance/orientation_graph.py          # human view
    python3 scripts/governance/orientation_graph.py --json   # machine packet
    make orient

Write behavior: never writes. Exit code: always 0 (informational).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(GOVERNANCE_DIR) not in sys.path:
    sys.path.insert(0, str(GOVERNANCE_DIR))
from dharma_swarm.operator_core.live_ops_census_contract import (
    census_payload_freshness,
    default_output_path,
    validate_census_payload,
)
from check_track_status import readiness_score_cap

ORGANISM_DOC = REPO_ROOT / "foundations/THE_ORGANISM.md"
NORTH_STAR_DOC = REPO_ROOT / "docs/vision_maps/NORTH_STAR.md"
GENOME_SYNTHESIS = REPO_ROOT / "reports/swarm_genome/2026-06-11/SYNTHESIS.md"
PORTFOLIO = REPO_ROOT / "docs/governance/VENTURE_CELL_PORTFOLIO.yaml"
ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
ASSERTIONS = REPO_ROOT / "docs/docops/assertions.yaml"
BROKEN_REGISTER = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"


def _census_receipt_path() -> Path | None:
    """Receipt path declared by the live-ops census contract.

    State-dir knowledge stays in the contract; this view only asks for the
    configured output path, which honors DHARMA_STATE_DIR.
    """
    try:
        return Path(default_output_path())
    except Exception:
        return None


@dataclass
class Identity:
    one_line: str
    read_first: list[str]
    missing_sources: list[str] = field(default_factory=list)


@dataclass
class Organ:
    id: str
    instrument: str
    status: str
    external_name: str = ""


@dataclass
class Track:
    id: str
    status: str
    serves: str
    owner: str
    readiness: str = ""
    owned_surfaces: list[str] = field(default_factory=list)


@dataclass
class CustodyReport:
    registered_total: int
    present: int
    missing: list[str] = field(default_factory=list)


@dataclass
class Liveness:
    receipt: str
    generated_at: str = ""
    surfaces: list[dict[str, Any]] = field(default_factory=list)
    daemon_dispatch_launch: str = ""
    daemon_dispatch_running: str = ""
    daemon_receipt_head: str = ""
    daemon_provider_model_coverage: str = ""
    ds_goal_wrapper_contract: str = ""


@dataclass
class Loop1Closure:
    live: bool
    provider: str = ""
    model: str = ""
    started_at: str = ""
    detail: str = ""


@dataclass
class BrokenItem:
    id: str
    status: str
    title: str


@dataclass
class OrientationPacket:
    identity: Identity
    organs: list[Organ]
    tracks: list[Track]
    custody: CustodyReport
    liveness: Liveness
    loop1: Loop1Closure
    broken: list[BrokenItem]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def build_identity() -> Identity:
    read_first = [
        "foundations/THE_ORGANISM.md",
        "docs/vision_maps/NORTH_STAR.md",
        "reports/swarm_genome/2026-06-11/SYNTHESIS.md",
        "docs/MEGAFILE_INDEX.md",
    ]
    missing = [p for p in read_first if not (REPO_ROOT / p).exists()]
    one_line = ""
    if ORGANISM_DOC.exists():
        for line in ORGANISM_DOC.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("> **dharma_swarm is"):
                one_line = stripped.lstrip("> ").strip().strip("*")
                break
    if not one_line:
        one_line = ("(identity owner missing — read docs/vision_maps/"
                    "NORTH_STAR.md §1 for the telos)")
    return Identity(one_line=one_line, read_first=read_first,
                    missing_sources=missing)


def build_organs() -> list[Organ]:
    data = _load_yaml(PORTFOLIO)
    organs: list[Organ] = []
    for cell in data.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        organs.append(Organ(
            id=str(cell.get("id", "")),
            instrument=str(cell.get("instrument", "")),
            status=str(cell.get("status", "")),
            external_name=str(cell.get("external_name", "") or ""),
        ))
    return organs


def _format_track_readiness(entry: dict[str, Any]) -> str:
    baseline = entry.get("readiness_baseline")
    hardening = entry.get("hardening_status")
    if not isinstance(baseline, dict) and not isinstance(hardening, dict):
        return ""
    baseline = baseline if isinstance(baseline, dict) else {}
    hardening = hardening if isinstance(hardening, dict) else {}
    bits: list[str] = []
    if baseline:
        bits.append(f"baseline={baseline.get('score')}/{baseline.get('scale', 100)}")
    if hardening:
        bits.append(f"current={hardening.get('current_score')}/{hardening.get('scale', 100)}")
        cap = readiness_score_cap(entry)
        if cap:
            cap_text = f"cap={cap.get('cap_score')}/{cap.get('scale', 100)}"
            if not cap.get("within_cap"):
                cap_text += " OVER_CAP"
            bits.append(cap_text)
            errors = cap.get("errors") or []
            if errors:
                bits.append("cap_errors=" + ",".join(str(error) for error in errors))
        evidence_ref = hardening.get("evidence_ref")
        if evidence_ref:
            bits.append(f"evidence={evidence_ref}")
    rejected = baseline.get("claim_rejected")
    if rejected:
        bits.append(f"rejected={rejected}")
    return "; ".join(bits)


def build_tracks() -> list[Track]:
    data = _load_yaml(ACTIVE_TRACK)
    tracks: list[Track] = []
    for entry in data.get("active_tracks") or []:
        if not isinstance(entry, dict):
            continue
        tracks.append(Track(
            id=str(entry.get("id", "")),
            status=str(entry.get("status", "")),
            serves=str(entry.get("serves", "")),
            owner=str(entry.get("owner", "")),
            readiness=_format_track_readiness(entry),
            owned_surfaces=[str(s) for s in entry.get("owned_surfaces") or []],
        ))
    return tracks


def build_custody() -> CustodyReport:
    registered: list[str] = []
    try:
        data = json.loads(ASSERTIONS.read_text(encoding="utf-8"))
        guard = data.get("canonical_guard", {})
        registered = [str(p) for p in guard.get("registered") or []]
    except Exception:
        data = _load_yaml(ASSERTIONS)
        guard = data.get("canonical_guard", {}) if isinstance(data, dict) else {}
        registered = [str(p) for p in guard.get("registered") or []]
    missing = [p for p in registered if not (REPO_ROOT / p).exists()]
    return CustodyReport(
        registered_total=len(registered),
        present=len(registered) - len(missing),
        missing=missing,
    )


_DAEMON_SPINE_RUNTIME_PROOFS = {
    "spine_enabled_self_report",
    "daemon_default_receipt_proven",
    "daemon_default_spine_receipt_proven",
}


def _surface_proof_gaps(surface: dict[str, Any]) -> list[str]:
    proof_gaps = surface.get("proof_gaps")
    if isinstance(proof_gaps, list):
        return [str(item) for item in proof_gaps if item]
    surface_id = str(surface.get("surface_id") or surface.get("id") or "")
    status = str(surface.get("status") or "")
    raw = surface.get("raw") if isinstance(surface.get("raw"), dict) else {}
    gaps: list[str] = []
    if surface_id == "substrate.dharma_daemon" and status == "live":
        dispatch_launch = raw.get("dispatch_launch")
        launch_state = (
            str(dispatch_launch.get("state") or "")
            if isinstance(dispatch_launch, dict)
            else ""
        )
        if launch_state != "spine_enabled_launch_spec":
            gaps.append("daemon_launch_not_spine_enabled")
        running_proof = str(raw.get("running_dispatch_proof") or "")
        if running_proof not in _DAEMON_SPINE_RUNTIME_PROOFS:
            gaps.append("daemon_dispatch_runtime_unproven")
        receipt_head = (
            raw.get("runtime_receipt_active_head")
            if isinstance(raw.get("runtime_receipt_active_head"), dict)
            else {}
        )
        if receipt_head:
            dirty = (
                receipt_head.get("active_head_side_effect_key_clean") is False
                and any(
                    int(row.get("total", 0)) > 0
                    and int(row.get("missing_side_effect_key", 0)) > 0
                    for row in receipt_head.get("windows", [])
                    if isinstance(row, dict)
                )
            )
            if dirty:
                gaps.append("daemon_runtime_receipts_active_head_dirty")
            if (
                receipt_head.get("latest_fresh") is False
                and int(receipt_head.get("runtime_receipts_total") or 0) > 0
            ):
                gaps.append("daemon_runtime_receipts_stale")
    if surface_id == "dashboard.local" and status == "live":
        dashboard_probe = raw.get("control_surface_rows_probe")
        probe_state = (
            str(dashboard_probe.get("state") or "")
            if isinstance(dashboard_probe, dict)
            else ""
        )
        if probe_state and probe_state not in {"ok", "not_checked"}:
            gaps.append("dashboard_control_surface_rows_unproven")
    return gaps


def _runtime_receipt_head_line(head: dict[str, Any]) -> str:
    if not head:
        return ""
    clean = head.get("active_head_side_effect_key_clean")
    clean_text = "unknown" if clean is None else str(bool(clean)).lower()
    fresh = head.get("latest_fresh")
    fresh_text = "unknown" if fresh is None else str(bool(fresh)).lower()
    age = head.get("latest_age_hours")
    age_text = "unknown" if age is None else str(age)
    max_age = head.get("latest_max_age_hours")
    max_age_text = "unknown" if max_age is None else str(max_age)
    latest = str(head.get("latest_created_at") or "unknown")
    total = str(head.get("runtime_receipts_total") or 0)
    window_parts: list[str] = []
    for row in head.get("windows") or []:
        if not isinstance(row, dict):
            continue
        window_parts.append(
            f"{row.get('window_minutes')}m:"
            f"{row.get('missing_side_effect_key')}/{row.get('total')}"
        )
    windows = ",".join(window_parts) if window_parts else "none"
    return (
        f"clean={clean_text}; fresh={fresh_text}; "
        f"age_hours={age_text}; max_age_hours={max_age_text}; "
        f"total={total}; latest={latest}; windows={windows}"
    )


def _field_gap_summary_text(coverage: dict[str, Any]) -> str:
    summary = coverage.get("field_gap_summary")
    if not isinstance(summary, dict):
        return ""
    total = int(summary.get("total_missing") or 0)
    if total <= 0:
        return ""
    freshness = summary.get("by_freshness_class")
    freshness_counts = freshness if isinstance(freshness, dict) else {}
    parts = [f"total:{total}"]
    for key in ("active_head_60m", "recent_historical_24h", "older_historical"):
        count = int(freshness_counts.get(key) or 0)
        if count > 0:
            parts.append(f"{key}:{count}")
    quarantine_count = int(summary.get("quarantine_candidate_missing") or 0)
    if quarantine_count > 0:
        parts.append(f"quarantine_candidate:{quarantine_count}")
    return "; field_gap_summary=" + "|".join(parts)


def _field_gap_actions_text(coverage: dict[str, Any]) -> str:
    queue = [
        item
        for item in coverage.get("field_gap_action_queue") or []
        if isinstance(item, dict)
    ]
    if not queue:
        return ""
    parts = []
    for item in queue[:7]:
        label = item.get("short_label") or item.get("action") or "unknown"
        parts.append(f"{label}:{int(item.get('missing') or 0)}")
    return "; field_gap_actions=" + "|".join(parts)


def _compact_fresh_proof_status(status: Any) -> str:
    status_text = str(status or "")
    statuses = {
        "fresh_scoped_proof_recorded": "fresh",
        "pin_mitigation_proof_recorded_default_still_broken": (
            "pin_proved_default_dirty"
        ),
        "candidate_policy_recorded_not_applied": "policy_candidate",
        "fresh_proof_not_recorded": "missing",
    }
    return statuses.get(status_text, status_text)


def _field_gap_proofs_text(coverage: dict[str, Any]) -> str:
    queue = [
        item
        for item in coverage.get("field_gap_action_queue") or []
        if isinstance(item, dict)
    ]
    if not queue:
        return ""
    parts = []
    for item in queue[:7]:
        fresh_proof = (
            item.get("fresh_proof")
            if isinstance(item.get("fresh_proof"), dict)
            else {}
        )
        status = _compact_fresh_proof_status(fresh_proof.get("status"))
        if not status:
            continue
        label = item.get("short_label") or item.get("action") or "unknown"
        parts.append(f"{label}:{status}")
    if not parts:
        return ""
    return "; field_gap_proofs=" + "|".join(parts)


def _gate_70_to_75_text(coverage: dict[str, Any]) -> str:
    components = [
        item
        for item in coverage.get("gate_70_to_75_components") or []
        if isinstance(item, dict)
    ]
    if not components:
        return ""
    parts = []
    for item in components[:5]:
        label = item.get("short_label") or item.get("id") or "unknown"
        status = item.get("status")
        if not status:
            status = "pass" if item.get("passed") else "fail"
        parts.append(f"{label}:{status}")
    return "; gate_70_75=" + "|".join(parts)


def _provider_model_coverage_line(coverage: dict[str, Any]) -> str:
    if not coverage:
        return ""
    latest_sample = str(coverage.get("latest_sample_size") or 0)
    provider_model = str(coverage.get("latest_with_provider_model_payload") or 0)
    provider_model_proof = str(coverage.get("latest_with_provider_model_provenance") or 0)
    provider_model_accounted = str(
        coverage.get("latest_with_provider_model_accounted") or 0
    )
    terminal_sample = str(coverage.get("latest_terminal_sample_size") or 0)
    terminal_provider_model = str(
        coverage.get("latest_terminal_with_provider_model_payload") or 0
    )
    terminal_provider_model_proof = str(
        coverage.get("latest_terminal_with_provider_model_provenance") or 0
    )
    terminal_provider_model_accounted = str(
        coverage.get("latest_terminal_with_provider_model_accounted") or 0
    )
    pending = str(coverage.get("latest_provider_model_pending_execution") or 0)
    percent = coverage.get("latest_major_task_receipts_provider_model_percent")
    percent_text = "unknown" if percent is None else str(percent)
    proof_percent = coverage.get(
        "latest_major_task_receipts_provider_model_provenance_percent"
    )
    proof_percent_text = "unknown" if proof_percent is None else str(proof_percent)
    terminal_percent = coverage.get(
        "latest_terminal_major_task_receipts_provider_model_percent"
    )
    terminal_percent_text = "unknown" if terminal_percent is None else str(terminal_percent)
    terminal_proof_percent = coverage.get(
        "latest_terminal_major_task_receipts_provider_model_provenance_percent"
    )
    terminal_proof_percent_text = (
        "unknown" if terminal_proof_percent is None else str(terminal_proof_percent)
    )
    accounted_percent = coverage.get(
        "latest_major_task_receipts_provider_model_accounted_percent"
    )
    accounted_percent_text = (
        "unknown" if accounted_percent is None else str(accounted_percent)
    )
    terminal_accounted_percent = coverage.get(
        "latest_terminal_major_task_receipts_provider_model_accounted_percent"
    )
    terminal_accounted_percent_text = (
        "unknown"
        if terminal_accounted_percent is None
        else str(terminal_accounted_percent)
    )
    complete = coverage.get("provider_model_latest_complete")
    complete_text = "unknown" if complete is None else str(bool(complete)).lower()
    field_gap_groups = [
        group
        for group in coverage.get("field_gap_producer_groups") or []
        if isinstance(group, dict)
    ]
    field_gap_text = ""
    if field_gap_groups:
        parts = []
        for group in field_gap_groups[:3]:
            freshness = group.get("freshness_class") or "unknown"
            parts.append(
                f"{group.get('gap_type')}/"
                f"{group.get('receipt_type')}/"
                f"{group.get('producer_source')}/"
                f"{group.get('producer_failure_code')}"
                f"={group.get('missing')}@{freshness}"
            )
        field_gap_text = "; field_gap_producers=" + "|".join(parts)
    return (
        f"latest={provider_model}/{latest_sample}; "
        f"percent={percent_text}; proof={provider_model_proof}/{latest_sample}; "
        f"proof_percent={proof_percent_text}; accounted={provider_model_accounted}/"
        f"{latest_sample}; accounted_percent={accounted_percent_text}; "
        f"terminal={terminal_provider_model}/"
        f"{terminal_sample}; terminal_percent={terminal_percent_text}; "
        f"terminal_proof={terminal_provider_model_proof}/{terminal_sample}; "
        f"terminal_proof_percent={terminal_proof_percent_text}; "
        f"terminal_accounted={terminal_provider_model_accounted}/{terminal_sample}; "
        f"terminal_accounted_percent={terminal_accounted_percent_text}; "
        f"pending={pending}; complete={complete_text}"
        f"{field_gap_text}"
        f"{_field_gap_summary_text(coverage)}"
        f"{_field_gap_actions_text(coverage)}"
        f"{_field_gap_proofs_text(coverage)}"
        f"{_gate_70_to_75_text(coverage)}"
    )


def _ds_goal_wrapper_contract_line(surface: dict[str, Any]) -> str:
    raw = surface.get("raw") if isinstance(surface.get("raw"), dict) else {}
    contract = (
        raw.get("installed_wrapper_contract")
        if isinstance(raw.get("installed_wrapper_contract"), dict)
        else {}
    )
    default_target = (
        raw.get("default_wrapper_target")
        if isinstance(raw.get("default_wrapper_target"), dict)
        else {}
    )
    hardening = (
        raw.get("target_sync_receipt_hardening")
        if isinstance(raw.get("target_sync_receipt_hardening"), dict)
        else {}
    )
    decision = (
        raw.get("convergence_decision_packet")
        if isinstance(raw.get("convergence_decision_packet"), dict)
        else {}
    )
    preflight = (
        raw.get("longrun_preflight_gate")
        if isinstance(raw.get("longrun_preflight_gate"), dict)
        else {}
    )
    if not raw:
        return ""
    sha = str(contract.get("wrapper_sha256") or "")
    sha_label = sha[:12] if sha else "<missing>"
    safe = str(raw.get("safe_current_checkout_invocation") or "")
    safe_text = (
        f"; safe={safe}"
        if safe and raw.get("target_matches_current_repo") is False
        else ""
    )
    decision_state = str(decision.get("approval_state") or "")
    decision_text = f"; decision={decision_state}" if decision_state else ""
    preflight_status = str(preflight.get("status") or "")
    preflight_text = f"; preflight={preflight_status}" if preflight_status else ""
    return (
        f"target={raw.get('target_repo') or '<blank>'}; "
        f"source={raw.get('target_resolution_source') or '<blank>'}; "
        f"default={default_target.get('target_repo') or '<blank>'}; "
        f"matches_current={str(raw.get('target_matches_current_repo')).lower()}; "
        f"wrapper_sha256={sha_label}; "
        f"pin={str(contract.get('dharma_swarm_repo_pin_supported')).lower()}; "
        f"hardening={hardening.get('state') or '<unknown>'}"
        f"{decision_text}"
        f"{preflight_text}"
        f"{safe_text}"
    )


def _validate_live_ops_census_payload(payload: Any) -> list[str]:
    try:
        return [str(error) for error in validate_census_payload(payload)]
    except Exception as exc:
        return [f"unable to validate live ops census receipt: {exc}"]


def _live_ops_census_freshness(payload: Any) -> dict[str, Any]:
    try:
        result = census_payload_freshness(payload)
        return result if isinstance(result, dict) else {}
    except Exception as exc:
        return {
            "state": "unknown",
            "age_minutes": None,
            "evidence": f"unable to check live ops census freshness: {exc}",
        }


def build_liveness() -> Liveness:
    receipt_path = _census_receipt_path()
    if receipt_path is None or not receipt_path.exists():
        return Liveness(receipt=(
            "no census receipt — run "
            "python3 scripts/runtime/live_ops_census.py --write"))
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return Liveness(receipt=f"unreadable receipt at {receipt_path}")
    validation_errors = _validate_live_ops_census_payload(payload)
    if validation_errors:
        return Liveness(
            receipt=f"invalid receipt at {receipt_path}: {'; '.join(validation_errors)}"
        )
    generated_at = str(payload.get("generated_at", ""))
    freshness = _live_ops_census_freshness(payload)
    if str(freshness.get("state") or "") == "stale":
        evidence = str(freshness.get("evidence") or "live ops census receipt is stale")
        age = freshness.get("age_minutes")
        if age is not None:
            evidence = f"{evidence}; age_minutes={age}"
        return Liveness(
            receipt=f"stale receipt at {receipt_path}: {evidence}",
            generated_at=generated_at,
        )
    surfaces = []
    daemon_dispatch_launch = ""
    daemon_dispatch_running = ""
    daemon_receipt_head = ""
    daemon_provider_model_coverage = ""
    ds_goal_wrapper_contract = ""
    for surface in payload.get("surfaces") or []:
        if not isinstance(surface, dict):
            continue
        surface_id = str(surface.get("surface_id") or surface.get("id") or "")
        if surface_id == "substrate.dharma_daemon":
            raw = surface.get("raw")
            if isinstance(raw, dict):
                dispatch_launch = raw.get("dispatch_launch")
                if isinstance(dispatch_launch, dict):
                    daemon_dispatch_launch = str(
                        dispatch_launch.get("state", ""))
                daemon_dispatch_running = str(
                    raw.get("running_dispatch_proof", ""))
                receipt_head = raw.get("runtime_receipt_active_head")
                if isinstance(receipt_head, dict):
                    daemon_receipt_head = _runtime_receipt_head_line(receipt_head)
                receipt_coverage = raw.get("runtime_receipt_coverage")
                if isinstance(receipt_coverage, dict):
                    daemon_provider_model_coverage = _provider_model_coverage_line(
                        receipt_coverage
                    )
        if surface_id == "cli.ds_goal":
            ds_goal_wrapper_contract = _ds_goal_wrapper_contract_line(surface)
        surfaces.append({
            "id": surface_id,
            "label": str(surface.get("label", "")),
            "status": str(surface.get("status", "")),
            "proof_gaps": _surface_proof_gaps(surface),
        })
    return Liveness(
        receipt=str(receipt_path),
        generated_at=generated_at,
        surfaces=surfaces,
        daemon_dispatch_launch=daemon_dispatch_launch,
        daemon_dispatch_running=daemon_dispatch_running,
        daemon_receipt_head=daemon_receipt_head,
        daemon_provider_model_coverage=daemon_provider_model_coverage,
        ds_goal_wrapper_contract=ds_goal_wrapper_contract,
    )


def _coerce_utc_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _default_runtime_db() -> Path:
    try:
        from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

        return Path(DEFAULT_RUNTIME_DB)
    except Exception:
        return Path("~/.dharma/state/runtime.db").expanduser()


def build_loop1_closure(db_path: Any = None) -> Loop1Closure:
    """Project Loop 1 closure from delegation_runs.receipt_json.

    This is read-only and owns no fact. LIVE requires the newest persisted
    dispatch receipt to carry a non-empty actually-served provider/model pair,
    runtime_provider.actual_served provenance, and a fresh timestamp.
    """
    resolved = Path(db_path).expanduser() if db_path is not None else _default_runtime_db()
    if not resolved.exists():
        return Loop1Closure(live=False, detail=f"runtime db missing: {resolved}")
    try:
        with sqlite3.connect(resolved) as db:
            row = db.execute(
                """
                SELECT started_at, receipt_json
                FROM delegation_runs
                WHERE receipt_json IS NOT NULL AND receipt_json != ''
                ORDER BY started_at DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
    except sqlite3.Error as exc:
        return Loop1Closure(live=False, detail=f"runtime db unreadable: {exc}")
    if not row:
        return Loop1Closure(live=False, detail="no delegation_runs receipt_json rows")
    started_at, raw_receipt = row
    try:
        receipt = json.loads(str(raw_receipt))
    except Exception:
        return Loop1Closure(
            live=False,
            started_at=str(started_at or ""),
            detail="latest receipt_json is not valid JSON",
        )
    if not isinstance(receipt, dict):
        return Loop1Closure(
            live=False,
            started_at=str(started_at or ""),
            detail="latest receipt_json is not an object",
        )
    provider = str(receipt.get("provider") or "").strip()
    model = str(receipt.get("model") or "").strip()
    attributes = receipt.get("attributes") if isinstance(receipt.get("attributes"), dict) else {}
    source = str(
        attributes.get("provider_model_truth_source")
        or receipt.get("provider_model_truth_source")
        or ""
    ).strip()
    if not provider or not model:
        return Loop1Closure(
            live=False,
            provider=provider,
            model=model,
            started_at=str(started_at or ""),
            detail="latest receipt missing provider and/or model",
        )
    if source != "runtime_provider.actual_served":
        return Loop1Closure(
            live=False,
            provider=provider,
            model=model,
            started_at=str(started_at or ""),
            detail=f"latest provider/model provenance is {source or 'missing'}",
        )
    stamped = _coerce_utc_datetime(started_at or receipt.get("started_at"))
    if stamped is None:
        return Loop1Closure(
            live=False,
            provider=provider,
            model=model,
            started_at=str(started_at or ""),
            detail="latest receipt timestamp is unreadable",
        )
    age_seconds = (datetime.now(timezone.utc) - stamped).total_seconds()
    if age_seconds > 24 * 60 * 60:
        age_hours = round(age_seconds / 3600, 2)
        return Loop1Closure(
            live=False,
            provider=provider,
            model=model,
            started_at=str(started_at or ""),
            detail=f"latest actual-served receipt is stale ({age_hours}h old)",
        )
    return Loop1Closure(
        live=True,
        provider=provider,
        model=model,
        started_at=str(started_at or ""),
        detail="latest dispatch receipt carries fresh actual-served provider/model",
    )


_BR_HEAD = re.compile(r"^###\s+(?P<id>BR-\d+)\s*[—-]\s*(?P<title>.+)$")
_BR_STATUS = re.compile(r"^-\s*\*\*status:\*\*\s*(?:\*\*)?(?P<status>[A-Z]+)(?:\*\*)?")


def build_broken() -> list[BrokenItem]:
    items: list[BrokenItem] = []
    if not BROKEN_REGISTER.exists():
        return items
    current: BrokenItem | None = None
    for line in BROKEN_REGISTER.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## CLOSED"):
            break
        head = _BR_HEAD.match(stripped)
        if head:
            current = BrokenItem(id=head.group("id"), status="OPEN",
                                 title=head.group("title").strip())
            items.append(current)
            continue
        status = _BR_STATUS.match(stripped)
        if status and current is not None:
            current.status = status.group("status")
    return [i for i in items if i.status not in {"FIXED", "CLOSED"}]


def build_packet() -> OrientationPacket:
    return OrientationPacket(
        identity=build_identity(),
        organs=build_organs(),
        tracks=build_tracks(),
        custody=build_custody(),
        liveness=build_liveness(),
        loop1=build_loop1_closure(),
        broken=build_broken(),
    )


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def render(packet: OrientationPacket) -> None:
    _section("ORIENTATION — the whole organism at once (projection, not authority)")
    print(f"  {packet.identity.one_line}")
    print("  Read-first:")
    for path in packet.identity.read_first:
        marker = "MISSING " if path in packet.identity.missing_sources else ""
        print(f"    - {marker}{path}")

    _section(f"ORGANS ({len(packet.organs)}) — owner: docs/governance/VENTURE_CELL_PORTFOLIO.yaml")
    for organ in packet.organs:
        name = f" ({organ.external_name})" if organ.external_name else ""
        print(f"  [{organ.status:<18}] {organ.id}{name} — {organ.instrument}")

    _section(f"ACTIVE TRACKS ({len(packet.tracks)}) — owner: docs/governance/ACTIVE_TRACK.yaml")
    for track in packet.tracks:
        print(f"  [{track.status}] {track.id} serves={track.serves} owner={track.owner}")
        if track.readiness:
            print(f"      readiness: {track.readiness}")
        for surface in track.owned_surfaces:
            print(f"      owns {surface}")

    _section("CANON CUSTODY — owner: docs/docops/assertions.yaml canonical_guard.registered")
    print(f"  Registered canon docs: {packet.custody.registered_total} "
          f"(present in this checkout: {packet.custody.present})")
    for path in packet.custody.missing:
        print(f"  MISSING: {path}")

    _section("LIVENESS — owner: live ops census receipt (read-only)")
    print(f"  Receipt: {packet.liveness.receipt}")
    if packet.liveness.generated_at:
        print(f"  Generated: {packet.liveness.generated_at}")
    if packet.liveness.daemon_dispatch_launch or packet.liveness.daemon_dispatch_running:
        launch = packet.liveness.daemon_dispatch_launch or "unknown"
        running = packet.liveness.daemon_dispatch_running or "unknown"
        print(f"  Daemon spine: launch={launch}; running={running}")
    if packet.liveness.daemon_receipt_head:
        print(f"  Receipt head: {packet.liveness.daemon_receipt_head}")
    if packet.liveness.daemon_provider_model_coverage:
        print(f"  Provider/model: {packet.liveness.daemon_provider_model_coverage}")
    if packet.liveness.ds_goal_wrapper_contract:
        print(f"  ds-goal CLI: {packet.liveness.ds_goal_wrapper_contract}")
    for surface in packet.liveness.surfaces:
        proof_gaps = surface.get("proof_gaps") or []
        proof = f"; proof_gaps={','.join(proof_gaps)}" if proof_gaps else ""
        print(f"  [{surface['status']:<8}] {surface['id']} — {surface['label']}{proof}")

    _section("LOOP 1 CLOSURE — owner: delegation_runs.receipt_json (read-only)")
    status = "LIVE" if packet.loop1.live else "NOT-LIVE"
    print(f"  Loop 1 (provider chain + dispatch): {status}")
    if packet.loop1.provider or packet.loop1.model:
        print(
            f"    latest receipt: provider={packet.loop1.provider!r} "
            f"model={packet.loop1.model!r}"
        )
    if packet.loop1.started_at:
        print(f"    started_at: {packet.loop1.started_at}")
    if packet.loop1.detail:
        print(f"    detail: {packet.loop1.detail}")

    _section(f"BROKEN REGISTER — open-like items ({len(packet.broken)})")
    for item in packet.broken:
        print(f"  [{item.status}] {item.id} — {item.title}")

    print()
    print("  Depth: make onboard (state) · docs/MEGAFILE_INDEX.md (maps)")
    print("  This view writes nothing and owns nothing.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the whole organism at once from its owners.")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print the machine packet JSON to stdout")
    args = parser.parse_args(argv)
    packet = build_packet()
    if args.as_json:
        print(json.dumps(asdict(packet), sort_keys=True, indent=1))
    else:
        render(packet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
