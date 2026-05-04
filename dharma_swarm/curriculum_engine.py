"""Curriculum proposal engine for frontier-task derivation."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid4().hex[:12]


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

    OPPORTUNITY_STAGES: tuple[str, ...] = (
        "scope",
        "validate",
        "deep_research",
        "capability",
        "mvp",
        "first_artifact",
    )

    def derive_from_opportunity_board(
        self,
        opportunities: list[dict[str, Any]],
        *,
        top_k: int = 3,
        min_telos_alignment: float = 0.5,
        addressed_ids: set[str] | None = None,
    ) -> list[FrontierTask]:
        """Bootstrap opportunity-board entries into frontier task chains."""
        addressed = {str(opp_id) for opp_id in (addressed_ids or set())}
        candidates: list[tuple[float, str, float, dict[str, Any]]] = []

        for opportunity in opportunities:
            opp_id = str(opportunity.get("opportunity_id") or "")
            if not opp_id or opp_id in addressed:
                continue

            factor_scores = dict(opportunity.get("factor_scores") or {})
            telos_alignment = float(
                factor_scores.get("telos_alignment")
                or opportunity.get("telos_alignment")
                or 0.0
            )
            if telos_alignment < min_telos_alignment:
                continue

            final_score = float(opportunity.get("final_score") or 0.0)
            candidates.append((final_score, opp_id, telos_alignment, opportunity))

        candidates.sort(key=lambda item: (-item[0], item[1]))

        tasks: list[FrontierTask] = []
        for final_score, opp_id, telos_alignment, opportunity in candidates[:top_k]:
            title = str(opportunity.get("title") or opp_id)
            domain = str(opportunity.get("domain") or "unknown")
            thesis = str(opportunity.get("thesis") or "")
            why_now = str(opportunity.get("why_now") or "")
            provenance_base: dict[str, Any] = {
                "opportunity_id": opp_id,
                "domain": domain,
                "thesis": thesis,
                "why_now": why_now,
                "final_score": final_score,
                "telos_alignment": telos_alignment,
            }

            for stage in self.OPPORTUNITY_STAGES:
                tasks.append(
                    FrontierTask(
                        frontier_id=f"ftask_{stage}_{opp_id}",
                        title=f"{stage.replace('_', ' ').title()}: {title}",
                        description=self._opportunity_stage_description(
                            stage=stage,
                            title=title,
                            thesis=thesis,
                        ),
                        source=f"opportunity:{stage}",
                        verifier_type="research_grade",
                        difficulty=self._difficulty_for_opportunity_stage(
                            stage=stage,
                            final_score=final_score,
                        ),
                        provenance={**provenance_base, "stage": stage},
                        metadata={
                            "seed_kind": "opportunity_bootstrap",
                            "stage": stage,
                        },
                    )
                )

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
    def _opportunity_stage_description(
        *,
        stage: str,
        title: str,
        thesis: str,
    ) -> str:
        thesis_clause = f" Thesis: {thesis}" if thesis else ""
        descriptions = {
            "scope": f"Define the wedge, constraints, and success criteria for {title}.{thesis_clause}",
            "validate": f"Validate demand, feasibility, and telos fit for {title}.{thesis_clause}",
            "deep_research": f"Run a cited deep-research pass for {title}.{thesis_clause}",
            "capability": f"Map the minimum capability needed to execute {title}.{thesis_clause}",
            "mvp": f"Draft the smallest testable MVP plan for {title}.{thesis_clause}",
            "first_artifact": f"Produce the first operator-reviewable artifact for {title}.{thesis_clause}",
        }
        return descriptions.get(stage, f"Advance {title} through the {stage} stage.{thesis_clause}")

    @staticmethod
    def _difficulty_for_opportunity_stage(stage: str, final_score: float) -> str:
        if stage in {"deep_research", "first_artifact"}:
            return "high"
        if final_score >= 80.0 and stage in {"scope", "validate"}:
            return "medium"
        if final_score < 50.0:
            return "high"
        return "medium"

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


__all__ = ["CurriculumEngine", "FrontierTask"]
