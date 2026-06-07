"""Business idea gauntlet for revenue/outreach approval readiness.

The gauntlet is intentionally file-backed and deterministic. It does not send
outreach, approve outreach, or create a new runtime authority. It only reads a
candidate folder and decides whether the candidate is ready for human review.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DECISION_PASS = "PASS_TO_HUMAN"
DECISION_REFINE = "REFINE"
DECISION_PARK = "PARK"
DECISION_HOLD = "HOLD"
DECISION_KILL = "KILL"

PASSING_GATE_STATUSES = {"pass", "passed", "ok"}
PASSING_EVIDENCE_GRADES = {"A", "B"}
PASSING_RED_TEAM = {"pass", "passed", "ok"}
REFINING_RED_TEAM = {"refine", "refine_required", "needs_refinement"}
PARKING_RED_TEAM = {"park", "parked"}
HOLDING_RED_TEAM = {"hold", "held"}
BLOCKING_RED_TEAM = {"kill", "no_go", "no-go"}
APPROVED_EVIDENCE_URI_SCHEMES = {"artifact", "http", "https", "receipt", "sakshi"}
HARD_GATES = (
    "buyer_pain",
    "budget_wtp",
    "channel",
    "delivery_proof",
    "risk_welfare",
)

SCORE_WEIGHTS = {
    "buyer_pain_specificity": 20,
    "budget_wtp_signal": 15,
    "channel_access": 15,
    "delivery_fit": 15,
    "differentiation": 10,
    "receipt_path_clarity": 10,
    "vision_telos_fit": 10,
    "risk_cleanliness": 5,
}


@dataclass(frozen=True)
class GateFinding:
    gate: str
    status: str
    severity: str
    message: str


@dataclass(frozen=True)
class GauntletEvaluation:
    candidate_id: str
    title: str
    decision: str
    score: int
    hard_gate_failures: list[GateFinding] = field(default_factory=list)
    findings: list[GateFinding] = field(default_factory=list)
    can_create_human_packet: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_candidate(candidate_dir: str | Path) -> dict[str, Any]:
    """Load a candidate's gate evidence from a file-backed run directory."""
    path = Path(candidate_dir) / "gate_evidence.json"
    if not path.exists():
        raise FileNotFoundError(f"missing gate evidence: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("gate_evidence.json root must be an object")
    return payload


def evaluate_candidate_dir(candidate_dir: str | Path) -> GauntletEvaluation:
    candidate_path = Path(candidate_dir)
    return evaluate_candidate(
        load_candidate(candidate_path),
        evidence_base_dir=candidate_path,
        require_resolvable_refs=True,
        repo_root=_find_repo_root(candidate_path),
    )


def evaluate_candidate(
    candidate: dict[str, Any],
    *,
    evidence_base_dir: str | Path | None = None,
    repo_root: str | Path | None = None,
    require_resolvable_refs: bool = False,
) -> GauntletEvaluation:
    """Evaluate one business idea candidate against hard gates and scorecard."""
    candidate_id = str(candidate.get("candidate_id") or "unknown")
    title = str(candidate.get("title") or candidate_id)
    gates = _dict(candidate.get("gates"))
    scorecard = _dict(candidate.get("scorecard"))
    red_team = _dict(candidate.get("red_team"))
    override = bool(candidate.get("operator_ceo_override"))

    hard_failures: list[GateFinding] = []
    findings: list[GateFinding] = []

    for gate_name in HARD_GATES:
        raw_gate = gates.get(gate_name)
        if gate_name not in gates:
            hard_failures.append(GateFinding(
                gate=gate_name,
                status="missing",
                severity="ERROR",
                message=f"Hard gate {gate_name} is missing.",
            ))
            continue
        if not isinstance(raw_gate, dict):
            hard_failures.append(GateFinding(
                gate=gate_name,
                status="malformed",
                severity="ERROR",
                message=f"Hard gate {gate_name} must be an object.",
            ))
            continue

        gate = raw_gate
        status = _normalised_token(gate.get("status"))
        grade = _normalised_grade(gate.get("evidence_grade"))
        refs = _evidence_refs(gate.get("evidence_refs"))

        if status not in PASSING_GATE_STATUSES:
            hard_failures.append(GateFinding(
                gate=gate_name,
                status=status,
                severity="ERROR",
                message=f"Hard gate {gate_name} is not passed.",
            ))
            continue
        if grade == "C":
            hard_failures.append(GateFinding(
                gate=gate_name,
                status=status,
                severity="ERROR",
                message=f"Hard gate {gate_name} cannot pass on C-grade evidence.",
            ))
            continue
        if grade not in PASSING_EVIDENCE_GRADES:
            hard_failures.append(GateFinding(
                gate=gate_name,
                status=status,
                severity="ERROR",
                message=f"Hard gate {gate_name} has unknown evidence grade {grade}.",
            ))
            continue
        if not refs:
            hard_failures.append(GateFinding(
                gate=gate_name,
                status=status,
                severity="ERROR",
                message=f"Hard gate {gate_name} has no evidence refs.",
            ))
            continue
        if require_resolvable_refs:
            unresolved_ref = _first_unresolved_evidence_ref(
                refs,
                evidence_base_dir=evidence_base_dir,
                repo_root=repo_root,
            )
            if unresolved_ref is not None:
                hard_failures.append(GateFinding(
                    gate=gate_name,
                    status=status,
                    severity="ERROR",
                    message=f"Hard gate {gate_name} has unresolved evidence ref: {unresolved_ref}.",
                ))

    scorecard_findings = _scorecard_findings(scorecard)
    findings.extend(scorecard_findings)

    red_team_recommendation = _normalised_token(red_team.get("recommendation"))
    if red_team_recommendation in BLOCKING_RED_TEAM:
        findings.append(GateFinding(
            gate="red_team",
            status=red_team_recommendation,
            severity="ERROR",
            message="Red-team kill recommendation blocks human packet creation.",
        ))
        if override:
            return GauntletEvaluation(
                candidate_id=candidate_id,
                title=title,
                decision=DECISION_HOLD,
                score=_weighted_score(scorecard),
                hard_gate_failures=hard_failures,
                findings=findings,
                can_create_human_packet=False,
            )
        return GauntletEvaluation(
            candidate_id=candidate_id,
            title=title,
            decision=DECISION_KILL,
            score=_weighted_score(scorecard),
            hard_gate_failures=hard_failures,
            findings=findings,
            can_create_human_packet=False,
        )

    score = _weighted_score(scorecard)
    red_team_decision: str | None = None
    if red_team_recommendation in HOLDING_RED_TEAM:
        findings.append(GateFinding(
            gate="red_team",
            status=red_team_recommendation,
            severity="ERROR",
            message="Red-team hold recommendation blocks human packet creation.",
        ))
        red_team_decision = DECISION_HOLD
    elif red_team_recommendation in REFINING_RED_TEAM:
        findings.append(GateFinding(
            gate="red_team",
            status=red_team_recommendation,
            severity="WARNING",
            message="Red-team refinement recommendation blocks human packet creation.",
        ))
        red_team_decision = DECISION_REFINE
    elif red_team_recommendation in PARKING_RED_TEAM:
        findings.append(GateFinding(
            gate="red_team",
            status=red_team_recommendation,
            severity="WARNING",
            message="Red-team park recommendation blocks human packet creation.",
        ))
        red_team_decision = DECISION_PARK
    elif red_team_recommendation not in PASSING_RED_TEAM:
        findings.append(GateFinding(
            gate="red_team",
            status=red_team_recommendation,
            severity="ERROR",
            message="Red-team recommendation is missing or unknown.",
        ))
        red_team_decision = DECISION_HOLD

    if hard_failures or scorecard_findings:
        return GauntletEvaluation(
            candidate_id=candidate_id,
            title=title,
            decision=DECISION_HOLD,
            score=score,
            hard_gate_failures=hard_failures,
            findings=findings,
            can_create_human_packet=False,
        )

    if red_team_decision is not None:
        return GauntletEvaluation(
            candidate_id=candidate_id,
            title=title,
            decision=red_team_decision,
            score=score,
            hard_gate_failures=hard_failures,
            findings=findings,
            can_create_human_packet=False,
        )

    if score >= 75:
        packet_failure = _human_packet_failure(
            candidate,
            evidence_base_dir=evidence_base_dir,
            repo_root=repo_root,
            require_resolvable_refs=require_resolvable_refs,
        )
        if packet_failure is None:
            decision = DECISION_PASS
        else:
            findings.append(GateFinding(
                gate="human_packet",
                status="missing_or_unresolved",
                severity="ERROR",
                message=packet_failure,
            ))
            decision = DECISION_HOLD
    elif score >= 60:
        decision = DECISION_REFINE
    else:
        decision = DECISION_PARK

    return GauntletEvaluation(
        candidate_id=candidate_id,
        title=title,
        decision=decision,
        score=score,
        hard_gate_failures=hard_failures,
        findings=findings,
        can_create_human_packet=decision == DECISION_PASS,
    )


def write_evaluation(candidate_dir: str | Path, evaluation: GauntletEvaluation) -> Path:
    """Write evaluation.json beside gate_evidence.json for operator review."""
    path = Path(candidate_dir) / "evaluation.json"
    path.write_text(
        json.dumps(evaluation.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _weighted_score(scorecard: dict[str, Any]) -> int:
    total = 0.0
    weight_total = sum(SCORE_WEIGHTS.values())
    for key, weight in SCORE_WEIGHTS.items():
        raw = scorecard.get(key, 0)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        value = max(0.0, min(5.0, value))
        total += (value / 5.0) * weight
    if weight_total != 100:
        total *= 100 / weight_total
    return int(round(total))


def _scorecard_findings(scorecard: dict[str, Any]) -> list[GateFinding]:
    missing_keys = [key for key in SCORE_WEIGHTS if key not in scorecard]
    if not missing_keys:
        return []
    return [
        GateFinding(
            gate="scorecard",
            status="missing_keys",
            severity="ERROR",
            message="Scorecard missing required keys: " + ", ".join(missing_keys),
        )
    ]


def _human_packet_failure(
    candidate: dict[str, Any],
    *,
    evidence_base_dir: str | Path | None,
    repo_root: str | Path | None,
    require_resolvable_refs: bool,
) -> str | None:
    if not require_resolvable_refs:
        return None

    packet_ref = candidate.get("human_packet_ref")
    if not isinstance(packet_ref, str) or not packet_ref.strip():
        default_packet = Path(evidence_base_dir or ".") / "human_packet.md"
        if default_packet.exists():
            return None
        return "PASS_TO_HUMAN requires a resolvable human_packet_ref or human_packet.md."

    unresolved_ref = _first_unresolved_evidence_ref(
        [packet_ref],
        evidence_base_dir=evidence_base_dir,
        repo_root=repo_root,
    )
    if unresolved_ref is not None:
        return f"PASS_TO_HUMAN has unresolved human packet ref: {unresolved_ref}."
    return None


def _first_unresolved_evidence_ref(
    refs: list[str],
    *,
    evidence_base_dir: str | Path | None,
    repo_root: str | Path | None,
) -> str | None:
    base_dir = Path(evidence_base_dir) if evidence_base_dir is not None else None
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    for ref in refs:
        if not _evidence_ref_resolves(ref, evidence_base_dir=base_dir, repo_root=root):
            return ref
    return None


def _evidence_ref_resolves(
    ref: str,
    *,
    evidence_base_dir: Path | None,
    repo_root: Path,
) -> bool:
    parsed = urlparse(ref)
    if parsed.scheme:
        if parsed.scheme not in APPROVED_EVIDENCE_URI_SCHEMES:
            return False
        if parsed.scheme in {"http", "https"}:
            return bool(parsed.netloc)
        return bool(parsed.netloc or parsed.path)

    ref_path = Path(ref)
    candidates = [ref_path] if ref_path.is_absolute() else [repo_root / ref_path]
    if evidence_base_dir is not None and not ref_path.is_absolute():
        candidates.append(evidence_base_dir / ref_path)

    for candidate in candidates:
        resolved = candidate.resolve()
        if not resolved.exists():
            continue
        try:
            resolved.relative_to(repo_root.resolve())
            return True
        except ValueError:
            if evidence_base_dir is None:
                continue
        try:
            resolved.relative_to(evidence_base_dir.resolve())
        except (AttributeError, ValueError):
            continue
        return True
    return False


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [ref.strip() for ref in value if isinstance(ref, str) and ref.strip()]


def _normalised_grade(value: Any) -> str:
    if not isinstance(value, str):
        return "missing"
    return value.strip().upper() or "missing"


def _normalised_token(value: Any) -> str:
    if not isinstance(value, str):
        return "missing" if value is None else "malformed"
    return value.strip().lower().replace("-", "_").replace(" ", "_") or "missing"


def _find_repo_root(path: Path) -> Path:
    search_start = path if path.is_dir() else path.parent
    for candidate in (search_start, *search_start.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return Path.cwd()
