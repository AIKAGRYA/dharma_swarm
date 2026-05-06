"""Read-only S4 executive consumer.

Stage 2 keeps the executive intentionally narrow: it consumes persisted
ZeitgeistScanner signals, ranks strategic pressure, and emits warrant-pressure
artifacts. It does not dispatch work, rewrite campaign memory, or own action
authority.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.fourfold_action_warrant import (
    ActionWarrantRequest,
    CapabilityInventory,
    EvidenceItem,
    FourfoldActionWarrant,
    MIN_EVIDENCE_FILES,
    build_fourfold_action_warrant,
    trigger_reasons_for_action,
)
from dharma_swarm.models import _new_id, _utc_now
from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB
from dharma_swarm.zeitgeist import ZeitgeistScanner, ZeitgeistSignal

logger = logging.getLogger(__name__)

DISPATCH_AUTHORITY = False

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

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "reliability": ("failure", "blocked", "gate", "semgrep", "test", "hook"),
    "research": ("research", "paper", "interpretability", "agentic", "model"),
    "artifact_publication": ("article", "publish", "brief", "report", "docs"),
    "productization": ("dashboard", "api", "user", "operator", "product"),
    "ecosystem_scan": ("zeitgeist", "external", "frontier", "release", "tool"),
    "revenue_exploration": ("revenue", "market", "customer", "venture"),
    "strategic_infrastructure": ("ontology", "mcp", "plugin", "memory", "schema"),
}

_WORLD_FACING = frozenset(
    {
        "research",
        "artifact_publication",
        "productization",
        "ecosystem_scan",
        "revenue_exploration",
    }
)


class ExecutiveSignal(BaseModel):
    signal_id: str = Field(default_factory=_new_id)
    source: str
    category: str
    title: str
    relevance: float = 0.0
    urgency: float = 0.0
    domain: str = "internal_maintenance"
    keywords: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)


class ScoredOpportunity(BaseModel):
    opportunity_id: str = Field(default_factory=_new_id)
    title: str
    domain: str
    thesis: str = ""
    final_score: float = 0.0
    evidence_signals: list[str] = Field(default_factory=list)
    why_now: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class WarrantPressure(BaseModel):
    required_for_next_action: bool = False
    pressure_score: float = 0.0
    trigger_reasons: list[str] = Field(default_factory=list)
    min_evidence_files: int = MIN_EVIDENCE_FILES
    suggested_evidence_categories: list[str] = Field(
        default_factory=lambda: ["root", "code", "tests", "history", "tools"]
    )
    zeitgeist_signal_ids: list[str] = Field(default_factory=list)


class ExecutiveCycleState(BaseModel):
    cycle_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utc_now)
    signals_ingested: int = 0
    signals_by_source: dict[str, int] = Field(default_factory=dict)
    opportunities: list[ScoredOpportunity] = Field(default_factory=list)
    warrant_pressure: WarrantPressure = Field(default_factory=WarrantPressure)
    dispatch_authority: bool = DISPATCH_AUTHORITY
    duration_ms: float = 0.0


class ShaktiZeitgeistExecutive:
    """Read-only strategic consumer of S4 zeitgeist signals."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or DEFAULT_RUNTIME_DB.parent.parent
        self._meta_dir = self._state_dir / "meta"
        self._briefs_dir = self._meta_dir / "executive_briefs"
        self._history_path = self._meta_dir / "shakti_zeitgeist_history.jsonl"

    async def cycle(self) -> ExecutiveCycleState:
        """Ingest S4 signals, rank pressure, and emit read-only artifacts."""

        start = datetime.now().timestamp()
        signals = self._ingest_zeitgeist()
        opportunities = self._rank_opportunities(signals)
        warrant_pressure = self._build_warrant_pressure(signals)
        state = ExecutiveCycleState(
            signals_ingested=len(signals),
            signals_by_source=_count_by(signals, "source"),
            opportunities=opportunities[:8],
            warrant_pressure=warrant_pressure,
            duration_ms=round((datetime.now().timestamp() - start) * 1000, 1),
        )
        self._emit_artifacts(state)
        return state

    def assess_action(
        self,
        *,
        title: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
        evidence: list[EvidenceItem] | None = None,
        capabilities: CapabilityInventory | None = None,
        integrated_vision: str = "",
        connection_map: str = "",
        meaningful_action: str = "",
        min_evidence_files: int = MIN_EVIDENCE_FILES,
    ) -> FourfoldActionWarrant:
        """Evaluate a proposed action without executing or routing it."""

        signal_ids = [sig.signal_id for sig in self._ingest_zeitgeist()[-20:]]
        request = ActionWarrantRequest(
            title=title,
            description=description,
            metadata=metadata or {},
            evidence=evidence or [],
            capabilities=capabilities or CapabilityInventory(),
            zeitgeist_signal_ids=signal_ids,
            integrated_vision=integrated_vision,
            connection_map=connection_map,
            meaningful_action=meaningful_action,
        )
        return build_fourfold_action_warrant(
            request,
            min_evidence_files=min_evidence_files,
        )

    def _ingest_zeitgeist(self) -> list[ExecutiveSignal]:
        try:
            raw = ZeitgeistScanner(state_dir=self._state_dir).load_history()
        except Exception as exc:
            logger.debug("executive zeitgeist ingest failed: %s", exc)
            return []

        out: list[ExecutiveSignal] = []
        for sig in raw[-200:]:
            out.append(_from_zeitgeist(sig))
        return out

    def _rank_opportunities(
        self,
        signals: list[ExecutiveSignal],
    ) -> list[ScoredOpportunity]:
        grouped: dict[str, list[ExecutiveSignal]] = {domain: [] for domain in DOMAINS}
        for sig in signals:
            domain = sig.domain if sig.domain in grouped else "internal_maintenance"
            grouped[domain].append(sig)

        opportunities: list[ScoredOpportunity] = []
        for domain, domain_signals in grouped.items():
            if not domain_signals:
                continue
            best = max(
                domain_signals,
                key=lambda sig: (sig.urgency, sig.relevance, sig.timestamp),
            )
            score = _domain_score(domain, domain_signals)
            opportunities.append(
                ScoredOpportunity(
                    title=best.title,
                    domain=domain,
                    thesis=best.category,
                    final_score=score,
                    evidence_signals=[sig.signal_id for sig in domain_signals[:8]],
                    why_now=f"{len(domain_signals)} S4 signals in {domain}",
                )
            )
        opportunities.sort(key=lambda item: item.final_score, reverse=True)
        return opportunities

    def _build_warrant_pressure(
        self,
        signals: list[ExecutiveSignal],
    ) -> WarrantPressure:
        pressure_signals = [
            sig for sig in signals
            if sig.category == "threat" or sig.relevance >= 0.85 or sig.urgency >= 0.8
        ]
        pressure_score = min(
            1.0,
            sum(max(sig.relevance, sig.urgency) for sig in pressure_signals) / 5.0,
        )
        reasons = set()
        if pressure_signals:
            reasons.add("active_s4_pressure")
        for sig in pressure_signals:
            reasons.update(trigger_reasons_for_action(sig.title, " ".join(sig.keywords)))
        return WarrantPressure(
            required_for_next_action=bool(pressure_signals),
            pressure_score=round(pressure_score, 3),
            trigger_reasons=sorted(reasons),
            zeitgeist_signal_ids=[sig.signal_id for sig in pressure_signals[:12]],
        )

    def _emit_artifacts(self, state: ExecutiveCycleState) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        self._briefs_dir.mkdir(parents=True, exist_ok=True)
        _write_json(
            self._meta_dir / "shakti_zeitgeist_state.json",
            state.model_dump(mode="json"),
        )
        _write_json(
            self._meta_dir / "s4_warrant_pressure.json",
            state.warrant_pressure.model_dump(mode="json"),
        )
        (self._meta_dir / "s4_warrant_pressure.md").write_text(
            _render_warrant_pressure(state),
            encoding="utf-8",
        )
        brief_name = state.timestamp.strftime("%Y-%m-%dT%H%M%S") + ".md"
        (self._briefs_dir / brief_name).write_text(_render_brief(state), encoding="utf-8")
        with self._history_path.open("a", encoding="utf-8") as fh:
            fh.write(state.model_dump_json() + "\n")


def _from_zeitgeist(signal: ZeitgeistSignal) -> ExecutiveSignal:
    domain = _classify_domain(
        f"{signal.title}\n{signal.description}\n{' '.join(signal.keywords)}"
    )
    urgency = 1.0 if signal.category == "threat" else min(0.8, signal.relevance_score)
    return ExecutiveSignal(
        source="zeitgeist",
        category=signal.category,
        title=signal.title,
        relevance=signal.relevance_score,
        urgency=urgency,
        domain=domain,
        keywords=signal.keywords,
        raw_data={"zeitgeist_id": signal.id},
        timestamp=signal.timestamp,
    )


def _classify_domain(text: str) -> str:
    lowered = text.lower()
    scores = {
        domain: sum(1 for keyword in keywords if keyword in lowered)
        for domain, keywords in _DOMAIN_KEYWORDS.items()
    }
    best_domain, best_score = max(scores.items(), key=lambda item: item[1])
    return best_domain if best_score > 0 else "internal_maintenance"


def _domain_score(domain: str, signals: list[ExecutiveSignal]) -> float:
    avg_relevance = sum(sig.relevance for sig in signals) / max(1, len(signals))
    max_urgency = max((sig.urgency for sig in signals), default=0.0)
    world_bonus = 0.15 if domain in _WORLD_FACING else 0.0
    density_bonus = min(0.15, len(signals) * 0.03)
    score = min(1.0, avg_relevance * 0.5 + max_urgency * 0.35 + world_bonus + density_bonus)
    return round(score * 100, 1)


def _count_by(items: list[ExecutiveSignal], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(getattr(item, attr, ""))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_warrant_pressure(state: ExecutiveCycleState) -> str:
    pressure = state.warrant_pressure
    lines = [
        "# S4 Warrant Pressure",
        "",
        f"- Required: {pressure.required_for_next_action}",
        f"- Pressure: {pressure.pressure_score}",
        f"- Minimum evidence files: {pressure.min_evidence_files}",
    ]
    if pressure.trigger_reasons:
        lines.append("- Triggers: " + ", ".join(pressure.trigger_reasons))
    if pressure.zeitgeist_signal_ids:
        lines.append("- Signal IDs: " + ", ".join(pressure.zeitgeist_signal_ids))
    return "\n".join(lines) + "\n"


def _render_brief(state: ExecutiveCycleState) -> str:
    lines = [
        "# Shakti Zeitgeist Executive Brief",
        "",
        f"Cycle: {state.cycle_id}",
        f"Signals ingested: {state.signals_ingested}",
        f"Dispatch authority: {state.dispatch_authority}",
        "",
        "## Top Opportunities",
    ]
    if not state.opportunities:
        lines.append("No opportunities detected.")
    for opp in state.opportunities:
        lines.append(f"- [{opp.domain}] {opp.title} ({opp.final_score})")
    lines.extend(["", "## Warrant Pressure"])
    lines.append(f"- Required: {state.warrant_pressure.required_for_next_action}")
    lines.append(f"- Pressure: {state.warrant_pressure.pressure_score}")
    return "\n".join(lines) + "\n"


__all__ = [
    "DISPATCH_AUTHORITY",
    "DOMAINS",
    "ExecutiveCycleState",
    "ExecutiveSignal",
    "ScoredOpportunity",
    "ShaktiZeitgeistExecutive",
    "WarrantPressure",
]
