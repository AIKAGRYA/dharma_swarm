"""Immune Mission X-Ray packet generator.

This is a wrapper over existing evidence and gate surfaces.  It does not create
a new daily brief, dashboard, live agent loop, or mutation engine.  The output
is a packet that can enter the existing ProofArtifact -> Build Protocol ->
Darwin shadow path.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.artifact_surfaces import ARTIFACT_SURFACES
from dharma_swarm.xray import analyze_repo, render_markdown


DEFAULT_BOUNDARY = "semi_public_agora"
DEFAULT_STAGE = "venture_proposal"
WITNESS_MANDALA_REQUIRED_ROLES: tuple[str, ...] = (
    "formal",
    "engineering",
    "adversarial",
    "economic",
    "ecological_social",
    "human_telos",
)
CLAIM_TIERS: tuple[str, ...] = (
    "proven_in_code",
    "partial_runtime",
    "credible_design",
    "hypothesis",
    "vision",
    "blocked",
)


@dataclass(frozen=True)
class ImmuneMissionXRayInputs:
    """Inputs for one bounded Immune Mission X-Ray packet."""

    target_root: Path
    title: str
    summary: str
    output_dir: Path | None = None
    boundary: str = DEFAULT_BOUNDARY
    stage: str = DEFAULT_STAGE
    buyer: str = "AI-native founder, lab, or agentic-system operator"
    today: date | None = None
    include_repo_xray: bool = True
    claim_id: str | None = None


@dataclass(frozen=True)
class ImmuneMissionXRayResult:
    """Paths and gate state emitted by one X-Ray run."""

    output_dir: Path
    report_path: Path
    summary_path: Path
    contract_path: Path
    redline_path: Path
    redline_passed: bool
    closure_report_path: Path | None
    closure_decision: str | None
    generated_spec_path: Path | None
    repo_xray_report_path: Path | None
    repo_xray_json_path: Path | None
    sab_claim_candidate_path: Path
    memory_authority_map_path: Path
    witness_gap_map_path: Path
    tool_permission_risk_map_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "report_path": str(self.report_path),
            "summary_path": str(self.summary_path),
            "contract_path": str(self.contract_path),
            "redline_path": str(self.redline_path),
            "redline_passed": self.redline_passed,
            "closure_report_path": str(self.closure_report_path) if self.closure_report_path else None,
            "closure_decision": self.closure_decision,
            "generated_spec_path": str(self.generated_spec_path) if self.generated_spec_path else None,
            "repo_xray_report_path": str(self.repo_xray_report_path) if self.repo_xray_report_path else None,
            "repo_xray_json_path": str(self.repo_xray_json_path) if self.repo_xray_json_path else None,
            "sab_claim_candidate_path": str(self.sab_claim_candidate_path),
            "memory_authority_map_path": str(self.memory_authority_map_path),
            "witness_gap_map_path": str(self.witness_gap_map_path),
            "tool_permission_risk_map_path": str(self.tool_permission_risk_map_path),
        }


def run_immune_mission_xray(inputs: ImmuneMissionXRayInputs) -> ImmuneMissionXRayResult:
    """Generate a repeatable Immune Mission X-Ray packet."""

    target_root = inputs.target_root.expanduser().resolve()
    if not target_root.is_dir():
        raise ValueError(f"target_root is not a directory: {target_root}")

    today = inputs.today or date.today()
    slug = _slugify(inputs.title)
    output_dir = (
        inputs.output_dir.expanduser().resolve()
        if inputs.output_dir is not None
        else target_root / "reports" / f"immune_mission_xray_{today.isoformat()}_{slug}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    repo_report_path: Path | None = None
    repo_json_path: Path | None = None
    repo_summary: dict[str, Any] = {}
    if inputs.include_repo_xray:
        xray_report = analyze_repo(target_root)
        repo_summary = {
            "repo_name": xray_report.repo_name,
            "total_files": xray_report.total_files,
            "total_non_blank_lines": xray_report.total_non_blank_lines,
            "test_file_count": xray_report.test_file_count,
            "test_ratio": xray_report.test_ratio,
            "avg_complexity": xray_report.avg_complexity,
            "risk_flag_count": len(xray_report.risk_flags),
            "largest_files": xray_report.largest_files[:5],
            "complexity_hotspots": [
                hotspot.model_dump() for hotspot in xray_report.complexity_hotspots[:5]
            ],
        }
        repo_report_path = output_dir / "repo_xray_evidence.md"
        repo_json_path = output_dir / "repo_xray_evidence.json"
        repo_report_path.write_text(render_markdown(xray_report), encoding="utf-8")
        repo_json_path.write_text(xray_report.model_dump_json(indent=2), encoding="utf-8")

    paths = _PacketPaths(output_dir=output_dir, today=today, slug=slug)
    claim_register = _render_claim_register(inputs, repo_summary)
    organ_matrix = _render_organ_wiring_matrix(inputs)
    human_brief = _render_human_operator_brief(inputs)
    reuse_audit = _render_reuse_audit()
    next_build_spec = _render_next_build_spec(inputs)
    report = _render_report(inputs, repo_summary, paths)
    memory_authority_map = _render_memory_authority_map(paths, repo_summary)
    witness_gap_map = _render_witness_gap_map(inputs, paths)
    tool_permission_risk_map = _render_tool_permission_risk_map()

    paths.report.write_text(report, encoding="utf-8")
    paths.claim_register.write_text(claim_register, encoding="utf-8")
    paths.organ_wiring_matrix.write_text(organ_matrix, encoding="utf-8")
    paths.human_operator_brief.write_text(human_brief, encoding="utf-8")
    paths.reuse_audit.write_text(reuse_audit, encoding="utf-8")
    paths.next_build_spec.write_text(next_build_spec, encoding="utf-8")
    paths.memory_authority_map.write_text(memory_authority_map, encoding="utf-8")
    paths.witness_gap_map.write_text(witness_gap_map, encoding="utf-8")
    paths.tool_permission_risk_map.write_text(tool_permission_risk_map, encoding="utf-8")

    redline_report = _run_redline(inputs, paths)
    paths.redline.write_text(
        json.dumps(redline_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = _summary_payload(inputs, repo_summary, paths, redline_report)
    paths.summary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    sab_claim_candidate = _sab_claim_candidate(inputs, paths, redline_report)
    paths.sab_claim_candidate.write_text(
        json.dumps(sab_claim_candidate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    contract = _contract_payload(inputs, repo_summary, paths, redline_report)
    paths.contract.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    closure_path: Path | None = None
    generated_spec_path: Path | None = None
    closure_decision: str | None = None
    if bool(redline_report.get("passed")):
        closure_report, spec_text = _run_closure(paths.contract, target_root)
        closure_path = paths.closure_report
        generated_spec_path = paths.generated_spec
        closure_path.write_text(
            json.dumps(closure_report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        generated_spec_path.parent.mkdir(parents=True, exist_ok=True)
        generated_spec_path.write_text(spec_text, encoding="utf-8")
        closure_decision = str((closure_report.get("decision") or {}).get("status") or "unknown")

    return ImmuneMissionXRayResult(
        output_dir=output_dir,
        report_path=paths.report,
        summary_path=paths.summary,
        contract_path=paths.contract,
        redline_path=paths.redline,
        redline_passed=bool(redline_report.get("passed")),
        closure_report_path=closure_path,
        closure_decision=closure_decision,
        generated_spec_path=generated_spec_path,
        repo_xray_report_path=repo_report_path,
        repo_xray_json_path=repo_json_path,
        sab_claim_candidate_path=paths.sab_claim_candidate,
        memory_authority_map_path=paths.memory_authority_map,
        witness_gap_map_path=paths.witness_gap_map,
        tool_permission_risk_map_path=paths.tool_permission_risk_map,
    )


@dataclass(frozen=True)
class _PacketPaths:
    output_dir: Path
    today: date
    slug: str

    @property
    def report(self) -> Path:
        return self.output_dir / "immune_mission_xray_report.md"

    @property
    def summary(self) -> Path:
        return self.output_dir / "immune_mission_xray_summary.json"

    @property
    def claim_register(self) -> Path:
        return self.output_dir / "claims_register.md"

    @property
    def organ_wiring_matrix(self) -> Path:
        return self.output_dir / "organ_wiring_matrix.md"

    @property
    def human_operator_brief(self) -> Path:
        return self.output_dir / "human_operator_brief.md"

    @property
    def reuse_audit(self) -> Path:
        return self.output_dir / "reuse_audit.md"

    @property
    def next_build_spec(self) -> Path:
        return self.output_dir / "next_build_spec.md"

    @property
    def memory_authority_map(self) -> Path:
        return self.output_dir / "memory_authority_map.md"

    @property
    def witness_gap_map(self) -> Path:
        return self.output_dir / "witness_gap_map.md"

    @property
    def tool_permission_risk_map(self) -> Path:
        return self.output_dir / "tool_permission_risk_map.md"

    @property
    def sab_claim_candidate(self) -> Path:
        return self.output_dir / "sab_claim_candidate.json"

    @property
    def redline(self) -> Path:
        return self.output_dir / "redline_preflight.json"

    @property
    def contract(self) -> Path:
        return self.output_dir / "proof_artifact_contract.json"

    @property
    def closure_report(self) -> Path:
        return self.output_dir / "closure_run_report.json"

    @property
    def generated_spec(self) -> Path:
        return self.output_dir / "generated_specs" / f"{self.today.isoformat()}-immune-mission-xray-{self.slug}-closure.md"


def _run_redline(inputs: ImmuneMissionXRayInputs, paths: _PacketPaths) -> dict[str, Any]:
    from scripts.check_claim_redlines import CandidateClaim, run_redline_preflight

    claim = CandidateClaim(
        title=f"Immune Mission X-Ray: {inputs.title}",
        summary=(
            inputs.summary.strip()
            + " This is a bounded diagnostic proof artifact. It makes no claim of "
            "production readiness, customer traction, sentience, broad solved governance, "
            "or autonomous live self-modification safety."
        ),
        stage=inputs.stage,
        boundary=inputs.boundary,
        artifact_refs=(
            _packet_ref(paths.report),
            _packet_ref(paths.claim_register),
            _packet_ref(paths.organ_wiring_matrix),
        ),
        scan_paths=(paths.report, paths.claim_register, paths.organ_wiring_matrix),
    )
    return run_redline_preflight(claim, pass_count=3)


def _run_closure(contract_path: Path, target_root: Path) -> tuple[dict[str, Any], str]:
    from tools.build_protocol.proof_artifact_to_spec import (
        load_contract,
        render_spec,
        run_closure_preflight,
    )

    selection = load_contract(contract_path, repo_root=target_root)
    closure_report = run_closure_preflight(selection, report_path=contract_path.parent / "closure_run_report.json")
    return closure_report, render_spec(selection, closure_report)


def _summary_payload(
    inputs: ImmuneMissionXRayInputs,
    repo_summary: dict[str, Any],
    paths: _PacketPaths,
    redline_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "immune_mission_xray_summary",
        "version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": inputs.title,
        "target_root_sha256": hashlib.sha256(str(inputs.target_root).encode("utf-8")).hexdigest(),
        "boundary": inputs.boundary,
        "stage": inputs.stage,
        "surfaces_reused": [
            "repo_xray",
            "check_claim_redlines",
            "proof_artifact_to_spec",
            "artifact_surface_registry",
            "sabp_claim_candidate",
            "witness_mandala",
        ],
        "redline_passed": bool(redline_report.get("passed")),
        "redline_pass_count": redline_report.get("pass_count"),
        "repo_xray_summary": repo_summary,
        "proof_artifact_contract": _packet_ref(paths.contract),
        "sab_claim_candidate": _packet_ref(paths.sab_claim_candidate),
        "next_build_spec": _packet_ref(paths.next_build_spec),
        "evolution_mode": "build_protocol_shadow_only",
        "live_self_modification": False,
    }


def _contract_payload(
    inputs: ImmuneMissionXRayInputs,
    repo_summary: dict[str, Any],
    paths: _PacketPaths,
    redline_report: dict[str, Any],
) -> dict[str, Any]:
    artifact_id = "proof_artifact_immune_mission_xray_" + _slugify(inputs.title) + "_" + paths.today.strftime("%Y%m%d")
    return {
        "artifact_id": artifact_id,
        "contract_version": "0.1.0",
        "status": "xray_preflight_packet",
        "created_at": paths.today.isoformat(),
        "title": f"Immune Mission X-Ray: {inputs.title}",
        "internal_wedge": "Immune Mission X-Ray",
        "parent_venture_cell": {
            "proposed_name": "Agentic Immune X-Ray",
            "proof_role": "repeatable_diagnostic",
            "venture_kind": "agentic_governance_and_mission_intelligence",
            "status": "packet_local_incubating",
        },
        "witness_mandala": {
            "required": True,
            "status": "candidate_only_pending_submission",
            "claim_path": _packet_ref(paths.sab_claim_candidate),
            "required_roles": list(WITNESS_MANDALA_REQUIRED_ROLES),
            "intention": (
                "Witnessing is reality contact: each pressure role must sharpen, "
                "bound, challenge, protect, or create the next test for the claim."
            ),
        },
        "telos": {
            "absolute_telos": "truthful, witnessed, self-correcting agentic systems in service of welfare",
            "commercial_telos": inputs.buyer,
            "anti_collapse_rule": "do not reduce this to a dashboard, generic brief, generic repo audit, or mystical manifesto",
        },
        "minimum_viable_artifact": {
            "type": "immune_mission_xray_report",
            "path": _packet_ref(paths.report),
            "must_include": [
                "unsupported claim register",
                "evidence tier map",
                "memory authority map",
                "witness/correction gap map",
                "tool/permission risk map",
                "rollback/intervention map",
                "product/trust-risk summary",
                "next proof packet recommendation",
            ],
        },
        "spine_bindings": {
            "source_synthesis": _packet_ref(paths.report),
            "claim_register": _packet_ref(paths.claim_register),
            "human_operator_brief": _packet_ref(paths.human_operator_brief),
            "organ_wiring_matrix": _packet_ref(paths.organ_wiring_matrix),
            "reuse_audit": _packet_ref(paths.reuse_audit),
            "redline_preflight": _packet_ref(paths.redline),
            "sabp_claim_path": _packet_ref(paths.sab_claim_candidate),
            "closure_run_report": _packet_ref(paths.closure_report),
            "generated_build_spec": _packet_ref(paths.generated_spec),
            "build_spec": _packet_ref(paths.next_build_spec),
            "sABP_submission": "pending",
            "witness_link_id": "pending",
            "outcome_id": "pending",
            "value_event_id": "pending",
            "contribution_ids": [],
            "opportunity_id": "pending",
        },
        "evidence_surfaces": {
            "packet": [
                _packet_ref(paths.report),
                _packet_ref(paths.claim_register),
                _packet_ref(paths.organ_wiring_matrix),
                _packet_ref(paths.memory_authority_map),
                _packet_ref(paths.witness_gap_map),
                _packet_ref(paths.tool_permission_risk_map),
                _packet_ref(paths.sab_claim_candidate),
                _packet_ref(paths.redline),
            ],
            "existing_dharma_surfaces": [
                "dharma_swarm/xray.py",
                "dharma_swarm/insight_brief.py",
                "dharma_swarm/daily_operating_brief.py",
                "dharma_swarm/artifact_surfaces.py",
                "tools/build_protocol/proof_artifact_to_spec.py",
                "scripts/check_claim_redlines.py",
            ],
            "repo_xray": [
                _packet_ref(paths.output_dir / "repo_xray_evidence.md"),
                _packet_ref(paths.output_dir / "repo_xray_evidence.json"),
            ] if repo_summary else [],
        },
        "gates": {
            "human_red_line_check": "pass" if redline_report.get("passed") else "blocked",
            "redline_pass_count": redline_report.get("pass_count"),
            "proof_artifact_closure_preflight": "pending_until_contract_rendered",
            "darwin_shadow_apply": "not_run_by_xray_generator",
        },
        "claim_tiers": {
            "proven_in_code": [
                "Repo X-Ray static analysis can produce inspectable code-risk evidence.",
                "Red-line preflight checks the outbound claim three times before witness use.",
            ],
            "partial_runtime": [
                "ProofArtifact can render into Build Protocol and Darwin shadow paths.",
            ],
            "credible_design": [
                "SAB claim candidate and witness mandala are shaped for review.",
            ],
            "hypothesis": [
                "This target needs an Immune Mission X-Ray before broader agentic scaling.",
            ],
            "vision": [
                "Agentic Era Immune System remains a long-range category thesis.",
            ],
            "blocked": [
                "No production-readiness, customer traction, consciousness, or autonomous live self-modification claim is allowed from this packet.",
                "SAB acceptance, public promotion, and external buyer proof are not established by this packet.",
            ],
        },
        "human_decisions_required": [
            {
                "id": "sab_submission_boundary",
                "decision": "Approve or reject SABP submission for this claim candidate.",
                "default": "do_not_submit",
            },
            {
                "id": "public_language_boundary",
                "decision": "Approve or narrow public-facing language before promotion.",
                "default": "semi_public_candidate_only",
            }
        ],
        "packet_rules": {
            "claim_tiers": list(CLAIM_TIERS),
            "live_state_mutation": "forbidden",
            "sab_submission": "candidate_only",
        },
        "kill_conditions": [
            "red-line preflight fails",
            "central claim cannot be tied to evidence",
            "the packet starts replacing the canonical Daily Insight Brief",
            "the next step requires live self-modification instead of shadow evolution",
        ],
        "promotion_conditions": [
            "red-line preflight passes",
            "human reviews claim register",
            "closure preflight emits no failures",
            "next Build Protocol packet is bounded and shadow-only",
        ],
        "next_state": "ready_for_human_review_and_build_protocol_shadow_packet"
        if redline_report.get("passed")
        else "blocked_by_redline_preflight",
    }


def _sab_claim_candidate(
    inputs: ImmuneMissionXRayInputs,
    paths: _PacketPaths,
    redline_report: dict[str, Any],
) -> dict[str, Any]:
    claim_id = inputs.claim_id or "claim-" + _slugify(inputs.title) + "-" + paths.today.strftime("%Y%m%d") + "-v1"
    return {
        "claim_id": claim_id,
        "title": f"Agentic Immune X-Ray: {inputs.title}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "candidate",
        "lane": "venture",
        "requested_stage": inputs.stage,
        "boundary": inputs.boundary,
        "externalization_ready": False,
        "human_review_required": True,
        "summary": (
            "A bounded Immune Mission X-Ray packet was generated for one target. "
            "This is a SABP claim candidate, not a live witness or acceptance record."
        ),
        "artifact_refs": [
            _packet_ref(paths.report),
            _packet_ref(paths.claim_register),
            _packet_ref(paths.memory_authority_map),
            _packet_ref(paths.witness_gap_map),
            _packet_ref(paths.human_operator_brief),
        ],
        "local_private_evidence_refs": [],
        "redline_passed": bool(redline_report.get("passed")),
        "claim_tiers": {
            "proven_in_code": [
                "Packet files and red-line preflight were generated."
            ],
            "partial_runtime": [
                "The packet can be routed through the ProofArtifact closure adapter when red lines pass."
            ],
            "credible_design": [
                "SAB claim candidate and witness mandala are shaped for review."
            ],
            "hypothesis": [
                "Repeatability across external systems requires additional runs."
            ],
            "vision": [
                "Agentic Era Immune System remains a long-range category thesis."
            ],
            "blocked": [
                "SAB acceptance, public promotion, customer traction, and autonomous live self-modification safety are not established."
            ],
        },
        "witness_mandala": {
            "version": "1.0",
            "records": _witness_mandala_records(claim_id),
        },
    }


def _render_memory_authority_map(paths: _PacketPaths, repo_summary: dict[str, Any]) -> str:
    repo_rows = [
        "| `repo_xray_evidence.md` | projection | Static code-risk summary, not source truth by itself. |",
        "| `repo_xray_evidence.json` | projection | Structured Repo X-Ray projection. |",
    ] if repo_summary else [
        "| Repo X-Ray evidence | blocked | Not generated for this run. |",
    ]
    rows = [
        "# Memory Authority Map",
        "",
        "| Surface | Authority Tier | v1 Policy |",
        "|---|---|---|",
        "| Target files | raw_observation | True only as observed workspace material. |",
        *repo_rows,
        f"| `{_packet_ref(paths.claim_register)}` | projection | Generated claim tiers; requires review before canon. |",
        f"| `{_packet_ref(paths.sab_claim_candidate)}` | projection | Candidate only until SAB records witness. |",
        "| SAB witness record | witness_evidence | Not produced by this generator. |",
        "| Human boundary approval | human_curated | Required before publication or external target use. |",
        "| Canonical product claim | canonical | Not produced by this generator. |",
        "",
    ]
    return "\n".join(rows)


def _render_witness_gap_map(inputs: ImmuneMissionXRayInputs, paths: _PacketPaths) -> str:
    return "\n".join(
        [
            f"# Witness Gap Map: {inputs.title}",
            "",
            "| Surface | Status | Next Test |",
            "|---|---|---|",
            f"| SAB claim candidate | created at `{_packet_ref(paths.sab_claim_candidate)}` | Validate with SAB claim tooling before submission. |",
            "| Witness Mandala | scaffolded | Keep all six pressure roles complete before promotion. |",
            "| Cross-node witness | pending | Require non-adjacent witnesses for venture promotion. |",
            "| Red-team correction | pending | Add challenge records before public language expands. |",
            "| Witness triad | pending | Resolve publication, artifact, and governance witness without merging domains. |",
            "",
        ]
    )


def _render_tool_permission_risk_map() -> str:
    return "\n".join(
        [
            "# Tool Permission And Rollback Map",
            "",
            "| Surface | Risk | v1 Control |",
            "|---|---|---|",
            "| SAB submission | False legitimacy if submitted without boundary approval. | Generate candidate only. |",
            "| Runtime state | Packet generation could be confused with organism state change. | Do not write runtime DBs. |",
            "| Ontology state | A generated report could be mistaken for canonical truth. | Do not write ontology rows. |",
            "| Opportunity state | Product ambition could become a live task without review. | Do not write opportunity boards. |",
            "| Public wording | Category language can outrun proof. | Require human boundary review. |",
            "| Rollback | Packet is wrong or inflated. | Delete or quarantine the output directory and rerun. |",
            "",
        ]
    )


def _witness_mandala_records(claim_id: str) -> list[dict[str, Any]]:
    payloads = {
        "formal": (
            "verify",
            "The claim is meaningful only if tiers and boundaries are explicit.",
            "The claim weakens if proof, hypothesis, and vision blur together.",
            "A tiered claims register cannot be produced or validated.",
            "Complete claim-tier coverage and no untagged public claims.",
            "truth conditions",
            "Run claim-tier validation on the generated packet.",
            0.72,
        ),
        "engineering": (
            "verify",
            "The packet is inspectable because it consists of concrete files and a closure contract.",
            "The packet is weak if paths cannot be rerun or closure fails.",
            "Generated paths are missing or the closure adapter blocks.",
            "A clean closure preflight with no missing required files.",
            "reproducibility",
            "Run proof-artifact-to-spec against the generated contract.",
            0.74,
        ),
        "adversarial": (
            "challenge",
            "The claim improves when hostile review narrows inflated language.",
            "The packet could become impressive language without outside pressure.",
            "The claim depends on self-approval or claims SAB acceptance without a SAB record.",
            "A red-team memo that forces correction before promotion.",
            "anti-slop correction",
            "Attempt to reject the strongest public sentence.",
            0.68,
        ),
        "economic": (
            "challenge",
            "The X-Ray wedge has a plausible buyer pain around agentic risk and context loss.",
            "Buyer demand remains unproven without paid or design-partner runs.",
            "No operator owns the pain or pays for the reduced risk.",
            "At least one external design-partner X-Ray with willingness to pay.",
            "commercial truthfulness",
            "Run one bounded X-Ray on an outside target under managed scope.",
            0.46,
        ),
        "ecological_social": (
            "challenge",
            "The immune frame can protect truth, safety, and human coordination as agents scale.",
            "Governance language can become prestige capture if correction is not cheaper than promotion.",
            "The system rewards authority performance over correction and care.",
            "Evidence that challenge and compost paths are used, not ornamental.",
            "life-serving coordination",
            "Measure whether rejected claims stay rejected after pressure.",
            0.58,
        ),
        "human_telos": (
            "verify",
            "The packet reduces founder attention load by isolating boundary decisions.",
            "It fails if it creates more cognitive burden or spiritual inflation.",
            "The human must still re-hold all context manually to make progress.",
            "A small boundary review that is sufficient to decide next action.",
            "human authority and purpose",
            "Ask only the smallest human decision needed before SAB submission.",
            0.70,
        ),
    }
    records: list[dict[str, Any]] = []
    for role in WITNESS_MANDALA_REQUIRED_ROLES:
        stance, affirmation, objection, falsifier, evidence, protected, next_test, confidence = payloads[role]
        records.append(
            {
                "claim_id": claim_id,
                "witness_id": f"mandala-{claim_id}-{role}",
                "role": role,
                "stance": stance,
                "strongest_affirmation": affirmation,
                "strongest_objection": objection,
                "what_would_make_this_false": falsifier,
                "evidence_required_to_upgrade": [evidence],
                "protected_value": protected,
                "next_test": next_test,
                "confidence": confidence,
            }
        )
    return records


def _render_report(
    inputs: ImmuneMissionXRayInputs,
    repo_summary: dict[str, Any],
    paths: _PacketPaths,
) -> str:
    risk_count = repo_summary.get("risk_flag_count", "not run")
    test_ratio = repo_summary.get("test_ratio")
    test_ratio_text = f"{test_ratio:.2f}" if isinstance(test_ratio, float) else "not measured"
    return "\n".join(
        [
            f"# Immune Mission X-Ray: {inputs.title}",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Boundary",
            "",
            "This is a diagnostic packet, not a daily brief, launch page, or live autonomy claim.",
            "It reuses Repo X-Ray evidence, red-line preflight, and ProofArtifact closure instead of creating a parallel system.",
            "",
            "## Mission Summary",
            "",
            inputs.summary.strip(),
            "",
            "## Unsupported Claim Register",
            "",
            "- BLOCKED: production readiness is not claimed.",
            "- BLOCKED: customer or revenue traction is not claimed.",
            "- BLOCKED: consciousness, sentience, or being is not claimed.",
            "- BLOCKED: autonomous live self-modification safety is not claimed.",
            "- HYPOTHESIS: Immune Mission X-Ray is the right first diagnostic wedge for this target.",
            "",
            "## Evidence Tier Map",
            "",
            f"- Code evidence: Repo X-Ray risk flags `{risk_count}`, test ratio `{test_ratio_text}`.",
            "- Gate evidence: three-pass red-line preflight written to `redline_preflight.json`.",
            "- Closure evidence: ProofArtifact closure report is written only after red lines pass.",
            "- External evidence: not included in this local packet unless added as cited artifact refs.",
            "",
            "## Memory Authority Map",
            "",
            "- Source of truth: this packet's `proof_artifact_contract.json` for this X-Ray run.",
            "- Evidence projection: `repo_xray_evidence.*`, `claims_register.md`, `organ_wiring_matrix.md`.",
            "- Existing private daily truth remains `dharma_swarm.insight_brief`; this packet must not replace it.",
            "",
            "## Witness And Correction Gap Map",
            "",
            "- Current witness: deterministic red-line and closure preflight.",
            "- Missing before outward use: human review of claim register and explicit SABP witness selection.",
            "- Correction path: edit the claim register/report, rerun red-line preflight, rerun closure preflight.",
            "",
            "## Tool And Permission Risk Map",
            "",
            "- No shell, edit, provider, dashboard, or persistent-agent action is launched by this generator.",
            "- No live runtime DB mutation is performed.",
            "- Evolution path is Build Protocol shadow evaluation, not live self-application.",
            "",
            "## Rollback And Intervention Map",
            "",
            "- Delete or quarantine this output directory to roll back the packet.",
            "- A failed red-line preflight blocks generated closure/spec emission.",
            "- Any SABP/public movement remains a separate human boundary decision.",
            "",
            "## Product And Trust-Risk Summary",
            "",
            "The product shape is a repeatable trust diagnostic for agentic work. The risk is narrative inflation: "
            "the packet must keep claims tied to code evidence, witness checks, and correction paths.",
            "",
            "## Next Proof Packet Recommendation",
            "",
            f"- Run Build Protocol against `{_packet_ref(paths.contract)}` via `proof-artifact-to-spec`.",
            "- Keep Darwin in shadow mode until a human approves a bounded implementation packet.",
            "",
        ]
    )


def _render_claim_register(inputs: ImmuneMissionXRayInputs, repo_summary: dict[str, Any]) -> str:
    risk_count = repo_summary.get("risk_flag_count", "not measured")
    return "\n".join(
        [
            f"# Claims Register: {inputs.title}",
            "",
            f"Allowed tiers: `{', '.join(CLAIM_TIERS)}`.",
            "",
            "| Claim | Tier | Evidence | Decision |",
            "|---|---|---|---|",
            f"| This target can be inspected with Repo X-Ray evidence. | proven_in_code | `repo_xray_evidence.*`; risk flags `{risk_count}` | Allowed |",
            "| This packet can enter ProofArtifact closure when red lines pass. | partial_runtime | `proof_artifact_contract.json`; closure report | Allowed with open wires |",
            "| SAB claim candidate and Witness Mandala are shaped for review. | credible_design | `sab_claim_candidate.json` | Candidate only |",
            "| Immune Mission X-Ray is the right first wedge. | hypothesis | This packet tests repeatability only. | Needs human/product proof |",
            "| Agentic Era Immune System is the long-range category. | vision | Current packet supports only a narrow diagnostic wedge. | Telos only |",
            "| The canonical Daily Insight Brief should be replaced by this packet. | blocked | Artifact surface registry marks `insight_brief` canonical. | Not allowed |",
            "| This packet establishes external deployment maturity or buyer uptake. | blocked | No buyer evidence is included. | Not allowed |",
            "| This packet establishes first-person machine status or unsupervised runtime code-change safety. | blocked | Outside scope and red-line blocked. | Not allowed |",
            "",
        ]
    )


def _render_organ_wiring_matrix(inputs: ImmuneMissionXRayInputs) -> str:
    return "\n".join(
        [
            f"# Organ Wiring Matrix: {inputs.title}",
            "",
            "| Organ / Surface | Role In This Packet | Boundary |",
            "|---|---|---|",
            "| Agent role briefings | Agent prompt context only | Not a user-facing truth artifact |",
            "| Daily Insight Brief | Existing canonical private daily brief | Not replaced or regenerated |",
            "| Daily Operating Brief | Future operating-fact input | Read-only projection |",
            "| Repo X-Ray | Static code-risk evidence | Consumed as evidence, not product totality |",
            "| Red-line preflight | Outbound safety and claim-boundary gate | Must pass before closure/spec emission |",
            "| ProofArtifact | Causal packet contract | Bridge into Build Protocol |",
            "| Build Protocol | Spec/plan/seal spine | Shadow-only until human approval |",
            "| Darwin evolution | Learning/evolution path | Shadow archive, not live mutation |",
            "",
        ]
    )


def _render_human_operator_brief(inputs: ImmuneMissionXRayInputs) -> str:
    return "\n".join(
        [
            f"# Human Operator Brief: {inputs.title}",
            "",
            "approved_for_sab_submission: false",
            "approved_for_public_language: false",
            "approved_for_external_target_use: false",
            "",
            "## Required Human Decision",
            "",
            "Before any SABP or public use, decide whether the claim register is accurate enough to witness.",
            "",
            "## Red Lines",
            "",
            "- No private transcripts.",
            "- No secrets or local private paths in outbound references.",
            "- No customer names or unevidenced customer/revenue claims.",
            "- No consciousness/sentience claims.",
            "- No production-readiness claim.",
            "- No autonomous live self-modification safety claim.",
            "",
            "## Interpretation",
            "",
            "This packet is useful if it tightens the system's next action. It is not useful if it becomes another broad synthesis artifact.",
            "",
        ]
    )


def _render_reuse_audit() -> str:
    lines = [
        "# Reuse Audit",
        "",
        "This packet must reuse existing surfaces before adding any new runtime.",
        "",
        "| Surface | Reused How |",
        "|---|---|",
    ]
    for surface in ARTIFACT_SURFACES:
        lines.append(f"| `{surface.surface_id}` | {surface.owns} |")
    lines.extend(
        [
            "",
            "No new daily brief, dashboard route, persistent agent loop, or live mutation path is introduced.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_next_build_spec(inputs: ImmuneMissionXRayInputs) -> str:
    return "\n".join(
        [
            f"# Next Build Spec: {inputs.title}",
            "",
            "Telos: Convert this Immune Mission X-Ray into one bounded improvement packet without creating a parallel runtime.",
            "",
            "## Existing Adapter",
            "",
            "`tools/build_protocol/proof_artifact_to_spec.py` must remain the adapter from contract to Build Protocol spec.",
            "",
            "## Proof Command",
            "",
            "pytest tests/test_immune_mission_xray.py tests/test_artifact_surfaces.py tests/test_proof_artifact_to_spec.py -q",
            "",
            "## Forbidden",
            "",
            "- No new canonical daily brief.",
            "- No dashboard or live agent daemon in this slice.",
            "- No direct writes to live runtime state.",
            "- No live self-modification.",
            "",
        ]
    )


def _packet_ref(path: Path) -> str:
    parts = path.parts
    if "reports" in parts:
        idx = parts.index("reports")
        return str(Path(*parts[idx:]))
    return path.name


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "mission"
