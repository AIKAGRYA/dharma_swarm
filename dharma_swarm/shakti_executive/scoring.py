"""Deterministic opportunity scoring for Shakti executive signals."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable

from dharma_swarm.shakti_executive.models import ExecutiveSignal, OpportunityCandidate

_INTERNAL_WORDS = frozenset({
    "test",
    "tests",
    "ci",
    "semgrep",
    "governance",
    "module",
    "budget",
    "refactor",
    "coverage",
    "dependency",
    "gate",
    "guardian",
    "outcome",
    "dispatcher",
    "campaign",
    "sealed",
    "packet",
    "feedback",
})
_REVENUE_WORDS = frozenset({
    "revenue",
    "customer",
    "market",
    "paid",
    "wedge",
    "audit",
    "service",
    "grant",
    "bounty",
    "mrv",
    "welfare",
})
_RESEARCH_WORDS = frozenset({
    "research",
    "paper",
    "preprint",
    "arxiv",
    "mechanistic",
    "interpretability",
    "experiment",
    "evidence",
    "replicated",
})
_URGENCY_WORDS = frozenset({
    "critical",
    "high",
    "blocked",
    "threat",
    "scooped",
    "failing",
    "drift",
    "failed",
    "failure",
    "quarantined",
    "operator",
    "now",
})


def candidates_from_signals(
    signals: Iterable[ExecutiveSignal],
    *,
    timestamp: str | None = None,
) -> list[OpportunityCandidate]:
    """Convert normalized signals into ranked opportunity candidates."""
    now = timestamp or datetime.now(timezone.utc).isoformat()
    candidates = [_candidate_from_signal(signal, timestamp=now) for signal in signals]
    candidates = [candidate for candidate in candidates if candidate.final_score > 0.0]
    candidates.sort(key=lambda candidate: candidate.final_score, reverse=True)
    return candidates


def _candidate_from_signal(
    signal: ExecutiveSignal,
    *,
    timestamp: str,
) -> OpportunityCandidate:
    text = " ".join((
        signal.title,
        signal.category,
        signal.description,
        signal.suggested_action,
        " ".join(signal.keywords),
    )).lower()
    words = set(text.replace("-", " ").replace("_", " ").split())
    domain = _domain_for_signal(signal, words)
    thesis = _thesis_for_signal(signal, words)
    scores = _factor_scores(signal, words, domain=domain)
    final_score = round(_weighted_score(scores), 2)
    title = _title_for_signal(signal, domain=domain)
    evidence = [signal.evidence_line]
    if signal.suggested_action:
        evidence.append(f"suggested_action - {signal.suggested_action}")
    candidate = OpportunityCandidate(
        opportunity_id=_stable_id(domain, title, signal.evidence_line),
        title=title,
        domain=domain,
        thesis=thesis,
        factor_scores=scores,
        final_score=final_score,
        evidence_signals=evidence,
        why_now=_why_now(signal, scores),
        timestamp=timestamp,
        source_inputs=[{
            "source": signal.source,
            "category": signal.category,
            "evidence_ref": signal.evidence_ref,
            "confidence": signal.confidence,
            "relevance_score": signal.relevance_score,
        }],
    )
    return candidate


def _domain_for_signal(signal: ExecutiveSignal, words: set[str]) -> str:
    if signal.domain_hint:
        hint = signal.domain_hint.lower().strip()
        if hint in {"runtime_feedback", "dispatcher_health", "campaign_feedback", "sealed_packet"}:
            return "internal_maintenance"
        if hint in {"security", "tests", "architecture", "routing", "evolution"}:
            return "internal_maintenance"
        if hint in {"external", "market", "revenue", "external_revenue"}:
            return "external_revenue"
        if hint in {"research", "strategic_vision", "operator_priority"}:
            return hint
    if words & _REVENUE_WORDS:
        return "external_revenue"
    if words & _RESEARCH_WORDS:
        return "research"
    if words & _INTERNAL_WORDS:
        return "internal_maintenance"
    return "strategic_vision"


def _thesis_for_signal(signal: ExecutiveSignal, words: set[str]) -> str:
    category = signal.category.lower()
    if category in {
        "runtime_outcome",
        "value_event_feedback",
        "contribution_feedback",
        "dispatcher_health",
        "campaign_feedback",
        "sealed_packet_archive",
    }:
        return "feedback_closure"
    if category in {"threat", "operator_directive"}:
        return category
    if words & _REVENUE_WORDS:
        return "revenue_wedge"
    if "actionable" in category or signal.suggested_action:
        return "actionable_improvement"
    if words & _RESEARCH_WORDS:
        return "research_lead"
    if "strategic" in category:
        return "strategic_attractor"
    return category or "opportunity"


def _factor_scores(
    signal: ExecutiveSignal,
    words: set[str],
    *,
    domain: str,
) -> dict[str, float]:
    urgency = _clamp(signal.relevance_score)
    if signal.category.lower() in {"threat", "operator_directive"} or words & _URGENCY_WORDS:
        urgency = max(urgency, 0.82)

    artifact_potential = 0.35
    if signal.suggested_action:
        artifact_potential = 0.85
    elif domain in {"internal_maintenance", "external_revenue"}:
        artifact_potential = 0.7

    telos_alignment = 0.62
    if words & {"welfare", "jagat", "safety", "governance", "evidence", "verified"}:
        telos_alignment = 0.88
    if domain == "external_revenue" and "welfare" not in words:
        telos_alignment = 0.66

    world_value = 0.55
    if domain == "external_revenue":
        world_value = 0.82
    elif domain == "research":
        world_value = 0.7
    elif domain == "internal_maintenance":
        world_value = 0.62

    leverage = _clamp(0.35 + signal.confidence * 0.35 + signal.relevance_score * 0.3)
    capability_fit = 0.58
    if signal.evidence_ref and (
        signal.evidence_ref.endswith(".py") or ".py:" in signal.evidence_ref
    ):
        capability_fit = 0.78
    if signal.source.startswith("scout:"):
        capability_fit = max(capability_fit, 0.72)

    strategic_compounding = 0.35
    if domain in {"strategic_vision", "operator_priority", "external_revenue"}:
        strategic_compounding = 0.72
    if "recognition" in signal.source:
        strategic_compounding = max(strategic_compounding, 0.82)

    internal_churn_penalty = 0.0
    if domain == "internal_maintenance" and not signal.suggested_action:
        internal_churn_penalty = 0.18

    return {
        "telos_alignment": round(telos_alignment, 3),
        "world_value": round(world_value, 3),
        "leverage": round(leverage, 3),
        "algedonic_urgency": round(urgency, 3),
        "novelty": round(0.55 if "recognition" in signal.source else 0.35, 3),
        "urgency": round(urgency, 3),
        "capability_fit": round(capability_fit, 3),
        "domain_balance_bonus": round(0.12 if domain == "external_revenue" else 0.0, 3),
        "artifact_potential": round(artifact_potential, 3),
        "strategic_compounding": round(strategic_compounding, 3),
        "internal_churn_penalty": round(internal_churn_penalty, 3),
        "repetition_penalty": 0.0,
    }


def _weighted_score(scores: dict[str, float]) -> float:
    positive = (
        scores["telos_alignment"] * 18.0
        + scores["world_value"] * 14.0
        + scores["leverage"] * 14.0
        + scores["urgency"] * 12.0
        + scores["capability_fit"] * 10.0
        + scores["artifact_potential"] * 14.0
        + scores["strategic_compounding"] * 10.0
        + scores["domain_balance_bonus"] * 6.0
        + scores["novelty"] * 2.0
    )
    penalty = (
        scores["internal_churn_penalty"] * 20.0
        + scores["repetition_penalty"] * 12.0
    )
    return max(0.0, positive - penalty)


def _title_for_signal(signal: ExecutiveSignal, *, domain: str) -> str:
    title = signal.title.strip().rstrip(".")
    if domain == "external_revenue" and "revenue" not in title.lower():
        return f"Revenue wedge: {title}"
    if domain == "internal_maintenance" and not title.lower().startswith("repair"):
        return f"Repair: {title}"
    return title


def _why_now(signal: ExecutiveSignal, scores: dict[str, float]) -> str:
    urgency = scores["urgency"]
    if signal.suggested_action:
        return f"actionable signal with urgency={urgency:.2f}"
    if signal.category == "operator_directive":
        return "operator directive is active"
    if signal.category == "threat":
        return f"threat signal with urgency={urgency:.2f}"
    return f"{signal.source} signal with score pressure {urgency:.2f}"


def _stable_id(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8", errors="replace"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
