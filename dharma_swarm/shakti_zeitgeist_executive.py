"""ShaktiZeitgeistExecutive — strategic executive layer.

Phase 1 (landed 2026-04-13): ingests signals from zeitgeist, mission state,
organism/algedonic, and capability sources. Scores opportunities with a
12-factor model. Tracks domain balance across 8 operational domains. Emits
durable artifacts under ``~/.dharma/meta/``.

Phase 2 governance emission (landed 2026-04-14): in addition to the Phase 1
artifacts, the executive now emits a governance bundle consumed by the
orchestrator's governance overlay and the operator CLI:

    * ``promise_pressure.json``       heartbeat-derived promises with stable
                                      ids and urgency scores
    * ``disagreement_quarantine.json`` repeated loop signatures that
                                      coordination_synthesis should skip
    * ``role_underuse_report.json``    nominal-only agents and
                                      underexpressed roles
    * ``challenge_pressure.json``     deadline-driven per-domain multipliers
                                      sourced from ``deadlines.json``
    * ``governance_signal.json``      combined summary for
                                      ``dgc status --governance``

The executive still does NOT control dispatch directly — the governance
overlay in ``orchestrator.route_next`` reads these files and reorders the
ready queue behind ``DGC_GOVERNANCE_OVERLAY``.

IMPORTANT INVARIANT: the executive does NOT write to
``active_campaigns.json`` once it exists. Write authority over campaign
memory belongs to ``dharma_swarm.campaigns`` (and by extension the CLI).
The executive only creates the file on first cycle if absent, and reads it
every cycle to compute stale_campaign alerts.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.executive_substrates import (
    build_memory_pressure_snapshot,
    build_role_ecology_snapshot,
)
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


def _as_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
    role_ecology: dict[str, Any] = Field(default_factory=dict)
    memory_pressure: dict[str, Any] = Field(default_factory=dict)
    operator_summary: dict[str, Any] = Field(default_factory=dict)
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

        active_campaigns = self._read_active_campaigns()
        signals = self._ingest_signals(active_campaigns=active_campaigns)
        mission_state, mission_title, mission_status, mission_theme = self._read_mission()
        pulse_health = self._read_organism()
        role_ecology = build_role_ecology_snapshot(state_dir=self._state_dir)
        memory_pressure = build_memory_pressure_snapshot(state_dir=self._state_dir)
        balances = self._compute_domain_balance(signals)
        opportunities = self._rank_opportunities(
            signals, balances, mission_theme, pulse_health, role_ecology, memory_pressure,
        )
        weights = self._build_allocation_weights(balances)
        starvation_alerts = [b.domain for b in balances if b.starvation]
        starvation_alerts.extend(f"role:{role}" for role in role_ecology.underexpressed_roles[:5])
        starvation_alerts.extend(
            f"promise:{promise[:80]}" for promise in memory_pressure.unresolved_promises[:5]
        )
        starvation_alerts.extend(
            f"loop:{loop}" for loop in memory_pressure.repeated_loop_signatures[:5]
        )

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
            role_ecology={
                "seeded_agents": role_ecology.seeded_agents,
                "active_agents_72h": role_ecology.active_agents_72h,
                "nominal_only_agents": role_ecology.nominal_only_agents,
                "overloaded_agents": role_ecology.overloaded_agents,
                "underexpressed_roles": role_ecology.underexpressed_roles,
            },
            memory_pressure={
                "distilled_roles": memory_pressure.distilled_roles,
                "unresolved_promises": memory_pressure.unresolved_promises,
                "repeated_loop_signatures": memory_pressure.repeated_loop_signatures,
                "top_stigmergy_hotspots": memory_pressure.top_stigmergy_hotspots,
                "memory_health": memory_pressure.memory_health,
            },
            operator_summary=self._build_operator_summary(
                role_ecology=role_ecology,
                memory_pressure=memory_pressure,
                opportunities=opportunities,
                mission_title=mission_title,
                active_campaigns=active_campaigns,
            ),
            allocation_weights=weights,
            mission_title=mission_title,
            mission_status=mission_status,
            duration_ms=round((time.monotonic() - t0) * 1000, 1),
        )

        self._emit_artifacts(state)
        return state

    # -- signal ingestion ---------------------------------------------------

    def _ingest_signals(
        self,
        *,
        active_campaigns: list[dict[str, Any]] | None = None,
    ) -> list[ExecutiveSignal]:
        signals: list[ExecutiveSignal] = []
        signals.extend(self._ingest_campaigns(active_campaigns=active_campaigns))
        signals.extend(self._ingest_zeitgeist())
        signals.extend(self._ingest_mission())
        signals.extend(self._ingest_organism())
        signals.extend(self._ingest_algedonic())
        return signals

    def _ingest_campaigns(
        self,
        *,
        active_campaigns: list[dict[str, Any]] | None = None,
    ) -> list[ExecutiveSignal]:
        campaigns = active_campaigns if active_campaigns is not None else self._read_active_campaigns()
        out: list[ExecutiveSignal] = []
        now = _utc_now()
        for campaign in campaigns:
            if campaign.get("status", "active") != "active":
                continue
            campaign_id = str(campaign.get("campaign_id") or "").strip()
            title = str(campaign.get("title") or campaign_id).strip()
            if not title:
                continue
            domain = str(campaign.get("domain") or "").strip()
            if domain not in DOMAINS:
                domain = self._classify_domain(
                    f"{title}\n{campaign.get('success_criteria', '')}"
                )
            is_primary = bool(campaign.get("primary"))
            urgency = 0.95 if is_primary else 0.55
            ts_raw = campaign.get("last_check_in") or campaign.get("created")
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                    ts = _as_utc_datetime(ts)
                    if (now - ts).total_seconds() > 7200:
                        urgency = min(1.0, urgency + 0.05)
                except Exception:
                    pass
            keywords = [campaign_id]
            artifact_path = str(campaign.get("artifact_path") or "").strip()
            if artifact_path:
                keywords.append(artifact_path)
            out.append(
                ExecutiveSignal(
                    source="campaign",
                    category="primary_campaign" if is_primary else "campaign_state",
                    title=title,
                    relevance=1.0 if is_primary else 0.7,
                    urgency=urgency,
                    domain=domain,
                    keywords=keywords[:5],
                    raw_data={
                        "campaign_id": campaign_id,
                        "primary": is_primary,
                        "artifact_path": artifact_path,
                        "success_criteria": str(campaign.get("success_criteria") or ""),
                    },
                )
            )
        return out

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
        role_ecology: Any | None = None,
        memory_pressure: Any | None = None,
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
                domain,
                sigs,
                balance_map.get(domain),
                mission_theme,
                pulse_health,
                role_ecology,
                memory_pressure,
            )
            raw = sum(factors[k] * SCORING_FACTORS[k] for k in SCORING_FACTORS)
            final = round(max(0.0, min(100.0, (raw / MAX_SCORE) * 100)), 1)

            best_sig = max(
                sigs,
                key=lambda s: (
                    self._signal_priority(s),
                    s.relevance,
                    s.urgency,
                    s.timestamp,
                ),
            )
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

    def _signal_priority(self, signal: ExecutiveSignal) -> int:
        raw_data = signal.raw_data if isinstance(signal.raw_data, dict) else {}
        if signal.source == "campaign":
            return 50 if raw_data.get("primary") else 40
        if signal.source == "mission":
            return 35
        if signal.source == "algedonic":
            return 30
        if signal.source == "organism":
            return 25
        if signal.source == "zeitgeist" and signal.title.startswith("Keywords in "):
            return 5
        return 10

    def _score_factors(
        self,
        domain: str,
        signals: list[ExecutiveSignal],
        balance: DomainBalance | None,
        mission_theme: str,
        pulse_health: dict[str, float],
        role_ecology: Any | None = None,
        memory_pressure: Any | None = None,
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

        underexpressed_roles = set(getattr(role_ecology, "underexpressed_roles", []))
        repeated_loops = list(getattr(memory_pressure, "repeated_loop_signatures", []))
        unresolved_promises = list(getattr(memory_pressure, "unresolved_promises", []))

        if domain == "strategic_infrastructure" and underexpressed_roles:
            factors["domain_balance_bonus"] = min(
                1.0,
                factors["domain_balance_bonus"] + 0.35,
            )
            factors["strategic_compounding"] = min(
                1.0,
                factors["strategic_compounding"] + 0.25,
            )

        if domain == "reliability" and unresolved_promises:
            factors["urgency"] = min(1.0, factors["urgency"] + 0.35)
            factors["artifact_potential"] = min(1.0, factors["artifact_potential"] + 0.1)

        if domain == "internal_maintenance" and repeated_loops:
            loop_pressure = min(1.0, len(repeated_loops) / 4.0)
            factors["internal_churn_penalty"] = max(
                factors["internal_churn_penalty"], loop_pressure
            )
            factors["repetition_penalty"] = max(
                factors["repetition_penalty"], min(1.0, loop_pressure * 0.8)
            )

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

        # active_campaigns.json: create if absent, preserve if present.
        # Write authority belongs to dharma_swarm.campaigns — the executive
        # must never clobber operator-pinned work here.
        self._ensure_active_campaigns_file()
        active_campaigns = self._read_active_campaigns()

        _write_json(
            self._meta_dir / "executive_operator_summary.json",
            state.operator_summary,
        )

        # Phase 2 governance emission bundle.
        promises = self._emit_promise_pressure(state)
        quarantine = self._emit_disagreement_quarantine(state)
        role_report = self._emit_role_underuse(state)
        challenge = self._emit_challenge_pressure(state)
        self._emit_governance_signal(
            state,
            promises=promises,
            quarantine=quarantine,
            role_report=role_report,
            challenge=challenge,
            active_campaigns=active_campaigns,
        )

        # Executive brief.
        brief = self._render_brief(state)
        ts_slug = state.timestamp.strftime("%Y-%m-%dT%H%M%S")
        (self._briefs_dir / f"{ts_slug}.md").write_text(brief)

        # Append to history JSONL.
        with open(self._history_path, "a") as fh:
            fh.write(state.model_dump_json() + "\n")

        # Prune old briefs.
        self._prune_briefs()

    # -- active_campaigns: read-only after first cycle ---------------------

    def _ensure_active_campaigns_file(self) -> None:
        """Create an empty active_campaigns.json only if it doesn't exist.

        Once created, the executive never rewrites this file — operator and
        CLI via ``dharma_swarm.campaigns`` own its contents.
        """
        path = self._meta_dir / "active_campaigns.json"
        if not path.exists():
            _write_json(path, [])

    def _read_active_campaigns(self) -> list[dict[str, Any]]:
        path = self._meta_dir / "active_campaigns.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
        except Exception:
            logger.warning("executive: active_campaigns.json unreadable; treating as empty")
            return []
        if not isinstance(data, list):
            return []
        return [c for c in data if isinstance(c, dict) and c.get("campaign_id")]

    # -- phase 2 governance emission ----------------------------------------

    def _emit_promise_pressure(self, state: ExecutiveCycleState) -> list[dict[str, Any]]:
        """Turn heartbeat-derived promises into structured, stable-id records."""
        raw_promises = state.memory_pressure.get("unresolved_promises") or []
        records: list[dict[str, Any]] = []
        for i, line in enumerate(raw_promises):
            if not isinstance(line, str) or not line.strip():
                continue
            pid = _promise_id_from_text(line)
            domain = _classify_domain(line)
            # Urgency: age-agnostic bootstrap — inverse rank within the list.
            rank = i + 1
            urgency = round(max(0.2, 1.0 - (rank - 1) * 0.15), 3)
            records.append({
                "id": pid,
                "text": line.strip()[:400],
                "urgency": urgency,
                "domain_hint": domain,
                "rank": rank,
            })
        payload = {
            "generated_at": _now_iso(),
            "cycle_id": state.cycle_id,
            "count": len(records),
            "promises": records,
        }
        _write_json(self._meta_dir / "promise_pressure.json", payload)
        return records

    def _emit_disagreement_quarantine(self, state: ExecutiveCycleState) -> list[dict[str, Any]]:
        """Extract repeated loop signatures that synthesis should skip."""
        raw = state.memory_pressure.get("repeated_loop_signatures") or []
        topics: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            # Format from executive_substrates: "label:count".
            m = re.match(r"^([\w\-]+):(\d+)$", item.strip())
            if m:
                topics.append({"topic": m.group(1), "count": int(m.group(2))})
            else:
                topics.append({"topic": item.strip().lower(), "count": 0})
        payload = {
            "generated_at": _now_iso(),
            "cycle_id": state.cycle_id,
            "cooling_off_seconds": 21600,  # 6h default
            "topics": [t["topic"] for t in topics],
            "active": topics,
        }
        _write_json(self._meta_dir / "disagreement_quarantine.json", payload)
        return topics

    def _emit_role_underuse(self, state: ExecutiveCycleState) -> dict[str, Any]:
        ecology = state.role_ecology or {}
        payload = {
            "generated_at": _now_iso(),
            "cycle_id": state.cycle_id,
            "seeded_agents": ecology.get("seeded_agents", 0),
            "active_agents_72h": ecology.get("active_agents_72h", 0),
            "nominal_only_agents": list(ecology.get("nominal_only_agents") or []),
            "underexpressed_roles": list(ecology.get("underexpressed_roles") or []),
            "overloaded_agents": list(ecology.get("overloaded_agents") or []),
        }
        _write_json(self._meta_dir / "role_underuse_report.json", payload)
        return payload

    def _emit_challenge_pressure(self, state: ExecutiveCycleState) -> dict[str, Any]:
        """Read ~/.dharma/meta/deadlines.json and derive per-domain pressure."""
        deadlines = self._load_deadlines()
        active: list[dict[str, Any]] = []
        per_domain: dict[str, float] = {}
        now = _utc_now()
        for d in deadlines:
            try:
                dt = datetime.fromisoformat(str(d.get("date", "")).replace("Z", "+00:00"))
                dt = _as_utc_datetime(dt)
            except Exception:
                continue
            days_remaining = (dt - now).total_seconds() / 86400.0
            if days_remaining < -1.0:  # more than one day past
                continue
            domain = str(d.get("domain") or "")
            if domain not in DOMAINS:
                continue
            # Pressure ramps as deadline approaches. 60+ days → 0.0, 7 days → 0.5, 0 days → 1.0.
            if days_remaining >= 60:
                pressure = 0.0
            elif days_remaining >= 14:
                pressure = round(0.2 * (60 - days_remaining) / 46.0, 3)
            elif days_remaining >= 0:
                pressure = round(0.4 + 0.6 * (14 - days_remaining) / 14.0, 3)
            else:
                pressure = 1.0
            record = {
                "name": str(d.get("name", "")),
                "date": d.get("date"),
                "days_remaining": round(days_remaining, 2),
                "domain": domain,
                "pressure": pressure,
            }
            active.append(record)
            per_domain[domain] = max(per_domain.get(domain, 0.0), pressure)
        payload = {
            "generated_at": _now_iso(),
            "cycle_id": state.cycle_id,
            "active_deadlines": active,
            "per_domain": per_domain,
        }
        _write_json(self._meta_dir / "challenge_pressure.json", payload)
        return payload

    def _load_deadlines(self) -> list[dict[str, Any]]:
        path = self._meta_dir / "deadlines.json"
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text())
        except Exception:
            logger.warning("executive: deadlines.json unreadable; skipping challenge pressure")
            return []
        if isinstance(raw, dict):
            items = raw.get("deadlines") or []
        elif isinstance(raw, list):
            items = raw
        else:
            items = []
        return [d for d in items if isinstance(d, dict)]

    def _emit_governance_signal(
        self,
        state: ExecutiveCycleState,
        *,
        promises: list[dict[str, Any]],
        quarantine: list[dict[str, Any]],
        role_report: dict[str, Any],
        challenge: dict[str, Any],
        active_campaigns: list[dict[str, Any]],
    ) -> None:
        """Combined summary for dgc status --governance."""
        # Stale campaigns: last_check_in older than 2 * executive interval.
        executive_interval_s = 2700.0  # 45 min — matches orchestrate_live
        stale_ids: list[str] = []
        now = _utc_now()
        for c in active_campaigns:
            ts_raw = c.get("last_check_in") or c.get("created")
            if not ts_raw:
                continue
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                ts = _as_utc_datetime(ts)
            except Exception:
                continue
            if (now - ts).total_seconds() >= executive_interval_s * 2:
                stale_ids.append(str(c.get("campaign_id", "?")))

        domain_shares = {
            b.domain: b.signal_share for b in state.domain_balances
        }
        payload = {
            "generated_at": _now_iso(),
            "cycle_id": state.cycle_id,
            "executive_interval_s": executive_interval_s,
            "domain_shares": domain_shares,
            "starvation_alerts": list(state.starvation_alerts),
            "promise_count": len(promises),
            "quarantine_count": len(quarantine),
            "active_campaign_count": len(active_campaigns),
            "stale_campaign_ids": stale_ids,
            "per_domain_challenge": challenge.get("per_domain", {}),
            "underexpressed_role_count": len(role_report.get("underexpressed_roles", [])),
            "nominal_only_agent_count": len(role_report.get("nominal_only_agents", [])),
        }
        _write_json(self._meta_dir / "governance_signal.json", payload)

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

        ecology = state.role_ecology
        if ecology:
            lines.append("## Role Ecology")
            lines.append(
                f"Seeded agents: {ecology.get('seeded_agents', 0)} | "
                f"active in 72h: {ecology.get('active_agents_72h', 0)}"
            )
            if ecology.get("underexpressed_roles"):
                lines.append(
                    "Underexpressed roles: "
                    + ", ".join(ecology.get("underexpressed_roles", [])[:6])
                )
            if ecology.get("nominal_only_agents"):
                lines.append(
                    "Nominal-only agents: "
                    + ", ".join(ecology.get("nominal_only_agents", [])[:6])
                )
            lines.append("")

        pressure = state.memory_pressure
        if pressure:
            lines.append("## Memory Pressure")
            if pressure.get("unresolved_promises"):
                lines.append("Unresolved promises:")
                for promise in pressure.get("unresolved_promises", [])[:5]:
                    lines.append(f"- {promise}")
            if pressure.get("repeated_loop_signatures"):
                lines.append("Repeated loops:")
                for loop in pressure.get("repeated_loop_signatures", [])[:5]:
                    lines.append(f"- {loop}")
            lines.append("")

        summary = state.operator_summary
        if summary:
            lines.append("## Operator Summary")
            for key in (
                "mission",
                "top_priority_domain",
                "top_priority_title",
                "role_attention",
                "promise_attention",
                "loop_attention",
                "nominal_agent_attention",
            ):
                value = summary.get(key)
                if value:
                    label = key.replace("_", " ").title()
                    lines.append(f"- **{label}**: {value}")
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

    def _build_operator_summary(
        self,
        *,
        role_ecology: Any,
        memory_pressure: Any,
        opportunities: list[ScoredOpportunity],
        mission_title: str,
        active_campaigns: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        primary_campaign = None
        for campaign in active_campaigns or []:
            if campaign.get("status", "active") == "active" and campaign.get("primary") is True:
                primary_campaign = campaign
                break
        top_opp = opportunities[0] if opportunities else None
        mission_label = mission_title or str((primary_campaign or {}).get("title") or "").strip() or "(none)"
        top_priority_domain = top_opp.domain if top_opp else ""
        top_priority_title = top_opp.title if top_opp else ""
        if primary_campaign and not mission_title:
            top_priority_domain = str(primary_campaign.get("domain") or top_priority_domain or "")
            top_priority_title = str(primary_campaign.get("title") or top_priority_title or "")
        role_attention = ""
        if getattr(role_ecology, "underexpressed_roles", None):
            role_attention = ", ".join(role_ecology.underexpressed_roles[:4])
        promise_attention = ""
        if getattr(memory_pressure, "unresolved_promises", None):
            promise_attention = " | ".join(memory_pressure.unresolved_promises[:2])
        loop_attention = ""
        if getattr(memory_pressure, "repeated_loop_signatures", None):
            loop_attention = ", ".join(memory_pressure.repeated_loop_signatures[:3])
        nominal_attention = ""
        if getattr(role_ecology, "nominal_only_agents", None):
            nominal_attention = ", ".join(role_ecology.nominal_only_agents[:4])
        return {
            "mission": mission_label,
            "top_priority_domain": top_priority_domain,
            "top_priority_title": top_priority_title,
            "role_attention": role_attention,
            "promise_attention": promise_attention,
            "loop_attention": loop_attention,
            "nominal_agent_attention": nominal_attention,
        }

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _promise_id_from_text(text: str) -> str:
    """Match campaigns.promise_id_from_text. Kept local to avoid import cycle."""
    # Lazy import: campaigns.py does not import this module, so this is safe,
    # but routing through the canonical implementation keeps IDs identical.
    from dharma_swarm.campaigns import promise_id_from_text
    return promise_id_from_text(text)


def _classify_domain(text: str) -> str:
    """Match domain_classify.classify_text. Kept local to avoid import cycle."""
    from dharma_swarm.domain_classify import classify_text
    return classify_text(text)
