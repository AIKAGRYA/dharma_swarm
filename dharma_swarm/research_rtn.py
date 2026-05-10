"""Research RTN — Recursive Transition Network for artifact-producing research.

PLAN → SEARCH → VERIFY → SYNTHESIZE → GRADE → PUBLISH → REVIEW
  ↑                                                        │
  └──────────── (if grade fails or review finds gaps) ─────┘
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.artifact_store import RuntimeArtifactStore, StoredArtifact
from dharma_swarm.auto_grade.engine import AutoGradeEngine
from dharma_swarm.auto_grade.models import RewardSignal
from dharma_swarm.auto_research.claim_graph import ClaimGraphBuilder
from dharma_swarm.auto_research.engine import AutoResearchEngine
from dharma_swarm.auto_research.models import (
    ClaimRecord,
    ResearchBrief,
    ResearchReport,
    SourceDocument,
)
from dharma_swarm.auto_research.planner import ResearchPlanner
from dharma_swarm.auto_research.reader import SourceReader
from dharma_swarm.auto_research.reporter import ResearchReporter
from dharma_swarm.auto_research.search import NullSearchBackend, SearchBackend
from dharma_swarm.research_rtn_review import ReviewResult, review_report
from dharma_swarm.research_rtn_verify import VerificationResult, verify_claims

logger = logging.getLogger(__name__)

MAX_DEPTH = 3
ARTIFACT_ROOT = Path.home() / ".dharma" / "artifacts" / "research"


@dataclass
class RTNRunResult:
    brief: ResearchBrief
    report: ResearchReport | None = None
    reward: RewardSignal | None = None
    verification: VerificationResult | None = None
    review: ReviewResult | None = None
    artifact: StoredArtifact | None = None
    sub_results: list["RTNRunResult"] = field(default_factory=list)
    depth: int = 0
    passed_gates: bool = False
    error: str = ""
    duration_seconds: float = 0.0


class ResearchRTN:
    def __init__(
        self,
        *,
        search_backend: SearchBackend | None = None,
        artifact_store: RuntimeArtifactStore | None = None,
        synthesis_engine: Any | None = None,
        max_depth: int = MAX_DEPTH,
        session_id: str = "",
        artifact_dir: Path | None = None,
    ) -> None:
        self.search_backend = search_backend or NullSearchBackend()
        self.artifact_store = artifact_store or RuntimeArtifactStore()
        self.synthesis_engine = synthesis_engine
        self.max_depth = max_depth
        self.session_id = session_id or f"rtn-{uuid4().hex[:8]}"
        self.artifact_dir = artifact_dir or ARTIFACT_ROOT

        self._planner = ResearchPlanner()
        self._reader = SourceReader()
        self._claim_graph = ClaimGraphBuilder()
        self._reporter = ResearchReporter()
        self._grader = AutoGradeEngine()
        self._engine = AutoResearchEngine(
            planner=self._planner,
            search_backend=self.search_backend,
            reader=self._reader,
            claim_graph=self._claim_graph,
            reporter=self._reporter,
        )

    def execute_brief(self, brief: ResearchBrief, *, depth: int = 0) -> RTNRunResult:
        t0 = time.monotonic()
        result = RTNRunResult(brief=brief, depth=depth)

        try:
            # PLAN + SEARCH + SYNTHESIZE (via engine.run)
            report = self._engine.run(brief)
            result.report = report

            # Collect sources for grading
            queries = self._planner.plan(brief)
            raw_sources = self.search_backend.search(brief, queries)
            sources = self._reader.normalize_all(list(raw_sources))

            # VERIFY
            verification = verify_claims(report.claims, sources)
            result.verification = verification

            # Rebuild report with verified claims
            all_verified = verification.verified_claims + verification.contradicted_claims
            if all_verified:
                report = self._reporter.create_report(
                    brief=brief,
                    queries=queries,
                    sources=sources,
                    claims=all_verified,
                )
                result.report = report

            # GRADE
            reward = self._grader.grade(report, sources)
            result.reward = reward
            result.passed_gates = reward.gate_multiplier > 0

            # REVIEW
            review = review_report(
                report=report,
                verification=verification,
                reward=reward,
                original_brief=brief,
            )
            result.review = review

            # RECURSIVE EXPANSION
            if review.should_recurse and depth < self.max_depth:
                for sub_brief in review.follow_up_briefs:
                    sub_result = self.execute_brief(sub_brief, depth=depth + 1)
                    result.sub_results.append(sub_result)

                # RE-SYNTHESIZE if sub-results improved things
                merged_claims = list(report.claims)
                for sr in result.sub_results:
                    if sr.report and sr.passed_gates:
                        merged_claims.extend(sr.report.claims)

                if len(merged_claims) > len(report.claims):
                    report = self._reporter.create_report(
                        brief=brief,
                        queries=queries,
                        sources=sources,
                        claims=merged_claims,
                    )
                    result.report = report
                    reward = self._grader.grade(report, sources)
                    result.reward = reward
                    result.passed_gates = reward.gate_multiplier > 0

            # PUBLISH (only at depth 0, only if gates pass)
            if depth == 0 and result.passed_gates:
                result.artifact = self._publish(report, reward, brief)

        except Exception as exc:
            result.error = str(exc)
            logger.exception("RTN execution failed for %s", brief.task_id)

        result.duration_seconds = time.monotonic() - t0
        return result

    def execute(self, topic: str, **kwargs: Any) -> RTNRunResult:
        brief = ResearchBrief(
            task_id=f"rtn-adhoc-{uuid4().hex[:8]}",
            topic=topic,
            question=topic,
            **kwargs,
        )
        return self.execute_brief(brief)

    def _publish(
        self,
        report: ResearchReport,
        reward: RewardSignal,
        brief: ResearchBrief,
    ) -> StoredArtifact:
        track = brief.metadata.get("track", "adhoc")
        out_dir = self.artifact_dir / track
        out_dir.mkdir(parents=True, exist_ok=True)

        content = self._format_artifact(report, reward, brief)

        stored = self.artifact_store.create_text_artifact(
            session_id=self.session_id,
            artifact_type="research_report",
            artifact_kind="research_rtn_report",
            content=content,
            created_by="research_rtn",
            extension="md",
            task_id=brief.task_id,
            promotion_state=reward.grade_card.promotion_state,
            metadata={
                "track": track,
                "topic": brief.topic,
                "final_score": reward.grade_card.final_score,
                "gate_failures": reward.grade_card.gate_failures,
                "source_count": len(report.source_ids),
                "claim_count": len(report.claims),
            },
            confidence=reward.grade_card.final_score,
        )

        # Also write to track artifact directory
        artifact_path = out_dir / f"{brief.task_id}.md"
        artifact_path.write_text(content, encoding="utf-8")

        manifest_path = out_dir / f"{brief.task_id}.manifest.json"
        manifest_path.write_text(json.dumps({
            "task_id": brief.task_id,
            "track": track,
            "topic": brief.topic,
            "final_score": reward.grade_card.final_score,
            "promotion_state": reward.grade_card.promotion_state,
            "gate_failures": reward.grade_card.gate_failures,
            "source_count": len(report.source_ids),
            "claim_count": len(report.claims),
            "artifact_id": stored.ref.artifact_id,
        }, indent=2) + "\n", encoding="utf-8")

        logger.info(
            "Published RTN artifact: %s (score=%.2f, track=%s)",
            brief.task_id,
            reward.grade_card.final_score,
            track,
        )
        return stored

    def _format_artifact(
        self,
        report: ResearchReport,
        reward: RewardSignal,
        brief: ResearchBrief,
    ) -> str:
        lines = [
            f"# {brief.topic}",
            "",
            f"**Question**: {brief.question}",
            f"**Track**: {brief.metadata.get('track', 'adhoc')}",
            f"**Score**: {reward.grade_card.final_score:.2f}",
            f"**Sources**: {len(report.source_ids)}",
            f"**Claims**: {len(report.claims)}",
            "",
            "## Summary",
            "",
            report.summary,
            "",
            "## Findings",
            "",
            report.body,
            "",
        ]

        if report.contradictions:
            lines.append("## Contradictions")
            lines.append("")
            for c in report.contradictions:
                lines.append(f"- {c}")
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated by Research RTN | Task: {brief.task_id}*")
        return "\n".join(lines)
