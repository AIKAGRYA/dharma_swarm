"""ShaktiZeitgeistExecutive — thin strategic executive layer (Phase 1: read-only).

Ingests signals from zeitgeist, mission state, organism/algedonic, and
capability sources.  Scores opportunities with a 12-factor model.  Tracks
domain balance across 8 operational domains.  Emits durable artifacts under
``~/.dharma/meta/``.

Phase 1 does NOT control dispatch, mint campaigns, or influence DGM.  It
writes ``allocation_weights.json`` but nothing reads it yet (Phase 2).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.models import _new_id, _utc_now

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOMAINS: tuple[str, ...] = (
    "internal_maintenance",
    "reliability",
    "research",
    "artifact_publication",
    "productization",
    "ecosystem_scan",
    "revenue_exploration",
    "strategic_infrastructure",
)

THEME_TO_DOMAIN: dict[str, str] = {
    "autonomy": "internal_maintenance",
    "cybernetics": "internal_maintenance",
    "memory": "internal_maintenance",
    "reliability": "reliability",
    "research": "research",
    "infrastructure": "strategic_infrastructure",
    "monetization": "revenue_exploration",
    "sustainability_impact": "artifact_publication",
}

SCORING_FACTORS: dict[str, float] = {
    "telos_alignment": 2.5,
    "world_value": 2.0,
    "leverage": 2.0,
    "algedonic_urgency": 2.0,
    "novelty": 1.5,
    "urgency": 1.5,
    "capability_fit": 1.5,
    "domain_balance_bonus": 1.5,
    "artifact_potential": 1.0,
    "strategic_compounding": 1.0,
    "internal_churn_penalty": -2.0,
    "repetition_penalty": -1.5,
}

MAX_SCORE = sum(abs(w) for w in SCORING_FACTORS.values())
MAX_BRIEFS = 100
STARVATION_DEFICIT_THRESHOLD = 0.10
STARVATION_HOURS_THRESHOLD = 72.0
INTERNAL_CHURN_SHARE_THRESHOLD = 0.40

# Domains that produce world-facing artifacts (bonus for world_value factor).
_WORLD_FACING = frozenset({
    "research", "artifact_publication", "productization",
    "revenue_exploration", "ecosystem_scan",
})


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ExecutiveSignal(BaseModel):
    signal_id: str = Field(default_factory=_new_id)
    source: str
    category: str
    title: str
    relevance: float = 0.0
    urgency: float = 0.0
    domain: str = ""
    keywords: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)


class ScoredOpportunity(BaseModel):
    opportunity_id: str = Field(default_factory=_new_id)
    title: str
    domain: str
    thesis: str = ""
    factor_scores: dict[str, float] = Field(default_factory=dict)
    final_score: float = 0.0
    evidence_signals: list[str] = Field(default_factory=list)
    why_now: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class DomainBalance(BaseModel):
    domain: str
    signal_share: float = 0.0
    target_share: float = 0.0
    deficit: float = 0.0
    last_activity_ts: str = ""
    starvation: bool = False
    opportunity_count: int = 0


class AllocationWeights(BaseModel):
    per_domain: dict[str, float] = Field(default_factory=dict)
    starvation_boosts: dict[str, float] = Field(default_factory=dict)
    churn_penalties: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)


class ExecutiveCycleState(BaseModel):
    cycle_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utc_now)
    signals_ingested: int = 0
    signals_by_source: dict[str, int] = Field(default_factory=dict)
    opportunities: list[ScoredOpportunity] = Field(default_factory=list)
    domain_balances: list[DomainBalance] = Field(default_factory=list)
    starvation_alerts: list[str] = Field(default_factory=list)
    organism_health: dict[str, float] = Field(default_factory=dict)
    allocation_weights: AllocationWeights = Field(default_factory=AllocationWeights)
    mission_title: str = ""
    mission_status: str = ""
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Executive engine
# ---------------------------------------------------------------------------


class ShaktiZeitgeistExecutive:
    """Phase 1 read-only strategic executive.

    Args:
        state_dir: Root of the ``.dharma`` state tree.  Defaults to
            ``~/.dharma``.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or (Path.home() / ".dharma")
        self._meta_dir = self._state_dir / "meta"
        self._briefs_dir = self._meta_dir / "executive_briefs"
        self._history_path = self._meta_dir / "executive_history.jsonl"
        self._recent_domains: list[str] = []

    async def cycle(self) -> ExecutiveCycleState:
        """Run one executive cycle: ingest, score, balance, emit."""
        t0 = time.monotonic()

        signals = self._ingest_signals()
        mission_state, mission_title, mission_status, mission_theme = self._read_mission()
        pulse_health = self._read_organism()
        balances = self._compute_domain_balance(signals)
        opportunities = self._rank_opportunities(
            signals, balances, mission_theme, pulse_health,
        )
        weights = self._build_allocation_weights(balances)
        starvation_alerts = [b.domain for b in balances if b.starvation]

        # Track recent domains for repetition penalty.
        if opportunities:
            self._recent_domains.append(opportunities[0].domain)
        if len(self._recent_domains) > 10:
            self._recent_domains = self._recent_domains[-10:]

        state = ExecutiveCycleState(
            signals_ingested=len(signals),
            signals_by_source=_count_by(signals, "source"),
            opportunities=opportunities[:8],
            domain_balances=balances,
            starvation_alerts=starvation_alerts,
            organism_health=pulse_health,
            allocation_weights=weights,
            mission_title=mission_title,
            mission_status=mission_status,
            duration_ms=round((time.monotonic() - t0) * 1000, 1),
        )

        self._emit_artifacts(state)
        return state

    # -- signal ingestion ---------------------------------------------------

    def _ingest_signals(self) -> list[ExecutiveSignal]:
        signals: list[ExecutiveSignal] = []
        signals.extend(self._ingest_zeitgeist())
        signals.extend(self._ingest_mission())
        signals.extend(self._ingest_organism())
        signals.extend(self._ingest_algedonic())
        return signals

    def _ingest_zeitgeist(self) -> list[ExecutiveSignal]:
        try:
            from dharma_swarm.zeitgeist import ZeitgeistScanner
            scanner = ZeitgeistScanner(state_dir=self._state_dir)
            raw = scanner.load_history()
        except Exception:
            return []

        # Take last 200 signals to bound memory.
        out: list[ExecutiveSignal] = []
        for sig in raw[-200:]:
            domain = self._classify_domain(sig.title + " " + sig.description)
            out.append(ExecutiveSignal(
                source="zeitgeist",
                category=sig.category,
                title=sig.title,
                relevance=sig.relevance_score,
                urgency=1.0 if sig.category == "threat" else 0.3,
                domain=domain,
                keywords=sig.keywords,
                timestamp=sig.timestamp,
            ))
        return out

    def _ingest_mission(self) -> list[ExecutiveSignal]:
        try:
            from dharma_swarm.mission_contract import load_active_mission_state
            artifact = load_active_mission_state(state_dir=self._state_dir)
        except Exception:
            return []
        if artifact is None:
            return []
        ms = artifact.state
        domain = self._classify_domain(ms.mission_title + " " + ms.mission_thesis)
        return [ExecutiveSignal(
            source="mission",
            category="mission_state",
            title=ms.mission_title,
            relevance=0.8,
            urgency=0.5 if ms.blockers else 0.2,
            domain=domain,
            keywords=ms.task_titles[:5],
            raw_data={"status": ms.status, "theme": ms.mission_theme},
        )]

    def _ingest_organism(self) -> list[ExecutiveSignal]:
        try:
            from dharma_swarm.organism import get_organism
            org = get_organism()
        except Exception:
            return []
        if org is None:
            return []
        pulse = org.latest_pulse
        if pulse is None:
            return []
        signals: list[ExecutiveSignal] = []
        if pulse.fleet_health < 0.5:
            signals.append(ExecutiveSignal(
                source="organism",
                category="health",
                title=f"Fleet health low ({pulse.fleet_health:.2f})",
                relevance=0.9,
                urgency=0.8,
                domain="reliability",
            ))
        if pulse.identity_coherence < 0.4:
            signals.append(ExecutiveSignal(
                source="organism",
                category="health",
                title=f"Identity coherence low ({pulse.identity_coherence:.2f})",
                relevance=0.9,
                urgency=0.9,
                domain="internal_maintenance",
            ))
        return signals

    def _ingest_algedonic(self) -> list[ExecutiveSignal]:
        try:
            from dharma_swarm.organism import get_organism
            org = get_organism()
        except Exception:
            return []
        if org is None or not hasattr(org, "algedonic_activation"):
            return []
        activations = org.algedonic_activation.recent_activations
        out: list[ExecutiveSignal] = []
        for act in activations[-10:]:
            sig_type = act.get("signal_type", act.get("signal", "unknown"))
            domain = "reliability" if "failure" in sig_type else "internal_maintenance"
            out.append(ExecutiveSignal(
                source="algedonic",
                category="pain",
                title=act.get("description", sig_type),
                relevance=0.9,
                urgency=1.0 if act.get("severity") == "critical" else 0.7,
                domain=domain,
                raw_data=act,
            ))
        return out

    # -- mission reader -----------------------------------------------------

    def _read_mission(self) -> tuple[Any, str, str, str]:
        try:
            from dharma_swarm.mission_contract import load_active_mission_state
            artifact = load_active_mission_state(state_dir=self._state_dir)
        except Exception:
            return None, "", "", "general"
        if artifact is None:
            return None, "", "", "general"
        ms = artifact.state
        return ms, ms.mission_title, ms.status, ms.mission_theme

    # -- organism reader ----------------------------------------------------

    def _read_organism(self) -> dict[str, float]:
        try:
            from dharma_swarm.organism import get_organism
            org = get_organism()
        except Exception:
            return {}
        if org is None:
            return {}
        pulse = org.latest_pulse
        if pulse is None:
            return {}
        return {
            "fleet_health": pulse.fleet_health,
            "identity_coherence": pulse.identity_coherence,
            "audit_failure_rate": pulse.audit_failure_rate,
            "algedonic_active": float(pulse.algedonic_active),
        }

    # -- domain classification ----------------------------------------------

    def _classify_domain(self, text: str) -> str:
        try:
            from dharma_swarm.thinkodynamic_director import (
                THEME_KEYWORDS,
                _theme_scores_from_text,
            )
            scores = _theme_scores_from_text(text)
        except Exception:
            return "internal_maintenance"
        if not scores:
            return "internal_maintenance"
        top_theme = max(scores, key=scores.get)  # type: ignore[arg-type]
        return THEME_TO_DOMAIN.get(top_theme, "internal_maintenance")

    # -- domain balance -----------------------------------------------------

    def _compute_domain_balance(
        self, signals: list[ExecutiveSignal],
    ) -> list[DomainBalance]:
        domain_counts: dict[str, int] = {d: 0 for d in DOMAINS}
        domain_last_ts: dict[str, str] = {d: "" for d in DOMAINS}
        for sig in signals:
            d = sig.domain if sig.domain in domain_counts else "internal_maintenance"
            domain_counts[d] += 1
            ts = sig.timestamp.isoformat() if sig.timestamp else ""
            if ts > domain_last_ts[d]:
                domain_last_ts[d] = ts

        total = max(1, sum(domain_counts.values()))
        n_domains = len(DOMAINS)
        base_share = 1.0 / n_domains

        balances: list[DomainBalance] = []
        for d in DOMAINS:
            sig_share = domain_counts[d] / total
            target = base_share
            deficit = max(0.0, target - sig_share)
            last_ts = domain_last_ts[d]
            starvation = deficit > STARVATION_DEFICIT_THRESHOLD and last_ts == ""
            balances.append(DomainBalance(
                domain=d,
                signal_share=round(sig_share, 4),
                target_share=round(target, 4),
                deficit=round(deficit, 4),
                last_activity_ts=last_ts,
                starvation=starvation,
                opportunity_count=domain_counts[d],
            ))
        return balances

    # -- opportunity ranking ------------------------------------------------

    def _rank_opportunities(
        self,
        signals: list[ExecutiveSignal],
        balances: list[DomainBalance],
        mission_theme: str,
        pulse_health: dict[str, float],
    ) -> list[ScoredOpportunity]:
        balance_map = {b.domain: b for b in balances}

        # Group signals by domain.
        domain_signals: dict[str, list[ExecutiveSignal]] = {d: [] for d in DOMAINS}
        for sig in signals:
            d = sig.domain if sig.domain in domain_signals else "internal_maintenance"
            domain_signals[d].append(sig)

        opportunities: list[ScoredOpportunity] = []
        for domain, sigs in domain_signals.items():
            if not sigs:
                continue
            factors = self._score_factors(
                domain, sigs, balance_map.get(domain), mission_theme, pulse_health,
            )
            raw = sum(factors[k] * SCORING_FACTORS[k] for k in SCORING_FACTORS)
            final = round(max(0.0, min(100.0, (raw / MAX_SCORE) * 100)), 1)

            best_sig = max(sigs, key=lambda s: s.relevance)
            opportunities.append(ScoredOpportunity(
                title=best_sig.title,
                domain=domain,
                thesis=best_sig.category,
                factor_scores=factors,
                final_score=final,
                evidence_signals=[s.signal_id for s in sigs[:5]],
                why_now=f"{len(sigs)} signals in {domain}",
            ))

        opportunities.sort(key=lambda o: o.final_score, reverse=True)
        return opportunities

    def _score_factors(
        self,
        domain: str,
        signals: list[ExecutiveSignal],
        balance: DomainBalance | None,
        mission_theme: str,
        pulse_health: dict[str, float],
    ) -> dict[str, float]:
        avg_relevance = sum(s.relevance for s in signals) / max(1, len(signals))
        threat_count = sum(1 for s in signals if s.category == "threat")
        pain_count = sum(1 for s in signals if s.source == "algedonic")

        # Map mission_theme to domain for alignment check.
        mission_domain = THEME_TO_DOMAIN.get(mission_theme, "")

        factors: dict[str, float] = {
            "telos_alignment": 1.0 if domain == mission_domain else 0.3,
            "world_value": 0.9 if domain in _WORLD_FACING else 0.2,
            "leverage": min(1.0, avg_relevance * 1.5),
            "algedonic_urgency": min(1.0, pain_count * 0.5),
            "novelty": 1.0 - min(1.0, self._recent_domains.count(domain) / 3.0),
            "urgency": min(1.0, threat_count * 0.3),
            "capability_fit": pulse_health.get("fleet_health", 0.7),
            "domain_balance_bonus": balance.deficit if balance else 0.0,
            "artifact_potential": 0.8 if domain in _WORLD_FACING else 0.3,
            "strategic_compounding": 0.7 if domain == mission_domain else 0.2,
            "internal_churn_penalty": 0.0,
            "repetition_penalty": 0.0,
        }

        # Apply penalties (these factor values are positive; the weight is negative).
        if domain == "internal_maintenance":
            share = balance.signal_share if balance else 0.0
            if share > INTERNAL_CHURN_SHARE_THRESHOLD:
                factors["internal_churn_penalty"] = min(1.0, share)

        recent_3 = self._recent_domains[-3:]
        if domain in recent_3:
            factors["repetition_penalty"] = min(1.0, recent_3.count(domain) / 3.0)

        return {k: round(v, 4) for k, v in factors.items()}

    # -- allocation weights -------------------------------------------------

    def _build_allocation_weights(
        self, balances: list[DomainBalance],
    ) -> AllocationWeights:
        per_domain: dict[str, float] = {}
        starvation_boosts: dict[str, float] = {}
        churn_penalties: dict[str, float] = {}

        for b in balances:
            per_domain[b.domain] = round(b.target_share + b.deficit * 0.5, 4)
            if b.starvation:
                starvation_boosts[b.domain] = round(b.deficit * 2.0, 4)
            if b.domain == "internal_maintenance" and b.signal_share > INTERNAL_CHURN_SHARE_THRESHOLD:
                churn_penalties[b.domain] = round(b.signal_share - INTERNAL_CHURN_SHARE_THRESHOLD, 4)

        return AllocationWeights(
            per_domain=per_domain,
            starvation_boosts=starvation_boosts,
            churn_penalties=churn_penalties,
        )

    # -- artifact emission --------------------------------------------------

    def _emit_artifacts(self, state: ExecutiveCycleState) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        self._briefs_dir.mkdir(parents=True, exist_ok=True)

        _write_json(self._meta_dir / "shakti_executive_state.json", state.model_dump(mode="json"))
        _write_json(
            self._meta_dir / "opportunity_board.json",
            [o.model_dump(mode="json") for o in state.opportunities],
        )
        _write_json(
            self._meta_dir / "allocation_weights.json",
            state.allocation_weights.model_dump(mode="json"),
        )
        _write_json(self._meta_dir / "active_campaigns.json", [])

        # Executive brief.
        brief = self._render_brief(state)
        ts_slug = state.timestamp.strftime("%Y-%m-%dT%H%M%S")
        (self._briefs_dir / f"{ts_slug}.md").write_text(brief)

        # Append to history JSONL.
        with open(self._history_path, "a") as fh:
            fh.write(state.model_dump_json() + "\n")

        # Prune old briefs.
        self._prune_briefs()

    def _render_brief(self, state: ExecutiveCycleState) -> str:
        ts = state.timestamp.strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# Executive Brief -- {ts}",
            f"## Cycle {state.cycle_id}",
            "",
            f"**Mission**: {state.mission_title or '(none)'} ({state.mission_status or 'unknown'})",
        ]
        oh = state.organism_health
        if oh:
            lines.append(
                f"**Organism**: fleet={oh.get('fleet_health', '?'):.2f}, "
                f"coherence={oh.get('identity_coherence', '?'):.2f}, "
                f"pain={int(oh.get('algedonic_active', 0))}"
            )
        lines.append(f"**Signals**: {state.signals_ingested} ingested")
        lines.append(f"**Duration**: {state.duration_ms:.0f}ms")
        lines.append("")

        lines.append("## Top Opportunities")
        for i, opp in enumerate(state.opportunities[:5], 1):
            lines.append(f"{i}. [{opp.domain}] {opp.title} (score={opp.final_score})")
            if opp.why_now:
                lines.append(f"   Why now: {opp.why_now}")
        if not state.opportunities:
            lines.append("(none detected)")
        lines.append("")

        lines.append("## Domain Balance")
        lines.append("| Domain | Share | Target | Deficit | Starved |")
        lines.append("|--------|-------|--------|---------|---------|")
        for b in state.domain_balances:
            starved = "YES" if b.starvation else "no"
            lines.append(
                f"| {b.domain} | {b.signal_share:.2f} | {b.target_share:.2f} "
                f"| {b.deficit:.2f} | {starved} |"
            )
        lines.append("")

        if state.starvation_alerts:
            lines.append("## Starvation Alerts")
            for d in state.starvation_alerts:
                lines.append(f"- **{d}**: starved (no recent signals, deficit above threshold)")
            lines.append("")

        return "\n".join(lines) + "\n"

    def _prune_briefs(self) -> None:
        try:
            briefs = sorted(self._briefs_dir.glob("*.md"), reverse=True)
            for old in briefs[MAX_BRIEFS:]:
                old.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def _count_by(signals: list[ExecutiveSignal], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sig in signals:
        key = getattr(sig, attr, "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts
