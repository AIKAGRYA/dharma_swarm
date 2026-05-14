"""Structural conflict and projection review for MemoryKernel evidence."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass

from dharma_swarm.knowledge_ops.memory_intake import MemoryEvidenceReview


_HIGH_RISK_VALUES = {"high", "critical"}
_PROMOTABLE_TRUTH_STATES = {"observed", "curated"}


@dataclass(frozen=True)
class MemoryReviewFinding:
    finding_id: str
    kind: str
    severity: str
    atom_id: str
    surface_id: str
    content_ref: str
    reason: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryPromotionCandidate:
    atom_id: str
    surface_id: str
    content_ref: str
    truth_state: str
    authority_level: str
    required_gates: tuple[str, ...]
    reasons: tuple[str, ...]
    source_review_status: str = ""
    canon_risk: str = "unknown"
    pii_risk: str = "unknown"
    projection_of: tuple[str, ...] = ()
    has_content: bool = False

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryConflictProjectionReview:
    total_atoms: int
    finding_count: int
    displayed_finding_count: int
    finding_truncated: bool
    promotion_candidate_count: int
    displayed_promotion_candidate_count: int
    promotion_candidate_truncated: bool
    promotion_blocked_atom_count: int
    promotion_blocker_count: int
    findings: tuple[MemoryReviewFinding, ...]
    promotion_candidates: tuple[MemoryPromotionCandidate, ...]
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "total_atoms": self.total_atoms,
            "finding_count": self.finding_count,
            "displayed_finding_count": self.displayed_finding_count,
            "finding_truncated": self.finding_truncated,
            "promotion_candidate_count": self.promotion_candidate_count,
            "displayed_promotion_candidate_count": self.displayed_promotion_candidate_count,
            "promotion_candidate_truncated": self.promotion_candidate_truncated,
            "promotion_blocked_atom_count": self.promotion_blocked_atom_count,
            "promotion_blocker_count": self.promotion_blocker_count,
            "warnings": self.warnings,
            "findings": [finding.to_json() for finding in self.findings],
            "promotion_candidates": [
                candidate.to_json() for candidate in self.promotion_candidates
            ],
        }


def review_memory_conflicts(
    evidence_review: MemoryEvidenceReview,
    *,
    max_findings: int = 50,
    max_promotion_candidates: int = 50,
) -> MemoryConflictProjectionReview:
    nodes = evidence_review.snapshot.evidence_nodes
    findings: list[MemoryReviewFinding] = []
    candidates: list[MemoryPromotionCandidate] = []
    blocked_atoms = 0
    blocker_count = 0

    for node in nodes:
        blockers = _promotion_blockers(node)
        if blockers:
            blocked_atoms += 1
            blocker_count += len(blockers)
        else:
            candidates.append(
                MemoryPromotionCandidate(
                    atom_id=str(node.memory_atom_id),
                    surface_id=node.surface_id,
                    content_ref=str(node.content_ref),
                    truth_state=str(node.truth_state),
                    authority_level=str(node.authority_level),
                    required_gates=_required_gates(),
                    reasons=("passed_structural_promotion_gate",),
                    source_review_status=str(node.status),
                    canon_risk=str(node.canon_risk),
                    pii_risk=str(node.pii_risk),
                    projection_of=tuple(str(ref) for ref in node.projection_of),
                    has_content=bool(node.has_content),
                )
            )

        findings.extend(_node_findings(node, blockers))

    findings.extend(_group_conflict_findings(nodes))

    displayed_findings = tuple(findings[: max(0, max_findings)])
    displayed_candidates = tuple(candidates[: max(0, max_promotion_candidates)])
    warnings = ["read_only_structural_review", "no_semantic_truth_inference"]
    if len(findings) > len(displayed_findings):
        warnings.append("finding_display_truncated")
    if len(candidates) > len(displayed_candidates):
        warnings.append("promotion_candidate_display_truncated")

    return MemoryConflictProjectionReview(
        total_atoms=evidence_review.total_atoms,
        finding_count=len(findings),
        displayed_finding_count=len(displayed_findings),
        finding_truncated=len(findings) > len(displayed_findings),
        promotion_candidate_count=len(candidates),
        displayed_promotion_candidate_count=len(displayed_candidates),
        promotion_candidate_truncated=len(candidates) > len(displayed_candidates),
        promotion_blocked_atom_count=blocked_atoms,
        promotion_blocker_count=blocker_count,
        findings=displayed_findings,
        promotion_candidates=displayed_candidates,
        warnings=tuple(warnings),
    )


def render_memory_conflict_review_markdown(
    review: MemoryConflictProjectionReview,
) -> str:
    lines = [
        "# MemoryKernel Conflict Projection Review",
        "",
        "Read-only structural review. This report does not decide semantic truth or promote memory.",
        "",
        "## Summary",
        "",
        f"- Total atoms: `{review.total_atoms}`",
        f"- Findings: `{review.finding_count}`",
        f"- Displayed findings: `{review.displayed_finding_count}`",
        f"- Finding truncated: `{str(review.finding_truncated).lower()}`",
        f"- Promotion candidates: `{review.promotion_candidate_count}`",
        f"- Displayed promotion candidates: `{review.displayed_promotion_candidate_count}`",
        f"- Promotion candidate truncated: `{str(review.promotion_candidate_truncated).lower()}`",
        f"- Promotion-blocked atoms: `{review.promotion_blocked_atom_count}`",
        f"- Promotion blocker occurrences: `{review.promotion_blocker_count}`",
        "",
    ]
    if review.findings:
        lines.extend(["## Findings", ""])
        for finding in review.findings:
            lines.append(
                f"- `{finding.severity}` `{finding.kind}` "
                f"atom=`{finding.atom_id}` reason={finding.reason}"
            )
        lines.append("")
    if review.promotion_candidates:
        lines.extend(["## Promotion Candidates", ""])
        for candidate in review.promotion_candidates:
            lines.append(
                f"- atom=`{candidate.atom_id}` surface=`{candidate.surface_id}` "
                f"truth=`{candidate.truth_state}`"
            )
        lines.append("")
    if review.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in review.warnings)
        lines.append("")
    return "\n".join(lines)


def _node_findings(node: object, blockers: tuple[str, ...]) -> list[MemoryReviewFinding]:
    findings: list[MemoryReviewFinding] = []
    for blocker in blockers:
        findings.append(
            MemoryReviewFinding(
                finding_id=_stable_id(str(node.memory_atom_id), blocker),
                kind=blocker,
                severity=_severity_for(blocker),
                atom_id=str(node.memory_atom_id),
                surface_id=str(node.surface_id),
                content_ref=str(node.content_ref),
                reason=blocker.replace("_", " "),
            )
        )
    if node.supersedes:
        findings.append(
            MemoryReviewFinding(
                finding_id=_stable_id(str(node.memory_atom_id), "supersedes_other_atoms"),
                kind="supersedes_other_atoms",
                severity="info",
                atom_id=str(node.memory_atom_id),
                surface_id=str(node.surface_id),
                content_ref=str(node.content_ref),
                reason="atom claims to supersede prior atoms",
            )
        )
    return findings


def _group_conflict_findings(nodes: tuple[object, ...]) -> list[MemoryReviewFinding]:
    by_ref: dict[str, list[object]] = defaultdict(list)
    for node in nodes:
        by_ref[str(node.content_ref)].append(node)

    findings: list[MemoryReviewFinding] = []
    for content_ref, grouped_nodes in by_ref.items():
        if len(grouped_nodes) < 2:
            continue
        truth_states = {str(node.truth_state) for node in grouped_nodes}
        authority_levels = {str(node.authority_level) for node in grouped_nodes}
        first = grouped_nodes[0]
        if len(truth_states) > 1:
            findings.append(
                MemoryReviewFinding(
                    finding_id=_stable_id(content_ref, "divergent_truth_states"),
                    kind="divergent_truth_states",
                    severity="warning",
                    atom_id=str(first.memory_atom_id),
                    surface_id=str(first.surface_id),
                    content_ref=content_ref,
                    reason="same content ref has multiple truth states",
                )
            )
        if len(authority_levels) > 1:
            findings.append(
                MemoryReviewFinding(
                    finding_id=_stable_id(content_ref, "divergent_authority_levels"),
                    kind="divergent_authority_levels",
                    severity="warning",
                    atom_id=str(first.memory_atom_id),
                    surface_id=str(first.surface_id),
                    content_ref=content_ref,
                    reason="same content ref has multiple authority levels",
                )
            )
    return findings


def _promotion_blockers(node: object) -> tuple[str, ...]:
    blockers: list[str] = []
    if not node.promotion_allowed:
        blockers.append("promotion_not_allowed")
    if str(node.truth_state) not in _PROMOTABLE_TRUTH_STATES:
        blockers.append("non_promotable_truth_state")
    if node.projection_of:
        blockers.append("projection_not_authority")
    if str(node.canon_risk) in _HIGH_RISK_VALUES:
        blockers.append("high_canon_risk")
    if str(node.pii_risk) in _HIGH_RISK_VALUES:
        blockers.append("high_pii_risk")
    if str(node.status) in {"superseded", "contested"}:
        blockers.append(f"{node.status}_atom")
    if node.has_content:
        blockers.append("content_bearing_atom")
    return tuple(blockers)


def _required_gates() -> tuple[str, ...]:
    return (
        "human_review",
        "provenance_review",
        "conflict_review",
        "privacy_review",
        "canon_policy_review",
        "knowledgeops_linking",
    )


def _severity_for(kind: str) -> str:
    if kind in {"high_canon_risk", "high_pii_risk"}:
        return "high"
    if kind in {"projection_not_authority", "content_bearing_atom"}:
        return "warning"
    return "info"


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"memory_review_finding:{digest[:24]}"
