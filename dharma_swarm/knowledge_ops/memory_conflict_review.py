"""Read-only conflict and projection review for MemoryKernel atoms."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable

from dharma_swarm.memory_kernel import MemoryAtom
from dharma_swarm.memory_kernel.atoms import TruthState


class MemoryReviewSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


_SEVERITY_RANK = {
    MemoryReviewSeverity.HIGH: 0,
    MemoryReviewSeverity.WARNING: 1,
    MemoryReviewSeverity.INFO: 2,
}


@dataclass(frozen=True)
class MemoryReviewFinding:
    finding_id: str
    kind: str
    severity: MemoryReviewSeverity
    atom_ids: tuple[str, ...]
    surface_ids: tuple[str, ...]
    content_ref: str
    reason: str
    metadata: dict[str, object]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["severity"] = self.severity.value
        return payload


@dataclass(frozen=True)
class MemoryPromotionCandidate:
    atom_id: str
    surface_id: str
    atom_type: str
    content_ref: str
    truth_state: str
    authority_level: str
    confidence: float
    reason: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryConflictProjectionReview:
    total_atoms: int
    finding_count: int
    displayed_finding_count: int
    finding_truncated: bool
    conflict_candidate_count: int
    projection_blocker_count: int
    promotion_candidate_count: int
    displayed_promotion_candidate_count: int
    promotion_candidate_truncated: bool
    promotion_blocked_atom_count: int
    promotion_blocker_count: int
    by_finding_kind: dict[str, int]
    by_severity: dict[str, int]
    promotion_blockers_by_reason: dict[str, int]
    warnings: tuple[str, ...]
    findings: tuple[MemoryReviewFinding, ...]
    promotion_candidates: tuple[MemoryPromotionCandidate, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["findings"] = [finding.to_json() for finding in self.findings]
        payload["promotion_candidates"] = [
            candidate.to_json() for candidate in self.promotion_candidates
        ]
        return payload


def review_memory_conflicts(
    atoms: Iterable[MemoryAtom],
    *,
    finding_limit: int = 100,
    promotion_candidate_limit: int = 50,
) -> MemoryConflictProjectionReview:
    rows = tuple(atoms)
    all_findings = list(_content_ref_findings(rows))
    all_findings.extend(_atom_findings(rows))
    all_findings = sorted(all_findings, key=_finding_sort_key)
    displayed_findings = tuple(all_findings[: max(0, finding_limit)])

    promotion_candidates: list[MemoryPromotionCandidate] = []
    promotion_blockers: Counter[str] = Counter()
    promotion_blocked_atom_count = 0
    for atom in rows:
        blockers = _promotion_blockers(atom)
        if blockers:
            promotion_blocked_atom_count += 1
            for blocker in blockers:
                promotion_blockers[blocker] += 1
            continue
        promotion_candidates.append(
            MemoryPromotionCandidate(
                atom_id=atom.atom_id,
                surface_id=atom.surface_id,
                atom_type=atom.atom_type.value,
                content_ref=_safe_content_ref(atom.content_ref),
                truth_state=atom.truth_state.value,
                authority_level=atom.authority_level.value,
                confidence=atom.confidence,
                reason="promotion_allowed atom passed structural review gates",
            )
        )

    displayed_promotion_candidates = tuple(
        promotion_candidates[: max(0, promotion_candidate_limit)]
    )
    finding_kind_counts = Counter(finding.kind for finding in all_findings)
    severity_counts = Counter(finding.severity.value for finding in all_findings)
    conflict_candidate_count = sum(
        1 for finding in all_findings if finding.kind.endswith("_conflict_candidate")
    )
    projection_blocker_count = sum(
        1 for finding in all_findings if finding.kind == "projection_not_authority"
    )
    return MemoryConflictProjectionReview(
        total_atoms=len(rows),
        finding_count=len(all_findings),
        displayed_finding_count=len(displayed_findings),
        finding_truncated=len(all_findings) > len(displayed_findings),
        conflict_candidate_count=conflict_candidate_count,
        projection_blocker_count=projection_blocker_count,
        promotion_candidate_count=len(promotion_candidates),
        displayed_promotion_candidate_count=len(displayed_promotion_candidates),
        promotion_candidate_truncated=len(promotion_candidates)
        > len(displayed_promotion_candidates),
        promotion_blocked_atom_count=promotion_blocked_atom_count,
        promotion_blocker_count=sum(promotion_blockers.values()),
        by_finding_kind=_sorted_counts(finding_kind_counts),
        by_severity=_sorted_counts(severity_counts),
        promotion_blockers_by_reason=_sorted_counts(promotion_blockers),
        warnings=_review_warnings(
            finding_count=len(all_findings),
            displayed_finding_count=len(displayed_findings),
            conflict_candidate_count=conflict_candidate_count,
            projection_blocker_count=projection_blocker_count,
            promotion_candidate_count=len(promotion_candidates),
            displayed_promotion_candidate_count=len(displayed_promotion_candidates),
        ),
        findings=displayed_findings,
        promotion_candidates=displayed_promotion_candidates,
    )


def render_memory_conflict_review_markdown(
    report: MemoryConflictProjectionReview,
) -> str:
    lines = [
        "# MemoryKernel Conflict Projection Review",
        "",
        "This is a read-only structural review. It identifies candidates and blockers; it does not decide truth.",
        "",
        "## Summary",
        "",
        f"- Total atoms: `{report.total_atoms}`",
        f"- Findings: `{report.finding_count}`",
        f"- Displayed findings: `{report.displayed_finding_count}`",
        f"- Findings truncated: `{str(report.finding_truncated).lower()}`",
        f"- Conflict candidates: `{report.conflict_candidate_count}`",
        f"- Projection blockers: `{report.projection_blocker_count}`",
        f"- Promotion candidates: `{report.promotion_candidate_count}`",
        f"- Displayed promotion candidates: `{report.displayed_promotion_candidate_count}`",
        f"- Promotion candidates truncated: `{str(report.promotion_candidate_truncated).lower()}`",
        f"- Promotion-blocked atoms: `{report.promotion_blocked_atom_count}`",
        f"- Promotion blockers: `{report.promotion_blocker_count}`",
        "",
    ]
    _append_counts(lines, "By Finding Kind", report.by_finding_kind)
    _append_counts(lines, "By Severity", report.by_severity)
    _append_counts(lines, "Promotion Blockers", report.promotion_blockers_by_reason)
    lines.extend(["", "## Warnings", ""])
    if report.warnings:
        for warning in report.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Findings", ""])
    if report.findings:
        for finding in report.findings:
            lines.append(
                f"- `{finding.kind}` `{finding.severity.value}` ref=`{finding.content_ref}` "
                f"surfaces=`{', '.join(finding.surface_ids)}` reason={finding.reason}"
            )
    else:
        lines.append("- No structural findings.")
    lines.extend(["", "## Promotion Candidates", ""])
    if report.promotion_candidates:
        for candidate in report.promotion_candidates:
            lines.append(
                f"- `{candidate.atom_id}` from `{candidate.surface_id}` "
                f"truth=`{candidate.truth_state}` authority=`{candidate.authority_level}`"
            )
    else:
        lines.append("- No atoms passed structural promotion-candidate gates.")
    lines.append("")
    return "\n".join(lines)


def _content_ref_findings(atoms: tuple[MemoryAtom, ...]) -> tuple[MemoryReviewFinding, ...]:
    by_ref: dict[str, list[MemoryAtom]] = defaultdict(list)
    for atom in atoms:
        by_ref[atom.content_ref].append(atom)

    findings: list[MemoryReviewFinding] = []
    for content_ref, grouped in by_ref.items():
        if len(grouped) < 2:
            continue
        truth_states = sorted({atom.truth_state.value for atom in grouped})
        authority_levels = sorted({atom.authority_level.value for atom in grouped})
        if len(truth_states) > 1:
            findings.append(
                _finding(
                    kind="truth_state_conflict_candidate",
                    severity=MemoryReviewSeverity.WARNING,
                    atoms=grouped,
                    content_ref=content_ref,
                    reason="same content_ref carries multiple truth states",
                    metadata={"truth_states": truth_states},
                )
            )
        if len(authority_levels) > 1:
            findings.append(
                _finding(
                    kind="authority_conflict_candidate",
                    severity=MemoryReviewSeverity.INFO,
                    atoms=grouped,
                    content_ref=content_ref,
                    reason="same content_ref carries multiple authority levels",
                    metadata={"authority_levels": authority_levels},
                )
            )
    return tuple(findings)


def _atom_findings(atoms: tuple[MemoryAtom, ...]) -> tuple[MemoryReviewFinding, ...]:
    findings: list[MemoryReviewFinding] = []
    for atom in atoms:
        single = (atom,)
        if _is_projection_atom(atom):
            findings.append(
                _finding(
                    kind="projection_not_authority",
                    severity=MemoryReviewSeverity.WARNING,
                    atoms=single,
                    content_ref=atom.content_ref,
                    reason="projection atom must not be treated as authority",
                    metadata={"projection_of": list(atom.projection_of)},
                )
            )
        if atom.canon_risk.value in {"high", "critical"}:
            findings.append(
                _finding(
                    kind="high_canon_risk",
                    severity=MemoryReviewSeverity.WARNING,
                    atoms=single,
                    content_ref=atom.content_ref,
                    reason="atom has high or critical canon risk",
                    metadata={"canon_risk": atom.canon_risk.value},
                )
            )
        if atom.pii_risk.value in {"high", "critical"}:
            findings.append(
                _finding(
                    kind="high_pii_risk",
                    severity=MemoryReviewSeverity.HIGH,
                    atoms=single,
                    content_ref=atom.content_ref,
                    reason="atom has high or critical PII/secrets risk",
                    metadata={"pii_risk": atom.pii_risk.value},
                )
            )
        if atom.truth_state in {TruthState.SUPERSEDED, TruthState.REJECTED}:
            findings.append(
                _finding(
                    kind="superseded_or_rejected",
                    severity=MemoryReviewSeverity.WARNING,
                    atoms=single,
                    content_ref=atom.content_ref,
                    reason="atom truth state is superseded or rejected",
                    metadata={"truth_state": atom.truth_state.value},
                )
            )
        if atom.supersedes:
            findings.append(
                _finding(
                    kind="supersedes_existing_atom",
                    severity=MemoryReviewSeverity.INFO,
                    atoms=single,
                    content_ref=atom.content_ref,
                    reason="atom claims to supersede other atoms",
                    metadata={"supersedes": list(atom.supersedes)},
                )
            )
        if atom.context_admissible:
            findings.append(
                _finding(
                    kind="context_admissible_atom",
                    severity=MemoryReviewSeverity.INFO,
                    atoms=single,
                    content_ref=atom.content_ref,
                    reason="atom is marked context-admissible and should pass context policy review",
                    metadata={"context_admissible": True},
                )
            )
        if atom.promotion_allowed:
            findings.append(
                _finding(
                    kind="promotion_allowed_atom",
                    severity=MemoryReviewSeverity.INFO,
                    atoms=single,
                    content_ref=atom.content_ref,
                    reason="atom is marked promotion-allowed but still requires gated review",
                    metadata={"promotion_allowed": True},
                )
            )
        if atom.content is not None:
            findings.append(
                _finding(
                    kind="content_present",
                    severity=MemoryReviewSeverity.HIGH,
                    atoms=single,
                    content_ref=atom.content_ref,
                    reason="atom carries bounded content and needs publication review",
                    metadata={"has_content": True},
                )
            )
    return tuple(findings)


def _promotion_blockers(atom: MemoryAtom) -> tuple[str, ...]:
    blockers: list[str] = []
    if not atom.promotion_allowed:
        blockers.append("promotion_not_allowed")
    if atom.truth_state not in {TruthState.OBSERVED, TruthState.CURATED}:
        blockers.append("truth_state_not_observed_or_curated")
    if _is_projection_atom(atom):
        blockers.append("projection_atom")
    if atom.canon_risk.value in {"high", "critical"}:
        blockers.append("high_canon_risk")
    if atom.pii_risk.value in {"high", "critical"}:
        blockers.append("high_pii_risk")
    if atom.truth_state in {TruthState.SUPERSEDED, TruthState.REJECTED}:
        blockers.append("superseded_or_rejected")
    if atom.content is not None:
        blockers.append("content_present")
    return tuple(blockers)


def _finding(
    *,
    kind: str,
    severity: MemoryReviewSeverity,
    atoms: tuple[MemoryAtom, ...] | list[MemoryAtom],
    content_ref: str,
    reason: str,
    metadata: dict[str, object],
) -> MemoryReviewFinding:
    atom_rows = tuple(atoms)
    atom_ids = tuple(sorted(atom.atom_id for atom in atom_rows))
    surface_ids = tuple(sorted({atom.surface_id for atom in atom_rows}))
    safe_content_ref = _safe_content_ref(content_ref)
    return MemoryReviewFinding(
        finding_id=f"{kind}:{safe_content_ref}:{':'.join(atom_ids)[:32]}",
        kind=kind,
        severity=severity,
        atom_ids=atom_ids,
        surface_ids=surface_ids,
        content_ref=safe_content_ref,
        reason=reason,
        metadata=metadata,
    )


def _is_projection_atom(atom: MemoryAtom) -> bool:
    return (
        bool(atom.projection_of)
        or atom.surface_category.value == "projection"
        or atom.memory_lane.value == "projection"
    )


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _safe_content_ref(content_ref: str) -> str:
    if not _needs_ref_redaction(content_ref):
        return content_ref
    digest = hashlib.sha256(content_ref.encode("utf-8")).hexdigest()[:16]
    return f"redacted_ref:{digest}"


def _needs_ref_redaction(content_ref: str) -> bool:
    return (
        content_ref.startswith("/")
        or content_ref.startswith("~")
        or "/" in content_ref
        or "\\" in content_ref
        or len(content_ref) > 96
    )


def _finding_sort_key(finding: MemoryReviewFinding) -> tuple[int, str, str, str]:
    return (
        _SEVERITY_RANK.get(finding.severity, 99),
        finding.kind,
        finding.content_ref,
        finding.finding_id,
    )


def _review_warnings(
    *,
    finding_count: int,
    displayed_finding_count: int,
    conflict_candidate_count: int,
    projection_blocker_count: int,
    promotion_candidate_count: int,
    displayed_promotion_candidate_count: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if finding_count > displayed_finding_count:
        warnings.append(
            f"{finding_count - displayed_finding_count} findings omitted by the bounded finding limit."
        )
    if promotion_candidate_count > displayed_promotion_candidate_count:
        warnings.append(
            f"{promotion_candidate_count - displayed_promotion_candidate_count} promotion candidates omitted by the bounded candidate limit."
        )
    if conflict_candidate_count:
        warnings.append(
            f"{conflict_candidate_count} structural conflict candidates require KnowledgeOps review."
        )
    if projection_blocker_count:
        warnings.append(
            f"{projection_blocker_count} projection atoms must not be treated as authority."
        )
    if promotion_candidate_count:
        warnings.append(
            f"{promotion_candidate_count} atoms passed structural promotion-candidate gates; human or gated review is still required."
        )
    return tuple(warnings)


def _append_counts(lines: list[str], title: str, counts: dict[str, int]) -> None:
    lines.extend(["", f"## {title}", ""])
    if counts:
        for key, count in counts.items():
            lines.append(f"- `{key}`: `{count}`")
    else:
        lines.append("- None.")
