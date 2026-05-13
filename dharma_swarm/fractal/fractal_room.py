"""Fractal room schema v0.

A FractalRoom is a causal membrane around existing Dharma Swarm organs. It is
not an executor, scheduler, ontology writer, dashboard surface, or autonomy
loop. The room describes purpose, law, economy, memory, pulse, and lifecycle so
existing systems can scope their facts with a shared room_id/cell_id.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any


ROOM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")
YDS_RE = re.compile(r"^5\.(?:6|7|8|9|10|11|12|13|14|15)(?:[abcd])?$")

ROOM_KINDS = {
    "root",
    "core_ops",
    "agentops",
    "governance",
    "research",
    "daily_operating",
    "venture_cell",
    "product",
    "revenue",
}
ROOM_STATUSES = {"proposed", "active", "paused", "archived", "spun_out", "killed"}
APPROVAL_ACTIONS = {
    "commit",
    "merge",
    "push",
    "change_gates",
    "change_playbooks",
    "assign_yds",
    "spend_budget",
    "spawn_child_room",
    "kill_room",
    "spin_out",
}
DEFAULT_AGENTOPS_GATES = ("compile", "diff-check", "focused-tests")


@dataclass(frozen=True)
class RoomModuleBinding:
    """Repo module binding for one layer of the room membrane."""

    layer: str
    owns: str
    modules: tuple[str, ...]
    room_contract: str


MODULE_BINDINGS: tuple[RoomModuleBinding, ...] = (
    RoomModuleBinding(
        layer="telos",
        owns="identity, meta-principles, and S5 constraints",
        modules=("dharma_swarm/dharma_kernel.py", "dharma_swarm/telos_gates.py"),
        room_contract="Room purpose and law must remain compatible with the kernel and gates.",
    ),
    RoomModuleBinding(
        layer="ontology",
        owns="VentureCell, ValueEvent, Contribution, and cell_id truth",
        modules=("dharma_swarm/ontology.py", "dharma_swarm/telic_seam.py"),
        room_contract="Room identity maps to VentureCell/cell_id; value facts stay in ontology.",
    ),
    RoomModuleBinding(
        layer="operation",
        owns="bounded work execution",
        modules=(
            "dharma_swarm/task_board.py",
            "dharma_swarm/agent_runner.py",
            "scripts/governance/run_agent_work_packet.py",
        ),
        room_contract="Rooms project scoped work packets; executors remain separate organs.",
    ),
    RoomModuleBinding(
        layer="coordination",
        owns="signals, stigmergy, and local coordination",
        modules=("dharma_swarm/signal_bus.py", "dharma_swarm/stigmergy.py"),
        room_contract="Room memory namespaces and channels scope coordination facts.",
    ),
    RoomModuleBinding(
        layer="economy",
        owns="budget, burn, revenue, and resource accounting",
        modules=(
            "dharma_swarm/economic_engine.py",
            "dharma_swarm/economic_spine.py",
            "dharma_swarm/cost_tracker.py",
        ),
        room_contract="Room economy declares budget and kill/spinout evidence; accounting organs own numbers.",
    ),
    RoomModuleBinding(
        layer="learning",
        owns="multi-run improvement and operating briefs",
        modules=(
            "dharma_swarm/insight_brief.py",
            "dharma_swarm/daily_operating_brief.py",
            "scripts/governance/kaizen_review_from_agentops.py",
        ),
        room_contract="Room pulse consumes reports and emits one conservative next move.",
    ),
    RoomModuleBinding(
        layer="human-quality",
        owns="human-authoritative YDS judgment",
        modules=(
            "dharma_swarm/operator_core/command_spine.py",
            "dharma_swarm/operator_core/operating_facts.py",
        ),
        room_contract="AI may prompt for YDS but cannot assign authoritative ratings.",
    ),
)


@dataclass(frozen=True)
class RoomIdentity:
    """Stable identity for a recursive room/cell."""

    id: str
    kind: str
    purpose: str
    parent_id: str = ""
    status: str = "proposed"
    operator: str = "dhyana"
    ontology_type: str = "VentureCell"


@dataclass(frozen=True)
class RoomLaw:
    """Explicit local law and capability membrane."""

    allowed_work: tuple[str, ...] = ()
    forbidden_work: tuple[str, ...] = ()
    allowed_files: tuple[str, ...] = ()
    forbidden_files: tuple[str, ...] = ()
    gates: tuple[str, ...] = DEFAULT_AGENTOPS_GATES
    approval_required_for: tuple[str, ...] = ("commit", "merge", "assign_yds")


@dataclass(frozen=True)
class RoomEconomy:
    """Resource and value hypothesis for a room."""

    budget_tokens: int | None = None
    current_burn_tokens: int = 0
    revenue_target_usd: float | None = None
    value_hypothesis: str = ""
    self_funding_hypothesis: str = ""
    kill_conditions: tuple[str, ...] = ()
    spinout_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoomMemory:
    """Where the room leaves evidence and learns."""

    memory_namespace: str = ""
    report_paths: tuple[str, ...] = ()
    witness_log_paths: tuple[str, ...] = ()
    knowledge_artifact_refs: tuple[str, ...] = ()
    stigmergy_channels: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoomPulse:
    """Latest feedback signals for a room."""

    last_brief_date: str = ""
    next_packet_recommendation: str = ""
    open_risks: tuple[str, ...] = ()
    kaizen_review_paths: tuple[str, ...] = ()
    human_yds_rating_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoomLifecycle:
    """Lifecycle and archive policy for a room."""

    created_at: str = ""
    updated_at: str = ""
    status_reason: str = ""
    archive_policy: str = "preserve reports, recycle agents and remaining budget to parent"


@dataclass(frozen=True)
class RoomValidation:
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class RoomWorkPacketScope:
    """Room projection into the existing AgentOps work-packet shape."""

    job_id: str
    room_id: str
    intent: str
    allowed_files: tuple[str, ...]
    forbidden_files: tuple[str, ...]
    gates: tuple[dict[str, str], ...]
    approval: dict[str, bool]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FractalRoom:
    """Recursive room membrane for repo-native AgentOps, Kaizen, and value facts."""

    identity: RoomIdentity
    law: RoomLaw = field(default_factory=RoomLaw)
    economy: RoomEconomy = field(default_factory=RoomEconomy)
    memory: RoomMemory = field(default_factory=RoomMemory)
    pulse: RoomPulse = field(default_factory=RoomPulse)
    lifecycle: RoomLifecycle = field(default_factory=RoomLifecycle)
    child_room_ids: tuple[str, ...] = ()

    @property
    def room_id(self) -> str:
        return self.identity.id

    @property
    def cell_id(self) -> str:
        return self.identity.id

    def validate(self) -> RoomValidation:
        return validate_room(self)

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))

    def to_agentops_scope(
        self,
        intent: str,
        *,
        job_id: str = "",
        include_metadata: bool = True,
    ) -> RoomWorkPacketScope:
        """Project this room into the existing AgentOps scope contract."""

        clean_intent = intent.strip()
        if not clean_intent:
            raise ValueError("intent must not be empty")
        clean_job_id = job_id.strip() or f"room-{self.room_id}-{_slug(clean_intent)}"
        approval = {
            "before_commit": "commit" in self.law.approval_required_for,
            "before_merge": "merge" in self.law.approval_required_for,
        }
        metadata = {
            "room_id": self.room_id,
            "cell_id": self.cell_id,
            "room_kind": self.identity.kind,
            "purpose": self.identity.purpose,
        }
        return RoomWorkPacketScope(
            job_id=clean_job_id[:96],
            room_id=self.room_id,
            intent=clean_intent,
            allowed_files=self.law.allowed_files,
            forbidden_files=self.law.forbidden_files,
            gates=tuple({"name": gate, "command": gate} for gate in self.law.gates),
            approval=approval,
            metadata=metadata if include_metadata else {},
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_human_yds_rating(rating: str) -> str:
    """Validate the repo's human-only Yosemite-style quality scale."""

    clean = rating.strip()
    if not YDS_RE.fullmatch(clean):
        raise ValueError("YDS rating must be Yosemite-style 5.6 through 5.15, optionally with a-d suffix")
    return clean


def validate_room(room: FractalRoom) -> RoomValidation:
    errors: list[str] = []
    warnings: list[str] = []
    identity = room.identity

    if not ROOM_ID_RE.fullmatch(identity.id):
        errors.append("identity.id must be a stable slug: [a-z0-9][a-z0-9_-]{1,79}")
    if identity.kind not in ROOM_KINDS:
        errors.append(f"identity.kind must be one of {sorted(ROOM_KINDS)}")
    if identity.status not in ROOM_STATUSES:
        errors.append(f"identity.status must be one of {sorted(ROOM_STATUSES)}")
    if not identity.purpose.strip():
        errors.append("identity.purpose must not be empty")
    if identity.kind == "root" and identity.parent_id:
        errors.append("root room must not have parent_id")

    _validate_law(room, errors, warnings)
    _validate_economy(room, errors, warnings)
    _validate_memory_and_pulse(room, warnings)
    _validate_lifecycle(room, warnings)

    return RoomValidation(errors=tuple(errors), warnings=tuple(warnings))


def room_from_dict(payload: dict[str, Any]) -> FractalRoom:
    """Load a room from a JSON-compatible dictionary."""

    if not isinstance(payload, dict):
        raise ValueError("room payload must be a JSON object")
    return FractalRoom(
        identity=RoomIdentity(**_dict(payload.get("identity"))),
        law=RoomLaw(**_room_law_payload(payload.get("law"))),
        economy=RoomEconomy(**_room_economy_payload(payload.get("economy"))),
        memory=RoomMemory(**_room_memory_payload(payload.get("memory"))),
        pulse=RoomPulse(**_room_pulse_payload(payload.get("pulse"))),
        lifecycle=RoomLifecycle(**_room_lifecycle_payload(payload.get("lifecycle"))),
        child_room_ids=_strings(payload.get("child_room_ids")),
    )


def room_module_bindings() -> tuple[RoomModuleBinding, ...]:
    """Return the repo organ map a room is allowed to reference conceptually."""

    return MODULE_BINDINGS


def build_core_ops_room() -> FractalRoom:
    """Canonical root/core room: preserve the organism before expanding it."""

    return FractalRoom(
        identity=RoomIdentity(
            id="dharma-swarm-core",
            kind="root",
            purpose="Preserve Dharma Swarm identity, governance, execution integrity, and learning capacity.",
            status="active",
        ),
        law=RoomLaw(
            allowed_work=(
                "governance hardening",
                "operator clarity",
                "internal reliability",
                "evidence-preserving refactors",
            ),
            forbidden_work=(
                "dashboard expansion without operating evidence",
                "unbounded autonomy",
                "AI-assigned authoritative YDS",
            ),
            allowed_files=("dharma_swarm/**", "scripts/governance/**", "docs/governance/**", "tests/**"),
            forbidden_files=("api/**", "dashboard/**"),
            approval_required_for=("commit", "merge", "assign_yds", "change_gates", "spawn_child_room"),
        ),
        economy=RoomEconomy(
            budget_tokens=0,
            value_hypothesis="A trusted internal operating substrate increases all later revenue and service work.",
            kill_conditions=("governance theater increases faster than verified operating facts",),
        ),
        memory=RoomMemory(
            memory_namespace="rooms/dharma-swarm-core",
            report_paths=("reports/agentops", "reports/kaizen"),
            stigmergy_channels=("governance", "operator"),
        ),
        pulse=RoomPulse(next_packet_recommendation="ship one narrow green operating packet"),
    )


def build_agentops_room(parent_id: str = "dharma-swarm-core") -> FractalRoom:
    """Room for safe, repeatable repo-agent work packets."""

    return FractalRoom(
        identity=RoomIdentity(
            id="agentops",
            kind="agentops",
            parent_id=parent_id,
            purpose="Turn fuzzy operator work into scoped AgentOps packets with gates, reports, and review.",
            status="active",
        ),
        law=RoomLaw(
            allowed_work=("work packet drafting", "gate execution", "scope reporting", "KaizenReview ingestion"),
            forbidden_work=("auto-merge", "unapproved scope expansion", "live swarm/autonomy execution"),
            allowed_files=("scripts/governance/**", "docs/governance/**", "tests/**"),
            forbidden_files=("api/**", "dashboard/**", "dharma_swarm/dharma_kernel.py", "dharma_swarm/telos_gates.py"),
            approval_required_for=("commit", "merge", "change_playbooks", "assign_yds"),
        ),
        economy=RoomEconomy(
            value_hypothesis="Less clipboard orchestration and fewer scope errors create compounding operator leverage.",
            kill_conditions=("AgentOps reports stop producing actionable KaizenReview recommendations",),
        ),
        memory=RoomMemory(
            memory_namespace="rooms/agentops",
            report_paths=("reports/agentops", "reports/kaizen"),
            stigmergy_channels=("agentops", "governance"),
        ),
        pulse=RoomPulse(next_packet_recommendation="run one bounded packet and review the report"),
    )


def build_revenue_wedge_room(
    *,
    room_id: str = "revenue-wedge",
    parent_id: str = "dharma-swarm-core",
    purpose: str = "Prove one self-funding Dharma Swarm wedge under explicit budget and kill conditions.",
) -> FractalRoom:
    """Room for a real customer/value proof, not general product theater."""

    return FractalRoom(
        identity=RoomIdentity(
            id=room_id,
            kind="venture_cell",
            parent_id=parent_id,
            purpose=purpose,
            status="proposed",
        ),
        law=RoomLaw(
            allowed_work=("customer discovery", "one-day proof", "pricing test", "evidence report"),
            forbidden_work=("brand expansion before proof", "dashboard build before customer signal"),
            allowed_files=("docs/**", "scripts/governance/**", "tests/**"),
            forbidden_files=("api/**", "dashboard/**"),
            approval_required_for=("commit", "merge", "spend_budget", "spin_out", "kill_room", "assign_yds"),
        ),
        economy=RoomEconomy(
            budget_tokens=100000,
            revenue_target_usd=100.0,
            value_hypothesis="A paid self-X-ray or Daily Operating Brief diagnostic can fund the next internal loop.",
            self_funding_hypothesis="One human buyer pays for a report that Dharma Swarm already uses internally.",
            kill_conditions=("no buyer or concrete external user after seven focused days",),
            spinout_conditions=("repeatable paid diagnostic with positive human YDS evidence",),
        ),
        memory=RoomMemory(
            memory_namespace=f"rooms/{room_id}",
            report_paths=("reports/agentops", "reports/kaizen"),
            stigmergy_channels=("revenue", "customer-discovery"),
        ),
        pulse=RoomPulse(next_packet_recommendation="draft the smallest paid diagnostic offer and falsification test"),
    )


def work_packet_scope_to_dict(scope: RoomWorkPacketScope) -> dict[str, Any]:
    return _json_ready(asdict(scope))


def _validate_law(room: FractalRoom, errors: list[str], warnings: list[str]) -> None:
    law = room.law
    unknown_approvals = sorted(set(law.approval_required_for) - APPROVAL_ACTIONS)
    if unknown_approvals:
        errors.append(f"law.approval_required_for has unknown action(s): {unknown_approvals}")
    if room.identity.status == "active":
        if not law.gates:
            errors.append("active room must declare at least one gate")
        if not law.forbidden_work:
            warnings.append("active room has no forbidden_work; autonomy boundary is too vague")
        if not law.approval_required_for:
            warnings.append("active room has no human approval requirements")
    if not law.allowed_work:
        warnings.append("law.allowed_work is empty; operators cannot tell what the room is for")
    if not law.allowed_files:
        warnings.append("law.allowed_files is empty; AgentOps projection will not constrain repo scope")


def _validate_economy(room: FractalRoom, errors: list[str], warnings: list[str]) -> None:
    economy = room.economy
    if economy.budget_tokens is not None and economy.budget_tokens < 0:
        errors.append("economy.budget_tokens must be non-negative")
    if economy.current_burn_tokens < 0:
        errors.append("economy.current_burn_tokens must be non-negative")
    if economy.revenue_target_usd is not None and economy.revenue_target_usd < 0:
        errors.append("economy.revenue_target_usd must be non-negative")
    if (
        economy.budget_tokens is not None
        and economy.budget_tokens > 0
        and economy.current_burn_tokens > economy.budget_tokens
    ):
        warnings.append("economy.current_burn_tokens exceeds budget_tokens")
    if room.identity.kind in {"venture_cell", "revenue", "product"}:
        if not economy.value_hypothesis.strip():
            errors.append("venture/product/revenue rooms require economy.value_hypothesis")
        if not economy.kill_conditions:
            errors.append("venture/product/revenue rooms require kill_conditions")
        if economy.revenue_target_usd is None and not economy.self_funding_hypothesis.strip():
            warnings.append("venture/product/revenue room has no revenue target or self_funding_hypothesis")


def _validate_memory_and_pulse(room: FractalRoom, warnings: list[str]) -> None:
    memory = room.memory
    pulse = room.pulse
    if not memory.memory_namespace:
        warnings.append("memory.memory_namespace is empty; room facts will be hard to query")
    if not (memory.report_paths or memory.knowledge_artifact_refs or pulse.kaizen_review_paths):
        warnings.append("room has no report, artifact, or KaizenReview path; learning loop is weak")
    if not pulse.next_packet_recommendation and room.identity.status in {"active", "proposed"}:
        warnings.append("pulse.next_packet_recommendation is empty; no next action is encoded")


def _validate_lifecycle(room: FractalRoom, warnings: list[str]) -> None:
    if not room.lifecycle.archive_policy:
        warnings.append("lifecycle.archive_policy is empty; dissolution recycling is unspecified")
    if room.identity.status in {"archived", "killed", "spun_out"} and not room.lifecycle.status_reason:
        warnings.append("terminal room status should include lifecycle.status_reason")


def _room_law_payload(raw: Any) -> dict[str, Any]:
    data = _dict(raw)
    return {
        "allowed_work": _strings(data.get("allowed_work")),
        "forbidden_work": _strings(data.get("forbidden_work")),
        "allowed_files": _strings(data.get("allowed_files")),
        "forbidden_files": _strings(data.get("forbidden_files")),
        "gates": _strings(data.get("gates")) or DEFAULT_AGENTOPS_GATES,
        "approval_required_for": _strings(data.get("approval_required_for")) or ("commit", "merge", "assign_yds"),
    }


def _room_economy_payload(raw: Any) -> dict[str, Any]:
    data = _dict(raw)
    return {
        "budget_tokens": _optional_int(data.get("budget_tokens")),
        "current_burn_tokens": _int(data.get("current_burn_tokens")),
        "revenue_target_usd": _optional_float(data.get("revenue_target_usd")),
        "value_hypothesis": _string(data.get("value_hypothesis")),
        "self_funding_hypothesis": _string(data.get("self_funding_hypothesis")),
        "kill_conditions": _strings(data.get("kill_conditions")),
        "spinout_conditions": _strings(data.get("spinout_conditions")),
    }


def _room_memory_payload(raw: Any) -> dict[str, Any]:
    data = _dict(raw)
    return {
        "memory_namespace": _string(data.get("memory_namespace")),
        "report_paths": _strings(data.get("report_paths")),
        "witness_log_paths": _strings(data.get("witness_log_paths")),
        "knowledge_artifact_refs": _strings(data.get("knowledge_artifact_refs")),
        "stigmergy_channels": _strings(data.get("stigmergy_channels")),
    }


def _room_pulse_payload(raw: Any) -> dict[str, Any]:
    data = _dict(raw)
    return {
        "last_brief_date": _string(data.get("last_brief_date")),
        "next_packet_recommendation": _string(data.get("next_packet_recommendation")),
        "open_risks": _strings(data.get("open_risks")),
        "kaizen_review_paths": _strings(data.get("kaizen_review_paths")),
        "human_yds_rating_refs": _strings(data.get("human_yds_rating_refs")),
    }


def _room_lifecycle_payload(raw: Any) -> dict[str, Any]:
    data = _dict(raw)
    return {
        "created_at": _string(data.get("created_at")),
        "updated_at": _string(data.get("updated_at")),
        "status_reason": _string(data.get("status_reason")),
        "archive_policy": _string(data.get("archive_policy"))
        or "preserve reports, recycle agents and remaining budget to parent",
    }


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _string(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return _int(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())[:8]
    return "-".join(words) or "work-packet"


__all__ = [
    "FractalRoom",
    "MODULE_BINDINGS",
    "RoomEconomy",
    "RoomIdentity",
    "RoomLaw",
    "RoomLifecycle",
    "RoomMemory",
    "RoomModuleBinding",
    "RoomPulse",
    "RoomValidation",
    "RoomWorkPacketScope",
    "build_agentops_room",
    "build_core_ops_room",
    "build_revenue_wedge_room",
    "room_from_dict",
    "room_module_bindings",
    "utc_now_iso",
    "validate_human_yds_rating",
    "validate_room",
    "work_packet_scope_to_dict",
]
