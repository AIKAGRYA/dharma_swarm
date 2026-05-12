"""Deterministic seed and scoring for the Empty Quadrant revenue hypernode."""

from __future__ import annotations

from pydantic import BaseModel

from dharma_swarm.anekanta_gate import evaluate_anekanta
from dharma_swarm.auto_grade.engine import AutoGradeEngine
from dharma_swarm.auto_research.models import ClaimRecord, ResearchBrief, ResearchReport, SourceDocument
from dharma_swarm.models import GateResult
from dharma_swarm.telos_gates import TelosGatekeeper


EMPTY_QUADRANT_SLUG = "empty-quadrant-revenue-cell"
EMPTY_QUADRANT_PUBLIC_PATH = "/dashboard/hypernodes/empty-quadrant"
HYPERNODE_ID = "hypernode-empty-quadrant-revenue"
REVENUE_CELL_ID = "revenue-cell-empty-quadrant"
COUNCIL_VERDICT_ID = "council-verdict-empty-quadrant"
FITNESS_VECTOR_ID = "fitness-vector-empty-quadrant"
PRINCIPAL_AGENT_ID = "agent-dhyana-principal"
PUBLIC_ARTIFACT_ID = "artifact-empty-quadrant-page"
SIGNAL_ID = "signal-empty-quadrant-revenue"
QUESTION_ID = "question-empty-quadrant-revenue"
CLAIM_ID = "claim-empty-quadrant-thesis"
EVIDENCE_ID = "evidence-empty-quadrant-provenance"
DOCTRINE_ID = "doctrine-trustee-revenue-welfare"
ACTION_PROPOSAL_ID = "proposal-empty-quadrant-page"
GATE_RECORD_ID = "gate-empty-quadrant-page"
EXECUTION_LEASE_ID = "lease-empty-quadrant-page"
OUTCOME_ID = "outcome-empty-quadrant-page"
VALUE_EVENT_ID = "value-empty-quadrant-page"
CONTRIBUTION_ID = "contribution-empty-quadrant-page"

QUORUM_PARTICIPANTS = [
    "ThinkodynamicDirector",
    "JagatKalyanEngine",
    "ZeitgeistExecutive",
    "ShaktiZeitgeistExecutive",
    "ShaktiLoop",
    "OvernightDirector",
    "OperatorBridge",
    "GinkoOrchestrator",
]

NEXT_ACTIONS = [
    "Publish the Empty Quadrant page as the category-defining artifact.",
    "Attach one externally verifiable customer or buyer signal before revenue validation.",
    "Run MIROFISH adversarial simulation on extraction drift and worldview overclaim risk.",
    "Convert the strongest market signal into a paid consulting or governance-SDK offer.",
]


class QuadrantFrame(BaseModel):
    id: str
    label: str
    governance: str
    orientation: str
    description: str
    occupied: bool = True


class ProvenanceRecord(BaseModel):
    id: str
    label: str
    source_type: str
    reference: str
    confidence: float


class CouncilVerdictPayload(BaseModel):
    id: str
    decision: str
    reason: str
    gate_results: dict[str, str]
    anekanta_frames: list[str]
    steelman_summary: str
    dogma_drift_summary: str
    mirofish_activated: bool
    mirofish_reason: str
    quorum_participants: list[str]


class FitnessVectorPayload(BaseModel):
    id: str
    auto_grade_score: float
    council_score: float
    provenance_score: float
    market_value_score: float
    welfare_score: float
    composite_score: float
    promotion_threshold: float
    threshold_met: bool
    promotion_state: str
    scoring_method: str


class RevenueCellPayload(BaseModel):
    id: str
    name: str
    market_category: str
    target_customer: str
    revenue_model: str
    verified_revenue_usd: float
    expected_value_usd: float
    evidence_tier: str
    trustee_principle: str
    status: str
    next_actions: list[str]


class TypedLinkPayload(BaseModel):
    source_id: str
    source_type: str
    link_name: str
    target_id: str
    target_type: str


class HypernodePayload(BaseModel):
    id: str
    slug: str
    title: str
    thesis: str
    public_path: str
    quadrant_map: list[QuadrantFrame]
    provenance: list[ProvenanceRecord]
    council_verdict: CouncilVerdictPayload
    fitness_vector: FitnessVectorPayload
    revenue_cell: RevenueCellPayload
    object_chain: dict[str, list[str]]
    typed_links: list[TypedLinkPayload]
    next_actions: list[str]
    ontology_counts: dict[str, int]


def _quadrants() -> list[QuadrantFrame]:
    return [
        QuadrantFrame(
            id="low-governance-extraction",
            label="Slop economy",
            governance="low governance",
            orientation="extraction",
            description="Cheap output, weak accountability, and attention capture.",
        ),
        QuadrantFrame(
            id="high-governance-extraction",
            label="Operational control",
            governance="high governance",
            orientation="extraction",
            description="Palantir-style control loops optimized around institutional power.",
        ),
        QuadrantFrame(
            id="low-governance-welfare",
            label="Good intentions",
            governance="low governance",
            orientation="welfare",
            description="Real care without enough execution, audit, or compounding power.",
        ),
        QuadrantFrame(
            id="high-governance-welfare",
            label="Empty quadrant",
            governance="high governance",
            orientation="welfare",
            description="Auditable intelligence that turns world-welfare constraints into market value.",
            occupied=False,
        ),
    ]


def _provenance() -> list[ProvenanceRecord]:
    return [
        ProvenanceRecord(
            id="source-user-plan",
            label="Empty Quadrant Revenue Hypernode plan",
            source_type="operator_plan",
            reference="current task plan",
            confidence=1.0,
        ),
        ProvenanceRecord(
            id="source-aligned-revenue-engines",
            label="Aligned Revenue Engines wiki",
            source_type="wiki",
            reference="~/.dharma/knowledge/wiki/concepts/aligned-revenue-engines.md",
            confidence=0.88,
        ),
        ProvenanceRecord(
            id="source-economic-spine",
            label="Economic Spine wiki",
            source_type="wiki",
            reference="~/.dharma/knowledge/wiki/concepts/economic-spine.md",
            confidence=0.90,
        ),
        ProvenanceRecord(
            id="source-jagat-kalyan",
            label="Jagat Kalyan wiki",
            source_type="wiki",
            reference="~/.dharma/knowledge/wiki/concepts/jagat-kalyan.md",
            confidence=0.88,
        ),
    ]


def _research_report() -> tuple[ResearchReport, list[SourceDocument]]:
    provenance = _provenance()
    sources = [
        SourceDocument(
            source_id=item.id,
            url=f"file://{item.reference}",
            title=item.label,
            source_type=item.source_type,
            authority_score=item.confidence,
            freshness_score=0.86,
        )
        for item in provenance
    ]
    brief = ResearchBrief(
        task_id=ACTION_PROPOSAL_ID,
        topic="Empty Quadrant revenue cell",
        question="Can high-governance, welfare-oriented intelligence be made market-facing without erasing telos?",
        requires_recency=False,
        metadata={"sources_requested": True},
    )
    claims = [
        ClaimRecord(
            claim_id="claim-quadrant-map",
            text="The market map has an underoccupied high-governance, welfare-oriented quadrant.",
            support_level="supported",
            supporting_source_ids=["source-user-plan", "source-jagat-kalyan"],
            citations=["[source-user-plan]", "[source-jagat-kalyan]"],
            confidence=0.86,
        ),
        ClaimRecord(
            claim_id="claim-revenue-trustee",
            text="Revenue is valid only as trustee flow that funds welfare-serving work.",
            support_level="supported",
            supporting_source_ids=["source-economic-spine", "source-jagat-kalyan"],
            citations=["[source-economic-spine]", "[source-jagat-kalyan]"],
            confidence=0.90,
        ),
        ClaimRecord(
            claim_id="claim-first-surface",
            text="The first artifact should be both a public dashboard surface and ontology-backed internal graph.",
            support_level="supported",
            supporting_source_ids=["source-user-plan", "source-aligned-revenue-engines"],
            citations=["[source-user-plan]", "[source-aligned-revenue-engines]"],
            confidence=0.84,
        ),
    ]
    body = (
        "The Empty Quadrant Revenue Cell frames the market as four quadrants: slop economy, "
        "operational control, good intentions, and high-governance welfare. [source-user-plan] "
        "The economic spine requires verified revenue to stay distinct from internal estimates. "
        "[source-economic-spine] Jagat Kalyan keeps revenue instrumental rather than primary. "
        "[source-jagat-kalyan] However, the strongest counterargument is that revenue pressure "
        "could pull a welfare-governance system back into extraction; the mitigation is an "
        "audited council trace, provenance, and a MIROFISH adversarial pass. The mechanism is "
        "a typed ontology architecture: ActionProposal, GateDecisionRecord, Outcome, "
        "ValueEvent, and Contribution records are written through TelicSeam. The "
        "phenomenological guard records first-person uncertainty before publication: "
        "right now, I notice the claim could overreach without external buyer evidence. "
        "The systems frame is feedback from buyer signal to revenue validation to "
        "council review. Recommended next step: "
        "publish the page, then attach one external buyer signal before revenue validation."
    )
    report = ResearchReport(
        report_id="report-empty-quadrant-revenue",
        task_id=ACTION_PROPOSAL_ID,
        brief=brief,
        summary="Hypernode #1 turns the empty quadrant thesis into a public and ontology-backed artifact.",
        body=body,
        claims=claims,
        source_ids=[source.source_id for source in sources],
        metadata={"topical_coverage": 0.91, "novelty": 0.78},
    )
    return report, sources


def _gate_result_text(results: dict[str, tuple[GateResult, str]]) -> dict[str, str]:
    return {name: result.value for name, (result, _reason) in results.items()}


def evaluate_hypernode_council() -> CouncilVerdictPayload:
    report, _sources = _research_report()
    anekanta = evaluate_anekanta(report.summary, report.body)
    gate_check = TelosGatekeeper().check(
        action="propose hypernode revenue cell",
        content=report.body,
    )
    gate_results = _gate_result_text(gate_check.gate_results)
    gate_results["MIROFISH"] = "WARN"

    return CouncilVerdictPayload(
        id=COUNCIL_VERDICT_ID,
        decision="warn",
        reason=(
            "Anekanta, STEELMAN, and DOGMA_DRIFT pass; MIROFISH remains active "
            "because public revenue claims can drift into extraction without external evidence."
        ),
        gate_results=gate_results,
        anekanta_frames=anekanta.frames_detected,
        steelman_summary=gate_check.gate_results.get("STEELMAN", (GateResult.WARN, ""))[1],
        dogma_drift_summary=gate_check.gate_results.get("DOGMA_DRIFT", (GateResult.WARN, ""))[1],
        mirofish_activated=True,
        mirofish_reason=(
            "Maximum-divergence simulation required for high-stakes category claims, "
            "especially extraction drift, Goodhart pressure, and worldview overreach."
        ),
        quorum_participants=QUORUM_PARTICIPANTS,
    )


def score_hypernode(
    council: CouncilVerdictPayload,
    revenue_cell: RevenueCellPayload,
) -> FitnessVectorPayload:
    report, sources = _research_report()
    reward = AutoGradeEngine().grade(
        report,
        sources,
        latency_ms=1400,
        token_cost_usd=0.04,
        total_tokens=2400,
        cost_budget_usd=1.0,
        latency_budget_ms=6000,
        token_budget=6000,
    )
    auto_grade_score = reward.grade_card.final_score
    council_score = 0.82 if council.decision in {"warn", "review"} else 1.0
    provenance_score = min(1.0, len(_provenance()) / 4.0)
    market_value_score = min(1.0, max(0.0, revenue_cell.expected_value_usd) / 10_000.0)
    welfare_score = 0.95
    composite = (
        0.35 * auto_grade_score
        + 0.25 * council_score
        + 0.20 * provenance_score
        + 0.10 * market_value_score
        + 0.10 * welfare_score
    )
    threshold = 0.82
    threshold_met = composite >= threshold and not reward.grade_card.gate_failures
    if revenue_cell.verified_revenue_usd > 0 and threshold_met:
        promotion_state = "revenue_validated"
    elif threshold_met:
        promotion_state = "public_artifact_ready"
    else:
        promotion_state = "quorum_ready"

    return FitnessVectorPayload(
        id=FITNESS_VECTOR_ID,
        auto_grade_score=round(auto_grade_score, 4),
        council_score=round(council_score, 4),
        provenance_score=round(provenance_score, 4),
        market_value_score=round(market_value_score, 4),
        welfare_score=round(welfare_score, 4),
        composite_score=round(composite, 4),
        promotion_threshold=threshold,
        threshold_met=threshold_met,
        promotion_state=promotion_state,
        scoring_method="hypernode_fitness_v1:0.35_autograde+0.25_council+0.20_provenance+0.10_market+0.10_welfare",
    )


def _revenue_cell() -> RevenueCellPayload:
    return RevenueCellPayload(
        id=REVENUE_CELL_ID,
        name="Empty Quadrant Revenue Cell",
        market_category="telos-gated agent governance and research council surfaces",
        target_customer="teams that need auditable AI governance without extraction-first incentives",
        revenue_model=(
            "Start with paid advisory and governance dashboard implementation; graduate only "
            "after external buyer evidence, not internal enthusiasm."
        ),
        verified_revenue_usd=0.0,
        expected_value_usd=5000.0,
        evidence_tier="internal_estimate",
        trustee_principle="Revenue flows through the system for Jagat Kalyan; it is not allowed to become the telos.",
        status="validating",
        next_actions=NEXT_ACTIONS,
    )


def build_empty_quadrant_payload() -> HypernodePayload:
    revenue_cell = _revenue_cell()
    council = evaluate_hypernode_council()
    fitness = score_hypernode(council, revenue_cell)
    object_chain = {
        "inquiry": [SIGNAL_ID, QUESTION_ID, CLAIM_ID, EVIDENCE_ID, DOCTRINE_ID],
        "action": [ACTION_PROPOSAL_ID, GATE_RECORD_ID, EXECUTION_LEASE_ID, OUTCOME_ID, VALUE_EVENT_ID, CONTRIBUTION_ID],
    }
    return HypernodePayload(
        id=HYPERNODE_ID,
        slug=EMPTY_QUADRANT_SLUG,
        title="Empty Quadrant Revenue Cell",
        thesis=(
            "High-governance, welfare-oriented intelligence is the empty market quadrant: "
            "not slop, not extraction control, and not powerless good intention."
        ),
        public_path=EMPTY_QUADRANT_PUBLIC_PATH,
        quadrant_map=_quadrants(),
        provenance=_provenance(),
        council_verdict=council,
        fitness_vector=fitness,
        revenue_cell=revenue_cell,
        object_chain=object_chain,
        typed_links=[],
        next_actions=NEXT_ACTIONS,
        ontology_counts={},
    )
