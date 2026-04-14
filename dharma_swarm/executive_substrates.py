"""Executive substrate readers for role ecology and memory pressure.

These helpers build a compact, operational summary of the living swarm
without owning dispatch. They exist to give the Shakti executive a stable
view of:

1. which seeded roles and named agents actually exist,
2. which of them are active vs. mostly nominal,
3. where the memory system is carrying unresolved loops, promises, and churn.

The goal is not philosophical description. The goal is a small amount of
runtime truth that a strategic allocator can consume directly.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import ROLE_BRIEFINGS
from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.startup_crew import CYBERNETICS_CREW, DEFAULT_CREW


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(raw: Any) -> datetime | None:
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open() as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _snippet(path: Path, max_chars: int = 600) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    return text[:max_chars].strip()


def _infer_agent_role(name: str) -> str:
    lowered = (name or "").strip().lower()
    if not lowered:
        return ""
    normalized = lowered.replace("_", "-")
    if normalized.startswith("cyber-"):
        suffix = normalized.removeprefix("cyber-")
        if "glm" in suffix:
            return AgentRole.RESEARCHER.value
        if "kimi" in suffix:
            return AgentRole.CARTOGRAPHER.value
        if "codex" in suffix:
            return AgentRole.SURGEON.value
        if "opus" in suffix:
            return AgentRole.ARCHITECT.value
    if normalized in ROLE_BRIEFINGS:
        return normalized
    if normalized in {"builder", "general"}:
        return AgentRole.GENERAL.value
    if normalized in {"researcher", "jagat-kalyan", "jagat_kalyan"}:
        return AgentRole.RESEARCHER.value
    return ""


@dataclass(slots=True)
class AgentPresence:
    name: str
    role: str
    provider: str = ""
    model: str = ""
    seeded: bool = False
    distill_exists: bool = False
    cost_calls_72h: int = 0
    stigmergy_marks_72h: int = 0
    last_seen_ts: str = ""
    active_72h: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RoleEcologySnapshot:
    generated_at: str
    seeded_agents: int
    active_agents_72h: int
    nominal_only_agents: list[str]
    overloaded_agents: list[str]
    underexpressed_roles: list[str]
    agents: list[AgentPresence]


@dataclass(slots=True)
class MemoryPressureSnapshot:
    generated_at: str
    distilled_roles: list[str]
    unresolved_promises: list[str]
    repeated_loop_signatures: list[str]
    top_shared_artifacts: list[str]
    top_stigmergy_hotspots: list[str]
    memory_health: dict[str, Any]


def build_role_ecology_snapshot(state_dir: Path | None = None) -> RoleEcologySnapshot:
    base = state_dir or (Path.home() / ".dharma")
    now = _utc_now()
    cutoff = now - timedelta(hours=72)

    seeded: dict[str, AgentPresence] = {}
    for spec in [*DEFAULT_CREW, *CYBERNETICS_CREW]:
        name = str(spec.get("name", "")).strip()
        if not name:
            continue
        provider = spec.get("provider")
        role = spec.get("role")
        seeded[name] = AgentPresence(
            name=name,
            role=getattr(role, "value", str(role or "")),
            provider=getattr(provider, "value", str(provider or "")),
            model=str(spec.get("model", "")),
            seeded=True,
        )

    for role_name in ROLE_BRIEFINGS:
        seeded.setdefault(
            role_name,
            AgentPresence(name=role_name, role=role_name, seeded=True),
        )

    cost_rows = _load_jsonl(base / "cost_log.jsonl")
    mark_rows = _load_jsonl(base / "stigmergy" / "marks.jsonl")
    distilled_dir = base / "context" / "distilled"
    for md in distilled_dir.glob("*_distilled.md"):
        role_name = md.stem.removesuffix("_distilled")
        seeded.setdefault(
            role_name,
            AgentPresence(name=role_name, role=_infer_agent_role(role_name), seeded=False),
        )
        seeded[role_name].distill_exists = True

    for row in cost_rows:
        dt = _parse_timestamp(row.get("timestamp"))
        if dt is None or dt < cutoff:
            continue
        name = str(row.get("agent_name") or "").strip()
        if not name:
            continue
        agent = seeded.setdefault(
            name,
            AgentPresence(name=name, role=_infer_agent_role(name), seeded=False),
        )
        agent.cost_calls_72h += 1
        agent.active_72h = True
        if dt.isoformat() > agent.last_seen_ts:
            agent.last_seen_ts = dt.isoformat()

    for row in mark_rows:
        dt = _parse_timestamp(row.get("timestamp"))
        if dt is None or dt < cutoff:
            continue
        name = str(row.get("agent") or "").strip()
        if not name:
            continue
        agent = seeded.setdefault(
            name,
            AgentPresence(name=name, role=_infer_agent_role(name), seeded=False),
        )
        agent.stigmergy_marks_72h += 1
        agent.active_72h = True
        if dt.isoformat() > agent.last_seen_ts:
            agent.last_seen_ts = dt.isoformat()

    agents = sorted(
        seeded.values(),
        key=lambda a: (a.active_72h, a.cost_calls_72h + a.stigmergy_marks_72h, a.name),
        reverse=True,
    )

    nominal_only = [
        a.name for a in agents
        if a.seeded and not a.active_72h and not a.distill_exists
    ]
    overloaded = [
        a.name for a in agents
        if a.cost_calls_72h >= 80 or a.stigmergy_marks_72h >= 120
    ]
    expressed_roles = {
        a.role for a in agents
        if a.role and (a.cost_calls_72h > 0 or a.stigmergy_marks_72h > 0)
    }
    underexpressed = sorted(
        role for role in ROLE_BRIEFINGS
        if role not in expressed_roles
    )

    return RoleEcologySnapshot(
        generated_at=now.isoformat(),
        seeded_agents=sum(1 for a in agents if a.seeded),
        active_agents_72h=sum(1 for a in agents if a.active_72h),
        nominal_only_agents=nominal_only,
        overloaded_agents=overloaded,
        underexpressed_roles=underexpressed,
        agents=agents,
    )


_LOOP_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"synthesize_disagreement_eval_probe_task", "eval_probe_loop"),
    (r"synthesize_disagreement_follow_up_latent", "latent_followup_loop"),
    (r"synthesize_disagreement_reopen_latent_br", "latent_reopen_loop"),
    (r"validate_and_reroute_", "reroute_loop"),
)


def build_memory_pressure_snapshot(state_dir: Path | None = None) -> MemoryPressureSnapshot:
    base = state_dir or (Path.home() / ".dharma")
    now = _utc_now()

    distilled_dir = base / "context" / "distilled"
    shared_dir = base / "shared"
    artifacts_dir = base / "artifacts"
    cron_dir = base / "cron_logs"
    stigmergy_path = base / "stigmergy" / "marks.jsonl"
    vectors_db = base / "vectors.db"

    distilled_roles = sorted(
        p.stem.removesuffix("_distilled")
        for p in distilled_dir.glob("*_distilled.md")
    )

    heartbeat_logs = sorted(cron_dir.glob("*heartbeat*.md"))
    unresolved_promises: list[str] = []
    if heartbeat_logs:
        latest = heartbeat_logs[-1]
        text = _snippet(latest, max_chars=4000)
        for line in text.splitlines():
            if "not started" in line or "blocked" in line:
                unresolved_promises.append(line.strip(" -"))

    loop_counter: Counter[str] = Counter()
    top_shared = sorted(shared_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:120]
    top_shared_artifacts: list[str] = []
    for p in top_shared[:12]:
        top_shared_artifacts.append(p.name)
        lowered = p.name.lower()
        for pattern, label in _LOOP_PATTERNS:
            if re.search(pattern, lowered):
                loop_counter[label] += 1

    hotspot_counter: Counter[str] = Counter()
    for row in _load_jsonl(stigmergy_path):
        ts = _parse_timestamp(row.get("timestamp"))
        if ts is None or ts < (now - timedelta(hours=72)):
            continue
        file_path = str(row.get("file_path") or "").strip()
        if file_path:
            hotspot_counter[file_path] += 1

    top_stigmergy_hotspots = [
        f"{path} ({count})" for path, count in hotspot_counter.most_common(8)
    ]

    research_artifacts = sorted(
        artifacts_dir.rglob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:20]
    if research_artifacts:
        top_shared_artifacts.extend(f"artifact:{p.name}" for p in research_artifacts[:6])

    memory_health = {
        "vectors_db_exists": vectors_db.exists(),
        "vectors_db_mb": round(vectors_db.stat().st_size / (1024 * 1024), 1) if vectors_db.exists() else 0.0,
        "distilled_role_count": len(distilled_roles),
        "shared_recent_count": len(top_shared),
        "research_artifact_count": len(research_artifacts),
    }

    repeated = [
        f"{label}:{count}" for label, count in loop_counter.most_common()
        if count >= 3
    ]

    return MemoryPressureSnapshot(
        generated_at=now.isoformat(),
        distilled_roles=distilled_roles,
        unresolved_promises=unresolved_promises[:12],
        repeated_loop_signatures=repeated,
        top_shared_artifacts=top_shared_artifacts[:18],
        top_stigmergy_hotspots=top_stigmergy_hotspots,
        memory_health=memory_health,
    )

