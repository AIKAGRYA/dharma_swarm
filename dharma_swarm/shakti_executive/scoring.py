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
_ECOSYSTEM_WORDS = frozenset({
    "agent",
    "agentic",
    "ai",
    "api",
    "arxiv",
    "benchmark",
    "company",
    "competitor",
    "frontier",
    "github",
    "launch",
    "market",
    "open-source",
    "open",
    "paper",
    "product",
    "reddit",
    "release",
    "startup",
    "tool",
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
    strategic_vision = _strategic_vision_for_signal(signal)
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
            "raw_source": _raw_source_for_signal(signal),
            "category": signal.category,
            "evidence_ref": signal.evidence_ref,
            "confidence": signal.confidence,
            "relevance_score": signal.relevance_score,
        }],
        strategic_vision=strategic_vision,
    )
    return candidate


def _domain_for_signal(signal: ExecutiveSignal, words: set[str]) -> str:
    if _is_world_zeitgeist(signal):
        return "ecosystem_scan"
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
    if _is_world_zeitgeist(signal):
        return "ecosystem_signal"
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
    is_world = domain == "ecosystem_scan" or _is_world_zeitgeist(signal)
    if signal.category.lower() in {"threat", "operator_directive"} or words & _URGENCY_WORDS:
        urgency = max(urgency, 0.82)

    artifact_potential = 0.35
    if signal.suggested_action:
        artifact_potential = 0.85
    elif is_world:
        artifact_potential = 0.78
    elif domain in {"internal_maintenance", "external_revenue"}:
        artifact_potential = 0.7

    telos_alignment = 0.62
    if words & {"welfare", "jagat", "safety", "governance", "evidence", "verified"}:
        telos_alignment = 0.88
    if domain == "external_revenue" and "welfare" not in words:
        telos_alignment = 0.66

    world_value = 0.55
    if is_world:
        world_value = 0.84
    elif domain == "external_revenue":
        world_value = 0.82
        if signal.domain_hint == "external_revenue" and "paid" in words:
            world_value = 0.88
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
    if is_world:
        capability_fit = max(capability_fit, 0.74)

    strategic_compounding = 0.35
    if is_world:
        strategic_compounding = 0.86
    elif domain in {"strategic_vision", "operator_priority", "external_revenue"}:
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
        "domain_balance_bonus": round(
            0.1 if is_world else 0.12 if domain == "external_revenue" else 0.0,
            3,
        ),
        "artifact_potential": round(artifact_potential, 3),
        "strategic_compounding": round(strategic_compounding, 3),
        "internal_churn_penalty": round(internal_churn_penalty, 3),
        "repetition_penalty": 0.0,
    }


_REVENUE_SCORE_CAP = 82.0


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
    raw = max(0.0, positive - penalty)
    if scores.get("domain_balance_bonus", 0.0) > 0.0:
        raw = min(raw, _REVENUE_SCORE_CAP)
    return raw


def _title_for_signal(signal: ExecutiveSignal, *, domain: str) -> str:
    title = signal.title.strip().rstrip(".")
    if domain == "ecosystem_scan" and not title.lower().startswith("world signal:"):
        return f"World signal: {title}"
    if domain == "external_revenue" and "revenue" not in title.lower():
        return f"Revenue wedge: {title}"
    if domain == "internal_maintenance" and not title.lower().startswith("repair"):
        return f"Repair: {title}"
    return title


def _why_now(signal: ExecutiveSignal, scores: dict[str, float]) -> str:
    urgency = scores["urgency"]
    if _is_world_zeitgeist(signal):
        raw_source = _raw_source_for_signal(signal)
        return f"external world signal cleared radar pressure via {raw_source} with urgency={urgency:.2f}"
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


def _is_world_zeitgeist(signal: ExecutiveSignal) -> bool:
    if signal.source != "zeitgeist":
        return False
    raw_source = _raw_source_for_signal(signal)
    raw = signal.raw if isinstance(signal.raw, dict) else {}
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    category = signal.category.lower().strip()
    if raw_source in {
        "world_zeitgeist",
        "world_scout",
        "world_signal_feed",
        "operator_drop",
        "github",
        "arxiv",
        "hacker_news",
        "reddit",
    }:
        return True
    if str(metadata.get("promotion_status") or "").strip():
        return True
    if category in {"company", "benchmark", "tool_release", "governance", "ecosystem_signal"}:
        return True
    return bool(set(word.lower() for word in signal.keywords) & _ECOSYSTEM_WORDS)


def _raw_source_for_signal(signal: ExecutiveSignal) -> str:
    raw = signal.raw if isinstance(signal.raw, dict) else {}
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    for value in (
        metadata.get("raw_source"),
        metadata.get("source_type"),
        raw.get("raw_source"),
        raw.get("source_type"),
        raw.get("source"),
        signal.source,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return "unknown"


def _strategic_vision_for_signal(signal: ExecutiveSignal) -> dict[str, object] | None:
    if not _is_world_zeitgeist(signal):
        return None
    raw = signal.raw if isinstance(signal.raw, dict) else {}
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    vision_keys = (
        "first_principles_questions",
        "iteration_steps",
        "adjacent_searches",
        "strategic_moves",
        "dimensions",
        "uncertainty",
        "first_move",
        "incubation_path",
    )
    vision = {key: metadata[key] for key in vision_keys if key in metadata}
    if not vision:
        title = signal.title.strip() or "this signal"
        vision = {
            "first_principles_questions": [
                f"What primitive does {title} prove is becoming valuable?",
                "What can Dharma reproduce as a governed public proof?",
                "Which adjacent companies, repos, papers, and communities confirm this movement?",
            ],
            "iteration_steps": [
                "Verify public primary sources.",
                "Map the external primitive to Dharma capabilities.",
                "Find adjacent signals and competitors.",
                "Draft the smallest artifact-backed opportunity.",
            ],
            "strategic_moves": [
                "research",
                "reverse_engineer_public_pattern",
                "prototype_smallest_governed_version",
            ],
            "uncertainty": "medium until independent evidence is refreshed",
        }
    vision.setdefault("raw_source", _raw_source_for_signal(signal))
    vision.setdefault("url", metadata.get("url") or raw.get("url") or "")
    return vision
