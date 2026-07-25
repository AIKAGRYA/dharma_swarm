"""Control Surface Projector v0.

Reconciles ACTIVE_SURFACE_MANIFEST.yaml (declared intent) with runtime,
code, evidence, and documentation observations.  Produces typed rows that
the dashboard renders as an operator cockpit grid.

ACTIVE_SURFACE_MANIFEST.yaml declares intent; observed reality comes from
runtime/code/evidence adapters.  The manifest is *not* the single source
of truth -- it is the declared-intent layer only.

Models and row contract live in control_surface_models.py.
Handoff prompt generation lives in control_surface_handoff.py.
"""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from dharma_swarm.operator_core.control_surface_handoff import (  # noqa: F401
    generate_handoff_prompt,
)
from dharma_swarm.operator_core.control_surface_go import (  # noqa: F401
    _go_receipt_rows,
    _go_world_receipt_summary_rows,
)
from dharma_swarm.operator_core.control_surface_memory import memory_kernel_control_rows
from dharma_swarm.operator_core.control_surface_spine import (  # noqa: F401
    _spine_pulse_row,
)
from dharma_swarm.operator_core.control_surface_live_ops import (  # noqa: F401
    _live_ops_census_rows,
    _rows_from_live_ops_census,
)
from dharma_swarm.operator_core.control_surface_models import (
    AUTHORITY_ROLES,  # noqa: F401  (re-export)
    COHERENCE_STATES,
    PRIORITIES,
    ROW_KINDS,  # noqa: F401  (re-export)
    AgentHandoffPrompt,  # noqa: F401
    ControlSurfaceEnvelope,  # noqa: F401
    ControlSurfaceRow,
    DisplayHints,  # noqa: F401
    EvidenceItem,  # noqa: F401
    HumanDecisionContext,  # noqa: F401  (re-export)
    SourceError,  # noqa: F401
    SourceRef,  # noqa: F401
    VerificationEvent,  # noqa: F401
    _build_human_decision_context,
    _compute_display_hints,
    _needs_human_decision,  # noqa: F401  (re-export)
)
from dharma_swarm.operator_core.onboarding.broken_register import (
    parse_broken_register,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _file_freshness(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return ""


def _module_importable(dotted: str) -> bool:
    try:
        importlib.import_module(dotted)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# A) Manifest adapter
# ---------------------------------------------------------------------------

def load_active_surface_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    manifest_path = root / "ACTIVE_SURFACE_MANIFEST.yaml"
    if not manifest_path.exists():
        return {}
    with manifest_path.open("r") as fh:
        return yaml.safe_load(fh) or {}


def _manifest_source_ref() -> SourceRef:
    return SourceRef(kind="manifest_section", path="ACTIVE_SURFACE_MANIFEST.yaml", exists=True)


def _manifest_api_router_rows(manifest: dict[str, Any]) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    for entry in manifest.get("api_routers", []):
        rid = f"api.{entry['id']}"
        row = ControlSurfaceRow(
            id=rid,
            kind="api_router",
            label=entry.get("id", rid),
            authority_role="declared_authority",
            declared_state=f"prefix={entry.get('prefix', '?')} module={entry.get('module', '?')}",
            desired_state="live",
            priority="p0",
            owner_module=entry.get("module", ""),
            truth_owner="ACTIVE_SURFACE_MANIFEST.yaml",
            raw=entry,
        )
        row.source_refs.append(_manifest_source_ref())
        row.source_ref_labels.append("ACTIVE_SURFACE_MANIFEST.yaml")
        rows.append(row)
    return rows


def _manifest_dashboard_page_rows(manifest: dict[str, Any]) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    for entry in manifest.get("dashboard_surfaces", []):
        rid = f"dashboard.{entry['id']}"
        declared = entry.get("status", "unknown")
        row = ControlSurfaceRow(
            id=rid,
            kind="dashboard_page",
            label=entry.get("label", entry["id"]),
            authority_role="declared_authority",
            declared_state=declared,
            desired_state=declared if declared != "stub" else "live",
            priority=entry.get("priority", "unknown"),
            next_action=entry.get("next_action", "") or "",
            owner_module=entry.get("route", ""),
            truth_owner="ACTIVE_SURFACE_MANIFEST.yaml",
            raw=entry,
        )
        row.source_refs.append(_manifest_source_ref())
        row.source_ref_labels.append("ACTIVE_SURFACE_MANIFEST.yaml")
        rows.append(row)
    return rows


def _manifest_agent_rows(manifest: dict[str, Any]) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    for entry in manifest.get("agents", []):
        rid = f"agent.{entry['id']}"
        declared = entry.get("status", "unknown")
        row = ControlSurfaceRow(
            id=rid,
            kind="agent_subsystem",
            label=entry.get("label", entry["id"]),
            authority_role="declared_authority",
            declared_state=declared,
            desired_state="live",
            priority=entry.get("priority", "unknown"),
            next_action=entry.get("next_action", "") or "",
            owner_module=entry.get("module", ""),
            truth_owner="ACTIVE_SURFACE_MANIFEST.yaml",
            raw=entry,
        )
        row.source_refs.append(_manifest_source_ref())
        row.source_ref_labels.append("ACTIVE_SURFACE_MANIFEST.yaml")
        rows.append(row)
    return rows


def _manifest_integration_rows(manifest: dict[str, Any]) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    for entry in manifest.get("integrations", []):
        rid = f"integration.{entry['id']}"
        declared = entry.get("status", "unknown")
        row = ControlSurfaceRow(
            id=rid,
            kind="integration",
            label=entry.get("label", entry["id"]),
            authority_role="declared_authority",
            declared_state=declared,
            desired_state="live",
            priority="p1",
            owner_module=entry.get("path", entry.get("env_var", "")),
            truth_owner="ACTIVE_SURFACE_MANIFEST.yaml",
            raw=entry,
        )
        row.source_refs.append(_manifest_source_ref())
        row.source_ref_labels.append("ACTIVE_SURFACE_MANIFEST.yaml")
        rows.append(row)
    return rows


def _manifest_loop_rows(manifest: dict[str, Any]) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    for entry in manifest.get("loops", []):
        rid = f"loop.{entry['id']}"
        declared = entry.get("status", "unknown")
        row = ControlSurfaceRow(
            id=rid,
            kind="feedback_loop",
            label=entry.get("label", entry["id"]),
            authority_role="declared_authority",
            declared_state=declared,
            desired_state="live",
            priority=entry.get("priority", "unknown"),
            next_action=entry.get("next_action", "") or "",
            owner_module=entry.get("module", ""),
            truth_owner="ACTIVE_SURFACE_MANIFEST.yaml",
            raw=entry,
        )
        row.source_refs.append(_manifest_source_ref())
        row.source_ref_labels.append("ACTIVE_SURFACE_MANIFEST.yaml")
        rows.append(row)
    return rows


def _manifest_cron_rows(manifest: dict[str, Any]) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    for entry in manifest.get("cron_jobs", []):
        rid = f"cron.{entry.get('id', entry.get('label', 'unknown'))}"
        row = ControlSurfaceRow(
            id=rid,
            kind="cron_job",
            label=entry.get("label", entry.get("id", "?")),
            authority_role="declared_authority",
            declared_state=entry.get("status", "unknown"),
            desired_state="live",
            priority="p2",
            owner_module=entry.get("script", entry.get("command", "")),
            truth_owner="ACTIVE_SURFACE_MANIFEST.yaml",
            raw=entry,
        )
        row.source_refs.append(_manifest_source_ref())
        row.source_ref_labels.append("ACTIVE_SURFACE_MANIFEST.yaml")
        rows.append(row)
    return rows


def _manifest_state_writer_rows(manifest: dict[str, Any]) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    for entry in manifest.get("state_writers", []):
        rid = f"state.{entry.get('id', entry.get('label', 'unknown'))}"
        row = ControlSurfaceRow(
            id=rid,
            kind="state_writer",
            label=entry.get("label", entry.get("id", "?")),
            authority_role="declared_authority",
            declared_state=entry.get("status", "unknown"),
            desired_state="live",
            priority="p1",
            owner_module=entry.get("module", ""),
            truth_owner="ACTIVE_SURFACE_MANIFEST.yaml",
            raw=entry,
        )
        row.source_refs.append(_manifest_source_ref())
        row.source_ref_labels.append("ACTIVE_SURFACE_MANIFEST.yaml")
        rows.append(row)
    return rows


def _manifest_recursive_discovery_rows(manifest: dict[str, Any]) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    for entry in manifest.get("recursive_discovery_surfaces", []):
        rid = f"recursive.{entry['id']}"
        row = ControlSurfaceRow(
            id=rid,
            kind="recursive_discovery",
            label=entry.get("label", entry["id"]),
            authority_role="incubating",
            declared_state=entry.get("status", "unknown"),
            desired_state="shadow",
            priority=entry.get("priority", "p1"),
            next_action=entry.get("next_action", "") or "",
            owner_module=entry.get("owner_module", "dharma_swarm/recursive_discovery.py"),
            truth_owner="ACTIVE_SURFACE_MANIFEST.yaml",
            raw=entry,
        )
        row.source_refs.append(_manifest_source_ref())
        row.source_ref_labels.append("ACTIVE_SURFACE_MANIFEST.yaml")
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# B) API / router reality adapter
# ---------------------------------------------------------------------------

def _observe_api_router(row: ControlSurfaceRow, repo_root: Path) -> None:
    module_dotted = row.raw.get("module", "")
    if not module_dotted:
        return
    module_path = repo_root / module_dotted.replace(".", "/")
    file_path = module_path.with_suffix(".py")
    if not file_path.exists():
        pkg_init = module_path / "__init__.py"
        if not pkg_init.exists():
            row.observed_state = "module file missing"
            row.coherence_state = "drifted"
            row.add_evidence(
                "file", str(file_path),
                status="missing",
                provenance_chain=["manifest api_routers", "file_exists_check"],
            )
            row.gap_codes.append("module_missing")
            return

    row.add_evidence(
        "file", str(file_path),
        status="present",
        provenance_chain=["manifest api_routers", "file_exists_check"],
    )
    row.add_source_ref("file", str(file_path.relative_to(repo_root)), exists=True)

    main_py = repo_root / "api" / "main.py"
    if main_py.exists():
        main_text = main_py.read_text(errors="ignore")
        module_leaf = module_dotted.rsplit(".", 1)[-1] if module_dotted else ""
        registered = False
        if module_leaf:
            registered = f"{module_leaf}" in main_text
        if not registered:
            prefix = row.raw.get("prefix", "")
            if prefix:
                registered = prefix in main_text
        if registered:
            row.add_evidence(
                "api_route", "api/main.py",
                status="present",
                provenance_chain=["manifest api_routers", "registration_check"],
            )
        else:
            row.add_evidence(
                "api_route", "api/main.py",
                status="missing",
                provenance_chain=["manifest api_routers", "registration_check"],
            )
            row.gap_codes.append("router_not_registered")

    if row.gap_codes:
        row.observed_state = "partial"
        row.coherence_state = "partial"
    else:
        row.observed_state = "live"
        row.coherence_state = "bound"


# ---------------------------------------------------------------------------
# C) Dashboard reality adapter
# ---------------------------------------------------------------------------

def _observe_dashboard_page(row: ControlSurfaceRow, repo_root: Path) -> None:
    route = row.raw.get("route", "")
    if not route:
        return

    route_dir = route.lstrip("/").replace("dashboard/", "", 1) if route.startswith("/dashboard/") else route.lstrip("/")
    if route == "/dashboard":
        route_dir = ""

    page_dir = repo_root / "dashboard" / "src" / "app" / "dashboard"
    if route_dir:
        page_dir = page_dir / route_dir
    page_file = page_dir / "page.tsx"

    rel_page = str(page_file.relative_to(repo_root))
    if page_file.exists():
        row.add_evidence(
            "file", rel_page,
            status="present",
            provenance_chain=["manifest dashboard_surfaces", "file_exists_check"],
        )
        row.add_source_ref("file", rel_page, exists=True)
        row.freshness = _file_freshness(page_file)
    else:
        row.add_evidence(
            "file", rel_page,
            status="missing",
            provenance_chain=["manifest dashboard_surfaces", "file_exists_check"],
        )
        row.add_source_ref("file", rel_page, exists=False)
        row.gap_codes.append("dashboard_page_missing")

    declared = row.declared_state
    if row.gap_codes:
        row.observed_state = "missing"
        row.coherence_state = "drifted" if declared in ("live", "degraded") else "declared_only"
    elif declared in ("stub", "degraded"):
        row.observed_state = declared
        row.coherence_state = "partial"
    else:
        row.observed_state = "live"
        row.coherence_state = "bound"


# ---------------------------------------------------------------------------
# D) Agent subsystem reality adapter
# ---------------------------------------------------------------------------

def _observe_agent_subsystem(row: ControlSurfaceRow, repo_root: Path) -> None:
    module_path_str = row.raw.get("module", "")
    if not module_path_str:
        return
    module_file = repo_root / module_path_str
    if module_file.exists():
        row.add_evidence(
            "file", module_path_str,
            status="present",
            provenance_chain=["manifest agents", "file_exists_check"],
        )
        row.add_source_ref("file", module_path_str, exists=True)
        row.freshness = _file_freshness(module_file)
    else:
        row.add_evidence(
            "file", module_path_str,
            status="missing",
            provenance_chain=["manifest agents", "file_exists_check"],
        )
        row.add_source_ref("file", module_path_str, exists=False)
        row.gap_codes.append("module_missing")

    test_name = "test_" + Path(module_path_str).stem + ".py"
    test_file = repo_root / "tests" / test_name
    if test_file.exists():
        row.add_evidence(
            "test", f"tests/{test_name}",
            status="present",
            provenance_chain=["manifest agents", "test_convention_check"],
        )
        row.add_source_ref("file", f"tests/{test_name}", exists=True)
    else:
        row.gap_codes.append("test_missing")

    declared = row.declared_state
    if "module_missing" in row.gap_codes:
        row.observed_state = "broken"
        row.coherence_state = "drifted"
    elif declared in ("stub",):
        row.observed_state = "stub"
        row.coherence_state = "declared_only"
    elif row.gap_codes:
        row.observed_state = "partial"
        row.coherence_state = "partial"
    else:
        row.observed_state = declared
        row.coherence_state = "bound" if declared == "live" else "partial"


# ---------------------------------------------------------------------------
# E) Integration reality adapter
# ---------------------------------------------------------------------------

def _observe_integration(row: ControlSurfaceRow, repo_root: Path) -> None:
    itype = row.raw.get("type", "")
    if itype == "database":
        db_path = row.raw.get("path", "")
        if db_path:
            expanded = Path(db_path).expanduser()
            if expanded.exists():
                row.add_evidence(
                    "db_probe", db_path,
                    status="present",
                    provenance_chain=["manifest integrations", "db_exists_check"],
                )
                row.add_source_ref("config", db_path, exists=True)
                row.freshness = _file_freshness(expanded)
                row.observed_state = "live"
                row.coherence_state = "bound"
            else:
                row.add_evidence(
                    "db_probe", db_path,
                    status="missing",
                    provenance_chain=["manifest integrations", "db_exists_check"],
                )
                row.add_source_ref("config", db_path, exists=False)
                row.observed_state = "missing"
                row.coherence_state = "drifted"
                row.gap_codes.append("db_missing")
    elif itype == "llm_provider":
        row.observed_state = "declared"
        row.coherence_state = "declared_only"
        row.add_evidence(
            "process", row.raw.get("env_var", "llm_provider"),
            status="stale",
            provenance_chain=["manifest integrations", "env_var_check_skipped"],
        )
    else:
        row.observed_state = "declared"
        row.coherence_state = "declared_only"


# ---------------------------------------------------------------------------
# F) Feedback loop reality adapter
# ---------------------------------------------------------------------------

def _observe_feedback_loop(row: ControlSurfaceRow, repo_root: Path) -> None:
    module_path_str = row.raw.get("module", "")
    if module_path_str:
        module_file = repo_root / module_path_str
        if module_file.exists():
            row.add_evidence(
                "file", module_path_str,
                status="present",
                provenance_chain=["manifest loops", "file_exists_check"],
            )
            row.add_source_ref("file", module_path_str, exists=True)
            row.freshness = _file_freshness(module_file)
        else:
            row.add_evidence(
                "file", module_path_str,
                status="missing",
                provenance_chain=["manifest loops", "file_exists_check"],
            )
            row.add_source_ref("file", module_path_str, exists=False)
            row.gap_codes.append("module_missing")

    declared = row.declared_state
    if "module_missing" in row.gap_codes:
        row.observed_state = "broken"
        row.coherence_state = "drifted"
    elif declared == "stub":
        row.observed_state = "stub"
        row.coherence_state = "declared_only"
    elif declared == "degraded":
        row.observed_state = "degraded"
        row.coherence_state = "partial"
    else:
        row.observed_state = declared
        row.coherence_state = "bound" if declared == "live" else "partial"


# ---------------------------------------------------------------------------
# G) Recursive discovery shadow adapter
# ---------------------------------------------------------------------------

def _observe_recursive_discovery_shadow(row: ControlSurfaceRow, repo_root: Path) -> None:
    try:
        from dharma_swarm.recursive_discovery import (
            receipt_counts_by_type,
            shadow_fixture_receipts,
        )
    except Exception as exc:
        row.observed_state = "adapter_error"
        row.coherence_state = "drifted"
        row.gap_codes.append("recursive_discovery_adapter_error")
        row.add_evidence(
            "process",
            f"recursive discovery adapter failed: {exc}",
            status="error",
            provenance_chain=["recursive_discovery", "adapter_import"],
        )
        return

    receipts = shadow_fixture_receipts()
    counts = receipt_counts_by_type(receipts)
    receipt_type = row.raw.get("receipt_type", "")
    count = counts.get(receipt_type, 0)
    row.add_source_ref("file", "dharma_swarm/recursive_discovery.py", exists=True)
    row.add_evidence(
        "recursive_receipt",
        f"{receipt_type}: fixture_count={count}",
        status="present" if count else "missing",
        provenance_chain=["recursive_discovery", "shadow_fixture"],
    )
    row.freshness = _file_freshness(repo_root / "dharma_swarm" / "recursive_discovery.py")

    if count:
        row.observed_state = f"shadow_fixture:{count}"
        row.coherence_state = "partial"
        row.gap_codes.append("shadow_only")
        if receipt_type in {"candidate_diff", "promotion_decision"}:
            row.gap_codes.append("human_promotion_required")
    else:
        row.observed_state = "missing_fixture"
        row.coherence_state = "declared_only"
        row.gap_codes.append("fixture_missing")


# ---------------------------------------------------------------------------
# H) Operating facts adapter
# ---------------------------------------------------------------------------

def _operating_facts_rows() -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    try:
        from dharma_swarm.operator_core.operating_facts import (
            organ_state_facts,
        )
        facts = organ_state_facts()
        for fact in facts:
            rid = f"organ.{fact.name}"
            row = ControlSurfaceRow(
                id=rid,
                kind="organ",
                label=fact.name,
                authority_role="observed_authority",
                declared_state=fact.declared_state,
                observed_state=fact.observed_state,
                coherence_state=fact.coherence_state if fact.coherence_state in COHERENCE_STATES else "unknown",
                priority="p1",
                owner_module=fact.name,
                truth_owner="operating_facts",
                gap_codes=[fact.open_gap] if fact.open_gap else [],
                next_action=fact.next_packet_hint,
                freshness=fact.last_observed,
            )
            for ref in fact.evidence_refs:
                row.add_evidence(
                    "file", ref,
                    status="present",
                    provenance_chain=["operating_facts", "organ_state"],
                )
            for store in fact.source_stores:
                row.add_source_ref("file", store, exists=True)
            rows.append(row)
    except Exception as exc:
        logger.warning("operating_facts adapter failed: %s", exc)
    return rows


# ---------------------------------------------------------------------------
# I) Module truth adapter
# ---------------------------------------------------------------------------

def _module_truth_rows() -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    try:
        from api.module_truth import list_truth_modules
        modules = list_truth_modules()
        for mod in modules:
            rid = f"truth.{mod.get('id', mod.get('label', 'unknown')).replace(' ', '_').lower()}"
            row = ControlSurfaceRow(
                id=rid,
                kind="doc_surface",
                label=mod.get("label", "?"),
                authority_role="observed_authority",
                declared_state="",
                observed_state=mod.get("health", "unknown"),
                coherence_state="bound" if mod.get("health") == "ok" else "partial",
                priority="p1",
                owner_module=mod.get("id", ""),
                truth_owner="module_truth",
            )
            row.add_evidence(
                "file", f"score={mod.get('score', '?')}",
                status="present",
                provenance_chain=["module_truth", "score_check"],
            )
            for p in mod.get("paths", []):
                path_str = p.get("path", "")
                if path_str and p.get("exists"):
                    row.add_source_ref("file", path_str, exists=True)
            rows.append(row)
    except Exception as exc:
        logger.warning("module_truth adapter failed: %s", exc)
    return rows


# ---------------------------------------------------------------------------
# J) Broken Register adapter
# ---------------------------------------------------------------------------

def _broken_register_rows(repo_root: Path | None = None) -> list[ControlSurfaceRow]:
    root = repo_root or _repo_root()
    br_path = root / "docs" / "state" / "BROKEN_REGISTER.md"
    result = parse_broken_register(br_path)
    rows: list[ControlSurfaceRow] = []
    for entry in result.open_entries:
        fields = entry.fields
        status_text = entry.raw_status or entry.status
        severity = fields.get("severity", "UNKNOWN")
        domain = fields.get("domain", "")
        row = ControlSurfaceRow(
            id=f"br.{entry.id.lower().replace('-', '_')}",
            kind="broken_register",
            label=f"{entry.id}: {entry.title}",
            authority_role="evidence",
            declared_state=status_text,
            desired_state="FIXED",
            observed_state=status_text,
            coherence_state="drifted" if entry.status == "OPEN" else "partial",
            priority="p0" if severity == "BLOCKER" else "p1" if severity == "DEGRADED" else "p2",
            owner_module=domain,
            truth_owner="BROKEN_REGISTER.md",
            gap_codes=[f"severity:{severity}"],
            next_action=f"close {entry.id}",
            freshness=fields.get("last_verified", ""),
            raw={
                "status": entry.status,
                "is_open_like": entry.is_open_like,
                "is_closed_like": entry.is_closed_like,
            },
        )
        ev_text = fields.get("evidence", "")
        if ev_text:
            row.add_evidence(
                "broken_register", ev_text,
                status="present",
                provenance_chain=["BROKEN_REGISTER.md", entry.id],
            )
        rc_text = fields.get("root_cause", "")
        if rc_text:
            row.add_evidence(
                "broken_register", rc_text,
                status="present",
                provenance_chain=["BROKEN_REGISTER.md", entry.id, "root_cause"],
            )
        row.add_source_ref("file", "docs/state/BROKEN_REGISTER.md", exists=True)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# K) Runtime state adapter
# ---------------------------------------------------------------------------

def _runtime_state_row(
    repo_root: Path | None = None,
    runtime_db: Path | None = None,
) -> ControlSurfaceRow | None:
    db_path = runtime_db or Path.home() / ".dharma" / "state" / "runtime.db"
    if not db_path.exists():
        row = ControlSurfaceRow(
            id="runtime.state_db",
            kind="runtime_store",
            label="Runtime State DB",
            authority_role="observed_authority",
            declared_state="live",
            desired_state="live",
            observed_state="missing",
            coherence_state="drifted",
            priority="p0",
            owner_module="dharma_swarm/runtime_state.py",
            truth_owner="runtime_state",
            gap_codes=["runtime_db_missing"],
        )
        row.add_evidence(
            "db_probe", str(db_path),
            status="missing",
            provenance_chain=["runtime_state", "db_exists_check"],
        )
        row.add_source_ref("file", "dharma_swarm/runtime_state.py", exists=True)
        return row

    freshness = _file_freshness(db_path)
    row = ControlSurfaceRow(
        id="runtime.state_db",
        kind="runtime_store",
        label="Runtime State DB",
        authority_role="observed_authority",
        declared_state="live",
        desired_state="live",
        observed_state="live",
        coherence_state="bound",
        priority="p0",
        owner_module="dharma_swarm/runtime_state.py",
        truth_owner="runtime_state",
        freshness=freshness,
    )
    row.add_evidence(
        "db_probe", str(db_path),
        status="present",
        provenance_chain=["runtime_state", "db_exists_check"],
    )
    row.add_source_ref("file", "dharma_swarm/runtime_state.py", exists=True)

    try:
        from dharma_swarm.operator_core.runtime_truth import connect_runtime_db_read_only

        with connect_runtime_db_read_only(db_path) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            counts: dict[str, int] = {}
            for tbl in ("sessions", "task_claims", "delegation_runs", "session_events",
                        "artifact_records", "context_bundles", "operator_actions"):
                if tbl in tables:
                    cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]  # noqa: S608
                    counts[tbl] = cnt
            summary = ", ".join(f"{k}={v}" for k, v in counts.items())
            row.add_evidence(
                "db_probe", f"tables: {summary}",
                status="present",
                provenance_chain=["runtime_state", "table_count_query"],
            )
            from dharma_swarm.operator_core.runtime_truth import (
                runtime_truth_packets_from_runtime_db,
                summarize_runtime_truth_packets,
            )

            packets = runtime_truth_packets_from_runtime_db(db_path)
            packet_summary = summarize_runtime_truth_packets(packets)
            row.raw["runtime_truth_packets"] = [packet.to_dict() for packet in packets]
            row.raw["runtime_truth_summary"] = packet_summary
            latest_receipt = packet_summary.get("latest_receipt")
            if latest_receipt:
                row.add_evidence(
                    "db_probe",
                    str(latest_receipt),
                    status="present",
                    provenance_chain=[
                        "runtime_state",
                        "sqlite_read_only_probe",
                        "RuntimeTruthPacket",
                    ],
                )
            else:
                row.gap_codes.append("runtime_receipt_missing")
                row.add_evidence(
                    "db_probe",
                    "latest runtime receipt missing",
                    status="missing",
                    provenance_chain=[
                        "runtime_state",
                        "sqlite_read_only_probe",
                        "RuntimeTruthPacket",
                    ],
                )
    except Exception as exc:
        row.add_evidence(
            "db_probe", f"db query error: {exc}",
            status="error",
            provenance_chain=["runtime_state", "table_count_query"],
        )

    return row


# ---------------------------------------------------------------------------
# Projector: build all rows
# ---------------------------------------------------------------------------

def build_control_surface_rows(
    repo_root: Path | None = None,
    runtime_db: Path | None = None,
    memory_depth: str = "snapshot",
) -> list[ControlSurfaceRow]:
    """Build the full control surface projection.

    Reads declared intent from ACTIVE_SURFACE_MANIFEST.yaml.
    Observes reality from code, runtime stores, operating facts,
    module truth, and the broken register.
    """
    root = repo_root or _repo_root()
    manifest = load_active_surface_manifest(root)

    rows: list[ControlSurfaceRow] = []

    # A) Manifest-declared rows
    api_rows = _manifest_api_router_rows(manifest)
    dash_rows = _manifest_dashboard_page_rows(manifest)
    agent_rows = _manifest_agent_rows(manifest)
    integ_rows = _manifest_integration_rows(manifest)
    loop_rows = _manifest_loop_rows(manifest)
    cron_rows = _manifest_cron_rows(manifest)
    state_rows = _manifest_state_writer_rows(manifest)
    recursive_rows = _manifest_recursive_discovery_rows(manifest)

    # B) Observe API router reality
    for row in api_rows:
        _observe_api_router(row, root)
    rows.extend(api_rows)

    # C) Observe dashboard page reality
    for row in dash_rows:
        _observe_dashboard_page(row, root)
    rows.extend(dash_rows)

    # D) Observe agent subsystem reality
    for row in agent_rows:
        _observe_agent_subsystem(row, root)
    rows.extend(agent_rows)

    # E) Observe integration reality
    for row in integ_rows:
        _observe_integration(row, root)
    rows.extend(integ_rows)

    # F) Observe feedback loop reality
    for row in loop_rows:
        _observe_feedback_loop(row, root)
    rows.extend(loop_rows)

    # Cron and state writers (declared only for now)
    for row in cron_rows:
        row.observed_state = row.declared_state
        row.coherence_state = "declared_only"
    rows.extend(cron_rows)

    for row in state_rows:
        row.observed_state = row.declared_state
        row.coherence_state = "declared_only"
    rows.extend(state_rows)

    # G) Recursive discovery shadow receipts (fixture-backed only)
    for row in recursive_rows:
        _observe_recursive_discovery_shadow(row, root)
    rows.extend(recursive_rows)

    # H) Operating facts (organ-level observed reality)
    rows.extend(_operating_facts_rows())

    # I) Module truth (observed evidence for major modules)
    rows.extend(_module_truth_rows())

    # J) Broken register (known structural gaps)
    rows.extend(_broken_register_rows(root))

    # K) Runtime state DB (observed)
    rt_row = _runtime_state_row(root, runtime_db=runtime_db)
    if rt_row is not None:
        rows.append(rt_row)

    # L) Live ops census (observed process/port/receipt projection)
    rows.extend(_live_ops_census_rows(root))

    # M) MemoryKernel operator controls
    memory_projection_depth = "deep" if memory_depth == "deep" else "snapshot"
    rows.extend(memory_kernel_control_rows(root, depth=memory_projection_depth))

    # N) Go receipts (optional)
    rows.extend(_go_receipt_rows(root))

    # O) Spine pulse (read-only cockpit projection over the receipt stream)
    rows.append(_spine_pulse_row(root, runtime_db=runtime_db))

    # Apply human-decision policy with structured context
    for row in rows:
        ctx = _build_human_decision_context(row)
        row.human_decision_required = ctx.required
        row.human_decision = ctx

    # Compute display hints for each row
    for row in rows:
        row.display_hints = _compute_display_hints(row)

    return rows


def build_control_surface_summary(
    rows: list[ControlSurfaceRow] | None = None,
    repo_root: Path | None = None,
    memory_depth: str = "snapshot",
) -> dict[str, Any]:
    """Build a lightweight summary of the control surface."""
    if rows is None:
        rows = build_control_surface_rows(repo_root=repo_root, memory_depth=memory_depth)

    counts: dict[str, int] = {}
    for state in COHERENCE_STATES:
        counts[state] = 0
    for row in rows:
        cs = row.coherence_state if row.coherence_state in COHERENCE_STATES else "unknown"
        counts[cs] = counts.get(cs, 0) + 1

    priority_counts: dict[str, int] = {}
    for p in PRIORITIES:
        priority_counts[p] = sum(1 for r in rows if r.priority == p)

    human_count = sum(1 for r in rows if r.human_decision_required)

    sources: list[str] = [
        "ACTIVE_SURFACE_MANIFEST.yaml",
        "operating_facts",
        "module_truth",
        "BROKEN_REGISTER.md",
        "runtime_state",
        "live_ops_census",
        "go_sdk",
        "recursive_discovery_shadow",
        "MemoryKernel",
        "operator_prod_smoke",
        "code/filesystem",
    ]

    return {
        "total": len(rows),
        "bound": counts.get("bound", 0),
        "partial": counts.get("partial", 0),
        "drifted": counts.get("drifted", 0),
        "declared_only": counts.get("declared_only", 0),
        "unknown": counts.get("unknown", 0),
        "human_decision_required_count": human_count,
        "p0_count": priority_counts.get("p0", 0),
        "p1_count": priority_counts.get("p1", 0),
        "generated_at": _utc_now_iso(),
        "sources_consulted": sources,
    }
