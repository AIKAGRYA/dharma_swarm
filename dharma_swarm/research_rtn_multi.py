"""Multi-section Research RTN orchestrator.

Runs 6 section sub-briefs through the RTN pipeline, synthesizes each via
the two-tier LLM engine, merges into a final graded artifact, and wires
results back into the swarm's evolution loop.
"""

from __future__ import annotations

import asyncio
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
from dharma_swarm.auto_research.models import (
    ClaimRecord,
    ResearchBrief,
    ResearchReport,
    SourceDocument,
)
from dharma_swarm.auto_research.reader import SourceReader
from dharma_swarm.auto_research.search import NullSearchBackend, SearchBackend
from dharma_swarm.research_rtn import ResearchRTN, RTNRunResult
from dharma_swarm.research_rtn_synthesize import SynthesisEngine, SynthesizedSection

logger = logging.getLogger(__name__)

ARTIFACT_ROOT = Path.home() / ".dharma" / "artifacts" / "research"
SHARED_DIR = Path.home() / ".dharma" / "shared"
EVOLUTION_DIR = Path.home() / ".dharma" / "evolution"


@dataclass(frozen=True)
class SectionSpec:
    title: str
    description: str
    queries: list[str]
    target_words: int = 600
    requires_recency: bool = True


COMPETITIVE_LANDSCAPE_SECTIONS: list[SectionSpec] = [
    SectionSpec(
        title="Landscape Map: The Top 25 Autonomous Coding Agents",
        description="Comprehensive overview of the top 25 autonomous coding agent systems in production or active development as of April 2026. Include: Devin, Claude Code, Cursor, Codex CLI, OpenHands, SWE-Agent, Aider, Copilot Workspace, Amazon Q Developer, Tabnine, Codeium/Windsurf, Replit Agent, Bolt, v0, Continue, Sweep, Codegen, AutoCodeRover, Mentat, Pear AI, CodeRabbit, Qodo, Augment Code, Poolside, dharma_swarm.",
        queries=[
            "autonomous coding agents production 2026",
            "multi-agent AI frameworks landscape April 2026",
            "open source AI swarm ecosystem coding agents",
            "agentic coding tools landscape April 2026",
            "AI agent startups funding 2025 2026 coding",
        ],
        target_words=800,
    ),
    SectionSpec(
        title="Architecture Patterns: How Production Agents Actually Work",
        description="Deep analysis of architecture patterns across production agents: task selection and scoring, quality gates and verification, memory and continuity across sessions, self-improvement and evolutionary loops, sandboxing and safety mechanisms.",
        queries=[
            "agent task selection scoring function architecture",
            "quality gates autonomous coding agents verification",
            "cross-session memory multi-agent systems Mem0 Zep Letta",
            "self-improvement evolutionary code systems DGM AlphaCode",
        ],
        target_words=800,
    ),
    SectionSpec(
        title="The Hard Problems: Where Every Agent Fails",
        description="Unsolved challenges facing all autonomous coding agents: context window limitations, hallucinated tests and phantom fixes, regression and code slop, cost scaling, the evaluation problem (how do you grade an agent?), alignment under self-modification pressure.",
        queries=[
            "hard problems autonomous coding agents 2026",
            "context loss regression agentic coding systems",
            "hallucinated tests code generation failure modes",
        ],
        target_words=600,
    ),
    SectionSpec(
        title="dharma_swarm's Position in the Landscape",
        description="Honest assessment of where dharma_swarm sits relative to the field. What works: VSM architecture (Beer's cybernetics), stigmergy-based coordination, DGM evolution loop, 11 telos gates, gauntlet adversarial eval. What doesn't: no production users, single-operator system, unproven at scale.",
        queries=[
            "viable system model AI agents Beer cybernetics",
            "stigmergy coordination multi-agent systems",
        ],
        target_words=500,
        requires_recency=False,
    ),
    SectionSpec(
        title="Novel Contributions: What dharma_swarm Does That Nobody Else Does",
        description="Unique architectural innovations: autocatalytic set detection (Kauffman), telos gates as alignment mechanism, contemplative grounding (Akram Vignan), DGM with quality-diversity selection (Sakana pattern), recursive self-reference as design principle, archaeological institutional memory.",
        queries=[
            "autocatalytic set AI agents Kauffman complexity",
            "telos alignment autonomous multi-agent safety",
            "contemplative AI consciousness computing research",
        ],
        target_words=500,
        requires_recency=False,
    ),
    SectionSpec(
        title="Predictions: Where This Goes in 6-12 Months",
        description="Informed predictions about the autonomous coding agent landscape: consolidation (who survives?), regulatory pressure, agent-native applications, the memory problem getting solved, cost curves, and whether autonomous self-improvement actually works.",
        queries=[
            "AI agent predictions 2026 2027 future",
            "autonomous coding agent consolidation market",
            "agent-native applications emerging trends",
        ],
        target_words=500,
    ),
]


@dataclass
class SectionResult:
    spec: SectionSpec
    rtn_result: RTNRunResult | None = None
    synthesis: SynthesizedSection | None = None
    sources: list[SourceDocument] = field(default_factory=list)
    error: str = ""


@dataclass
class MultiSectionResult:
    sections: list[SectionResult] = field(default_factory=list)
    merged_report: ResearchReport | None = None
    reward: RewardSignal | None = None
    artifact: StoredArtifact | None = None
    final_score: float = 0.0
    artifact_path: str = ""
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


class MultiSectionRTN:
    def __init__(
        self,
        *,
        search_backend: SearchBackend | None = None,
        synthesis_engine: SynthesisEngine | None = None,
        artifact_store: RuntimeArtifactStore | None = None,
        sections: list[SectionSpec] | None = None,
        artifact_dir: Path | None = None,
        session_id: str = "",
    ) -> None:
        self.search_backend = search_backend or NullSearchBackend()
        self.synthesis_engine = synthesis_engine or SynthesisEngine()
        self.artifact_store = artifact_store or RuntimeArtifactStore()
        self.sections = sections or COMPETITIVE_LANDSCAPE_SECTIONS
        self.artifact_dir = artifact_dir or ARTIFACT_ROOT / "market-intelligence"
        self.session_id = session_id or f"multi-rtn-{uuid4().hex[:8]}"
        self._reader = SourceReader()
        self._grader = AutoGradeEngine()
        self._rtn = ResearchRTN(
            search_backend=self.search_backend,
            artifact_store=self.artifact_store,
            session_id=self.session_id,
        )

    async def execute(self) -> MultiSectionResult:
        t0 = time.monotonic()
        result = MultiSectionResult()

        # Phase 1: Run RTN per section (search + verify)
        for spec in self.sections:
            logger.info("Section: %s (%d queries)", spec.title, len(spec.queries))
            sr = await self._run_section(spec)
            result.sections.append(sr)
            if sr.error:
                result.errors.append(f"{spec.title}: {sr.error}")
                logger.warning("Section error: %s — %s", spec.title, sr.error)

        # Phase 2: Merge all sources and claims
        all_sources: list[SourceDocument] = []
        all_claims: list[ClaimRecord] = []
        section_texts: list[str] = []
        seen_source_ids: set[str] = set()

        for sr in result.sections:
            if sr.synthesis:
                section_texts.append(f"## {sr.synthesis.title}\n\n{sr.synthesis.text}")
                all_claims.extend(sr.synthesis.claims)
            elif sr.rtn_result and sr.rtn_result.report:
                section_texts.append(f"## {sr.spec.title}\n\n{sr.rtn_result.report.body}")
                all_claims.extend(sr.rtn_result.report.claims)

            for source in sr.sources:
                if source.source_id not in seen_source_ids:
                    all_sources.append(source)
                    seen_source_ids.add(source.source_id)

        # Phase 3: Build merged report
        brief = ResearchBrief(
            task_id=f"landscape-{uuid4().hex[:8]}",
            topic="Autonomous Coding Agents in Production (April 2026)",
            question="How do autonomous coding agents work, and what are the top 25 building E2E?",
            audience="business",
            requires_recency=True,
            source_budget=100,
            metadata={"track": "market-intelligence", "multi_section": True},
        )
        body = "\n\n".join(section_texts) if section_texts else "No sections produced."
        merged = ResearchReport(
            report_id=f"report-{brief.task_id}",
            task_id=brief.task_id,
            brief=brief,
            summary=f"Competitive landscape analysis of {len(all_sources)} sources across {len(result.sections)} sections.",
            body=body,
            claims=all_claims,
            source_ids=[s.source_id for s in all_sources],
            metadata={"section_count": len(result.sections), "total_sources": len(all_sources)},
        )
        result.merged_report = merged

        # Phase 4: Grade
        reward = self._grader.grade(merged, all_sources)
        result.reward = reward
        result.final_score = reward.grade_card.final_score
        logger.info(
            "Final grade: %.2f (gates: %s)",
            reward.grade_card.final_score,
            reward.grade_card.gate_failures or "all passed",
        )

        # Phase 5: Publish
        if reward.gate_multiplier > 0:
            artifact = self._publish(merged, reward, brief, body)
            result.artifact = artifact
            result.artifact_path = str(self.artifact_dir / f"{brief.task_id}.md")
            await self._wire_swarm_feedback(merged, reward, brief)
        else:
            logger.warning("Grade failed gates: %s — not publishing", reward.grade_card.gate_failures)
            # Publish anyway with 'rejected' promotion state for analysis
            artifact = self._publish(merged, reward, brief, body)
            result.artifact = artifact
            result.artifact_path = str(self.artifact_dir / f"{brief.task_id}.md")

        result.duration_seconds = time.monotonic() - t0
        return result

    async def _async_search(
        self,
        brief: ResearchBrief,
        queries: list,
    ) -> list:
        backend = self.search_backend
        if hasattr(backend, "_async_search"):
            return await backend._async_search(brief, queries)
        # Sync backend (e.g., NullSearchBackend) — safe to call directly
        return backend.search(brief, queries)

    async def _run_section(self, spec: SectionSpec) -> SectionResult:
        sr = SectionResult(spec=spec)
        try:
            brief = ResearchBrief(
                task_id=f"section-{uuid4().hex[:6]}",
                topic=spec.title,
                question=spec.description,
                audience="business",
                requires_recency=spec.requires_recency,
                source_budget=15,
                metadata={"track": "market-intelligence", "section": spec.title},
            )

            # Search (async-safe)
            queries = self._rtn._planner.plan(brief)
            raw = await self._async_search(brief, queries)
            sources = self._reader.normalize_all(list(raw))

            # Build claims from sources
            from dharma_swarm.auto_research.claim_graph import ClaimGraphBuilder
            claim_builder = ClaimGraphBuilder()
            claims = claim_builder.build(brief, sources)

            # Enrich sources with full text
            if sources:
                sources = await self._reader.enrich_sources(sources)
                # Re-extract claims after enrichment (more content available)
                enriched_claims = claim_builder.build(brief, sources)
                if len(enriched_claims) > len(claims):
                    claims = enriched_claims
            sr.sources = sources

            # Build basic report for RTN result tracking
            from dharma_swarm.auto_research.reporter import ResearchReporter
            reporter = ResearchReporter()
            report = reporter.create_report(
                brief=brief, queries=queries, sources=sources, claims=claims,
            )

            # Verify claims
            from dharma_swarm.research_rtn_verify import verify_claims
            verification = verify_claims(claims, sources)
            verified_claims = verification.verified_claims or claims

            # Store as RTN result
            from dharma_swarm.research_rtn import RTNRunResult
            sr.rtn_result = RTNRunResult(
                brief=brief,
                report=report,
                verification=verification,
            )

            # Synthesize via two-tier LLM
            summaries = await self.synthesis_engine.summarize_sources(sources)
            synthesis = await self.synthesis_engine.synthesize_section(
                section_title=spec.title,
                section_description=spec.description,
                summaries=summaries,
                claims=verified_claims,
                target_words=spec.target_words,
            )
            sr.synthesis = synthesis

        except Exception as exc:
            sr.error = str(exc)
            logger.exception("Section failed: %s", spec.title)

        return sr

    def _publish(
        self,
        report: ResearchReport,
        reward: RewardSignal,
        brief: ResearchBrief,
        body: str,
    ) -> StoredArtifact:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        content = self._format_artifact(report, reward, brief, body)

        stored = self.artifact_store.create_text_artifact(
            session_id=self.session_id,
            artifact_type="research",
            artifact_kind="competitive_landscape",
            content=content,
            created_by="research_rtn_multi",
            extension="md",
            task_id=brief.task_id,
            promotion_state=reward.grade_card.promotion_state,
            metadata={
                "track": "market-intelligence",
                "topic": brief.topic,
                "final_score": reward.grade_card.final_score,
                "source_count": len(report.source_ids),
                "claim_count": len(report.claims),
                "section_count": report.metadata.get("section_count", 0),
            },
            confidence=reward.grade_card.final_score,
        )

        # Write to track directory
        artifact_path = self.artifact_dir / f"{brief.task_id}.md"
        artifact_path.write_text(content, encoding="utf-8")

        manifest_path = self.artifact_dir / f"{brief.task_id}.manifest.json"
        manifest_path.write_text(json.dumps({
            "task_id": brief.task_id,
            "topic": brief.topic,
            "final_score": reward.grade_card.final_score,
            "promotion_state": reward.grade_card.promotion_state,
            "gate_failures": reward.grade_card.gate_failures,
            "source_count": len(report.source_ids),
            "claim_count": len(report.claims),
            "artifact_id": stored.ref.artifact_id,
        }, indent=2) + "\n", encoding="utf-8")

        logger.info("Published: %s (score=%.2f)", artifact_path, reward.grade_card.final_score)
        return stored

    async def _wire_swarm_feedback(
        self,
        report: ResearchReport,
        reward: RewardSignal,
        brief: ResearchBrief,
    ) -> None:
        # Stigmergy mark
        try:
            from dharma_swarm.stigmergy import StigmergyStore, StigmergicMark
            store = StigmergyStore()
            await store.init_db()
            mark = StigmergicMark(
                agent="research_rtn_multi",
                file_path=str(self.artifact_dir / f"{brief.task_id}.md"),
                action="write",
                observation=f"Published competitive landscape brief. Score: {reward.grade_card.final_score:.2f}. Sources: {len(report.source_ids)}.",
                salience=0.9,
                connections=["auto_research", "market_intelligence", "competitive_landscape"],
            )
            await store.leave_mark(mark)
            logger.info("Stigmergy mark left on research channel")
        except Exception as exc:
            logger.debug("Stigmergy mark failed: %s", exc)

        # Shared research for archaeology
        try:
            SHARED_DIR.mkdir(parents=True, exist_ok=True)
            findings_path = SHARED_DIR / "research_rtn_findings.md"
            findings_path.write_text(
                f"# Research RTN Findings — {brief.topic}\n\n"
                f"Score: {reward.grade_card.final_score:.2f}\n"
                f"Sources: {len(report.source_ids)}\n"
                f"Claims: {len(report.claims)}\n\n"
                f"{report.summary}\n",
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("Shared research write failed: %s", exc)

        # Evolution targets
        if reward.gate_multiplier > 0:
            try:
                EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)
                targets_path = EVOLUTION_DIR / "research_rtn_targets.jsonl"
                with targets_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "source": "research_rtn",
                        "task_id": brief.task_id,
                        "topic": brief.topic,
                        "score": reward.grade_card.final_score,
                        "insights": [c.text[:100] for c in report.claims[:5]],
                    }) + "\n")
            except Exception as exc:
                logger.debug("Evolution targets write failed: %s", exc)

    def _format_artifact(
        self,
        report: ResearchReport,
        reward: RewardSignal,
        brief: ResearchBrief,
        body: str,
    ) -> str:
        header = (
            f"# {brief.topic}\n\n"
            f"**Generated**: April 2026 | **Score**: {reward.grade_card.final_score:.2f} | "
            f"**Sources**: {len(report.source_ids)} | **Claims**: {len(report.claims)}\n\n"
            f"---\n\n"
        )
        footer = (
            "\n\n---\n"
            f"*Generated by Research RTN Multi-Section Pipeline | "
            f"Task: {brief.task_id} | "
            f"Promotion: {reward.grade_card.promotion_state}*\n"
        )
        return header + body + footer
