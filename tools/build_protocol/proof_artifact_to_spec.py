"""ProofArtifact contract -> whole-organism closure build spec.

This is the adapter named by the Agentic Era Immune System packet.  It does not
try to make ProofArtifact the center of Dharma Swarm.  It uses one
ProofArtifact as a tracer object and asks whether the existing organs can bind
to it: lodestones/source synthesis, telos gates, Thinkodynamic direction,
Shakti selection, Viveka challenge, Memory authority, Kalyan feedback, Agora
witness, and guarded Evolution.

The tool is intentionally bounded:

* reads one ``proof_artifact_contract.json`` and referenced packet files,
* writes an optional closure report next to the packet,
* writes one Pilot-00-compatible spec,
* does not mutate runtime DBs, opportunity boards, ontology rows, agents, or
  source files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.build_protocol.brief_to_spec import DEFAULT_FORBIDDEN_PATHS

CORE_ORGANS: tuple[str, ...] = (
    "Lodestones",
    "Telos",
    "ThinkodynamicDirector",
    "Shakti",
    "Viveka",
    "MemoryKernel",
    "Kalyan",
    "Agora/SABP",
    "Evolution",
    "HumanOperator",
)

DEFAULT_PROOF_COMMAND = (
    "pytest tests/test_proof_artifact_to_spec.py tests/test_build_protocol_cli.py -q"
)

WITNESS_MANDALA_REQUIRED_ROLES: tuple[str, ...] = (
    "formal",
    "engineering",
    "adversarial",
    "economic",
    "ecological_social",
    "human_telos",
)

WITNESS_MANDALA_REQUIRED_FIELDS: tuple[str, ...] = (
    "role",
    "stance",
    "strongest_affirmation",
    "strongest_objection",
    "what_would_make_this_false",
    "evidence_required_to_upgrade",
    "protected_value",
    "next_test",
    "confidence",
)


@dataclass(frozen=True)
class ClosureCheck:
    """One organ-binding check in the closure preflight."""

    organ: str
    name: str
    status: str
    detail: str
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "organ": self.organ,
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class ProofArtifactSelection:
    """Normalized paths and contract data for one ProofArtifact."""

    contract: dict[str, Any]
    contract_path: Path
    repo_root: Path
    packet_dir: Path

    @property
    def artifact_id(self) -> str:
        return str(self.contract.get("artifact_id") or self.title)

    @property
    def title(self) -> str:
        return str(self.contract.get("title") or "Proof Artifact").strip()

    @property
    def status(self) -> str:
        return str(self.contract.get("status") or "unknown")


def load_contract(contract_path: Path, *, repo_root: Path | None = None) -> ProofArtifactSelection:
    """Load and normalize a proof artifact contract."""
    resolved = contract_path.expanduser().resolve()
    contract = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise ValueError(f"contract is not a JSON object: {resolved}")
    root = (repo_root or _find_repo_root(resolved.parent)).expanduser().resolve()
    return ProofArtifactSelection(
        contract=contract,
        contract_path=resolved,
        repo_root=root,
        packet_dir=resolved.parent,
    )


def run_closure_preflight(
    selection: ProofArtifactSelection,
    *,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Run bounded organ-binding checks and return a serializable report."""
    checks: list[ClosureCheck] = []
    contract = selection.contract
    title = selection.title
    telos = _telos_text(contract)
    packet_text = _read_packet_text(selection)

    checks.extend(_contract_shape_checks(selection))
    checks.extend(_spine_binding_checks(selection))
    checks.extend(_witness_mandala_checks(selection))
    checks.extend(_evidence_surface_checks(selection))
    checks.extend(_memory_authority_checks())
    checks.extend(_telos_and_viveka_checks(selection, telos, packet_text, report_path=report_path))
    checks.extend(_metabolic_binding_checks(selection))
    checks.extend(_evolution_binding_checks(selection))

    summary = _summarize_checks(checks)
    report = {
        "kind": "whole_organism_closure_run",
        "version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_id": selection.artifact_id,
        "title": title,
        "contract_path": _display_path(selection.contract_path, selection.repo_root),
        "contract_status": selection.status,
        "core_organs": list(CORE_ORGANS),
        "summary": summary,
        "checks": [check.to_dict() for check in checks],
        "decision": _closure_decision(summary),
        "next_required_wires": _next_required_wires(checks),
    }
    return report


def render_spec(
    selection: ProofArtifactSelection,
    closure_report: dict[str, Any],
    *,
    today: date | None = None,
    reviewer: str = "codex-reviewer",
    proof_command: str = DEFAULT_PROOF_COMMAND,
) -> str:
    """Render a Pilot-00-compatible markdown spec from a closure report."""
    today = today or date.today()
    slug = _slugify(f"proof-artifact-{selection.title}-closure")
    contract = selection.contract
    title = f"proof-artifact-{today.isoformat()}-{slug}"
    allowed = _allowed_paths(selection)
    forbidden = tuple(dict.fromkeys(DEFAULT_FORBIDDEN_PATHS))
    telos = _spec_telos(selection)
    decision = closure_report.get("decision", {})
    next_wires = closure_report.get("next_required_wires", [])
    summary = closure_report.get("summary", {})

    lines: list[str] = [
        f"# {title}",
        "",
        "<!-- Generated by tools/build_protocol/proof_artifact_to_spec.py.",
        f"     Source contract: {_display_path(selection.contract_path, selection.repo_root)}",
        f"     Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "     This is a whole-organism tracer spec, not a product manifesto. -->",
        "",
        f"Telos: {telos}",
        "",
        "Allowed paths:",
    ]
    lines += [f"- {path}" for path in allowed]
    lines += ["", "Forbidden paths:"]
    lines += [f"- {path}" for path in forbidden]
    lines += [
        "",
        f"Proof command: {proof_command}",
        "",
        f"Reviewer: {reviewer}",
        "",
        "## Whole-organism closure frame",
        "",
        f"- artifact_id: {selection.artifact_id}",
        f"- artifact_title: {selection.title}",
        f"- contract_status: {selection.status}",
        f"- internal_wedge: {contract.get('internal_wedge', 'unknown')}",
        f"- parent_venture_cell_status: {_venture_cell_status(contract)}",
        "",
        "## Organs this spec must preserve",
        "",
    ]
    lines += [f"- {organ}" for organ in CORE_ORGANS]
    lines += [
        "",
        "## Preflight summary",
        "",
        f"- pass: {summary.get('pass', 0)}",
        f"- warn: {summary.get('warn', 0)}",
        f"- fail: {summary.get('fail', 0)}",
        f"- pending: {summary.get('pending', 0)}",
        f"- decision: {decision.get('status', 'unknown')} - {decision.get('reason', 'no reason recorded')}",
        "",
        "## Next required wires",
        "",
    ]
    if next_wires:
        lines += [f"- {wire}" for wire in next_wires]
    else:
        lines += ["- No missing wire was detected by the preflight."]

    lines += [
        "",
        "## Work order",
        "",
        "Create the next smallest closure improvement that binds this artifact back into the organism.",
        "Do not broaden the product surface, add autonomous live mutation, or rename the organs.",
        "The expected output is a bounded improvement to the packet/adapter/gate path that can be sealed and Darwin-shadow-applied.",
        "",
        "## Source report",
        "",
        f"`{_display_path(_default_report_path(selection), selection.repo_root)}`",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_report(report: dict[str, Any], report_path: Path) -> Path:
    """Write a closure report JSON file."""
    path = report_path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_spec(
    spec_text: str,
    *,
    output_dir: Path | None = None,
    title_slug: str,
    today: date | None = None,
) -> Path:
    """Write spec_text to ~/.dharma/build_protocol/specs/<date>-<slug>.md."""
    today = today or date.today()
    output_dir = (output_dir or Path.home() / ".dharma" / "build_protocol" / "specs").expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{today.isoformat()}-{title_slug}.md"
    out_path.write_text(spec_text, encoding="utf-8")
    return out_path


def proof_artifact_to_spec(
    contract_path: Path,
    *,
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    report_path: Path | None = None,
    today: date | None = None,
) -> Path:
    """End-to-end: write closure report, write Pilot-00 spec, return spec path."""
    selection = load_contract(contract_path, repo_root=repo_root)
    resolved_report_path = report_path or _default_report_path(selection)
    report = run_closure_preflight(selection, report_path=resolved_report_path)
    write_report(report, resolved_report_path)
    slug = _slugify(f"proof-artifact-{selection.title}-closure") or "proof-artifact-closure"
    spec_text = render_spec(selection, report, today=today)
    return write_spec(spec_text, output_dir=output_dir, title_slug=slug, today=today)


def _contract_shape_checks(selection: ProofArtifactSelection) -> list[ClosureCheck]:
    contract = selection.contract
    checks: list[ClosureCheck] = []
    for field in ("artifact_id", "title", "telos", "minimum_viable_artifact", "spine_bindings"):
        if field in contract and contract[field]:
            checks.append(ClosureCheck("HumanOperator", f"contract.{field}", "pass", "Contract field present."))
        else:
            checks.append(ClosureCheck("HumanOperator", f"contract.{field}", "fail", "Required contract field missing."))

    mva = contract.get("minimum_viable_artifact") or {}
    artifact_path = _resolve(selection, mva.get("path"))
    if artifact_path and artifact_path.is_file():
        checks.append(
            ClosureCheck(
                "ProofArtifact",
                "minimum_viable_artifact.path",
                "pass",
                "Minimum viable artifact exists.",
                (_display_path(artifact_path, selection.repo_root),),
            )
        )
    else:
        checks.append(
            ClosureCheck(
                "ProofArtifact",
                "minimum_viable_artifact.path",
                "fail",
                "Minimum viable artifact is missing or unresolved.",
                (str(mva.get("path") or ""),),
            )
        )
    return checks


def _spine_binding_checks(selection: ProofArtifactSelection) -> list[ClosureCheck]:
    bindings = selection.contract.get("spine_bindings") or {}
    checks: list[ClosureCheck] = []
    path_bindings = {
        "source_synthesis": "Lodestones",
        "claim_register": "Viveka",
        "human_operator_brief": "HumanOperator",
        "organ_wiring_matrix": "ThinkodynamicDirector",
        "build_spec": "Evolution",
    }
    for key, organ in path_bindings.items():
        raw = bindings.get(key)
        path = _resolve(selection, raw)
        status = "pass" if path and path.is_file() else "fail"
        detail = "Binding path exists." if status == "pass" else "Binding path missing."
        evidence = (_display_path(path, selection.repo_root),) if path else (str(raw or ""),)
        checks.append(ClosureCheck(organ, f"spine_bindings.{key}", status, detail, evidence))

    pending_bindings = {
        "sABP_submission": "Agora/SABP",
        "witness_link_id": "Agora/SABP",
        "outcome_id": "Kalyan",
        "value_event_id": "Kalyan",
        "opportunity_id": "Shakti",
    }
    for key, organ in pending_bindings.items():
        value = str(bindings.get(key) or "").strip()
        if value and value.lower() != "pending":
            checks.append(ClosureCheck(organ, f"spine_bindings.{key}", "pass", "Runtime binding is present.", (value,)))
        else:
            checks.append(
                ClosureCheck(
                    organ,
                    f"spine_bindings.{key}",
                    "pending",
                    "Runtime binding is not present yet; this is a required future wire.",
                )
            )

    contributions = bindings.get("contribution_ids")
    if isinstance(contributions, list) and contributions:
        checks.append(
            ClosureCheck("Kalyan", "spine_bindings.contribution_ids", "pass", "Contribution IDs are present.", tuple(map(str, contributions)))
        )
    else:
        checks.append(
            ClosureCheck("Kalyan", "spine_bindings.contribution_ids", "pending", "No contribution IDs recorded yet.")
        )
    return checks


def _witness_mandala_checks(selection: ProofArtifactSelection) -> list[ClosureCheck]:
    cfg = selection.contract.get("witness_mandala")
    bindings = selection.contract.get("spine_bindings") or {}
    required = False
    claim_path_raw: Any = bindings.get("sabp_claim_path")
    if isinstance(cfg, Mapping):
        required = bool(cfg.get("required", False))
        claim_path_raw = cfg.get("claim_path") or claim_path_raw
    if not required and not claim_path_raw:
        return []

    claim_path = _resolve(selection, claim_path_raw)
    if not claim_path or not claim_path.is_file():
        status = "pending" if required else "warn"
        return [
            ClosureCheck(
                "Agora/SABP",
                "witness_mandala",
                status,
                "Witness Mandala claim path is missing or unresolved.",
                (str(claim_path_raw or ""),),
            )
        ]

    try:
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [
            ClosureCheck(
                "Agora/SABP",
                "witness_mandala",
                "warn",
                f"Witness Mandala claim JSON could not be read: {exc}",
                (_display_path(claim_path, selection.repo_root),),
            )
        ]
    if not isinstance(claim, Mapping):
        return [
            ClosureCheck(
                "Agora/SABP",
                "witness_mandala",
                "warn",
                "Witness Mandala claim file is not a JSON object.",
                (_display_path(claim_path, selection.repo_root),),
            )
        ]

    mandala = claim.get("witness_mandala")
    if not isinstance(mandala, Mapping):
        status = "pending" if required else "warn"
        return [
            ClosureCheck(
                "Agora/SABP",
                "witness_mandala",
                status,
                "Witness Mandala is not present on the SABP claim.",
                (_display_path(claim_path, selection.repo_root),),
            )
        ]

    records = [
        record
        for record in mandala.get("records", [])
        if isinstance(record, Mapping)
    ]
    by_role = {
        str(record.get("role") or "").strip(): record
        for record in records
        if str(record.get("role") or "").strip()
    }
    missing_roles = [
        role for role in WITNESS_MANDALA_REQUIRED_ROLES if role not in by_role
    ]
    incomplete_roles = [
        role
        for role, record in by_role.items()
        if role in WITNESS_MANDALA_REQUIRED_ROLES
        and not _mandala_record_complete(record)
    ]
    if missing_roles or incomplete_roles:
        detail_parts: list[str] = []
        if missing_roles:
            detail_parts.append("missing roles: " + ", ".join(missing_roles))
        if incomplete_roles:
            detail_parts.append("incomplete roles: " + ", ".join(incomplete_roles))
        return [
            ClosureCheck(
                "Agora/SABP",
                "witness_mandala",
                "pending" if required else "warn",
                "; ".join(detail_parts),
                tuple(sorted(by_role)),
            )
        ]

    return [
        ClosureCheck(
            "Agora/SABP",
            "witness_mandala",
            "pass",
            "Witness Mandala has all pressure roles with objections, falsifiers, protected values, and next tests.",
            tuple(WITNESS_MANDALA_REQUIRED_ROLES),
        )
    ]


def _evidence_surface_checks(selection: ProofArtifactSelection) -> list[ClosureCheck]:
    surfaces = selection.contract.get("evidence_surfaces") or {}
    checks: list[ClosureCheck] = []
    for group, values in surfaces.items():
        if not isinstance(values, list):
            checks.append(ClosureCheck("MemoryKernel", f"evidence_surfaces.{group}", "warn", "Evidence surface group is not a list."))
            continue
        present = 0
        missing = 0
        references: list[str] = []
        for value in values:
            raw = str(value)
            path = _resolve(selection, raw)
            if _looks_like_path(raw):
                if path and path.exists():
                    present += 1
                    references.append(_display_path(path, selection.repo_root))
                else:
                    missing += 1
                    references.append(raw)
            else:
                references.append(raw)
        if missing:
            status = "warn" if present else "pending"
            detail = f"{present} path reference(s) present; {missing} missing or outside this checkout."
        else:
            status = "pass"
            detail = f"{present} inspectable path reference(s); non-path references are treated as external claims."
        checks.append(
            ClosureCheck("MemoryKernel", f"evidence_surfaces.{group}", status, detail, tuple(references[:8]))
        )
    return checks


def _memory_authority_checks() -> list[ClosureCheck]:
    try:
        from dharma_swarm.memory_kernel.surfaces import default_surface_specs
    except Exception as exc:
        return [
            ClosureCheck(
                "MemoryKernel",
                "memory_surface_registry",
                "pending",
                f"Memory surface registry could not be imported: {exc}",
            )
        ]

    specs = default_surface_specs()
    source_truth = {
        spec.surface_id: tuple(spec.source_of_truth_for)
        for spec in specs
        if getattr(spec, "source_of_truth_for", ())
    }
    needed = ("home.memory_plane", "home.runtime_state")
    missing = [surface for surface in needed if surface not in source_truth]
    if missing:
        return [
            ClosureCheck(
                "MemoryKernel",
                "memory_authority_labels",
                "warn",
                f"Missing authority labels for: {', '.join(missing)}",
                tuple(sorted(source_truth)),
            )
        ]
    return [
        ClosureCheck(
            "MemoryKernel",
            "memory_authority_labels",
            "pass",
            "Runtime and evidence source-of-truth labels are present.",
            tuple(f"{key}: {', '.join(value)}" for key, value in source_truth.items() if key in needed),
        )
    ]


def _telos_and_viveka_checks(
    selection: ProofArtifactSelection,
    telos: str,
    packet_text: str,
    *,
    report_path: Path | None,
) -> list[ClosureCheck]:
    checks: list[ClosureCheck] = []
    content = _clip(packet_text, 12000)
    try:
        from dharma_swarm import telos_gates as tg

        witness_dir = (report_path or _default_report_path(selection)).parent / "witness"
        old_witness_dir = tg.WITNESS_DIR
        tg.WITNESS_DIR = witness_dir
        try:
            gatekeeper = tg.TelosGatekeeper(
                registry=tg.GateRegistry(
                    proposals_file=witness_dir / "gate_proposals.jsonl",
                )
            )
            result = gatekeeper.check(
                action=f"whole-organism closure preflight for {selection.title}",
                content=f"{telos}\n\n{content}",
                tool_name="proof_artifact_to_spec",
                trust_mode="external_strict",
                think_phase="before_complete",
                reflection=(
                    "Before converting this proof artifact into a build spec, I verified "
                    "risk, rollback path, evidence limits, and tests. If this fails, the "
                    "generated report and spec can be deleted without runtime state changes."
                ),
            )
        finally:
            tg.WITNESS_DIR = old_witness_dir
        checks.append(
            ClosureCheck(
                "Telos",
                "telos_gatekeeper",
                "pass" if result.decision.value == "allow" else "warn" if result.decision.value == "review" else "fail",
                f"{result.decision.value}: {result.reason}",
                tuple(f"{gate}={payload[0].value}" for gate, payload in result.gate_results.items()),
            )
        )
    except Exception as exc:
        checks.append(ClosureCheck("Telos", "telos_gatekeeper", "warn", f"Telos gatekeeper unavailable: {exc}"))

    dossier_path = _resolve(selection, (selection.contract.get("minimum_viable_artifact") or {}).get("path"))
    if dossier_path and dossier_path.is_file():
        try:
            from dharma_swarm.jk_credibility_gates import audit_proof_artifact

            audit = audit_proof_artifact(dossier_path)
            status = "pass" if audit.submission_ready else "warn"
            checks.append(
                ClosureCheck(
                    "Viveka",
                    "credibility_audit",
                    status,
                    f"submission_ready={audit.submission_ready}; failed={len(audit.failures)}; warned={len(audit.warnings)}",
                    tuple(f"{row.gate.value}={row.verdict.value}" for row in audit.results),
                )
            )
        except Exception as exc:
            checks.append(ClosureCheck("Viveka", "credibility_audit", "warn", f"Credibility audit unavailable: {exc}"))
    return checks


def _metabolic_binding_checks(selection: ProofArtifactSelection) -> list[ClosureCheck]:
    contract = selection.contract
    checks: list[ClosureCheck] = []
    parent_cell = contract.get("parent_venture_cell") or {}
    cell_status = str(parent_cell.get("status") or "").strip()
    if cell_status and "not_yet" not in cell_status:
        checks.append(ClosureCheck("Shakti", "parent_venture_cell.status", "pass", cell_status))
    else:
        checks.append(
            ClosureCheck(
                "Shakti",
                "parent_venture_cell.status",
                "pending",
                "Parent VentureCell is named but not runtime-bound yet.",
                (str(parent_cell.get("proposed_name") or ""),),
            )
        )

    human_decisions = contract.get("human_decisions_required")
    if isinstance(human_decisions, list) and human_decisions:
        checks.append(
            ClosureCheck(
                "HumanOperator",
                "human_decisions_required",
                "pending",
                f"{len(human_decisions)} human boundary decision(s) still require confirmation.",
                tuple(str(row.get("id") or "") for row in human_decisions if isinstance(row, dict)),
            )
        )
    else:
        checks.append(ClosureCheck("HumanOperator", "human_decisions_required", "pass", "No unresolved human boundary decisions listed."))
    return checks


def _evolution_binding_checks(selection: ProofArtifactSelection) -> list[ClosureCheck]:
    checks: list[ClosureCheck] = []
    next_state = str(selection.contract.get("next_state") or "").strip()
    if next_state:
        checks.append(ClosureCheck("Evolution", "next_state", "pass", next_state))
    else:
        checks.append(ClosureCheck("Evolution", "next_state", "warn", "No next_state recorded."))

    next_build_spec = _resolve(selection, (selection.contract.get("spine_bindings") or {}).get("build_spec"))
    if next_build_spec and next_build_spec.is_file():
        text = next_build_spec.read_text(encoding="utf-8")
        if "proof_artifact_to_spec.py" in text:
            checks.append(
                ClosureCheck(
                    "Evolution",
                    "build_protocol_adapter_named",
                    "pass",
                    "Next build spec names the ProofArtifact adapter.",
                    (_display_path(next_build_spec, selection.repo_root),),
                )
            )
        else:
            checks.append(
                ClosureCheck(
                    "Evolution",
                    "build_protocol_adapter_named",
                    "warn",
                    "Next build spec exists but does not name the ProofArtifact adapter.",
                    (_display_path(next_build_spec, selection.repo_root),),
                )
            )
    return checks


def _read_packet_text(selection: ProofArtifactSelection) -> str:
    parts: list[str] = []
    mva_path = _resolve(selection, (selection.contract.get("minimum_viable_artifact") or {}).get("path"))
    if mva_path and mva_path.is_file():
        parts.append(mva_path.read_text(encoding="utf-8"))
    bindings = selection.contract.get("spine_bindings") or {}
    for key in ("claim_register", "organ_wiring_matrix", "human_operator_brief", "build_spec"):
        path = _resolve(selection, bindings.get(key))
        if path and path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def _telos_text(contract: dict[str, Any]) -> str:
    telos = contract.get("telos")
    if isinstance(telos, dict):
        return "\n".join(str(value) for value in telos.values())
    return str(telos or "")


def _spec_telos(selection: ProofArtifactSelection) -> str:
    title = selection.title
    return (
        f"Run {title} as a whole-organism tracer through lodestones, telos, "
        "ThinkodynamicDirector, Shakti, Viveka, MemoryKernel, Kalyan, Agora/SABP, "
        "and guarded Evolution without collapsing the organism into one report."
    )


def _allowed_paths(selection: ProofArtifactSelection) -> tuple[str, ...]:
    allowed = [
        _display_path(selection.contract_path, selection.repo_root),
        _display_path(_default_report_path(selection), selection.repo_root),
    ]
    bindings = selection.contract.get("spine_bindings") or {}
    for key in (
        "source_synthesis",
        "claim_register",
        "human_operator_brief",
        "organ_wiring_matrix",
        "build_spec",
        "sabp_claim_path",
    ):
        raw = bindings.get(key)
        if raw and _looks_like_path(str(raw)):
            path = _resolve(selection, raw)
            allowed.append(_display_path(path, selection.repo_root) if path else str(raw))
    mandala = selection.contract.get("witness_mandala")
    if isinstance(mandala, Mapping):
        raw = mandala.get("claim_path")
        if raw and _looks_like_path(str(raw)):
            path = _resolve(selection, raw)
            allowed.append(_display_path(path, selection.repo_root) if path else str(raw))
    mva = selection.contract.get("minimum_viable_artifact") or {}
    if mva.get("path"):
        path = _resolve(selection, mva.get("path"))
        allowed.append(_display_path(path, selection.repo_root) if path else str(mva.get("path")))
    return tuple(dict.fromkeys(allowed))


def _summarize_checks(checks: Sequence[ClosureCheck]) -> dict[str, int]:
    summary = {"pass": 0, "warn": 0, "fail": 0, "pending": 0}
    for check in checks:
        if check.status in summary:
            summary[check.status] += 1
        else:
            summary["warn"] += 1
    return summary


def _closure_decision(summary: dict[str, int]) -> dict[str, str]:
    if summary.get("fail", 0):
        return {
            "status": "blocked",
            "reason": "At least one required artifact or binding path is missing.",
        }
    if summary.get("pending", 0) or summary.get("warn", 0):
        return {
            "status": "preflight_ready_with_open_wires",
            "reason": "The tracer can enter Build Protocol, but runtime, witness, or value bindings remain open.",
        }
    return {
        "status": "closure_ready",
        "reason": "All preflight checks passed without warnings or pending runtime wires.",
    }


def _next_required_wires(checks: Sequence[ClosureCheck]) -> list[str]:
    wires: list[str] = []
    for check in checks:
        if check.status not in {"pending", "warn", "fail"}:
            continue
        wires.append(f"{check.organ}: {check.name} - {check.detail}")
    return wires[:12]


def _default_report_path(selection: ProofArtifactSelection) -> Path:
    return selection.packet_dir / "closure_run_report.json"


def _resolve(selection: ProofArtifactSelection, value: Any) -> Path | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() == "pending":
        return None
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (selection.repo_root / raw).resolve()


def _looks_like_path(value: str) -> bool:
    if value.startswith(("~", "/", "./", "../")):
        return True
    return bool(re.search(r"\.(py|md|json|yaml|yml|toml|ts|tsx|js|sh)$", value))


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "dharma_swarm").exists():
            return candidate
        if (candidate / ".git").exists():
            return candidate
    return start


def _display_path(path: Path | None, repo_root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _venture_cell_status(contract: dict[str, Any]) -> str:
    cell = contract.get("parent_venture_cell")
    if not isinstance(cell, dict):
        return "missing"
    return str(cell.get("status") or "unknown")


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... clipped for gate preflight ...]"


def _mandala_record_complete(record: Mapping[str, Any]) -> bool:
    for field in WITNESS_MANDALA_REQUIRED_FIELDS:
        value = record.get(field)
        if field == "evidence_required_to_upgrade":
            if not isinstance(value, list) or not any(str(item).strip() for item in value):
                return False
        elif field == "confidence":
            try:
                confidence = float(value)
            except (TypeError, ValueError):
                return False
            if confidence < 0.0 or confidence > 1.0:
                return False
        elif not isinstance(value, str) or not value.strip():
            return False
    return True


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:72]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="proof-artifact-to-spec",
        description=__doc__,
    )
    parser.add_argument("contract_path", type=Path)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--print", action="store_true", help="print spec to stdout instead of writing")
    parser.add_argument("--print-report", action="store_true", help="print closure report JSON to stdout")
    args = parser.parse_args(argv)

    selection = load_contract(args.contract_path, repo_root=args.repo_root)
    report_path = args.report_path or _default_report_path(selection)
    report = run_closure_preflight(selection, report_path=report_path)
    spec_text = render_spec(selection, report)

    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["decision"]["status"] != "blocked" else 2
    if args.print:
        print(spec_text, end="")
        return 0 if report["decision"]["status"] != "blocked" else 2

    write_report(report, report_path)
    out = write_spec(
        spec_text,
        output_dir=args.output_dir,
        title_slug=_slugify(f"proof-artifact-{selection.title}-closure") or "proof-artifact-closure",
    )
    print(out)
    return 0 if report["decision"]["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
