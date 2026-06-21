"""Frontier Council — the verifier (Stage 1 of the seeing organ).

NOT a chatty analyst. A VERIFIER. It consumes a quarantined boundary world
signal and cross-falsifies its claim across >=2 DECORRELATED evaluator families,
producing a deterministic verdict and a ``WorldSensemakingReceipt`` that
explicitly carries NO action authority.

The moat: corroboration is *earned* by decorrelated agreement on real evidence,
never *granted* by confident prose. A single confident evaluator cannot
corroborate (Transcendence condition — decorrelated families so errors cancel),
and corroboration also requires evidence from >=2 decorrelated source families.

Hermetic by default: the evaluator families are deterministic functions over the
signal's declared ``evidence_refs``. Live LLM evaluators are env-gated
(``DHARMA_FRONTIER_COUNCIL_LLM=1``) and OFF by default — fixture mode needs no
network or keys.

Read-only: this module is a pure function. It never mutates active tracks,
ontology, memory, or dashboard owners. The receipt is *evidence*; it can propose,
it cannot dispatch. ``no_action_authority`` and ``dispatch_authority`` are stamped
on every receipt.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# Verdicts.
CORROBORATED = "corroborated"
REFUTED = "refuted"
INSUFFICIENT = "insufficient"
QUARANTINED = "quarantined"

_HIGH_QUALITY = 0.7  # a refutation at/above this quality dominates a claim


@dataclass(frozen=True)
class EvidenceRef:
    """One piece of evidence for/against the claim, from a named source family.
    Decorrelation is tracked by ``source_family`` (independent origins)."""
    source_family: str
    supports: bool
    quality: float = 0.5
    ref: str = ""


@dataclass
class FrontierCouncilInput:
    """A boundary world signal admitted for verification. ``safe`` and
    ``instruction_risk`` come from the Stage-0 safety substrate; a high-risk or
    unsafe signal is quarantined (its claim is NOT auto-evaluated)."""
    claim: str
    evidence_refs: list[EvidenceRef]
    input_signal_hash: str
    safe: bool = True
    instruction_risk: str = "low"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class FrontierCouncilConfig:
    min_corroborating_families: int = 2  # decorrelated evaluator families
    min_source_families: int = 2  # decorrelated evidence origins
    llm_enabled: bool = False  # live evaluators; env-gated, off by default


@dataclass
class CorroborationFinding:
    evaluator_family: str
    stance: str  # "corroborate" | "refute" | "insufficient"
    rationale: str
    supporting_families: list[str] = field(default_factory=list)
    refuting_families: list[str] = field(default_factory=list)


@dataclass
class WorldSensemakingReceipt:
    receipt_id: str
    input_signal_hash: str
    claim: str
    verdict: str
    corroboration_count: int  # observed_k: distinct corroborating evaluator families
    refutation_count: int
    source_family_count: int  # distinct decorrelated evidence origins
    findings: list[dict[str, Any]]
    evidence_refs: list[dict[str, Any]]
    risks: list[str]
    generated_at: str
    provenance: dict[str, Any]
    payload_hash: str
    no_action_authority: bool = True
    dispatch_authority: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, default=str)


# ── Decorrelated fixture evaluator families ────────────────────────────────
# Deterministic functions over the declared evidence. Each applies a different
# lens; none can corroborate from prose alone — they read the evidence.

def _supporting_families(refs: list[EvidenceRef]) -> set[str]:
    return {r.source_family for r in refs if r.supports}


def _refuting_families(refs: list[EvidenceRef], *, min_quality: float = 0.0) -> set[str]:
    return {r.source_family for r in refs if not r.supports and r.quality >= min_quality}


def _fixture_skeptic(inp: FrontierCouncilInput) -> CorroborationFinding:
    """Assumes the claim is false until decorrelated evidence forces otherwise.
    A single high-quality refutation refutes; <2 supporting families = insufficient."""
    supp = _supporting_families(inp.evidence_refs)
    refu = _refuting_families(inp.evidence_refs, min_quality=_HIGH_QUALITY)
    if refu:
        return CorroborationFinding("skeptic", "refute",
                                    f"{len(refu)} high-quality source(s) contradict the claim",
                                    sorted(supp), sorted(refu))
    if len(supp) >= 2:
        return CorroborationFinding("skeptic", "corroborate",
                                    f"{len(supp)} decorrelated sources support and none refute",
                                    sorted(supp), sorted(refu))
    return CorroborationFinding("skeptic", "insufficient",
                                "fewer than two decorrelated supporting sources",
                                sorted(supp), sorted(refu))


def _fixture_builder(inp: FrontierCouncilInput) -> CorroborationFinding:
    """Looks for actionable signal: corroborates on >=2 supporting decorrelated
    families absent a high-quality refutation."""
    supp = _supporting_families(inp.evidence_refs)
    refu = _refuting_families(inp.evidence_refs, min_quality=_HIGH_QUALITY)
    if len(supp) >= 2 and not refu:
        return CorroborationFinding("builder", "corroborate",
                                    "two or more independent supports, no strong contradiction",
                                    sorted(supp), sorted(refu))
    if refu and not supp:
        return CorroborationFinding("builder", "refute",
                                    "contradicted with no support", sorted(supp), sorted(refu))
    return CorroborationFinding("builder", "insufficient",
                                "support not decorrelated enough to act on",
                                sorted(supp), sorted(refu))


def _fixture_domain_reader(inp: FrontierCouncilInput) -> CorroborationFinding:
    """Weighs evidence quality across decorrelated families."""
    supp_refs = [r for r in inp.evidence_refs if r.supports]
    supp = {r.source_family for r in supp_refs}
    refu = _refuting_families(inp.evidence_refs, min_quality=_HIGH_QUALITY)
    avg_quality = (sum(r.quality for r in supp_refs) / len(supp_refs)) if supp_refs else 0.0
    if len(supp) >= 2 and avg_quality >= 0.5 and not refu:
        return CorroborationFinding("domain_reader", "corroborate",
                                    f"two+ decorrelated families, avg quality {avg_quality:.2f}",
                                    sorted(supp), sorted(refu))
    if refu:
        return CorroborationFinding("domain_reader", "refute",
                                    "domain contradiction present", sorted(supp), sorted(refu))
    return CorroborationFinding("domain_reader", "insufficient",
                                "insufficient decorrelated/quality support",
                                sorted(supp), sorted(refu))


_FIXTURE_FAMILIES = (_fixture_skeptic, _fixture_builder, _fixture_domain_reader)


def _payload_hash(obj: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def evaluate_boundary_signal(
    inp: FrontierCouncilInput, config: FrontierCouncilConfig | None = None
) -> WorldSensemakingReceipt:
    """Cross-falsify one boundary signal into a verdict + receipt. Pure; no I/O,
    no mutation of any owner. Deterministic in fixture mode."""
    cfg = config or FrontierCouncilConfig()
    risks: list[str] = []

    # A high-risk / unsafe signal is quarantined: its claim is NOT auto-evaluated.
    # (The Stage-0 fence still preserves it as inert data elsewhere.)
    if (not inp.safe) or inp.instruction_risk == "high":
        risks.append(f"signal quarantined (safe={inp.safe}, instruction_risk={inp.instruction_risk})")
        return _build_receipt(inp, QUARANTINED, [], 0, 0, 0, risks)

    findings = [fam(inp) for fam in _FIXTURE_FAMILIES]
    corroborating = {f.evaluator_family for f in findings if f.stance == "corroborate"}
    refuting = {f.evaluator_family for f in findings if f.stance == "refute"}
    source_families = _supporting_families(inp.evidence_refs)

    # The structural rule (the moat): corroboration requires BOTH >=2 decorrelated
    # EVALUATOR families AND >=2 decorrelated SOURCE families. Confident prose from
    # one family cannot upgrade a claim.
    if (
        len(corroborating) >= cfg.min_corroborating_families
        and len(source_families) >= cfg.min_source_families
        and len(corroborating) > len(refuting)
    ):
        verdict = CORROBORATED
    elif len(refuting) >= len(corroborating) and refuting:
        verdict = REFUTED
    else:
        verdict = INSUFFICIENT
        if len(source_families) < cfg.min_source_families:
            risks.append("fewer than two decorrelated source families")

    return _build_receipt(
        inp, verdict, findings, len(corroborating), len(refuting), len(source_families), risks
    )


def _build_receipt(
    inp: FrontierCouncilInput,
    verdict: str,
    findings: list[CorroborationFinding],
    corroboration_count: int,
    refutation_count: int,
    source_family_count: int,
    risks: list[str],
) -> WorldSensemakingReceipt:
    body = {
        "input_signal_hash": inp.input_signal_hash,
        "claim": inp.claim,
        "verdict": verdict,
        "corroboration_count": corroboration_count,
        "source_family_count": source_family_count,
    }
    return WorldSensemakingReceipt(
        receipt_id=f"world_sensemaking_{_payload_hash(body)[7:31]}",
        input_signal_hash=inp.input_signal_hash,
        claim=inp.claim,
        verdict=verdict,
        corroboration_count=corroboration_count,
        refutation_count=refutation_count,
        source_family_count=source_family_count,
        findings=[asdict(f) for f in findings],
        evidence_refs=[asdict(r) for r in inp.evidence_refs],
        risks=risks,
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        provenance=inp.provenance,
        payload_hash=_payload_hash(body),
        no_action_authority=True,
        dispatch_authority=False,
    )


def evaluate_boundary_signals(
    inputs: list[FrontierCouncilInput], config: FrontierCouncilConfig | None = None
) -> list[WorldSensemakingReceipt]:
    return [evaluate_boundary_signal(inp, config) for inp in inputs]
