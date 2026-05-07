"""Curriculum proposal engine for frontier-task derivation."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid4().hex[:12]


OPPORTUNITY_BOOTSTRAP_STAGES: tuple[str, ...] = (
    "scope",
    "validate",
    "deep_research",
    "capability",
    "mvp",
    "first_artifact",
)


class FrontierTask(BaseModel):
    """A proposed frontier task derived from existing runtime artifacts."""

    frontier_id: str = Field(default_factory=_new_id)
    title: str
    description: str
    source: str
    verifier_type: str
    difficulty: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CurriculumEngine:
    """Derive explicit next-step tasks from poor or uncertain research outcomes."""

    def derive_from_opportunity_board(
        self,
        board: list[dict[str, Any]],
        *,
        top_k: int = 3,
        min_telos_alignment: float = 0.5,
        addressed_ids: set[str] | None = None,
    ) -> list[FrontierTask]:
        """Bootstrap board opportunities into canonical frontier-task chains.

        This is Layer A's contract with ``opportunity_refill``: one selected
        opportunity becomes one row per canonical campaign stage. The dispatcher
        promotes those rows in stage order through the existing TelicSeam path.
        """
        addressed = addressed_ids or set()
        selected = self._select_opportunities(
            board,
            top_k=top_k,
            min_telos_alignment=min_telos_alignment,
            addressed_ids=addressed,
        )
        tasks: list[FrontierTask] = []
        for opportunity in selected:
            for stage in OPPORTUNITY_BOOTSTRAP_STAGES:
                tasks.append(self._frontier_task_for_opportunity_stage(opportunity, stage))
        return tasks

    def derive_frontier_tasks(
        self,
        *,
        report: Any,
        reward_signal: Any,
    ) -> list[FrontierTask]:
        payload = (
            reward_signal.model_dump()
            if hasattr(reward_signal, "model_dump")
            else dict(reward_signal)
        )
        grade_card = dict(payload.get("grade_card") or {})
        report_id = str(getattr(report, "report_id", "") or "")
        task_id = str(getattr(report, "task_id", "") or "")
        final_score = float(grade_card.get("final_score", 0.0) or 0.0)
        tasks: list[FrontierTask] = []

        for gate_failure in list(grade_card.get("gate_failures") or []):
            tasks.append(
                FrontierTask(
                    title=f"Resolve gate failure: {gate_failure}",
                    description=f"Produce evidence that clears the {gate_failure} gate.",
                    source="gate_failure",
                    verifier_type="research_grade",
                    difficulty=self._difficulty_for_gate_failure(gate_failure, final_score),
                    provenance={
                        "report_id": report_id,
                        "task_id": task_id,
                        "gate_failure": gate_failure,
                    },
                    metadata={"seed_kind": "gate_failure"},
                )
            )

        for contradiction in list(getattr(report, "contradictions", []) or []):
            if str(contradiction.get("status", "")).lower() != "unresolved":
                continue
            tasks.append(
                FrontierTask(
                    title="Resolve unresolved contradiction",
                    description="Investigate and reconcile the unresolved contradiction.",
                    source="contradiction",
                    verifier_type="contradiction_review",
                    difficulty="high",
                    provenance={
                        "report_id": report_id,
                        "task_id": task_id,
                        "claim_id": str(contradiction.get("claim_id", "") or ""),
                    },
                    metadata={"seed_kind": "contradiction"},
                )
            )

        freshness = float(grade_card.get("freshness", 0.0) or 0.0)
        brief = getattr(report, "brief", None)
        if getattr(brief, "requires_recency", False) and freshness < 0.8:
            tasks.append(
                FrontierTask(
                    title="Refresh stale capability evidence",
                    description="Repeat retrieval with stronger recency constraints.",
                    source="staleness",
                    verifier_type="freshness_probe",
                    difficulty="medium",
                    provenance={
                        "report_id": report_id,
                        "task_id": task_id,
                        "freshness": freshness,
                    },
                    metadata={"seed_kind": "freshness"},
                )
            )

        for claim in list(getattr(report, "claims", []) or []):
            confidence = float(getattr(claim, "confidence", 0.0) or 0.0)
            if confidence >= 0.5:
                continue
            tasks.append(
                FrontierTask(
                    title="Reduce claim uncertainty",
                    description="Collect stronger evidence for the low-confidence claim.",
                    source="uncertainty",
                    verifier_type="claim_audit",
                    difficulty="medium" if confidence >= 0.3 else "high",
                    provenance={
                        "report_id": report_id,
                        "task_id": task_id,
                        "claim_id": str(getattr(claim, "claim_id", "") or ""),
                    },
                    metadata={"seed_kind": "uncertainty", "confidence": confidence},
                )
            )

        return tasks

    @staticmethod
    def _difficulty_for_gate_failure(gate_failure: str, final_score: float) -> str:
        severe = {
            "unresolved_high_severity_contradictions",
            "unsupported_claim_ratio",
            "freshness",
        }
        if gate_failure in severe or final_score < 0.4:
            return "high"
        if final_score < 0.7:
            return "medium"
        return "low"

    @staticmethod
    def _select_opportunities(
        board: list[dict[str, Any]],
        *,
        top_k: int,
        min_telos_alignment: float,
        addressed_ids: set[str],
    ) -> list[dict[str, Any]]:
        addressable: list[dict[str, Any]] = []
        for opportunity in board:
            if not isinstance(opportunity, dict):
                continue
            opp_id = str(opportunity.get("opportunity_id") or "")
            if not opp_id or opp_id in addressed_ids:
                continue
            scores = dict(opportunity.get("factor_scores") or {})
            telos = _as_float(scores.get("telos_alignment"), default=0.0)
            if telos < min_telos_alignment:
                continue
            addressable.append(opportunity)
        addressable.sort(
            key=lambda opportunity: _as_float(opportunity.get("final_score"), default=0.0),
            reverse=True,
        )
        return addressable[:max(0, int(top_k))]

    @staticmethod
    def _frontier_task_for_opportunity_stage(
        opportunity: dict[str, Any],
        stage: str,
    ) -> FrontierTask:
        opp_id = str(opportunity.get("opportunity_id") or "")
        title = str(opportunity.get("title") or opp_id)
        domain = str(opportunity.get("domain") or "unknown")
        thesis = str(opportunity.get("thesis") or "opportunity")
        scores = dict(opportunity.get("factor_scores") or {})
        final_score = _as_float(opportunity.get("final_score"), default=0.0)
        return FrontierTask(
            title=f"{stage.replace('_', ' ').title()} for {title}",
            description=_stage_description(stage, title, thesis),
            source=f"opportunity:{stage}",
            verifier_type=_verifier_for_stage(stage),
            difficulty=_difficulty_for_opportunity_stage(stage, final_score),
            provenance={
                "opportunity_id": opp_id,
                "opportunity_title": title,
                "domain": domain,
                "thesis": thesis,
                "final_score": final_score,
                "factor_scores": scores,
                "stage": stage,
            },
            metadata={
                "seed_kind": "opportunity_bootstrap",
                "stage": stage,
                "opportunity_id": opp_id,
            },
        )


def _stage_description(stage: str, title: str, thesis: str) -> str:
    templates = {
        "scope": "Define beneficiary, boundary, risk, and proof target for {title}.",
        "validate": "Validate telos alignment, need, constraints, and non-goals for {title}.",
        "deep_research": "Produce cited research and falsification checks for {title}.",
        "capability": "Map existing capabilities, gaps, owners, and tests for {title}.",
        "mvp": "Build or specify the smallest verified capability slice for {title}.",
        "first_artifact": "Deliver the first externally useful artifact for {title}.",
    }
    base = templates.get(stage, "Advance {title}.")
    return f"{base.format(title=title)} Thesis: {thesis}."


def _verifier_for_stage(stage: str) -> str:
    if stage == "deep_research":
        return "research_grade"
    if stage == "first_artifact":
        return "artifact_contract"
    return "stage_doc"


def _difficulty_for_opportunity_stage(stage: str, final_score: float) -> str:
    if stage in {"deep_research", "mvp", "first_artifact"}:
        return "high" if final_score >= 75.0 else "medium"
    return "medium" if final_score >= 50.0 else "low"


def _as_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = ["CurriculumEngine", "FrontierTask", "OPPORTUNITY_BOOTSTRAP_STAGES"]
