"""Active track portfolio projection for the human cockpit.

This module projects durable meta-build tracks into a read-only cockpit model.
It does not create a new authority store; it joins ACTIVE_TRACK.yaml, the
portfolio report, git history, and selected report lines for display.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


TARGET_TRACK_SLOTS: list[dict[str, Any]] = [
    {
        "id": "spine-runtime-truth",
        "title": "Spine Runtime Truth",
        "theme": "Execution truth spine: runtime packets, receipts, invoke path, live process honesty, and loop-closure proof.",
        "declared_track_ids": [
            "runtime-truth-reconciliation-2026-06",
            "runtime-truth-spine-adoption-2026-06",
            "loop-closure-2026-06",
        ],
        "aliases": ["runtime truth", "spine", "receipt", "loop-closure", "spine-adoption"],
        "surfaces": [
            "dharma_swarm/operator_core/**",
            "dharma_swarm/spine/**",
            "dharma_swarm/runtime_state.py",
            "scripts/governance/agent_onboard.py",
            "docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md",
        ],
        "subtracks": [
            "RuntimeTruthPacket contract",
            "receipt equivalence and projection",
            "default invoke_agent path",
            "live process and bridge truth",
            "loop closure proof",
        ],
    },
    {
        "id": "a2a-lattice-shared-state",
        "title": "A2A Lattice & Shared State",
        "theme": "Agent-to-agent lattice: NATS transport, inbox bridges, protocol mapping, shared state graph, and reply receipts.",
        "declared_track_ids": [
            "runtime-truth-nats-2026-06",
            "a2a-cloud-agent-bridge-2026-06",
        ],
        "aliases": ["a2a", "nats", "jetstream", "lattice", "inbox", "domain reply", "runtime-truth-nats"],
        "surfaces": [
            "dharma_swarm/a2a/**",
            "scripts/runtime/a2a_send.py",
            "reports/a2a/**",
            "tests/test_nats_transport.py",
            "tests/test_a2a_send.py",
        ],
        "subtracks": [
            "A2A protocol/server",
            "NATS JetStream substrate",
            "inbox bridge receipts",
            "domain reply worker",
            "shared state graph mapping",
        ],
    },
    {
        "id": "memory-kernel-orientation-graph",
        "title": "Memory Kernel & Orientation Graph",
        "theme": "Durable memory, orientation graph, retrieval, promotion, and first-token context continuity.",
        "declared_track_ids": ["orientation-graph-2026-06"],
        "aliases": ["memory", "memorykernel", "knowledgeops", "orientation graph", "context"],
        "surfaces": [
            "dharma_swarm/operator_core/control_surface_memory.py",
            "reports/swarm_genome/2026-06-11/agent_3_research_chetana.md",
            "docs/reports/DGC_MEMORY_PALACE_EXECUTION_ROADMAP_2026-03-09.md",
        ],
        "subtracks": [
            "memory readiness",
            "orientation graph",
            "KnowledgeOps bridge",
            "context canary",
            "promotion policy",
        ],
    },
    {
        "id": "operator-command-center",
        "title": "Operator Command Center",
        "theme": "Human front door: /dashboard/cockpit, active-track board, Needs John queue, runtime rails, and terminal/TUI continuity.",
        "declared_track_ids": ["helm-worldclass-terminal-2026-06"],
        "aliases": ["cockpit", "control surface", "dashboard", "tui", "terminal", "helm", "tmux"],
        "surfaces": [
            "dashboard/src/app/dashboard/cockpit/page.tsx",
            "dashboard/src/app/dashboard/control-surface/page.tsx",
            "dashboard/src/components/cockpit/**",
            "terminal/**",
            "dharma_swarm/terminal_bridge.py",
        ],
        "subtracks": [
            "cockpit active-track portfolio",
            "Needs John queue",
            "runtime rail and live health",
            "Bun terminal surface",
            "tmux bridge discipline",
        ],
    },
    {
        "id": "holon-agent-identity",
        "title": "Holon & Agent Identity System",
        "theme": "Persistent agent identities: composer holons, admission, name drift control, wake proof, and guarded action boundaries.",
        "declared_track_ids": [
            "composer-holon-spine-longrun-2026-06",
            "agent-admission-semantic-commons-2026-06",
        ],
        "aliases": ["holon", "sovereign agent", "composer", "agent admission", "semantic commons", "fable_composer", "codex_composer"],
        "surfaces": [
            "dharma_swarm/holon_runtime.py",
            "docs/sovereign_holons/**",
            "reports/sovereign_holons/**",
            "docs/ops/AGENT_ADMISSION.md",
            "docs/ontology/**",
        ],
        "subtracks": [
            "composer identity continuity",
            "agent admission path",
            "semantic commons and aliases",
            "wake/chat proof",
            "guarded action readiness",
        ],
    },
    {
        "id": "agentops-build-factory",
        "title": "AgentOps Build Factory",
        "theme": "Work-packet factory: Forge Reality Arena, Hydra cycles, scorecards, verifier artifacts, and human-review transfer gates.",
        "declared_track_ids": [],
        "aliases": ["forge", "hydra", "reality arena", "agentops", "work packet", "build factory", "verifier"],
        "surfaces": [
            "reports/agentops/work_packets/**",
            "reports/forge/**",
            "scripts/runtime/forge_hydra_status.py",
            "tests/test_forge_hydra_status.py",
        ],
        "subtracks": [
            "Forge Reality Arena",
            "Hydra cycle status",
            "AgentOps work packets",
            "verifier-backed scorecards",
            "human-review transfer gates",
        ],
    },
    {
        "id": "revenue-external-humans",
        "title": "Revenue & External Humans Served",
        "theme": "Higher revenue track: first paid external human outcome, RevenueSpine, RevenueScout, CashClaw, service wedge, and approval gates.",
        "declared_track_ids": [],
        "aliases": ["revenue-external-humans-served", "revenue", "cashclaw", "cash claw", "first cash", "revenuespine", "revenuescout", "hyrve"],
        "surfaces": [
            "reports/swarm_genome/2026-06-11/agent_2_revenue_capital.md",
            "reports/revenue_wedge/**",
            "docs/governance/VENTURE_CELL_PORTFOLIO.yaml",
            "docs/governance/VENTURE_CELL_REVENUE_WEDGE.md",
            "dharma_swarm/revenue/**",
        ],
        "subtracks": [
            "RevenueSpine ledger",
            "RevenueScout prospecting",
            "Agentic Code Governance Sprint",
            "CashClaw PR/marketplace loop",
            "first cash receipt",
            "human approval and trust gates",
        ],
    },
    {
        "id": "tam-offer-delivery",
        "title": "TAM & Offer Delivery",
        "theme": "Target-account motion: customer map, outreach queue, offer delivery, external contact evidence, and value-loop follow-through.",
        "declared_track_ids": [],
        "aliases": ["tam", "target account", "customer", "external human", "outreach", "offer", "service sales"],
        "surfaces": [
            "docs/offers/agentic-code-governance-sprint.md",
            "dharma_swarm/revenue/spine.py",
            "dharma_swarm/revenue/scout_daemon.py",
            "scripts/revenue/find_targets.py",
            "scripts/revenue/draft_outreach.py",
        ],
        "subtracks": [
            "target account map",
            "approved outreach queue",
            "offer delivery and proof",
            "customer evidence loop",
            "no-spam approval gates",
        ],
    },
    {
        "id": "sab-dharmic-agora",
        "title": "SAB / Dharmic Agora",
        "theme": "Semantic product and public trust surface: signal assessment, witness chain, moderation, publication, and semantic refinery.",
        "declared_track_ids": ["telos-ai-morning-refinery-2026-06"],
        "aliases": ["sab", "dharmic agora", "sabp", "agora", "signal assessment", "telos ai", "semantic refinery"],
        "surfaces": [
            "docs/reports/DGC_TO_DHARMA_SWARM_HYPER_REVIEW_2026-03-09.md",
            "docs/governance/VENTURE_CELL_PORTFOLIO.yaml",
            "reports/swarm_genome/2026-06-11/agent_1_telos_vision.md",
            "docs/vision_maps/TELOS_MORNING_REFINERY_V0.md",
        ],
        "subtracks": [
            "Dharmic Agora boundary",
            "SAB witness and moderation chain",
            "signal publication protocol",
            "semantic refinery seed",
            "DGC integration adapter",
        ],
    },
    {
        "id": "north-star-coherence",
        "title": "North Star & Coherence Governance",
        "theme": "Whole-system telos: sovereign doctrine, cybernetic coherence, canon metabolism, track hygiene, and production-readiness synthesis.",
        "declared_track_ids": ["cybernetics-codex-stewardship-2026-06"],
        "aliases": ["north star", "north_star", "telos", "sovereign", "full system", "loop lattice", "cybernetics", "canon"],
        "surfaces": [
            "docs/governance/SOVEREIGN_MANIFEST.md",
            "docs/governance/ACTIVE_TRACK.yaml",
            "docs/archive/DGC_100X_LEAN_ESSENCE_2026-03-08.md",
            "reports/swarm_genome/2026-06-11/SYNTHESIS.md",
        ],
        "subtracks": [
            "NORTH_STAR v2",
            "canon metabolism",
            "cybernetics codex stewardship",
            "loop lattice",
            "portfolio hygiene",
            "whole-system readiness synthesis",
        ],
    },
]

REPORT_SCAN_PATHS = [
    "reports/swarm_genome/2026-06-11/SYNTHESIS.md",
    "reports/swarm_genome/2026-06-11/agent_1_telos_vision.md",
    "reports/swarm_genome/2026-06-11/agent_2_revenue_capital.md",
    "reports/swarm_genome/2026-06-11/agent_3_research_chetana.md",
    "reports/swarm_genome/2026-06-11/agent_5_runtime_organs_devops.md",
    "docs/state/LIVE_OPS_DASHBOARD.md",
    "docs/state/BROKEN_REGISTER.md",
    "reports/governance/track_portfolio.json",
]

AGENT_HINTS = (
    "codex_composer",
    "fable_composer",
    "opus_composer",
    "devin-ai-integration[bot]",
    "copilot-swe-agent[bot]",
    "AmitabhainArunachala",
    "John Shrader",
)


def build_active_track_portfolio(repo_root: Path | None = None) -> dict[str, Any]:
    """Build the cockpit active-track portfolio projection."""
    root = (repo_root or _repo_root()).expanduser().resolve()
    generated_at = _now_iso()
    active_track_doc = _read_yaml(root / "docs" / "governance" / "ACTIVE_TRACK.yaml")
    portfolio_report = _read_json(root / "reports" / "governance" / "track_portfolio.json")
    git_movements = _git_movements(root)

    declared_tracks = [
        track
        for track in active_track_doc.get("active_tracks", [])
        if isinstance(track, dict)
    ]
    declared_by_slot = _assign_declared_tracks_to_slots(declared_tracks)

    slots = []
    for index, slot_def in enumerate(TARGET_TRACK_SLOTS, start=1):
        linked_tracks = declared_by_slot.get(slot_def["id"], [])
        movements = _slot_movements(root, slot_def, linked_tracks, git_movements)
        evidence = _slot_evidence(root, slot_def, linked_tracks, movements)
        agents = _slot_agents(linked_tracks, movements, evidence)
        progress = _slot_progress(linked_tracks, portfolio_report)
        freshness = _slot_freshness(linked_tracks, movements)
        status = _slot_status(linked_tracks, progress, freshness)
        layers = _layers_for_slot(
            slot_def=slot_def,
            linked_tracks=linked_tracks,
            movements=movements,
            evidence=evidence,
            agents=agents,
            repo_root=root,
        )
        slots.append(
            {
                "slot": index,
                "id": slot_def["id"],
                "title": slot_def["title"],
                "theme": slot_def["theme"],
                "status": status,
                "freshness": freshness,
                "progress": progress,
                "agents": agents,
                "linked_track_ids": [str(track.get("id") or "") for track in linked_tracks],
                "subtracks": _subtracks(slot_def, linked_tracks),
                "source_refs": _source_refs(slot_def, linked_tracks),
                "last_movements": movements[:3],
                "layers": layers,
                "action_menu": [
                    "open_handoff_prompt",
                    "copy_handoff_prompt",
                    "send_to_llm_planned_permissioned",
                ],
            }
        )

    declared_track_ids = {track_id for slot in slots for track_id in slot["linked_track_ids"] if track_id}
    unassigned_declared_tracks = [
        track
        for track in declared_tracks
        if str(track.get("id") or "") not in declared_track_ids
    ]
    warnings = _portfolio_warnings(slots, active_track_doc, portfolio_report, unassigned_declared_tracks)

    return {
        "generated_at": generated_at,
        "source": "operator target 10-track model + docs/governance/ACTIVE_TRACK.yaml + reports/governance/track_portfolio.json + git log + report scan",
        "slot_count": len(slots),
        "policy_slot_capacity": _slot_capacity(slots, active_track_doc),
        "occupied_slot_count": sum(1 for slot in slots if slot["linked_track_ids"]),
        "declared_active_track_count": len(declared_tracks),
        "policy": active_track_doc.get("track_policy", {}),
        "warnings": warnings,
        "slots": slots,
        "unassigned_declared_tracks": [
            {
                "id": str(track.get("id") or ""),
                "name": str(track.get("name") or ""),
                "status": str(track.get("status") or ""),
            }
            for track in unassigned_declared_tracks
        ],
    }


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here.parent, here.parent.parent, here.parent.parent.parent):
        if (parent / "docs" / "governance" / "ACTIVE_TRACK.yaml").exists():
            return parent
    return Path.cwd()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _assign_declared_tracks_to_slots(
    declared_tracks: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    assigned: dict[str, list[dict[str, Any]]] = {}
    for track in declared_tracks:
        best_slot_id = ""
        best_score = 0
        haystack = _track_text(track)
        for slot in TARGET_TRACK_SLOTS:
            declared_ids = {str(item) for item in slot.get("declared_track_ids", [])}
            track_id = str(track.get("id") or "")
            if track_id and track_id in declared_ids:
                best_slot_id = str(slot["id"])
                best_score = 100
                break
            score = _alias_score(haystack, slot["aliases"])
            if score > best_score:
                best_score = score
                best_slot_id = str(slot["id"])
        if best_slot_id and best_score > 0:
            assigned.setdefault(best_slot_id, []).append(track)
    return assigned


def _slot_capacity(slots: list[dict[str, Any]], active_track_doc: dict[str, Any]) -> int:
    policy = active_track_doc.get("track_policy") or {}
    try:
        max_active = int(policy.get("max_active") or 0)
    except (TypeError, ValueError):
        max_active = 0
    return max(len(slots), max_active)


def _track_text(track: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "id",
        "name",
        "status",
        "description",
        "serves",
        "owner",
    ):
        value = track.get(key)
        if value:
            parts.append(str(value))
    for key in ("owned_surfaces", "moves_vital_signs", "complements", "depends_on"):
        value = track.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    for key in ("prerequisites", "completion_criteria", "next_items"):
        value = track.get(key)
        if isinstance(value, list):
            parts.extend(json.dumps(item, sort_keys=True) for item in value if isinstance(item, dict))
    return " ".join(parts).casefold()


def _alias_score(haystack: str, aliases: list[str]) -> int:
    score = 0
    for alias in aliases:
        needle = alias.casefold()
        if needle in haystack:
            score += max(1, len(needle.split()))
    return score


def _git_movements(repo_root: Path) -> list[dict[str, str]]:
    command = [
        "git",
        "log",
        "--date=iso-strict",
        "--pretty=format:%H%x1f%h%x1f%ad%x1f%an%x1f%s",
        "-n",
        "120",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    movements: list[dict[str, str]] = []
    for line in completed.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 5:
            continue
        full_hash, short_hash, at, author, subject = parts
        movements.append(
            {
                "kind": "commit",
                "id": short_hash,
                "hash": full_hash,
                "title": subject,
                "detail": f"{short_hash} by {author}",
                "at": at,
                "age": _human_age(at),
                "actor": author,
                "source_ref": full_hash,
                "pr_refs": _pr_refs(subject),
            }
        )
    return movements


def _slot_movements(
    repo_root: Path,
    slot_def: dict[str, Any],
    linked_tracks: list[dict[str, Any]],
    git_movements: list[dict[str, str]],
) -> list[dict[str, Any]]:
    aliases = list(slot_def["aliases"])
    for track in linked_tracks:
        aliases.extend(
            [
                str(track.get("id") or ""),
                str(track.get("name") or ""),
                str(track.get("serves") or ""),
            ]
        )
    movements: list[dict[str, Any]] = []
    for movement in git_movements:
        subject = movement.get("title", "").casefold()
        detail = movement.get("detail", "").casefold()
        if _alias_score(f"{subject} {detail}", aliases) > 0:
            movements.append(movement)
    movements.extend(_report_movements(repo_root, slot_def, linked_tracks))
    movements.sort(key=lambda item: str(item.get("at") or ""), reverse=True)
    if movements:
        return movements[:12]
    return [
        {
            "kind": "gap",
            "id": f"{slot_def['id']}:no-recent-movement",
            "title": "No recent repo movement matched this slot",
            "detail": "Declare or link active subtracks if this meta-build is live.",
            "at": "",
            "age": "unknown",
            "actor": "cockpit projection",
            "source_ref": "docs/governance/ACTIVE_TRACK.yaml",
            "pr_refs": [],
        }
    ]


def _report_movements(
    repo_root: Path,
    slot_def: dict[str, Any],
    linked_tracks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    aliases = list(slot_def["aliases"])
    aliases.extend(str(track.get("id") or "") for track in linked_tracks)
    aliases.extend(str(track.get("name") or "") for track in linked_tracks)
    movements: list[dict[str, Any]] = []
    for rel_path in REPORT_SCAN_PATHS:
        path = repo_root / rel_path
        if not path.exists() or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        for line_number, line in enumerate(lines, start=1):
            clean = line.strip()
            if len(clean) < 8:
                continue
            if _alias_score(clean.casefold(), aliases) <= 0:
                continue
            movements.append(
                {
                    "kind": "report_line",
                    "id": f"{rel_path}:{line_number}",
                    "title": _truncate(clean, 132),
                    "detail": f"{rel_path}:{line_number}",
                    "at": mtime,
                    "age": _human_age(mtime),
                    "actor": "report",
                    "source_ref": f"{rel_path}:{line_number}",
                    "pr_refs": _pr_refs(clean),
                }
            )
            if len(movements) >= 8:
                return movements
    return movements


def _slot_evidence(
    repo_root: Path,
    slot_def: dict[str, Any],
    linked_tracks: list[dict[str, Any]],
    movements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for surface in _source_refs(slot_def, linked_tracks):
        path = repo_root / surface
        evidence.append(
            {
                "kind": "surface",
                "label": surface,
                "detail": "declared surface" if path.exists() else "declared pattern or external/off-repo surface",
                "path": surface,
                "at": _file_time(path),
                "age": _human_age(_file_time(path)) if path.exists() else "unknown",
            }
        )
    for movement in movements[:6]:
        evidence.append(
            {
                "kind": str(movement.get("kind") or "movement"),
                "label": str(movement.get("title") or ""),
                "detail": str(movement.get("detail") or ""),
                "path": str(movement.get("source_ref") or ""),
                "at": str(movement.get("at") or ""),
                "age": str(movement.get("age") or "unknown"),
            }
        )
    return evidence[:14]


def _slot_agents(
    linked_tracks: list[dict[str, Any]],
    movements: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[str]:
    agents: list[str] = []
    for track in linked_tracks:
        owner = str(track.get("owner") or "").strip()
        if owner:
            agents.append(owner)
    for movement in movements:
        actor = str(movement.get("actor") or "").strip()
        if actor:
            agents.append(actor)
        text = " ".join(str(movement.get(key) or "") for key in ("title", "detail"))
        agents.extend(agent for agent in AGENT_HINTS if agent in text)
    for item in evidence:
        text = " ".join(str(item.get(key) or "") for key in ("label", "detail", "path"))
        agents.extend(agent for agent in AGENT_HINTS if agent in text)
    return _unique(agents)[:8]


def _slot_progress(
    linked_tracks: list[dict[str, Any]],
    portfolio_report: dict[str, Any],
) -> dict[str, Any]:
    passed = 0
    total = 0
    shippable = False
    for track in linked_tracks:
        progress = track.get("completion_progress") if isinstance(track.get("completion_progress"), dict) else {}
        passed += int(progress.get("passed") or 0)
        total += int(progress.get("total") or 0)
        shippable = shippable or bool(track.get("shippable"))
    if not total:
        report_tracks = portfolio_report.get("active_tracks", [])
        if isinstance(report_tracks, list):
            linked_ids = {str(track.get("id") or "") for track in linked_tracks}
            for track in report_tracks:
                if isinstance(track, dict) and str(track.get("id") or "") in linked_ids:
                    progress = track.get("completion_progress") if isinstance(track.get("completion_progress"), dict) else {}
                    passed += int(progress.get("passed") or 0)
                    total += int(progress.get("total") or 0)
                    shippable = shippable or bool(track.get("shippable"))
    percent = round((passed / total) * 100) if total else 0
    return {
        "passed": passed,
        "total": total,
        "percent": percent,
        "shippable": shippable,
    }


def _slot_freshness(
    linked_tracks: list[dict[str, Any]],
    movements: list[dict[str, Any]],
) -> dict[str, Any]:
    latest = next((str(item.get("at") or "") for item in movements if item.get("at")), "")
    stale_reasons: list[str] = []
    for track in linked_tracks:
        verified_at = str(track.get("verified_at") or "")
        ttl_days = int(track.get("ttl_days") or 0)
        if verified_at and ttl_days:
            verified = _parse_time(verified_at)
            if verified:
                age_days = (datetime.now(UTC) - verified).total_seconds() / 86400
                if age_days > ttl_days:
                    stale_reasons.append(
                        f"{track.get('id')} verified {round(age_days)}d ago, ttl {ttl_days}d"
                    )
    return {
        "latest_at": latest,
        "latest_age": _human_age(latest) if latest else "unknown",
        "stale": bool(stale_reasons),
        "stale_reasons": stale_reasons,
    }


def _slot_status(
    linked_tracks: list[dict[str, Any]],
    progress: dict[str, Any],
    freshness: dict[str, Any],
) -> str:
    if freshness.get("stale"):
        return "stale"
    if not linked_tracks:
        return "needs_declaration"
    if progress.get("shippable"):
        return "shippable"
    statuses = {str(track.get("status") or "").lower() for track in linked_tracks}
    if "blocked" in statuses:
        return "blocked"
    return "active"


def _layers_for_slot(
    *,
    slot_def: dict[str, Any],
    linked_tracks: list[dict[str, Any]],
    movements: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    agents: list[str],
    repo_root: Path,
) -> list[dict[str, Any]]:
    subtracks = _subtracks(slot_def, linked_tracks)
    source_refs = _source_refs(slot_def, linked_tracks)
    layers = [
        {
            "depth": 1,
            "label": "Theme",
            "summary": slot_def["theme"],
            "items": [movement["title"] for movement in movements[:3]],
            "movements": movements[:3],
            "evidence": evidence[:3],
        },
        {
            "depth": 2,
            "label": "Subtracks",
            "summary": "Nested build streams inside this meta-build.",
            "items": subtracks[:10],
            "movements": movements[:5],
            "evidence": evidence[:6],
        },
        {
            "depth": 3,
            "label": "Seams",
            "summary": "Owned surfaces and coordination seams that should not be blurred.",
            "items": source_refs[:12],
            "movements": movements[:8],
            "evidence": evidence[:10],
        },
        {
            "depth": 4,
            "label": "Evidence",
            "summary": "Commits, PR references, report lines, agents, timestamps, and exact handoff context.",
            "items": _deep_items(movements, evidence, agents),
            "movements": movements[:12],
            "evidence": evidence,
        },
    ]
    for layer in layers:
        layer["handoff_prompt"] = _handoff_prompt(
            repo_root=repo_root,
            slot_def=slot_def,
            linked_tracks=linked_tracks,
            layer=layer,
            agents=agents,
        )
    return layers


def _subtracks(slot_def: dict[str, Any], linked_tracks: list[dict[str, Any]]) -> list[str]:
    items = list(slot_def.get("subtracks") or [])
    for track in linked_tracks:
        name = str(track.get("name") or track.get("id") or "").strip()
        if name:
            items.append(name)
        next_items = track.get("next_items")
        if isinstance(next_items, list):
            for item in next_items:
                if isinstance(item, dict) and item.get("what"):
                    items.append(str(item["what"]))
    return _unique(items)


def _source_refs(slot_def: dict[str, Any], linked_tracks: list[dict[str, Any]]) -> list[str]:
    refs = list(slot_def.get("surfaces") or [])
    for track in linked_tracks:
        owned = track.get("owned_surfaces")
        if isinstance(owned, list):
            refs.extend(str(item) for item in owned)
    refs.extend(
        [
            "docs/governance/ACTIVE_TRACK.yaml",
            "reports/governance/track_portfolio.json",
        ]
    )
    return _unique(refs)


def _deep_items(
    movements: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    agents: list[str],
) -> list[str]:
    items: list[str] = []
    pr_refs = _unique(
        pr
        for movement in movements
        for pr in movement.get("pr_refs", [])
        if isinstance(pr, str)
    )
    if agents:
        items.append(f"Agents involved: {', '.join(agents)}")
    if pr_refs:
        items.append(f"PR refs: {', '.join(pr_refs)}")
    for movement in movements[:8]:
        title = str(movement.get("title") or "")
        age = str(movement.get("age") or "unknown")
        actor = str(movement.get("actor") or "")
        items.append(f"{age}: {title} ({actor})")
    for item in evidence[:6]:
        items.append(f"{item.get('kind')}: {item.get('path')}")
    return items[:16]


def _handoff_prompt(
    *,
    repo_root: Path,
    slot_def: dict[str, Any],
    linked_tracks: list[dict[str, Any]],
    layer: dict[str, Any],
    agents: list[str],
) -> str:
    track_ids = ", ".join(str(track.get("id") or "") for track in linked_tracks if track.get("id")) or "not declared in ACTIVE_TRACK.yaml"
    source_refs = "\n".join(f"- {ref}" for ref in _source_refs(slot_def, linked_tracks)[:10])
    layer_items = "\n".join(f"- {item}" for item in layer.get("items", [])[:10])
    agent_line = ", ".join(agents) if agents else "unknown; inspect receipts and git history"
    return "\n".join(
        [
            f"You are taking over the Dharma Swarm meta-build track: {slot_def['title']}.",
            f"Repo: {repo_root}",
            f"Linked ACTIVE_TRACK.yaml nodes: {track_ids}.",
            "",
            "Start here, in order:",
            "1. cd /Users/dhyana/dharma_swarm",
            "2. make onboard",
            "3. make hygiene",
            "4. git status --short",
            "5. git branch --show-current",
            "",
            "Read these authority files before edits:",
            "- docs/governance/ACTIVE_TRACK.yaml",
            "- ACTIVE_SURFACE_MANIFEST.yaml",
            "- docs/state/LIVE_OPS_DASHBOARD.md",
            "- docs/state/BROKEN_REGISTER.md",
            "- PRODUCT_SURFACE.md",
            "",
            "Operator front-door rule:",
            "- /dashboard/cockpit is John's human command front door.",
            "- make onboard is the agent intake door, not the human dashboard.",
            "",
            f"Layer scope: depth {layer['depth']} - {layer['label']}.",
            f"Layer summary: {layer['summary']}",
            "Layer items:",
            layer_items or "- No layer items projected yet.",
            "",
            "Agents already visible:",
            f"- {agent_line}",
            "",
            "Source refs:",
            source_refs,
            "",
            "Governance/hygiene constraints:",
            "- Do not create a new authority store when an existing owner can project the truth.",
            "- Do not revert user changes or unrelated dirty work.",
            "- Keep repo edits scoped to this track and its owned surfaces.",
            "- Run the narrowest meaningful tests, then report changed files and verification.",
            "- If touching dashboard/cockpit, keep /dashboard/cockpit as the human front door.",
            "",
            "Closeout expected:",
            "- concrete status",
            "- evidence path/line or command output",
            "- tests/checks run",
            "- remaining blocker or next handoff if not complete",
        ]
    )


def _portfolio_warnings(
    slots: list[dict[str, Any]],
    active_track_doc: dict[str, Any],
    portfolio_report: dict[str, Any],
    unassigned_declared_tracks: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    policy = active_track_doc.get("track_policy") or {}
    try:
        max_active = int(policy.get("max_active") or 0)
    except (TypeError, ValueError):
        max_active = 0
    if max_active and len(slots) != max_active:
        warnings.append(f"cockpit target slot count {len(slots)} differs from ACTIVE_TRACK.yaml max_active {max_active}")
    undeclared = [slot["title"] for slot in slots if not slot["linked_track_ids"]]
    if undeclared:
        warnings.append(f"{len(undeclared)} of {len(slots)} target slots have no linked ACTIVE_TRACK.yaml node")
    if unassigned_declared_tracks:
        warnings.append(f"{len(unassigned_declared_tracks)} ACTIVE_TRACK.yaml nodes did not map cleanly to an operator target slot")
    generated_at = str(portfolio_report.get("generated_at") or "")
    generated = _parse_time(generated_at)
    if generated:
        age_hours = (datetime.now(UTC) - generated).total_seconds() / 3600
        if age_hours > 24:
            warnings.append(f"track_portfolio.json is {round(age_hours)}h old")
    elif not portfolio_report:
        warnings.append("reports/governance/track_portfolio.json is missing or unreadable")
    return warnings


def _file_time(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    except OSError:
        return ""


def _human_age(value: str) -> str:
    dt = _parse_time(value)
    if dt is None:
        return "unknown"
    seconds = max(0, int((datetime.now(UTC) - dt).total_seconds()))
    if seconds < 90:
        return "just now"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raw = f"{raw}T00:00:00Z"
    raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _pr_refs(text: str) -> list[str]:
    return [f"#{match}" for match in re.findall(r"#(\d+)", text or "")]


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: max(0, limit - 3)]}..."


def _unique(items: list[str] | Any) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
