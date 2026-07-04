"""Go receipt rows for the operator control surface.

This module keeps optional Go-side evidence projection out of the central
control-surface projector. It is read-only: it checks files and receipt
summaries, then returns typed ``ControlSurfaceRow`` instances.
"""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow


_REPO_ROOT: Path | None = None


def _repo_root() -> Path:
    global _REPO_ROOT
    if _REPO_ROOT is not None:
        return _REPO_ROOT
    here = Path(__file__).resolve()
    for parent in (here.parent, here.parent.parent, here.parent.parent.parent):
        if (parent / "ACTIVE_SURFACE_MANIFEST.yaml").exists():
            _REPO_ROOT = parent
            return parent
    _REPO_ROOT = Path.cwd()
    return _REPO_ROOT


def _go_receipt_rows(repo_root: Path | None = None) -> list[ControlSurfaceRow]:
    repo_root = repo_root or _repo_root()
    rows: list[ControlSurfaceRow] = []

    def _append_file_row(
        *,
        row_id: str,
        label: str,
        authority_role: str,
        owner_module: str,
    ) -> None:
        path = repo_root / owner_module
        if not path.exists():
            return
        row = ControlSurfaceRow(
            id=row_id,
            kind="go_receipt",
            label=label,
            authority_role=authority_role,
            declared_state="incubating",
            desired_state="live",
            observed_state="file present",
            coherence_state="partial",
            priority="p2",
            owner_module=owner_module,
            truth_owner="go_sdk",
        )
        row.add_evidence(
            "go_receipt", str(path.relative_to(repo_root)),
            status="present",
            provenance_chain=["go_sdk", "file_check"],
        )
        row.add_source_ref("go_module", owner_module, exists=True)
        rows.append(row)

    _append_file_row(
        row_id="go.evidence_bridge",
        label="Go Evidence Bridge",
        authority_role="adapter",
        owner_module="dharma_swarm/operator_core/go_evidence_bridge.py",
    )
    _append_file_row(
        row_id="go.github_bridge",
        label="Go GitHub Bridge",
        authority_role="adapter",
        owner_module="dharma_swarm/operator_core/go_github_bridge.py",
    )
    _append_file_row(
        row_id="go.receipt_sdk",
        label="Go Receipt SDK",
        authority_role="evidence",
        owner_module="tools/go_sdk/receipt/receipt.go",
    )
    _append_file_row(
        row_id="go.adapter_contract",
        label="Go Adapter Contract",
        authority_role="adapter",
        owner_module="tools/go_sdk/adaptercontract/contract.go",
    )
    _append_file_row(
        row_id="go.evidence_ingestor",
        label="Go Evidence Ingestor",
        authority_role="adapter",
        owner_module="tools/evidence_ingestor_go/main.go",
    )
    _append_file_row(
        row_id="go.github_ingestor",
        label="Go GitHub Ingestor",
        authority_role="adapter",
        owner_module="tools/github_ingestor_go/adapter.go",
    )
    _append_file_row(
        row_id="go.world_signal_ingestor",
        label="Go World Signal Ingestor",
        authority_role="adapter",
        owner_module="tools/world_signal_ingestor_go/adapter.go",
    )

    rows.extend(_go_world_receipt_summary_rows())
    rows.extend(_go_world_radar_health_rows())
    return rows


def _go_world_radar_health_rows() -> list[ControlSurfaceRow]:
    """Project the world-radar Go chain health file (per-source errors, mode).

    Read-only view of ``~/.dharma/meta/world_radar/world_radar_health.json``,
    written by ``dharma_swarm/world_radar/go_bridge.py`` on every radar pass.
    Returns no row when the loop has never run on this host.
    """
    health_path = (
        dharma_state_dir("DHARMA_STATE_DIR") / "meta" / "world_radar" / "world_radar_health.json"
    )
    if not health_path.exists():
        return []
    try:
        health = json.loads(health_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        health = None
    if not isinstance(health, dict):
        row = ControlSurfaceRow(
            id="go.world_radar_health",
            kind="go_receipt",
            label="Go World Radar Health",
            authority_role="evidence",
            declared_state="incubating",
            desired_state="live",
            observed_state="health file unreadable",
            coherence_state="drifted",
            priority="p1",
            owner_module="dharma_swarm/world_radar/go_bridge.py",
            truth_owner="go_sdk",
            gap_codes=["go_world_radar_health_unreadable"],
        )
        row.add_evidence(
            "go_receipt", f"health_path={health_path}",
            status="error",
            provenance_chain=["go_sdk", "world_radar", "health_file"],
        )
        return [row]

    status = str(health.get("status") or ("ok" if health.get("ok") else "degraded"))
    source_errors = (
        health.get("source_errors") if isinstance(health.get("source_errors"), list) else []
    )
    failed_sources = int(float(health.get("failed_sources", 0) or 0))
    needs_host = "needs_host" in {
        str(health.get("scout_invocation_mode", "") or ""),
        str(health.get("ingestor_invocation_mode", "") or ""),
    }
    gaps: list[str] = []
    if needs_host:
        gaps.append("go_world_radar_needs_host")
    if status == "ok":
        observed_state = "radar pass ok"
        coherence_state = "bound"
    else:
        observed_state = (
            "Go organs not runnable on this host (needs_host)"
            if needs_host
            else f"radar degraded ({failed_sources} failed sources)"
        )
        coherence_state = "partial"
        gaps.append("go_world_radar_degraded")
    if source_errors:
        gaps.append("go_world_radar_source_errors")

    row = ControlSurfaceRow(
        id="go.world_radar_health",
        kind="go_receipt",
        label="Go World Radar Health",
        authority_role="evidence",
        declared_state="incubating",
        desired_state="live",
        observed_state=observed_state,
        coherence_state=coherence_state,
        priority="p1",
        owner_module="dharma_swarm/world_radar/go_bridge.py",
        truth_owner="go_sdk",
        freshness=str(health.get("checked_at", "")),
        gap_codes=gaps,
        next_action=(
            "Provision Go on this host: run `make go-build` (or install a Go toolchain)"
            if needs_host
            else ("Investigate per-source failures below" if source_errors else "")
        ),
        raw={
            "health_path": str(health_path),
            "status": status,
            "successful_sources": health.get("successful_sources", 0),
            "failed_sources": failed_sources,
            "scout_invocation_mode": health.get("scout_invocation_mode", ""),
            "ingestor_invocation_mode": health.get("ingestor_invocation_mode", ""),
            "source_errors": source_errors,
        },
    )
    row.add_evidence(
        "go_receipt",
        (
            f"status={status} successful_sources={health.get('successful_sources', 0)} "
            f"failed_sources={failed_sources} "
            f"scout_mode={health.get('scout_invocation_mode', '') or 'unknown'} "
            f"ingestor_mode={health.get('ingestor_invocation_mode', '') or 'unknown'}"
        ),
        status="present",
        provenance_chain=["go_sdk", "world_radar", "health_file"],
    )
    for entry in source_errors[:10]:
        if not isinstance(entry, dict):
            continue
        row.add_evidence(
            "go_receipt",
            (
                f"source_error source={entry.get('source', '')} "
                f"stage={entry.get('stage', '')} error={entry.get('error', '')}"
            ),
            status="error",
            provenance_chain=["go_sdk", "world_radar", "source_errors"],
        )
    row.add_source_ref("file", str(health_path), exists=True)
    row.add_source_ref("go_module", "dharma_swarm/world_radar/go_bridge.py", exists=True)
    return [row]


def _go_world_receipt_summary_rows() -> list[ControlSurfaceRow]:
    try:
        from dharma_swarm.operator_core.world_radar.receipt_bridge import (
            summarize_go_world_receipts,
        )
    except Exception as exc:
        row = ControlSurfaceRow(
            id="go.world_signal_receipts",
            kind="go_receipt",
            label="Go World Signal Receipts",
            authority_role="evidence",
            declared_state="incubating",
            desired_state="live",
            observed_state="bridge import failed",
            coherence_state="drifted",
            priority="p1",
            owner_module="dharma_swarm/operator_core/world_radar/receipt_bridge.py",
            truth_owner="go_sdk",
            gap_codes=["go_world_receipt_bridge_import_failed"],
        )
        row.add_evidence(
            "go_receipt", f"world receipt bridge import failed: {exc}",
            status="error",
            provenance_chain=["go_sdk", "world_radar", "bridge_import"],
        )
        row.add_source_ref(
            "file",
            "dharma_swarm/operator_core/world_radar/receipt_bridge.py",
            exists=True,
        )
        return [row]

    summary = summarize_go_world_receipts()
    gaps: list[str] = []
    if not summary["exists"]:
        observed_state = "receipts dir missing"
        coherence_state = "declared_only"
        gaps.append("go_world_receipts_dir_missing")
    elif summary["total"] == 0:
        observed_state = "no receipts"
        coherence_state = "declared_only"
        gaps.append("go_world_receipts_empty")
    elif summary["rejected"]:
        observed_state = "receipts have rejections"
        coherence_state = "partial"
        gaps.append("go_world_receipt_rejections")
    else:
        observed_state = "receipts accepted"
        coherence_state = "bound"

    row = ControlSurfaceRow(
        id="go.world_signal_receipts",
        kind="go_receipt",
        label="Go World Signal Receipts",
        authority_role="evidence",
        declared_state="incubating",
        desired_state="live",
        observed_state=observed_state,
        coherence_state=coherence_state,
        priority="p1",
        owner_module="dharma_swarm/operator_core/world_radar/receipt_bridge.py",
        truth_owner="go_sdk",
        freshness=summary["freshest_observed_at"],
        gap_codes=gaps,
        next_action="Project accepted world_signal receipts into Zeitgeist/Shakti surfaces",
        raw=summary,
    )
    row.add_evidence(
        "go_receipt", f"receipts_dir={summary['receipts_dir']}",
        status="present" if summary["exists"] else "missing",
        provenance_chain=["go_sdk", "world_receipts_dir"],
    )
    row.add_evidence(
        "go_receipt",
        (
            f"total={summary['total']} accepted={summary['accepted']} "
            f"rejected={summary['rejected']} world_signal={summary['world_signal']}"
        ),
        status="present",
        provenance_chain=["go_sdk", "world_receipts_summary"],
    )
    row.add_evidence(
        "go_receipt",
        f"projected_world_signals={summary['projected_world_signals']}",
        status="present",
        provenance_chain=["go_sdk", "world_signal_projection"],
    )
    if summary["rejected"]:
        row.add_evidence(
            "go_receipt", f"rejected_reasons={summary['rejected_reasons']}",
            status="rejected",
            provenance_chain=["go_sdk", "world_receipts_summary", "rejections"],
        )
    row.add_source_ref(
        "file",
        "dharma_swarm/operator_core/world_radar/receipt_bridge.py",
        exists=True,
    )
    row.add_source_ref("go_module", "tools/world_signal_ingestor_go/adapter.go", exists=True)
    row.add_source_ref("file", summary["receipts_dir"], exists=bool(summary["exists"]))
    return [row]
