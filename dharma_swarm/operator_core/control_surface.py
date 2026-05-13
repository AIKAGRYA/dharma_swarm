"""Control Surface Projector v0.

Reconciles ACTIVE_SURFACE_MANIFEST.yaml (declared intent) with runtime,
code, evidence, and documentation observations.  Produces typed rows that
the dashboard renders as an operator cockpit grid.

ACTIVE_SURFACE_MANIFEST.yaml declares intent; observed reality comes from
runtime/code/evidence adapters.  The manifest is *not* the single source
of truth -- it is the declared-intent layer only.
"""

from __future__ import annotations

import importlib
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured sub-models (Pydantic 2)
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """Structured evidence item with provenance."""

    kind: Literal[
        "file", "manifest_row", "api_route", "db_probe",
        "go_receipt", "broken_register", "process", "test",
    ]
    source: str
    line_range: tuple[int, int] | None = None
    observed_at: str = ""
    raw_content: str | None = None
    status: str | None = None
    provenance_chain: list[str] = []


class SourceRef(BaseModel):
    """Structured reference to a source file/route/config."""

    kind: Literal["file", "manifest_section", "api_route", "config", "go_module"]
    path: str
    exists: bool = True
    line_range: tuple[int, int] | None = None


class HumanDecisionContext(BaseModel):
    """Context for why a row requires human decision."""

    required: bool
    why_now: str = ""
    recommended_action: str = ""
    evidence_count: int = 0
    staleness_hours: float | None = None


class VerificationEvent(BaseModel):
    """Timeline event for how a surface moved through declare→drift→fix→verify."""

    timestamp: str
    event_type: Literal[
        "observed", "drift_detected", "fix_attempted",
        "fix_verified", "closure",
    ]
    detail: str
    agent_id: str | None = None


class AgentHandoffPrompt(BaseModel):
    """Scoped agent prompt generated from a control surface row."""

    row_id: str
    label: str
    prompt_text: str
    context_files: list[str]
    expected_tests: list[str]
    invariant: str
    generated_at: str


# ---------------------------------------------------------------------------
# Row contract
# ---------------------------------------------------------------------------

COHERENCE_STATES = ("bound", "partial", "drifted", "declared_only", "unknown")
AUTHORITY_ROLES = (
    "declared_authority",
    "observed_authority",
    "projection",
    "adapter",
    "evidence",
    "incubating",
    "frozen",
    "unknown",
)
PRIORITIES = ("p0", "p1", "p2", "backlog", "unknown")
ROW_KINDS = (
    "api_router",
    "dashboard_page",
    "runtime_store",
    "state_writer",
    "organ",
    "fleet",
    "memory_surface",
    "broken_register",
    "go_receipt",
    "doc_surface",
    "integration",
    "feedback_loop",
    "agent_subsystem",
    "cron_job",
)


@dataclass
class ControlSurfaceRow:
    """One row in the operator cockpit grid."""

    id: str
    kind: str
    label: str
    authority_role: str = "unknown"
    declared_state: str = ""
    desired_state: str = ""
    observed_state: str = ""
    coherence_state: str = "unknown"
    priority: str = "unknown"
    owner_module: str = ""
    truth_owner: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)
    evidence_labels: list[str] = field(default_factory=list)
    freshness: str = ""
    gap_codes: list[str] = field(default_factory=list)
    next_action: str = ""
    human_decision_required: bool = False
    human_decision: HumanDecisionContext | None = None
    source_refs: list[SourceRef] = field(default_factory=list)
    source_ref_labels: list[str] = field(default_factory=list)
    verification_timeline: list[VerificationEvent] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    # -- helpers for appending structured evidence/refs ----

    def add_evidence(
        self,
        kind: str,
        source: str,
        *,
        status: str | None = None,
        line_range: tuple[int, int] | None = None,
        raw_content: str | None = None,
        provenance_chain: list[str] | None = None,
    ) -> None:
        item = EvidenceItem(
            kind=kind,  # type: ignore[arg-type]
            source=source,
            observed_at=_utc_now_iso(),
            status=status,
            line_range=line_range,
            raw_content=raw_content[:500] if raw_content else None,
            provenance_chain=provenance_chain or [],
        )
        self.evidence.append(item)
        self.evidence_labels.append(source)

    def add_source_ref(
        self,
        kind: str,
        path: str,
        *,
        exists: bool = True,
        line_range: tuple[int, int] | None = None,
    ) -> None:
        ref = SourceRef(
            kind=kind,  # type: ignore[arg-type]
            path=path,
            exists=exists,
            line_range=line_range,
        )
        self.source_refs.append(ref)
        self.source_ref_labels.append(path)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = [e.model_dump() for e in self.evidence]
        d["source_refs"] = [s.model_dump() for s in self.source_refs]
        if self.human_decision is not None:
            d["human_decision"] = self.human_decision.model_dump()
        d["verification_timeline"] = [
            v.model_dump() for v in self.verification_timeline
        ]
        return d


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
# Human-decision policy
# ---------------------------------------------------------------------------

_HUMAN_DECISION_KEYWORDS = (
    "auth", "credential", "vps", "node_gateway", "destructive",
    "hot-path", "hot_path",
)


def _needs_human_decision(row: ControlSurfaceRow) -> bool:
    if row.kind in ("runtime_store", "state_writer", "fleet") and row.authority_role == "incubating":
        return True
    if row.priority == "p0" and row.coherence_state in ("drifted", "unknown"):
        return True
    if row.authority_role == "incubating" and row.desired_state == "live":
        return True
    if row.kind == "broken_register" and "OPEN" in row.declared_state.upper():
        return True
    label_lower = row.label.lower()
    for kw in _HUMAN_DECISION_KEYWORDS:
        if kw in label_lower or kw in row.owner_module.lower():
            return True
    return False


def _build_human_decision_context(row: ControlSurfaceRow) -> HumanDecisionContext:
    """Build structured human-decision context for a row."""
    required = _needs_human_decision(row)
    if not required:
        return HumanDecisionContext(
            required=False,
            evidence_count=len(row.evidence),
        )

    why_now = ""
    recommended_action = ""

    if row.kind in ("runtime_store", "state_writer", "fleet") and row.authority_role == "incubating":
        why_now = f"Incubating {row.kind} wants to go live"
        recommended_action = f"Review {row.label} and promote or archive"
    elif row.priority == "p0" and row.coherence_state == "drifted":
        why_now = "P0 surface has drifted from declared state"
        recommended_action = f"Investigate drift in {row.owner_module or row.label}"
    elif row.priority == "p0" and row.coherence_state == "unknown":
        why_now = "P0 surface has unknown coherence — no observation yet"
        recommended_action = f"Run observation for {row.label}"
    elif row.authority_role == "incubating" and row.desired_state == "live":
        why_now = "Incubating surface declared as desired=live"
        recommended_action = f"Implement or promote {row.label}"
    elif row.kind == "broken_register" and "OPEN" in row.declared_state.upper():
        why_now = f"Open broken register entry: {row.label}"
        recommended_action = f"Fix root cause and close {row.id.replace('br.', 'BR-').replace('_', '-')}"
    else:
        for kw in _HUMAN_DECISION_KEYWORDS:
            if kw in row.label.lower() or kw in row.owner_module.lower():
                why_now = f"Sensitive keyword '{kw}' detected in surface"
                recommended_action = f"Review {row.label} before automated changes"
                break

    staleness_hours: float | None = None
    if row.freshness:
        try:
            observed_dt = datetime.fromisoformat(row.freshness)
            delta = datetime.now(timezone.utc) - observed_dt
            staleness_hours = round(delta.total_seconds() / 3600, 1)
        except (ValueError, TypeError):
            pass

    return HumanDecisionContext(
        required=True,
        why_now=why_now,
        recommended_action=recommended_action,
        evidence_count=len(row.evidence),
        staleness_hours=staleness_hours,
    )


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
# G) Operating facts adapter
# ---------------------------------------------------------------------------

def _operating_facts_rows() -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    try:
        from dharma_swarm.operator_core.operating_facts import (
            ORGAN_BOUNDARIES,
            OrganStateFact,
            organ_state_facts,
        )
        facts = organ_state_facts()
        now = _utc_now_iso()
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
# H) Module truth adapter
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
# I) Broken Register adapter
# ---------------------------------------------------------------------------

_BR_PATTERN = re.compile(
    r"^###\s+(BR-\d+)\s*[—–-]\s*(.+)$",
    re.MULTILINE,
)
_BR_FIELD = re.compile(r"^-\s+\*\*(\w[\w_]*)\*?\*?:\*?\*?\s*(.+)$", re.MULTILINE)


def _broken_register_rows(repo_root: Path | None = None) -> list[ControlSurfaceRow]:
    root = repo_root or _repo_root()
    br_path = root / "docs" / "state" / "BROKEN_REGISTER.md"
    if not br_path.exists():
        return []
    text = br_path.read_text(errors="ignore")
    rows: list[ControlSurfaceRow] = []

    in_open_section = False
    for line in text.splitlines():
        if line.startswith("## OPEN ITEMS") or line.startswith("## OPEN"):
            in_open_section = True
            continue
        if line.startswith("## CLOSED"):
            in_open_section = False
            continue

    chunks = _BR_PATTERN.split(text)
    i = 1
    while i + 1 < len(chunks):
        br_id = chunks[i]
        title = chunks[i + 1].strip()
        body_start = text.find(f"### {br_id}")
        if body_start < 0:
            i += 3
            continue
        next_heading = text.find("\n### BR-", body_start + 1)
        next_closed = text.find("\n## CLOSED", body_start + 1)
        end = len(text)
        if next_heading > 0:
            end = min(end, next_heading)
        if next_closed > 0:
            end = min(end, next_closed)
        body = text[body_start:end]

        fields: dict[str, str] = {}
        for fm in _BR_FIELD.finditer(body):
            fields[fm.group(1).lower()] = fm.group(2).strip()

        status_text = fields.get("status", "OPEN")
        severity = fields.get("severity", "UNKNOWN")
        domain = fields.get("domain", "")

        is_closed = "CLOSED" in text[max(0, body_start - 200):body_start].upper()
        if is_closed or "FIXED" in status_text.upper():
            i += 3
            continue

        row = ControlSurfaceRow(
            id=f"br.{br_id.lower().replace('-', '_')}",
            kind="broken_register",
            label=f"{br_id}: {title}",
            authority_role="evidence",
            declared_state=status_text,
            desired_state="FIXED",
            observed_state=status_text,
            coherence_state="drifted" if "OPEN" in status_text.upper() else "partial",
            priority="p0" if severity == "BLOCKER" else "p1" if severity == "DEGRADED" else "p2",
            owner_module=domain,
            truth_owner="BROKEN_REGISTER.md",
            gap_codes=[f"severity:{severity}"],
            next_action=f"close {br_id}",
            freshness=fields.get("last_verified", ""),
        )
        ev_text = fields.get("evidence", "")
        if ev_text:
            row.add_evidence(
                "broken_register", ev_text,
                status="present",
                provenance_chain=["BROKEN_REGISTER.md", br_id],
            )
        rc_text = fields.get("root_cause", "")
        if rc_text:
            row.add_evidence(
                "broken_register", rc_text,
                status="present",
                provenance_chain=["BROKEN_REGISTER.md", br_id, "root_cause"],
            )
        row.add_source_ref("file", "docs/state/BROKEN_REGISTER.md", exists=True)
        rows.append(row)
        i += 3

    return rows


# ---------------------------------------------------------------------------
# J) Runtime state adapter
# ---------------------------------------------------------------------------

def _runtime_state_row(repo_root: Path | None = None) -> ControlSurfaceRow | None:
    db_path = Path.home() / ".dharma" / "state" / "runtime.db"
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
        import sqlite3
        with sqlite3.connect(str(db_path)) as conn:
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
    except Exception as exc:
        row.add_evidence(
            "db_probe", f"db query error: {exc}",
            status="error",
            provenance_chain=["runtime_state", "table_count_query"],
        )

    return row


# ---------------------------------------------------------------------------
# K) Go receipt adapter (optional)
# ---------------------------------------------------------------------------

def _go_receipt_rows(repo_root: Path | None = None) -> list[ControlSurfaceRow]:
    root = repo_root or _repo_root()
    rows: list[ControlSurfaceRow] = []

    bridge_path = root / "dharma_swarm" / "go_evidence_bridge.py"
    if bridge_path.exists():
        row = ControlSurfaceRow(
            id="go.evidence_bridge",
            kind="go_receipt",
            label="Go Evidence Bridge",
            authority_role="adapter",
            declared_state="incubating",
            desired_state="live",
            observed_state="file present",
            coherence_state="partial",
            priority="p2",
            owner_module="dharma_swarm/go_evidence_bridge.py",
            truth_owner="go_sdk",
        )
        row.add_evidence(
            "go_receipt", str(bridge_path.relative_to(root)),
            status="present",
            provenance_chain=["go_sdk", "bridge_file_check"],
        )
        row.add_source_ref("go_module", "dharma_swarm/go_evidence_bridge.py", exists=True)
        rows.append(row)

    receipt_go = root / "tools" / "go_sdk" / "receipt" / "receipt.go"
    if receipt_go.exists():
        row = ControlSurfaceRow(
            id="go.receipt_sdk",
            kind="go_receipt",
            label="Go Receipt SDK",
            authority_role="evidence",
            declared_state="incubating",
            desired_state="live",
            observed_state="file present",
            coherence_state="partial",
            priority="p2",
            owner_module="tools/go_sdk/receipt/receipt.go",
            truth_owner="go_sdk",
        )
        row.add_evidence(
            "go_receipt", str(receipt_go.relative_to(root)),
            status="present",
            provenance_chain=["go_sdk", "receipt_file_check"],
        )
        row.add_source_ref("go_module", "tools/go_sdk/receipt/receipt.go", exists=True)
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Projector: build all rows
# ---------------------------------------------------------------------------

def build_control_surface_rows(
    repo_root: Path | None = None,
    runtime_db: Path | None = None,
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

    # G) Operating facts (organ-level observed reality)
    rows.extend(_operating_facts_rows())

    # H) Module truth (observed evidence for major modules)
    rows.extend(_module_truth_rows())

    # I) Broken register (known structural gaps)
    rows.extend(_broken_register_rows(root))

    # J) Runtime state DB (observed)
    rt_row = _runtime_state_row(root)
    if rt_row is not None:
        rows.append(rt_row)

    # K) Go receipts (optional)
    rows.extend(_go_receipt_rows(root))

    # Apply human-decision policy with structured context
    for row in rows:
        ctx = _build_human_decision_context(row)
        row.human_decision_required = ctx.required
        row.human_decision = ctx

    return rows


def build_control_surface_summary(
    rows: list[ControlSurfaceRow] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Build a lightweight summary of the control surface."""
    if rows is None:
        rows = build_control_surface_rows(repo_root=repo_root)

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


# ---------------------------------------------------------------------------
# Agent Handoff Prompt Generation
# ---------------------------------------------------------------------------

_KIND_FIX_TEMPLATES: dict[str, str] = {
    "api_router": "Implement or fix the API router so it is registered and responds correctly.",
    "dashboard_page": "Create or repair the dashboard page so it renders the declared UI.",
    "agent_subsystem": "Wire the agent module so it can be dispatched by the orchestrator.",
    "broken_register": "Fix the root cause described in the broken register entry.",
    "feedback_loop": "Close the feedback loop so sense→act→evaluate→adapt completes.",
    "integration": "Connect the integration so the declared dependency is satisfied.",
    "runtime_store": "Ensure the runtime store is present and populated with the expected schema.",
    "organ": "Bring the organ into coherence with its declared boundary.",
}


def generate_handoff_prompt(
    row: ControlSurfaceRow,
    repo_root: Path | None = None,
) -> AgentHandoffPrompt:
    """Generate a scoped agent prompt for fixing a control surface row."""
    root = repo_root or _repo_root()

    context_files: list[str] = []
    for ref in row.source_refs:
        if ref.kind in ("file", "go_module") and ref.path:
            context_files.append(ref.path)
    if row.owner_module:
        mod_path = row.owner_module.replace(".", "/")
        if not mod_path.endswith(".py"):
            mod_path += ".py"
        if mod_path not in context_files:
            context_files.append(mod_path)

    expected_tests: list[str] = []
    if row.owner_module:
        stem = Path(row.owner_module.replace(".", "/")).stem
        test_file = f"tests/test_{stem}.py"
        expected_tests.append(test_file)
    for ref in row.source_refs:
        if ref.kind == "file" and ref.path.startswith("tests/"):
            if ref.path not in expected_tests:
                expected_tests.append(ref.path)

    fix_type = _KIND_FIX_TEMPLATES.get(row.kind, "Bring this surface into coherence.")
    gap_desc = ", ".join(row.gap_codes) if row.gap_codes else "none detected"

    evidence_block = ""
    for ev in row.evidence[:10]:
        evidence_block += f"  - [{ev.kind}] {ev.source} (status={ev.status})\n"

    invariant = (
        f"The declared state is '{row.declared_state}' with desired state "
        f"'{row.desired_state}'. After your fix, the coherence_state must be "
        f"'bound' (declared == observed). Do not break other surfaces."
    )

    prompt_text = f"""## Agent Handoff: {row.label}

**Row ID:** {row.id}
**Kind:** {row.kind}
**Coherence:** {row.coherence_state}
**Priority:** {row.priority}
**Gap Codes:** {gap_desc}

### What needs to happen
{fix_type}

### Current Evidence
{evidence_block}
### Context Files (read these first)
{chr(10).join(f"- {f}" for f in context_files)}

### Expected Tests
{chr(10).join(f"- {t}" for t in expected_tests)}

### Invariant
{invariant}

### Anti-slop Gates
- No decorative changes. Every edit must trace to this ControlSurfaceRow.
- Commit messages must include [impact-checked].
- Run `pytest {' '.join(expected_tests)}` before committing.
"""

    return AgentHandoffPrompt(
        row_id=row.id,
        label=row.label,
        prompt_text=prompt_text.strip(),
        context_files=context_files,
        expected_tests=expected_tests,
        invariant=invariant,
        generated_at=_utc_now_iso(),
    )
