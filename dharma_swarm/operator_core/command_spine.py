"""Operator command spine v0.

This module is the small Python boundary between fuzzy operator intent and the
repo's governed work-packet loop. It is deliberately dry-run first: it drafts
AgentOps-compatible packets, reads completed AgentOps reports, records explicit
human YDS ratings to an append-only ledger, and evaluates whether a stable
subproblem is ready for a future Rust extraction.

It does not execute worktrees, run gates, merge, push, mutate ontology state, or
assign authoritative YDS ratings by itself.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.intent_router import IntentRouter
from dharma_swarm.operator_core.operating_facts import append_human_yds_rating


DEFAULT_FORBIDDEN_FILES = [
    "api/**",
    "dashboard/**",
    "dharma_swarm/telos_gates.py",
    "dharma_swarm/dharma_kernel.py",
]
DEFAULT_GATE_COMMANDS = [
    {"name": "compile", "command": "python3 -m compileall dharma_swarm tests"},
    {"name": "diff-check", "command": "git diff --check"},
]
HUMAN_YDS_SOURCES = {"human", "operator", "dhyana"}
YDS_RE = re.compile(r"^5\.(?:6|7|8|9|10|11|12|13|14|15)(?:[abcd])?$")


def _default_gate_commands() -> list[dict[str, str]]:
    return [dict(gate) for gate in DEFAULT_GATE_COMMANDS]


@dataclass(frozen=True)
class OperatorCommandRequest:
    """Input to the dry-run command spine."""

    prompt: str
    base_ref: str = "HEAD"
    branch: str = "chore/operator-command"
    worktree: str = "/tmp/dharma_swarm_operator_command"
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=lambda: list(DEFAULT_FORBIDDEN_FILES))
    gates: list[dict[str, str]] = field(default_factory=_default_gate_commands)
    approval_before_commit: bool = True
    approval_before_merge: bool = True
    commit_allowed: bool = False
    commit_message: str = "chore(operator): execute command packet"
    knowledge_db_path: str | None = None
    mission_state_dir: str | None = None
    mission_path: str | None = None


@dataclass(frozen=True)
class PromptIntent:
    kind: str
    auto_execute: bool
    confidence: str
    reason: str
    command: str = ""


@dataclass(frozen=True)
class PlannedSubTask:
    task: str
    skill: str
    complexity: str
    risk_level: str
    recommended_agents: int


@dataclass(frozen=True)
class WorkPacketDraft:
    id: str
    base_ref: str
    branch: str
    worktree: str
    intent: str
    allowed_files: list[str]
    forbidden_files: list[str]
    gates: list[dict[str, str]]
    commit: dict[str, Any]
    approval: dict[str, bool]
    requires_human_scope: bool
    scope_confidence: str


@dataclass(frozen=True)
class CoherenceDelta:
    """Advisory declared-vs-actual delta attached to an operator plan."""

    organ_touched: str
    gap_closed: str
    proof_read: str
    new_drift_risk: str
    human_approval_needed: bool = True


@dataclass(frozen=True)
class MissionAttachment:
    found: bool
    source_kind: str = ""
    source_path: str = ""
    mission_title: str = ""
    status: str = ""
    blockers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OperatorCommandPlan:
    prompt_intent: PromptIntent
    primary_skill: str
    complexity: str
    risk_level: str
    recommended_agents: int
    sub_tasks: list[PlannedSubTask]
    prescriptions: list[dict[str, Any]]
    mission: MissionAttachment
    work_packet: WorkPacketDraft
    coherence_delta: CoherenceDelta
    warnings: list[str]
    next_step: str


@dataclass(frozen=True)
class AgentOpsReportSummary:
    source_path: str
    job_id: str
    status: str
    gates: str
    scope: str
    commit: str
    approval: str
    waste_patterns: list[str]


@dataclass(frozen=True)
class AgentOpsReview:
    reports_reviewed: int
    summaries: list[AgentOpsReportSummary]
    next_recommendation: str


@dataclass(frozen=True)
class HumanYDSRating:
    timestamp: str
    artifact: str
    rating: str
    source: str
    human_comment: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RustReadinessSignal:
    component: str
    deterministic: bool = False
    boundary_stable: bool = False
    has_green_tests: bool = False
    hot_path: bool = False
    security_critical: bool = False
    python_pain: bool = False


@dataclass(frozen=True)
class RustReadinessDecision:
    component: str
    decision: str
    reasons: list[str]
    next_step: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_prompt_intent(prompt: str) -> PromptIntent:
    """Resolve a prompt into the same coarse intent family as the operator shell."""

    text = prompt.strip()
    lowered = text.lower()
    if not text:
        return PromptIntent("chat", False, "low", "empty prompt")
    if text.startswith("/"):
        command = text[1:].split(None, 1)[0].lower()
        return PromptIntent("command", True, "high", "explicit slash command", command)
    if re.search(r"\b(who are you|what are you|where am i|what repo is this)\b", lowered):
        return PromptIntent("identity", True, "high", "identity-orientation request")
    if re.search(r"\b(compact|summarize session|save session|checkpoint)\b", lowered):
        return PromptIntent("memory", True, "medium", "session memory request")
    if any(term in lowered for term in ("subagent", "delegate", "agent swarm", "frontier model", "open model")):
        return PromptIntent("agent", False, "medium", "agent-orchestration request")
    if any(term in lowered for term in ("evolve", "improve yourself", "refine the shell", "cascade")):
        return PromptIntent("evolution", False, "medium", "self-improvement request")
    if re.match(r"^(show|run|open|check|view|inspect|brief)\b", lowered):
        return PromptIntent("command", True, "medium", "plain-language operator command")
    return PromptIntent("chat", False, "medium", "default conversational turn")


def plan_operator_command(request: OperatorCommandRequest) -> OperatorCommandPlan:
    """Create a dry-run plan and AgentOps-compatible packet draft."""

    prompt = request.prompt.strip()
    if not prompt:
        raise ValueError("prompt must not be empty")

    prompt_intent = resolve_prompt_intent(prompt)
    router = IntentRouter()
    decomposed = router.decompose(prompt)
    primary = decomposed.sub_tasks[0] if decomposed.sub_tasks else router.analyze(prompt)
    sub_tasks = [
        PlannedSubTask(
            task=item.task,
            skill=item.primary_skill or "general",
            complexity=item.complexity,
            risk_level=item.risk_level,
            recommended_agents=item.recommended_agents,
        )
        for item in decomposed.sub_tasks
    ]
    prescriptions = _load_prescriptions(prompt, request.knowledge_db_path)
    mission = _load_mission(request.mission_state_dir, request.mission_path)
    allowed_files, scope_confidence, requires_human_scope = _scope_for(request)
    packet = WorkPacketDraft(
        id=_packet_id(prompt),
        base_ref=request.base_ref,
        branch=request.branch,
        worktree=request.worktree,
        intent=prompt,
        allowed_files=allowed_files,
        forbidden_files=list(request.forbidden_files),
        gates=[dict(gate) for gate in request.gates],
        commit={"allowed": request.commit_allowed, "message": request.commit_message},
        approval={
            "before_commit": request.approval_before_commit,
            "before_merge": request.approval_before_merge,
        },
        requires_human_scope=requires_human_scope,
        scope_confidence=scope_confidence,
    )
    warnings = _plan_warnings(prompt_intent, packet, primary.risk_level)
    return OperatorCommandPlan(
        prompt_intent=prompt_intent,
        primary_skill=primary.primary_skill or "general",
        complexity=decomposed.estimated_complexity,
        risk_level=primary.risk_level,
        recommended_agents=decomposed.total_agents,
        sub_tasks=sub_tasks,
        prescriptions=prescriptions,
        mission=mission,
        work_packet=packet,
        coherence_delta=_coherence_delta_for(prompt, allowed_files, requires_human_scope),
        warnings=warnings,
        next_step=_next_plan_step(packet, warnings),
    )


def plan_to_dict(plan: OperatorCommandPlan) -> dict[str, Any]:
    """Return a JSON-ready plan payload."""

    return asdict(plan)


def work_packet_to_dict(draft: WorkPacketDraft) -> dict[str, Any]:
    """Return the AgentOps work-packet shape, excluding advisory metadata."""

    return {
        "id": draft.id,
        "base_ref": draft.base_ref,
        "branch": draft.branch,
        "worktree": draft.worktree,
        "intent": draft.intent,
        "allowed_files": draft.allowed_files,
        "forbidden_files": draft.forbidden_files,
        "gates": draft.gates,
        "commit": draft.commit,
        "approval": draft.approval,
    }


def review_agentops_reports(paths: Iterable[str | Path]) -> AgentOpsReview:
    """Read AgentOps report.json files or directories and recommend one next move."""

    report_paths = _find_agentops_reports(paths)
    summaries = [_summarize_report(path, _read_json(path)) for path in report_paths]
    return AgentOpsReview(
        reports_reviewed=len(summaries),
        summaries=summaries,
        next_recommendation=_recommend_from_reports(summaries),
    )


def record_human_yds_rating(
    *,
    ledger_path: str | Path,
    artifact: str,
    rating: str,
    source: str = "human",
    human_comment: str = "",
    context: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> HumanYDSRating:
    """Append one explicit human YDS rating to a JSONL ledger."""

    artifact_value = artifact.strip()
    rating_value = rating.strip()
    source_value = source.strip().lower()
    if not artifact_value:
        raise ValueError("artifact must not be empty")
    if not YDS_RE.match(rating_value):
        raise ValueError("rating must be a Yosemite-style value from 5.6 through 5.15")
    if source_value not in HUMAN_YDS_SOURCES:
        raise ValueError("authoritative YDS source must be human/operator/dhyana")

    fact = append_human_yds_rating(
        Path(ledger_path).expanduser(),
        artifact_uri=artifact_value,
        rating=rating_value,
        human_note=human_comment.strip() or "human rating recorded",
        operator_id=source_value,
        created_at=timestamp,
    )
    return HumanYDSRating(
        timestamp=fact.created_at or timestamp or utc_now_iso(),
        artifact=fact.artifact_uri,
        rating=fact.rating,
        source=fact.source,
        human_comment=fact.human_note,
        context=dict(context or {}),
    )


def evaluate_rust_readiness(signal: RustReadinessSignal) -> RustReadinessDecision:
    """Decide whether a component is ready for a future Rust extraction."""

    reasons: list[str] = []
    if not signal.boundary_stable:
        reasons.append("boundary is not stable")
    if not signal.deterministic:
        reasons.append("logic is not deterministic enough")
    if not signal.has_green_tests:
        reasons.append("green focused tests are missing")
    if not (signal.hot_path or signal.security_critical or signal.python_pain):
        reasons.append("no hot-path, security, or Python-pain driver")

    if reasons:
        return RustReadinessDecision(
            component=signal.component,
            decision="keep_python",
            reasons=reasons,
            next_step="stabilize the Python boundary and tests before considering Rust",
        )
    return RustReadinessDecision(
        component=signal.component,
        decision="rust_candidate",
        reasons=["deterministic stable boundary with tests and a concrete migration driver"],
        next_step="write a narrow FFI/CLI contract and keep Python as the orchestration layer",
    )


def _load_prescriptions(prompt: str, knowledge_db_path: str | None) -> list[dict[str, Any]]:
    if not knowledge_db_path:
        return []
    path = Path(knowledge_db_path).expanduser()
    if not path.exists():
        return []
    try:
        from dharma_swarm.knowledge_units import KnowledgeStore

        concepts = _concepts(prompt)
        with KnowledgeStore(str(path)) as store:
            return [
                {
                    "id": item.id,
                    "intent": item.intent,
                    "return_score": item.return_score,
                    "success_count": item.success_count,
                    "attempt_count": item.attempt_count,
                }
                for item in store.get_prescriptions_for_intent(prompt, concepts)
            ]
    except Exception:
        return []


def _load_mission(state_dir: str | None, mission_path: str | None) -> MissionAttachment:
    if not state_dir and not mission_path:
        return MissionAttachment(found=False)
    try:
        from dharma_swarm.mission_contract import load_active_mission_state

        artifact = load_active_mission_state(state_dir=state_dir, path=mission_path)
        if artifact is None:
            return MissionAttachment(found=False)
        state = artifact.state
        return MissionAttachment(
            found=True,
            source_kind=artifact.source_kind,
            source_path=artifact.source_path,
            mission_title=state.mission_title,
            status=state.status,
            blockers=list(state.blockers),
        )
    except Exception:
        return MissionAttachment(found=False)


def _scope_for(request: OperatorCommandRequest) -> tuple[list[str], str, bool]:
    if request.allowed_files:
        return list(request.allowed_files), "operator-provided", False
    lowered = request.prompt.lower()
    inferred: list[str] = []
    if any(term in lowered for term in ("command spine", "operator_core", "operator core")):
        inferred.extend(["dharma_swarm/operator_core/**", "tests/**", "docs/governance/**"])
    if any(term in lowered for term in ("agentops", "kaizen", "yds", "governance")):
        inferred.extend(["scripts/governance/**", "docs/governance/**", "tests/**"])
    if any(term in lowered for term in ("doc", "spec", "plan", "narrative")):
        inferred.append("docs/**")
    if any(term in lowered for term in ("test", "pytest", "regression")):
        inferred.append("tests/**")
    if inferred:
        return sorted(set(inferred)), "inferred-low", True
    return ["docs/**"], "fallback-low", True


def _plan_warnings(
    prompt_intent: PromptIntent,
    packet: WorkPacketDraft,
    risk_level: str,
) -> list[str]:
    warnings: list[str] = []
    if packet.requires_human_scope:
        warnings.append("allowed_files were inferred; human scope approval is required")
    if prompt_intent.kind in {"agent", "evolution"}:
        warnings.append(f"{prompt_intent.kind} request must remain approval-gated")
    if risk_level in {"high", "critical"}:
        warnings.append(f"router classified task risk as {risk_level}")
    if not packet.approval.get("before_commit", True):
        warnings.append("commit approval is disabled; use only for already-reviewed packets")
    return warnings


def _next_plan_step(packet: WorkPacketDraft, warnings: list[str]) -> str:
    if packet.requires_human_scope:
        return "tighten allowed_files, then run AgentOps dry-run inspection"
    if warnings:
        return "resolve plan warnings, then run AgentOps dry-run inspection"
    return "write the packet JSON and run AgentOps dry-run inspection"


def _coherence_delta_for(
    prompt: str,
    allowed_files: list[str],
    requires_human_scope: bool,
) -> CoherenceDelta:
    organ = _infer_organ_touched(prompt, allowed_files)
    if organ == "unknown":
        gap_closed = "operator must name the organ and declared-vs-actual gap before execution"
        drift = "unmapped organ can add drift because no OrganStateFact owns the change"
    elif requires_human_scope:
        gap_closed = f"candidate work for {organ}; scope is inferred and must be tightened"
        drift = "inferred allowed_files can widen the patch beyond the named organ"
    else:
        gap_closed = f"candidate work should close a named coherence gap for {organ}"
        drift = "low if changed files remain inside allowed_files and AgentOps reports clean"
    return CoherenceDelta(
        organ_touched=organ,
        gap_closed=gap_closed,
        proof_read="review AgentOps report, rebuild operating fact bundle, and read OrganStateFact",
        new_drift_risk=drift,
        human_approval_needed=True,
    )


def _infer_organ_touched(prompt: str, allowed_files: list[str]) -> str:
    haystack = " ".join([prompt, *allowed_files]).lower()
    organ_terms = (
        ("agentops", ("agentops", "agent ops", "run_agent_work_packet")),
        ("kaizen_review", ("kaizen", "review_agentops")),
        ("human_yds", ("yds", "human rating", "human_quality")),
        ("burn_cost", ("burn", "cost", "pricing", "spend")),
        ("revenue", ("revenue", "wedge", "customer", "pricing")),
        ("daily_operating_brief", ("daily_operating_brief", "daily brief", "operating brief")),
        ("command_spine", ("command_spine", "command spine", "operator_core", "operator core")),
        ("telic_value", ("telic", "valueevent", "contribution", "outcome")),
    )
    for organ, terms in organ_terms:
        if any(term in haystack for term in terms):
            return organ
    return "unknown"


def _packet_id(prompt: str) -> str:
    words = re.findall(r"[a-z0-9]+", prompt.lower())[:6]
    slug = "-".join(words) or "operator-command"
    return f"operator-command-{slug}"[:80]


def _concepts(text: str) -> list[str]:
    stop = {"the", "and", "for", "with", "that", "this", "into", "from", "what", "how"}
    return [word for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower()) if word not in stop][:12]


def _find_agentops_reports(paths: Iterable[str | Path]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_file() and path.name == "report.json":
            found.append(path)
        elif path.is_dir():
            found.extend(sorted(path.glob("**/report.json")))
    return sorted(set(found))


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"AgentOps report must be a JSON object: {path}")
    return data


def _summarize_report(path: Path, report: dict[str, Any]) -> AgentOpsReportSummary:
    gates = _gate_summary(report.get("gates"))
    scope = _scope_summary(report.get("scope"))
    commit = _commit_summary(report)
    approval = _approval_summary(report.get("approval"))
    waste = _waste_patterns(report, gates, scope, commit)
    return AgentOpsReportSummary(
        source_path=str(path),
        job_id=str(report.get("job_id") or "unknown"),
        status=str(report.get("status") or "unknown"),
        gates=gates,
        scope=scope,
        commit=commit,
        approval=approval,
        waste_patterns=waste,
    )


def _gate_summary(gates: Any) -> str:
    if not isinstance(gates, list) or not gates:
        return "unknown"
    failed = [gate for gate in gates if isinstance(gate, dict) and gate.get("passed") is False]
    unknown = [gate for gate in gates if not isinstance(gate, dict) or not isinstance(gate.get("passed"), bool)]
    if failed:
        return "some red"
    if unknown:
        return "unknown"
    return "all green"


def _scope_summary(scope: Any) -> str:
    if not isinstance(scope, dict):
        return "unknown"
    if scope.get("violations"):
        return "scope violation"
    if scope.get("passed") is True:
        return "scope clean"
    if scope.get("passed") is False:
        return "scope violation"
    return "unknown"


def _commit_summary(report: dict[str, Any]) -> str:
    if report.get("commit_hash"):
        return "commit created"
    decision = str(report.get("commit_decision") or "").lower()
    if "approval" in decision:
        return "blocked by approval"
    if decision:
        return "no commit"
    return "unknown"


def _approval_summary(approval: Any) -> str:
    if not isinstance(approval, dict):
        return "unknown"
    if approval.get("before_commit") or approval.get("before_merge"):
        return "human approval needed"
    return "not needed"


def _waste_patterns(report: dict[str, Any], gates: str, scope: str, commit: str) -> list[str]:
    patterns: set[str] = set()
    decision = str(report.get("commit_decision") or "").lower()
    changed = report.get("scope", {}).get("changed_files", []) if isinstance(report.get("scope"), dict) else []
    if "dirty" in decision:
        patterns.add("dirty worktree start")
    if gates == "some red":
        patterns.add("failed gate")
    if scope == "scope violation":
        patterns.add("out-of-scope files")
    if commit == "blocked by approval":
        patterns.add("approval blocked")
    if isinstance(changed, list) and not changed:
        patterns.add("no changed files")
    missing = {"job_id", "status", "gates", "scope", "approval", "commit_decision"} - set(report)
    if missing:
        patterns.add("missing report fields")
    return sorted(patterns)


def _recommend_from_reports(summaries: list[AgentOpsReportSummary]) -> str:
    if not summaries:
        return "run one bounded AgentOps packet and feed its report back into the spine"
    if any(summary.gates == "some red" for summary in summaries):
        return "fix the first failed gate before expanding scope"
    if any(summary.scope == "scope violation" for summary in summaries):
        return "repeat with narrower allowed_files and forbidden_files"
    if any(summary.commit == "blocked by approval" for summary in summaries):
        return "request human approval or keep the packet as a review artifact"
    if all(summary.gates == "all green" and summary.scope == "scope clean" for summary in summaries):
        return "promote the successful packet pattern into a playbook candidate"
    return "inspect missing report fields before trusting the next recommendation"


__all__ = [
    "AgentOpsReportSummary",
    "AgentOpsReview",
    "CoherenceDelta",
    "HumanYDSRating",
    "MissionAttachment",
    "OperatorCommandPlan",
    "OperatorCommandRequest",
    "PlannedSubTask",
    "PromptIntent",
    "RustReadinessDecision",
    "RustReadinessSignal",
    "WorkPacketDraft",
    "evaluate_rust_readiness",
    "plan_operator_command",
    "plan_to_dict",
    "record_human_yds_rating",
    "resolve_prompt_intent",
    "review_agentops_reports",
    "work_packet_to_dict",
]
