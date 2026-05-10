"""Research track definitions for the Research RTN."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from dharma_swarm.auto_research.models import ResearchBrief

ARTIFACT_ROOT = Path.home() / ".dharma" / "artifacts" / "research"


@dataclass(frozen=True)
class TrackBriefTemplate:
    topic: str
    question: str
    audience: str = "internal"
    requires_recency: bool = False
    source_budget: int = 12
    time_budget_seconds: int = 300


@dataclass
class ResearchTrack:
    name: str
    slug: str
    artifact_dir: Path
    templates: list[TrackBriefTemplate] = field(default_factory=list)
    cycle_interval_seconds: int = 1800

    def next_brief(self, index: int | None = None) -> ResearchBrief:
        if not self.templates:
            raise ValueError(f"Track '{self.name}' has no brief templates")
        idx = index if index is not None else 0
        tmpl = self.templates[idx % len(self.templates)]
        task_id = f"rtn-{self.slug}-{uuid4().hex[:8]}"
        return ResearchBrief(
            task_id=task_id,
            topic=tmpl.topic,
            question=tmpl.question,
            audience=tmpl.audience,
            requires_recency=tmpl.requires_recency,
            source_budget=tmpl.source_budget,
            time_budget_seconds=tmpl.time_budget_seconds,
            metadata={"track": self.slug, "track_name": self.name},
        )


SWARM_EVOLUTION = ResearchTrack(
    name="Evolve the Swarm",
    slug="swarm-evolution",
    artifact_dir=ARTIFACT_ROOT / "swarm-evolution",
    templates=[
        TrackBriefTemplate(
            topic="agent task selection scoring",
            question="What are the best practices for agent task selection scoring functions? (2025-2026 papers)",
            requires_recency=True,
        ),
        TrackBriefTemplate(
            topic="cross-session agent memory",
            question="How do production multi-agent systems handle cross-session memory? (Mem0, Zep, Letta architectures)",
            requires_recency=True,
        ),
        TrackBriefTemplate(
            topic="agent coordination mechanisms",
            question="What coordination mechanisms produce the highest artifact yield in autonomous coding agents?",
        ),
        TrackBriefTemplate(
            topic="evolutionary code improvement failures",
            question="What are the failure modes of evolutionary code improvement systems? (DGM, AlphaCode, Devin)",
        ),
    ],
)

NEURIPS_FOUNDATION = ResearchTrack(
    name="Deepen the Foundation",
    slug="neurips-foundation",
    artifact_dir=ARTIFACT_ROOT / "neurips-2026",
    templates=[
        TrackBriefTemplate(
            topic="geometric self-referential processing",
            question="All papers measuring geometric properties of self-referential processing in transformers (2023-2026)",
            audience="academic",
            requires_recency=True,
            source_budget=20,
        ),
        TrackBriefTemplate(
            topic="participation ratio in MI",
            question="Participation ratio as a metric in mechanistic interpretability — who else uses it, what do they find?",
            audience="academic",
        ),
        TrackBriefTemplate(
            topic="contemplative phenomenology meets transformers",
            question="Contemplative phenomenology meets transformer internals — any precedent for this bridge?",
            audience="academic",
        ),
        TrackBriefTemplate(
            topic="causal intervention methods in MI",
            question="Causal intervention methods in mechanistic interpretability — best practices for activation patching",
            audience="academic",
            requires_recency=True,
        ),
    ],
)

MARKET_INTELLIGENCE = ResearchTrack(
    name="Build Toward Revenue",
    slug="market-intelligence",
    artifact_dir=ARTIFACT_ROOT / "market-intelligence",
    templates=[
        TrackBriefTemplate(
            topic="AI agent infrastructure landscape",
            question="State of AI agent infrastructure: who's building what, who's funded, what's working (April 2026)",
            audience="business",
            requires_recency=True,
        ),
        TrackBriefTemplate(
            topic="consciousness computing market",
            question="Consciousness computing as a market category — what companies exist, what's the TAM?",
            audience="business",
        ),
        TrackBriefTemplate(
            topic="carbon credit automation",
            question="Carbon credit market automation opportunities — where does AI agent orchestration fit?",
            audience="business",
        ),
        TrackBriefTemplate(
            topic="geometric interpretability tools market",
            question="Geometric interpretability tools — who would pay for a library like geometric_lens?",
            audience="business",
        ),
    ],
)

ALL_TRACKS: list[ResearchTrack] = [SWARM_EVOLUTION, NEURIPS_FOUNDATION, MARKET_INTELLIGENCE]


def get_track(slug: str) -> ResearchTrack:
    for track in ALL_TRACKS:
        if track.slug == slug:
            return track
    raise KeyError(f"Unknown track: {slug}. Available: {[t.slug for t in ALL_TRACKS]}")
