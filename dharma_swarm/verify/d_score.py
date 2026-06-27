"""Read-only D-score verifier for persistent agents, holons, and substrate.

The D-score is a maturity score over runtime evidence. It does not promote an
agent by itself; hard gates cap the verified level when proof is missing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from dharma_swarm.holon_service_liveness import assess_service_liveness
from dharma_swarm.holon_transport_liveness import assess_transport_liveness
from dharma_swarm.living_dock_verifier import verify_living_dock

SCHEMA_VERSION = "dharma.d_score_report.v1"
AXES = (
    "identity_and_admission",
    "canonical_home",
    "runtime_persistence",
    "a2a_transport",
    "delegation_hierarchy",
    "authority_and_policy",
    "receipts_and_lineage",
    "verification",
    "operator_surface",
    "evolution_loop",
)
PROTECTED_ACTIONS = (
    "secrets",
    "money",
    "external_messages",
    "pr_approval",
    "policy_governance_writes",
)
CONVERSATION_RECEIPT_SCHEMA = "dharma.holon_conversation_receipt.v1"
SEMANTIC_RECEIPT_SCHEMA = "dharma.semantic_receipt.v1"
DOMAIN_RECEIPT_SCHEMAS = {
    "dharma.a2a.domain_reply_publish_receipt.v1",
    "dharma.a2a.reply_capture_receipt.v1",
}
DOMAIN_RECEIPT_STATUSES = {"DOMAIN_REPLY_PUBLISHED", "DOMAIN_RECEIPTED"}


@dataclass(frozen=True)
class EvidenceStatus:
    status: str
    summary: str
    evidence_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DScoreReport:
    schema_version: str
    generated_at: str
    agent_uid: str
    semantic_object: dict[str, Any]
    living_dock_status: dict[str, Any]
    service_heartbeat_status: dict[str, Any]
    transport_heartbeat_status: dict[str, Any]
    policy_gate_status: dict[str, Any]
    receipt_bundle_status: dict[str, Any]
    verifier_status: dict[str, Any]
    axis_scores: dict[str, int]
    hard_gate_failures: list[str]
    claimed_level: str
    verified_level: str
    total_score: int
    evidence_paths: list[str]
    protected_actions_gated: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _path_status(path: Path, label: str) -> EvidenceStatus:
    if path.exists():
        return EvidenceStatus("present", f"{label} present", [str(path)])
    return EvidenceStatus("missing", f"{label} missing", [])


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in {"_", "-"} else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def _aliases(agent_uid: str) -> list[str]:
    aliases = [agent_uid]
    if "_" in agent_uid:
        aliases.append(agent_uid.replace("_", "-"))
    if "-" in agent_uid:
        aliases.append(agent_uid.replace("-", "_"))
    return list(dict.fromkeys(aliases))


def _line_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        return sum(1 for _ in path.open(encoding="utf-8"))
    except Exception:
        return 0


def _latest_file(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists() and path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _recent_enough(path: Path | None, *, max_age_minutes: int) -> bool:
    if path is None or not path.exists():
        return False
    age_s = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age_s <= max_age_minutes * 60


def _latest_paths(root: Path, patterns: tuple[str, ...] = ("*.json",), *, limit: int = 200) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(path for path in root.glob(pattern) if path.is_file())

    def sort_key(path: Path) -> tuple[float, str]:
        try:
            return (path.stat().st_mtime, path.name)
        except OSError:
            return (0.0, path.name)

    return sorted(dict.fromkeys(paths), key=sort_key, reverse=True)[:limit]


def _read_jsonl(path: Path, *, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw in lines[-limit:]:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _agent_ref_matches(value: object, agent_uid: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    aliases = set(_aliases(agent_uid))
    if raw in aliases:
        return True
    lowered = raw.lower()
    return any(
        token in lowered
        for alias in aliases
        for token in (
            f"dharma.agent.{alias}.",
            f"/{alias}/",
            f"-{alias}-",
            f"_{alias}_",
        )
    )


def _payload_agent_matches(payload: dict[str, Any], agent_uid: str) -> bool:
    keys = (
        "agent_uid",
        "holon",
        "target_uid",
        "target",
        "to",
        "reply_subject",
        "subject",
        "correlation_id",
        "packet_id",
    )
    if any(_agent_ref_matches(payload.get(key), agent_uid) for key in keys):
        return True
    for nested_key in ("domain_receipt_payload", "reply_payload", "semantic_receipt"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict) and _payload_agent_matches(nested, agent_uid):
            return True
    return False


def _valid_dialogue_receipt(payload: dict[str, Any], agent_uid: str) -> bool:
    if payload.get("schema_version") != CONVERSATION_RECEIPT_SCHEMA:
        return False
    if not _payload_agent_matches(payload, agent_uid):
        return False
    if str(payload.get("provider_error") or "").strip():
        return False
    if not list(payload.get("context_refs") or []):
        return False
    if str(payload.get("routing_mode") or "") != "holon_route":
        return False
    reply = str(payload.get("reply") or "")
    reply_chars = payload.get("reply_chars")
    try:
        reply_count = int(reply_chars)
    except (TypeError, ValueError):
        reply_count = len(reply)
    return reply_count > 0 and not bool(payload.get("protected_action_claim"))


def _valid_semantic_receipt(payload: dict[str, Any], agent_uid: str) -> bool:
    return bool(
        payload.get("schema_version") == SEMANTIC_RECEIPT_SCHEMA
        and _payload_agent_matches(payload, agent_uid)
        and payload.get("semantic_reply_claim") is True
        and payload.get("peer_model_processed_claim") is True
        and not str(payload.get("failure_type") or "")
    )


def _valid_domain_receipt(payload: dict[str, Any], agent_uid: str) -> bool:
    schema = str(payload.get("schema_version") or "")
    status = str(payload.get("status") or "")
    return bool(
        schema in DOMAIN_RECEIPT_SCHEMAS
        and _payload_agent_matches(payload, agent_uid)
        and payload.get("domain_receipt_claim") is True
        and status in DOMAIN_RECEIPT_STATUSES
    )


def _semantic_object(agent_uid: str, repo_root: Path) -> dict[str, Any]:
    objects_path = repo_root / "docs" / "ontology" / "semantic_objects.yaml"
    aliases_path = repo_root / "docs" / "ontology" / "semantic_aliases.yaml"
    objects_doc = _read_yaml(objects_path)
    aliases_doc = _read_yaml(aliases_path)
    ids: set[str] = set()
    for item in aliases_doc.get("aliases", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("alias") or "") in _aliases(agent_uid):
            ids.add(str(item.get("canonical_id") or ""))
    for item in objects_doc.get("semantic_objects", objects_doc.get("objects", [])):
        if not isinstance(item, dict):
            continue
        names = [str(item.get("id") or ""), str(item.get("canonical_name") or "")]
        names.extend(str(alias) for alias in item.get("aliases", []) or [])
        if any(name in _aliases(agent_uid) for name in names):
            ids.add(str(item.get("id") or ""))
    if not ids:
        return {
            "status": "missing",
            "canonical_id": "",
            "evidence_paths": [str(objects_path), str(aliases_path)],
        }
    canonical_id = sorted(ids)[0]
    return {
        "status": "present",
        "canonical_id": canonical_id,
        "evidence_paths": [str(objects_path), str(aliases_path)],
    }


def _find_agent_home(agent_uid: str, state_root: Path) -> Path:
    agents_root = state_root / "agents"
    for alias in _aliases(agent_uid):
        path = agents_root / alias
        if path.exists():
            return path
    return agents_root / agent_uid


def _passport_paths(agent_uid: str, state_root: Path, home: Path) -> list[Path]:
    paths = [home / "authority_passport.json"]
    for alias in _aliases(agent_uid):
        paths.append(state_root / "agent_passports" / f"{alias}.json")
    return list(dict.fromkeys(paths))


def _a2a_card_paths(agent_uid: str, state_root: Path, home: Path) -> list[Path]:
    paths = [home / "a2a_card.json"]
    for alias in _aliases(agent_uid):
        paths.append(state_root / "a2a" / "cards" / f"{alias}.json")
        paths.append(state_root / "a2a_bus" / "cards" / f"{alias}.json")
    return list(dict.fromkeys(paths))


def _living_dock_status(agent_uid: str, state_root: Path) -> tuple[dict[str, Any], Path, list[str]]:
    dock_report = verify_living_dock(
        agent_uid,
        dharma_home=state_root,
        agents_root=state_root / "agents",
        require_dialogue=True,
        require_sanctum=True,
    )
    home = Path(dock_report.living_dock_path)
    required = {
        "identity": home / "identity.json",
        "living_agent": home / "living_agent.json",
        "service_heartbeats": home / "service_heartbeats.jsonl",
        "transport_heartbeats": home / "transport_heartbeats.jsonl",
        "dialogue_operator_sessions": home / "dialogue" / "operator_sessions.jsonl",
        "dialogue_relationship_memory": home / "dialogue" / "relationship_memory.jsonl",
        "dialogue_conversation_receipts": home / "dialogue" / "conversation_receipts",
        "sanctum_codex": home / "sanctum" / "codex",
        "sanctum_vault": home / "sanctum" / "vault",
        "sanctum_dojo": home / "sanctum" / "dojo",
        "sanctum_ingest_gate": home / "sanctum" / "ingest_gate",
        "sanctum_tools": home / "sanctum" / "tools",
        "sanctum_receipts": home / "sanctum" / "receipts",
    }
    passport = _latest_file(_passport_paths(agent_uid, state_root, home))
    card = _latest_file(_a2a_card_paths(agent_uid, state_root, home))
    present = {name: path.exists() for name, path in required.items()}
    if passport is not None:
        present["authority_passport"] = True
    else:
        present["authority_passport"] = False
    if card is not None:
        present["a2a_card"] = True
    else:
        present["a2a_card"] = False
    evidence = [str(path) for path in required.values() if path.exists()]
    evidence.extend(dock_report.evidence_paths)
    if passport:
        evidence.append(str(passport))
    if card:
        evidence.append(str(card))
    missing = [name for name, exists in present.items() if not exists]
    strict_failures = [finding.to_dict() for finding in dock_report.findings if finding.severity == "fail"]
    status = "complete" if not missing and not strict_failures else ("partial" if evidence else "missing")
    return (
        {
            "status": status,
            "home": str(home),
            "present": present,
            "missing": missing,
            "strict_status": dock_report.status,
            "strict_failures": strict_failures,
            "evidence_paths": list(dict.fromkeys(evidence)),
        },
        home,
        list(dict.fromkeys(evidence)),
    )


def _heartbeat_status(path: Path, label: str, *, max_age_minutes: int) -> dict[str, Any]:
    lines = _line_count(path)
    recent = _recent_enough(path, max_age_minutes=max_age_minutes)
    if lines and recent:
        status = "fresh"
    elif lines:
        status = "stale"
    else:
        status = "missing"
    return {
        "status": status,
        "line_count": lines,
        "max_age_minutes": max_age_minutes,
        "summary": f"{label}: {lines} line(s), {status}",
        "evidence_paths": [str(path)] if path.exists() else [],
    }


def _service_heartbeat_status(home: Path, *, max_age_minutes: int) -> dict[str, Any]:
    liveness = assess_service_liveness(
        home.name,
        agents_root=home.parent,
        fresh_after_seconds=max_age_minutes * 60,
    )
    if liveness["service_alive"]:
        status = "fresh"
    elif not liveness["heartbeat_seen"]:
        status = "missing"
    elif not liveness["ledger_ok"]:
        status = "invalid"
    elif not liveness["fresh"]:
        status = "stale"
    elif liveness["service_paused"]:
        status = "paused"
    else:
        status = str(liveness.get("status") or "unhealthy")
    path = home / "service_heartbeats.jsonl"
    lines = _line_count(path)
    return {
        "status": status,
        "line_count": lines,
        "max_age_minutes": max_age_minutes,
        "summary": f"service heartbeat: {lines} line(s), {status}",
        "evidence_paths": [str(path)] if path.exists() else [],
        "liveness": liveness,
    }


def _transport_heartbeat_status(home: Path, *, max_age_minutes: int) -> dict[str, Any]:
    liveness = assess_transport_liveness(
        home.name,
        agents_root=home.parent,
        fresh_after_seconds=max_age_minutes * 60,
        transport_id="a2a_inbox_bridge",
    )
    if liveness["transport_reachable"]:
        status = "fresh"
    elif not liveness["heartbeat_seen"]:
        status = "missing"
    elif not liveness["ledger_ok"]:
        status = "invalid"
    elif not liveness["fresh"]:
        status = "stale"
    else:
        status = str(liveness.get("status") or "unreachable")
    path = home / "transport_heartbeats.jsonl"
    lines = _line_count(path)
    return {
        "status": status,
        "line_count": lines,
        "max_age_minutes": max_age_minutes,
        "summary": f"transport heartbeat: {lines} line(s), {status}",
        "evidence_paths": [str(path)] if path.exists() else [],
        "liveness": liveness,
    }


def _policy_gate_status(repo_root: Path) -> dict[str, Any]:
    source = repo_root / "dharma_swarm" / "persistent_agent.py"
    text = source.read_text(encoding="utf-8") if source.exists() else ""
    fail_closed = "gate check failed closed" in text and '"gate_status": "fail_closed"' in text
    return {
        "status": "fail_closed" if fail_closed else "fail_open_or_unknown",
        "summary": (
            "PersistentAgent gate exceptions block standing-agent wakes"
            if fail_closed
            else "PersistentAgent gate exception path is not proven fail-closed"
        ),
        "evidence_paths": [str(source)] if source.exists() else [],
    }


def _receipt_bundle_status(agent_uid: str, repo_root: Path, state_root: Path, home: Path) -> dict[str, Any]:
    evidence: list[str] = []
    semantic = False
    domain = False
    dialogue = False
    structured = False

    last_receipt = _read_json(home / "last_receipt.json")
    if last_receipt and _payload_agent_matches(last_receipt, agent_uid):
        evidence.append(str(home / "last_receipt.json"))
        structured = True

    talk_ledger = home / "talk_receipts.jsonl"
    if any(_valid_dialogue_receipt(row, agent_uid) for row in _read_jsonl(talk_ledger)):
        evidence.append(str(talk_ledger))
        dialogue = True
        structured = True

    conversation_dir = home / "dialogue" / "conversation_receipts"
    for match in _latest_paths(conversation_dir):
        payload = _read_json(match)
        if _valid_dialogue_receipt(payload, agent_uid):
            evidence.append(str(match))
            dialogue = True
            structured = True

    for root in (
        repo_root / "reports" / "a2a" / "domain_reply_receipts",
        repo_root / "reports" / "a2a" / "reply_receipts",
    ):
        for match in _latest_paths(root):
            payload = _read_json(match)
            if _valid_domain_receipt(payload, agent_uid):
                evidence.append(str(match))
                domain = True
                structured = True

    semantic_root = repo_root / "reports" / "agentops" / "semantic_receipts"
    for match in _latest_paths(semantic_root):
        payload = _read_json(match)
        if _valid_semantic_receipt(payload, agent_uid):
            evidence.append(str(match))
            semantic = True
            structured = True

    outbox_root = state_root / "a2a_bus" / "outboxes" / agent_uid
    for match in _latest_paths(outbox_root):
        payload = _read_json(match)
        if _payload_agent_matches(payload, agent_uid):
            evidence.append(str(match))
            structured = True

    status = "semantic" if semantic else ("domain" if domain else ("structured" if structured else "missing"))
    return {
        "status": status,
        "domain_receipt": domain,
        "semantic_receipt": semantic,
        "dialogue_receipt": dialogue,
        "evidence_paths": list(dict.fromkeys(evidence)),
    }


def _verifier_status(repo_root: Path) -> dict[str, Any]:
    candidates = [
        repo_root / "dharma_swarm" / "operator_core" / "semantic_receipt.py",
        repo_root / "scripts" / "runtime" / "model_critic_runner.py",
        repo_root / "tests" / "test_semantic_receipt.py",
        repo_root / "tests" / "test_model_critic_runner.py",
    ]
    evidence = [str(path) for path in candidates if path.exists()]
    status = "present" if len(evidence) >= 3 else ("partial" if evidence else "missing")
    return {
        "status": status,
        "summary": f"{len(evidence)}/{len(candidates)} verifier files present",
        "evidence_paths": evidence,
    }


def _score_from_status(status: str, mapping: dict[str, int], default: int = 0) -> int:
    return max(0, min(5, mapping.get(status, default)))


def _level_for_score(score: int) -> str:
    if score >= 44:
        return "D5"
    if score >= 35:
        return "D4"
    if score >= 25:
        return "D3"
    if score >= 16:
        return "D2"
    if score >= 8:
        return "D1"
    return "D0"


def _cap_level(level: str, hard_gate_failures: list[str]) -> str:
    if any(item.startswith("d2_") for item in hard_gate_failures):
        return min(level, "D1", key=lambda item: int(item[1:]))
    if any(item.startswith("d3_") for item in hard_gate_failures):
        return min(level, "D2", key=lambda item: int(item[1:]))
    if any(item.startswith("d4_") or item == "policy_gate_not_fail_closed" for item in hard_gate_failures):
        return min(level, "D3", key=lambda item: int(item[1:]))
    if any(item.startswith("d5_") for item in hard_gate_failures):
        return min(level, "D4", key=lambda item: int(item[1:]))
    return level


def _identity(agent_uid: str, home: Path) -> dict[str, Any]:
    for path in (home / "identity.json", home / "identity_invariant.json"):
        data = _read_json(path)
        if data:
            return data
    return {}


def score_agent(
    agent_uid: str,
    *,
    state_root: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> DScoreReport:
    """Score one agent from current filesystem evidence."""
    state = Path(state_root or Path.home() / ".dharma").expanduser().resolve()
    repo = Path(repo_root or Path.cwd()).expanduser().resolve()
    semantic = _semantic_object(agent_uid, repo)
    living, home, living_evidence = _living_dock_status(agent_uid, state)
    service = _service_heartbeat_status(home, max_age_minutes=15)
    transport = _transport_heartbeat_status(home, max_age_minutes=5)
    policy = _policy_gate_status(repo)
    receipts = _receipt_bundle_status(agent_uid, repo, state, home)
    verifier = _verifier_status(repo)
    identity = _identity(agent_uid, home)

    hard: list[str] = []
    if semantic["status"] != "present":
        hard.append("d2_semantic_identity_missing")
    if living["status"] != "complete":
        hard.append("d3_living_dock_incomplete")
    if service["status"] != "fresh":
        hard.append("d3_service_heartbeat_not_fresh")
    if transport["status"] != "fresh":
        hard.append("d3_transport_heartbeat_not_fresh")
    if policy["status"] != "fail_closed":
        hard.append("policy_gate_not_fail_closed")
    if not receipts["domain_receipt"]:
        hard.append("d4_domain_receipt_missing")
    if not receipts["semantic_receipt"]:
        hard.append("d4_semantic_receipt_missing")
    if not receipts["dialogue_receipt"]:
        hard.append("d4_dialogue_receipt_missing")

    axis_scores = {
        "identity_and_admission": 5 if semantic["status"] == "present" and identity else (3 if identity else 0),
        "canonical_home": _score_from_status(living["status"], {"complete": 5, "partial": 3, "missing": 0}),
        "runtime_persistence": _score_from_status(
            service["status"],
            {"fresh": 5, "paused": 3, "stale": 2, "error": 1, "invalid": 1, "missing": 0},
        ),
        "a2a_transport": max(
            _score_from_status(
                transport["status"],
                {"fresh": 5, "stale": 2, "unreachable": 1, "invalid": 1, "missing": 0},
            ),
            5 if receipts["semantic_receipt"] else (4 if receipts["domain_receipt"] else 0),
        ),
        "delegation_hierarchy": 4 if (home / "runs").exists() or (home / "artifacts").exists() else 1,
        "authority_and_policy": 5 if policy["status"] == "fail_closed" else 1,
        "receipts_and_lineage": _score_from_status(receipts["status"], {"semantic": 5, "domain": 4, "structured": 3, "missing": 0}),
        "verification": _score_from_status(verifier["status"], {"present": 4, "partial": 2, "missing": 0}),
        "operator_surface": 5 if receipts["dialogue_receipt"] else (3 if (home / "interface").exists() else 1),
        "evolution_loop": 5 if (home / "sanctum" / "dojo").exists() else (3 if (home / "wake").exists() else 1),
    }
    total = sum(axis_scores.values())
    claimed = _level_for_score(total)
    apex_claim = bool(
        identity.get("apex_command_identity")
        or identity.get("apex_identity")
        or (isinstance(identity.get("apex"), dict) and identity["apex"].get("command_identity"))
    )
    if claimed == "D5" and not apex_claim:
        hard.append("d5_apex_command_identity_unproven")
    verified = _cap_level(claimed, hard)
    evidence = list(
        dict.fromkeys(
            [
                *semantic.get("evidence_paths", []),
                *living_evidence,
                *service["evidence_paths"],
                *transport["evidence_paths"],
                *policy["evidence_paths"],
                *receipts["evidence_paths"],
                *verifier["evidence_paths"],
            ]
        )
    )
    notes = []
    if agent_uid == "sarathi":
        notes.append("Sarathi is treated as read-only APEX seed until runtime breath receipts exist.")

    return DScoreReport(
        schema_version=SCHEMA_VERSION,
        generated_at=utc_now_iso(),
        agent_uid=agent_uid,
        semantic_object=semantic,
        living_dock_status=living,
        service_heartbeat_status=service,
        transport_heartbeat_status=transport,
        policy_gate_status=policy,
        receipt_bundle_status=receipts,
        verifier_status=verifier,
        axis_scores=axis_scores,
        hard_gate_failures=hard,
        claimed_level=claimed,
        verified_level=verified,
        total_score=total,
        evidence_paths=evidence,
        protected_actions_gated=list(PROTECTED_ACTIONS),
        notes=notes,
    )


def score_substrate(
    *,
    state_root: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> DScoreReport:
    """Score the Dharma substrate row from repo and runtime owner evidence."""
    state = Path(state_root or Path.home() / ".dharma").expanduser().resolve()
    repo = Path(repo_root or Path.cwd()).expanduser().resolve()
    policy = _policy_gate_status(repo)
    semantic_files = [
        repo / "docs" / "ontology" / "semantic_objects.yaml",
        repo / "docs" / "ontology" / "semantic_aliases.yaml",
        repo / "docs" / "ops" / "AGENT_ADMISSION.md",
    ]
    runtime_files = [
        repo / "dharma_swarm" / "runtime_state.py",
        repo / "dharma_swarm" / "operator_core" / "runtime_truth.py",
        state / "state" / "runtime.db",
    ]
    a2a_files = [
        repo / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md",
        repo / "scripts" / "runtime" / "a2a_inbox_bridge.py",
        repo / "scripts" / "runtime" / "a2a_domain_reply_worker.py",
    ]
    verifier = _verifier_status(repo)
    evidence = [str(path) for path in [*semantic_files, *runtime_files, *a2a_files] if path.exists()]
    semantic_score = sum(1 for path in semantic_files if path.exists())
    runtime_score = sum(1 for path in runtime_files if path.exists())
    a2a_score = sum(1 for path in a2a_files if path.exists())
    hard = []
    if policy["status"] != "fail_closed":
        hard.append("policy_gate_not_fail_closed")
    if runtime_score < len(runtime_files):
        hard.append("d5_global_runtime_map_incomplete")
    hard.append("d5_single_apex_control_plane_unproven")
    axis_scores = {
        "identity_and_admission": min(5, semantic_score + 2),
        "canonical_home": 3,
        "runtime_persistence": min(5, runtime_score + 2),
        "a2a_transport": min(5, a2a_score + 2),
        "delegation_hierarchy": 4,
        "authority_and_policy": 5 if policy["status"] == "fail_closed" else 2,
        "receipts_and_lineage": 4 if (state / "state" / "runtime.db").exists() else 3,
        "verification": _score_from_status(verifier["status"], {"present": 4, "partial": 2, "missing": 0}),
        "operator_surface": 4 if (repo / "api" / "routers" / "control_surface.py").exists() else 2,
        "evolution_loop": 3,
    }
    total = sum(axis_scores.values())
    claimed = _level_for_score(total)
    return DScoreReport(
        schema_version=SCHEMA_VERSION,
        generated_at=utc_now_iso(),
        agent_uid="dharma_substrate",
        semantic_object={
            "status": "system",
            "canonical_id": "dharma_substrate",
            "evidence_paths": [str(path) for path in semantic_files if path.exists()],
        },
        living_dock_status={
            "status": "system_projection",
            "home": str(state),
            "evidence_paths": evidence,
        },
        service_heartbeat_status={
            "status": "system",
            "summary": "substrate scored from runtime_state/control-surface evidence",
            "evidence_paths": [str(path) for path in runtime_files if path.exists()],
        },
        transport_heartbeat_status={
            "status": "system",
            "summary": "substrate scored from NATS/A2A specs and workers",
            "evidence_paths": [str(path) for path in a2a_files if path.exists()],
        },
        policy_gate_status=policy,
        receipt_bundle_status={
            "status": "runtime_projection",
            "evidence_paths": [str(path) for path in runtime_files if path.exists()],
        },
        verifier_status=verifier,
        axis_scores=axis_scores,
        hard_gate_failures=hard,
        claimed_level=claimed,
        verified_level=_cap_level(claimed, hard),
        total_score=total,
        evidence_paths=list(dict.fromkeys([*evidence, *policy["evidence_paths"], *verifier["evidence_paths"]])),
        protected_actions_gated=list(PROTECTED_ACTIONS),
        notes=["Substrate score is a system row, not an agent promotion."],
    )


def render_markdown(report: DScoreReport) -> str:
    data = report.to_dict()
    lines = [
        f"# D-Score Report: {report.agent_uid}",
        "",
        f"- generated_at: `{report.generated_at}`",
        f"- total_score: `{report.total_score}/50`",
        f"- claimed_level: `{report.claimed_level}`",
        f"- verified_level: `{report.verified_level}`",
        f"- semantic_object: `{data['semantic_object'].get('canonical_id', '') or 'missing'}`",
        f"- policy_gate_status: `{data['policy_gate_status'].get('status', '')}`",
        "",
        "## Axis Scores",
        "",
    ]
    for axis in AXES:
        lines.append(f"- `{axis}`: {report.axis_scores.get(axis, 0)}/5")
    lines.extend(["", "## Hard Gate Failures", ""])
    if report.hard_gate_failures:
        lines.extend(f"- `{item}`" for item in report.hard_gate_failures)
    else:
        lines.append("- none")
    lines.extend(["", "## Evidence Paths", ""])
    if report.evidence_paths:
        lines.extend(f"- `{path}`" for path in report.evidence_paths[:80])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_d_score_report(report: DScoreReport, out_dir: Path | str) -> tuple[Path, Path]:
    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    stamp = report.generated_at.replace("-", "").replace(":", "").replace("Z", "Z")
    base = f"{stamp}-{_safe_token(report.agent_uid)}"
    json_path = out / f"{base}.json"
    md_path = out / f"{base}.md"
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
