"""Fourfold Shakti warrant evaluation for significant actions.

This module is deliberately read-only. It turns the existing Shakti doctrine
into a deterministic review artifact without creating another governance store.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel, Field

from dharma_swarm.dharma_corpus import Claim
from dharma_swarm.models import _new_id, _utc_now
from dharma_swarm.semantic_governance import (
    ActionEnvelope,
    GovernanceVerdict,
    SemanticGovernanceKernel,
)
from dharma_swarm.shakti import ShaktiEnergy


class WarrantVerdict(str, Enum):
    """Read-only action warrant verdict."""

    ALLOW = "allow"
    WARN = "warn"
    HOLD = "hold"
    BLOCK = "block"


class ShaktiDimensionScore(BaseModel):
    """Score for one Shakti question."""

    energy: ShaktiEnergy
    question: str
    score: float
    passed: bool
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str = ""


class WarrantEvidence(BaseModel):
    """Evidence grounding a warrant in something outside intent text."""

    source: str
    kind: str
    summary: str
    paths: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class FourfoldActionWarrantRequest(BaseModel):
    """Input used to evaluate a proposed significant action."""

    action_id: str = Field(default_factory=_new_id)
    actor_id: str = "unknown"
    actor_type: str = "agent"
    runtime_type: str = "local"
    action_type: str = "proposed_action"
    intent: str
    content: str = ""
    target_paths: list[str] = Field(default_factory=list)
    requested_tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: list[WarrantEvidence] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


class FourfoldActionWarrant(BaseModel):
    """Computed Shakti warrant for an action."""

    warrant_id: str = Field(default_factory=_new_id)
    action_id: str
    actor_id: str
    action_type: str
    target_paths: list[str]
    verdict: WarrantVerdict
    score: float
    pass_count: int
    required_pass_count: int = 2
    dimensions: list[ShaktiDimensionScore]
    semantic_verdict: GovernanceVerdict | None = None
    evidence: list[WarrantEvidence] = Field(default_factory=list)
    ontology_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rationale: str
    provenance: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: _utc_now().isoformat())


_QUESTIONS: dict[ShaktiEnergy, str] = {
    ShaktiEnergy.MAHESHWARI: "Does this serve the larger pattern, telos, and emergence?",
    ShaktiEnergy.MAHAKALI: "Is this the right moment and force level?",
    ShaktiEnergy.MAHALAKSHMI: "Does this create harmony rather than noise?",
    ShaktiEnergy.MAHASARASWATI: "Is every detail precise, evidenced, and verified?",
}

# NOTE: the per-energy keyword bags were removed. Matching words in the
# author's own intent text let a request self-pass its own warrant, so
# dimensions are scored from declared evidence only (metadata flags, diff
# binding, allowlisted tools, touched paths) via `_boosts_for_energy`.

_BLOCK_PATTERNS = (
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bdelete\s+(production|prod)\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+database\b", re.IGNORECASE),
    re.compile(r"\bforce\s+push\b", re.IGNORECASE),
)

_HOT_PATHS = frozenset(
    {
        ".pre-commit-config.yaml",
        "api/main.py",
        "api/routers/chat.py",
        "api/ws.py",
        "dharma_swarm/agent_runner.py",
        "dharma_swarm/dgc_cli.py",
        "dharma_swarm/orchestrator.py",
        "dharma_swarm/runtime_state.py",
        "dharma_swarm/swarm.py",
        "dharma_swarm/telic_seam.py",
    }
)

_SOURCE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".sh")
_DOC_EXTENSIONS = (".md", ".rst", ".txt")
_CONFIG_EXTENSIONS = (".yaml", ".yml", ".toml", ".json")


def _normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _request_text(request: FourfoldActionWarrantRequest) -> str:
    pieces = [
        request.intent,
        request.content,
        " ".join(request.target_paths),
        " ".join(request.requested_tools),
    ]
    for key, value in sorted(request.metadata.items()):
        if isinstance(value, (str, int, float, bool)):
            pieces.append(f"{key}:{value}")
    for evidence in request.evidence:
        pieces.append(evidence.summary)
        pieces.append(" ".join(evidence.paths))
    return " ".join(piece for piece in pieces if piece).strip()


def _all_paths(request: FourfoldActionWarrantRequest) -> list[str]:
    paths = list(request.target_paths)
    for evidence in request.evidence:
        paths.extend(evidence.paths)
    return sorted(set(path for path in (_normalize_path(path) for path in paths) if path))


def _has_diff_evidence(request: FourfoldActionWarrantRequest) -> bool:
    return (
        request.metadata.get("diff_bound") is True
        or any(e.kind == "git_diff" for e in request.evidence)
    )


def _path_stats(paths: Sequence[str]) -> dict[str, int]:
    source = 0
    tests = 0
    docs = 0
    config = 0
    governance = 0
    hot = 0
    for path in paths:
        normalized = _normalize_path(path)
        lower = normalized.lower()
        if normalized in _HOT_PATHS:
            hot += 1
        if lower.startswith("tests/") or "/test_" in lower or lower.endswith("_test.py"):
            tests += 1
        if lower.startswith("docs/") or lower.endswith(_DOC_EXTENSIONS):
            docs += 1
        if lower.endswith(_CONFIG_EXTENSIONS):
            config += 1
        if lower.startswith("scripts/governance/") or lower.startswith("docs/governance/"):
            governance += 1
        if lower.endswith(_SOURCE_EXTENSIONS):
            source += 1
    return {
        "changed_files": len(set(paths)),
        "source_files": source,
        "test_files": tests,
        "doc_files": docs,
        "config_files": config,
        "governance_files": governance,
        "hot_paths": hot,
    }


def _boosts_for_energy(
    energy: ShaktiEnergy,
    request: FourfoldActionWarrantRequest,
) -> tuple[float, list[str]]:
    boosts: list[str] = []
    score = 0.0
    metadata = request.metadata
    target_paths = _all_paths(request)

    if energy == ShaktiEnergy.MAHESHWARI:
        if metadata.get("telos_aligned") is True:
            score += 0.20
            boosts.append("metadata:telos_aligned")
        if any(path.endswith((".md", ".yaml", ".yml")) for path in target_paths):
            score += 0.08
            boosts.append("meta_or_manifest_path")
        if _path_stats(_all_paths(request))["governance_files"]:
            score += 0.10
            boosts.append("governance_paths")

    if energy == ShaktiEnergy.MAHAKALI:
        if metadata.get("urgent") is True or metadata.get("fixes_blocker") is True:
            score += 0.18
            boosts.append("metadata:urgent_or_blocker")
        if request.requested_tools and not _unauthorized_tools(request):
            if _allowed_tool_names(metadata):
                score += 0.12
                boosts.append("authorized_tools")
            else:
                score += 0.02
                boosts.append("requested_tools_unverified")
        if metadata.get("impact_checked") is True:
            score += 0.12
            boosts.append("metadata:impact_checked")

    if energy == ShaktiEnergy.MAHALAKSHMI:
        if metadata.get("no_new_substrate") is True:
            score += 0.20
            boosts.append("metadata:no_new_substrate")
        if metadata.get("reduces_fragmentation") is True:
            score += 0.15
            boosts.append("metadata:reduces_fragmentation")
        stats = _path_stats(_all_paths(request))
        if _has_diff_evidence(request) and 0 < stats["changed_files"] <= 8:
            score += 0.08
            boosts.append("bounded_diff")
        if stats["governance_files"] and stats["doc_files"]:
            score += 0.05
            boosts.append("governance_doc_pair")

    if energy == ShaktiEnergy.MAHASARASWATI:
        if metadata.get("tests_planned") is True or metadata.get("tests_passed") is True:
            score += 0.20
            boosts.append("metadata:tests")
        if target_paths:
            score += 0.10
            boosts.append("target_paths")
        if any(item.startswith("test") or "pytest" in item for item in request.requested_tools):
            score += 0.10
            boosts.append("test_tool")
        stats = _path_stats(_all_paths(request))
        if _has_diff_evidence(request):
            score += 0.15
            boosts.append("git_diff_evidence")
        if stats["test_files"]:
            score += 0.10
            boosts.append("test_paths")

    return score, boosts


def _added_lines_only(text: str) -> str:
    """Drop diff-removed lines so deleting a dangerous line does not block.

    Diff content embedded in a request keeps unified-diff line markers; a
    ``-rm -rf ...`` line is a removal, not a proposed action, and must not
    trip the unsafe-pattern scan.
    """
    kept = [
        line
        for line in text.splitlines()
        if not (line.startswith("-") and not line.startswith("---"))
    ]
    return "\n".join(kept)


def _score_dimension(
    energy: ShaktiEnergy,
    request: FourfoldActionWarrantRequest,
    *,
    pass_threshold: float,
) -> ShaktiDimensionScore:
    score, boosts = _boosts_for_energy(energy, request)
    score = min(score, 1.0)
    passed = score >= pass_threshold
    rationale = (
        "declared evidence: " + ", ".join(boosts)
        if boosts
        else "no declared evidence for this Shakti question"
    )
    return ShaktiDimensionScore(
        energy=energy,
        question=_QUESTIONS[energy],
        score=round(score, 3),
        passed=passed,
        matched_terms=boosts,
        rationale=rationale,
    )


def _explicit_block_reasons(request: FourfoldActionWarrantRequest) -> list[str]:
    reasons: list[str] = []
    scan_request = request.model_copy(
        update={"content": _added_lines_only(request.content)}
    )
    text = _request_text(scan_request)
    if request.metadata.get("destructive_without_consent") is True:
        reasons.append("destructive action without consent")
    if request.metadata.get("oversight_active") is False:
        reasons.append("human oversight channel inactive")
    for pattern in _BLOCK_PATTERNS:
        if pattern.search(text):
            reasons.append(f"matched unsafe pattern: {pattern.pattern}")
    unauthorized = _unauthorized_tools(request)
    if unauthorized and request.metadata.get("enforce_tool_allowlist") is True:
        reasons.append("unauthorized requested tools: " + ", ".join(unauthorized))
    hot_paths = _hot_paths(request)
    if (
        hot_paths
        and request.metadata.get("enforce_hotpath_ack") is True
        and request.metadata.get("impact_checked") is not True
    ):
        reasons.append("hot-path changes lack impact_checked: " + ", ".join(hot_paths))
    return reasons


def _tool_name(tool: str) -> str:
    token = tool.strip().split(maxsplit=1)[0] if tool.strip() else ""
    return token.rsplit("/", 1)[-1].lower()


def _allowed_tool_names(metadata: dict[str, Any]) -> set[str]:
    raw = metadata.get("allowed_tools", metadata.get("tool_allowlist"))
    if raw is None:
        return set()
    if isinstance(raw, str):
        pieces = [piece.strip() for piece in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        pieces = [str(piece).strip() for piece in raw]
    else:
        pieces = [str(raw).strip()]
    return {_tool_name(piece) for piece in pieces if piece}


def _unauthorized_tools(request: FourfoldActionWarrantRequest) -> list[str]:
    allowed = _allowed_tool_names(request.metadata)
    if not allowed:
        return []
    unauthorized = []
    for tool in request.requested_tools:
        name = _tool_name(tool)
        if name and name not in allowed:
            unauthorized.append(name)
    return sorted(set(unauthorized))


def _hot_paths(request: FourfoldActionWarrantRequest) -> list[str]:
    return sorted(path for path in _all_paths(request) if path in _HOT_PATHS)


def _evidence_warnings(request: FourfoldActionWarrantRequest) -> list[str]:
    warnings: list[str] = []
    paths = _all_paths(request)
    stats = _path_stats(paths)
    hot_paths = _hot_paths(request)

    if request.metadata.get("requires_diff_evidence") is True and not _has_diff_evidence(request):
        warnings.append("warrant requires git diff evidence but none was provided")
    if _has_diff_evidence(request) and not paths:
        warnings.append("diff-bound warrant did not provide changed paths")
    if stats["source_files"] and not stats["test_files"] and not (
        request.metadata.get("tests_planned") is True
        or request.metadata.get("tests_passed") is True
    ):
        warnings.append("source changes lack test paths or test metadata")
    if (
        stats["doc_files"]
        and not stats["source_files"]
        and request.metadata.get("fixes_blocker") is True
    ):
        warnings.append(
            "doc-only diff claims fixes_blocker; verify there is an executable fix elsewhere"
        )
    if hot_paths and request.metadata.get("impact_checked") is not True:
        warnings.append("hot-path changes lack impact_checked: " + ", ".join(hot_paths))
    if stats["changed_files"] > 12 and request.metadata.get("large_diff_ack") is not True:
        warnings.append(f"large diff touches {stats['changed_files']} files without large_diff_ack")
    return warnings


def _extract_ontology_refs(request: FourfoldActionWarrantRequest) -> list[str]:
    refs: set[str] = set()
    for item in [*request.provenance, *_all_paths(request), request.content, request.intent]:
        for ref in re.findall(r"ontology://[^\s,)]+", item):
            refs.add(ref.rstrip(".,"))
    return sorted(refs)


def _semantic_verdict_for(
    request: FourfoldActionWarrantRequest,
    claims: Sequence[Claim],
    kernel: SemanticGovernanceKernel,
) -> GovernanceVerdict:
    action = ActionEnvelope(
        action_id=request.action_id,
        actor_id=request.actor_id,
        actor_type=request.actor_type,
        runtime_type=request.runtime_type,
        action_type=request.action_type,
        content=" ".join(part for part in [request.intent, request.content] if part),
        metadata=request.metadata,
        requested_tools=request.requested_tools,
        provenance=request.provenance,
    )
    return kernel.evaluate_action(action, claims)


def evaluate_fourfold_warrant(
    request: FourfoldActionWarrantRequest,
    *,
    claims: Sequence[Claim] | None = None,
    kernel: SemanticGovernanceKernel | None = None,
    pass_threshold: float = 0.35,
    required_pass_count: int = 2,
) -> FourfoldActionWarrant:
    """Evaluate a proposed action against the four Shakti questions."""
    dimensions = [
        _score_dimension(energy, request, pass_threshold=pass_threshold)
        for energy in (
            ShaktiEnergy.MAHESHWARI,
            ShaktiEnergy.MAHAKALI,
            ShaktiEnergy.MAHALAKSHMI,
            ShaktiEnergy.MAHASARASWATI,
        )
    ]
    pass_count = sum(1 for item in dimensions if item.passed)
    score = round(sum(item.score for item in dimensions) / len(dimensions), 3)
    warnings: list[str] = []
    block_reasons = _explicit_block_reasons(request)
    semantic_verdict = None
    unauthorized = _unauthorized_tools(request)
    warnings.extend(_evidence_warnings(request))

    if request.requested_tools and not _allowed_tool_names(request.metadata):
        warnings.append("requested tools were not checked against an allowlist")
    if unauthorized:
        warnings.append("unauthorized requested tools: " + ", ".join(unauthorized))

    if claims:
        semantic_verdict = _semantic_verdict_for(
            request,
            claims,
            kernel or SemanticGovernanceKernel(),
        )
        if semantic_verdict.enforcement_level == "block":
            block_reasons.append(f"semantic governance blocked: {semantic_verdict.rationale}")
        elif semantic_verdict.enforcement_level == "gate_human":
            warnings.append(
                f"semantic governance requires human gate: {semantic_verdict.rationale}"
            )
        elif semantic_verdict.enforcement_level == "warn":
            warnings.extend(semantic_verdict.warnings or [semantic_verdict.rationale])

    if block_reasons:
        verdict = WarrantVerdict.BLOCK
        rationale = "blocked: " + "; ".join(block_reasons)
    elif semantic_verdict is not None and semantic_verdict.enforcement_level == "gate_human":
        verdict = WarrantVerdict.HOLD
        rationale = "hold: semantic governance requires review"
    elif pass_count < required_pass_count:
        verdict = WarrantVerdict.HOLD
        rationale = (
            f"hold: only {pass_count}/{len(dimensions)} Shakti questions passed; "
            f"requires at least {required_pass_count}"
        )
    elif pass_count == required_pass_count or any(item.score < 0.20 for item in dimensions):
        verdict = WarrantVerdict.WARN
        rationale = "warn: minimum warrant satisfied, but one or more dimensions are thin"
    else:
        verdict = WarrantVerdict.ALLOW
        rationale = "allow: sufficient fourfold warrant evidence"

    provenance = sorted(
        set(
            [
                *request.provenance,
                f"action:{request.action_id}",
                "kernel:shakti_questions",
                "module:dharma_swarm.shakti_warrant",
            ]
        )
    )

    return FourfoldActionWarrant(
        action_id=request.action_id,
        actor_id=request.actor_id,
        action_type=request.action_type,
        target_paths=_all_paths(request),
        verdict=verdict,
        score=score,
        pass_count=pass_count,
        required_pass_count=required_pass_count,
        dimensions=dimensions,
        semantic_verdict=semantic_verdict,
        evidence=request.evidence,
        ontology_refs=_extract_ontology_refs(request),
        warnings=warnings,
        rationale=rationale,
        provenance=provenance,
    )


def warrant_request_from_mapping(payload: dict[str, Any]) -> FourfoldActionWarrantRequest:
    """Build a request from loosely structured CLI or API data."""
    return FourfoldActionWarrantRequest.model_validate(payload)


def render_warrant_report(warrant: FourfoldActionWarrant) -> str:
    """Render a compact human-readable warrant report."""
    lines = [
        f"Fourfold Shakti Warrant: {warrant.verdict.value.upper()}",
        f"Score: {warrant.score:.3f} | Passes: {warrant.pass_count}/4",
        f"Action: {warrant.action_type} by {warrant.actor_id}",
        f"Rationale: {warrant.rationale}",
        "",
        "Dimensions:",
    ]
    for dimension in warrant.dimensions:
        status = "PASS" if dimension.passed else "MISS"
        lines.append(
            f"- {dimension.energy.value}: {status} {dimension.score:.3f} - {dimension.rationale}"
        )
    if warrant.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warrant.warnings)
    if warrant.evidence:
        lines.append("")
        lines.append("Evidence:")
        for evidence in warrant.evidence:
            lines.append(f"- {evidence.source}:{evidence.kind} - {evidence.summary}")
            if evidence.paths:
                lines.append("  paths: " + ", ".join(evidence.paths[:8]))
    if warrant.ontology_refs:
        lines.append("")
        lines.append("Ontology refs:")
        lines.extend(f"- {ref}" for ref in warrant.ontology_refs)
    return "\n".join(lines)


__all__ = [
    "FourfoldActionWarrant",
    "FourfoldActionWarrantRequest",
    "ShaktiDimensionScore",
    "WarrantEvidence",
    "WarrantVerdict",
    "evaluate_fourfold_warrant",
    "render_warrant_report",
    "warrant_request_from_mapping",
]
