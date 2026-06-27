"""Read-only Agent Card meishi index.

This module projects existing identity surfaces into one portable Agent Card
view. It does not own identity, authority, routing, or runtime truth; it joins
the existing lanes so dashboards and handoff tools can consume one stable
packet.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - only exercised in broken envs
    yaml = None  # type: ignore

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.operator_core.identity_invariant import validate_identity_invariant

SCHEMA_VERSION = "dharma.agent_card.meishi_index.v0"
CARD_SCHEMA_VERSION = "dharma.agent_card.meishi.v0"


@dataclass(frozen=True)
class AgentCardFinding:
    severity: str
    check: str
    agent_uid: str
    path: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class AgentCardProjection:
    agent_uid: str
    display_name: str = ""
    callsign: str = ""
    role: str = ""
    status: str = ""
    endpoint: str = ""
    provider: str = ""
    model: str = ""
    harness: str = ""
    department: str = ""
    squad_id: str = ""
    team_id: str = ""
    authority: str = ""
    card_names: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    semantic: dict[str, Any] = field(default_factory=dict)
    a2a: dict[str, Any] = field(default_factory=dict)
    registration: dict[str, Any] = field(default_factory=dict)
    identity_invariant: dict[str, Any] = field(default_factory=dict)
    authority_passport: dict[str, Any] = field(default_factory=dict)
    living_dock: dict[str, Any] = field(default_factory=dict)
    nats: dict[str, Any] = field(default_factory=dict)
    handoff: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, list[str]] = field(default_factory=dict)
    findings: list[AgentCardFinding] = field(default_factory=list)
    trust_grade: str = "unverified"

    def add_source(self, kind: str, path: Path | str) -> None:
        value = str(path)
        bucket = self.sources.setdefault(kind, [])
        if value not in bucket:
            bucket.append(value)

    def add_finding(
        self,
        severity: str,
        check: str,
        path: Path | str,
        detail: str,
    ) -> None:
        self.findings.append(
            AgentCardFinding(
                severity=severity,
                check=check,
                agent_uid=self.agent_uid,
                path=str(path),
                detail=detail,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CARD_SCHEMA_VERSION,
            "agent_uid": self.agent_uid,
            "display_name": self.display_name or self.agent_uid,
            "callsign": self.callsign,
            "role": self.role,
            "status": self.status,
            "endpoint": self.endpoint,
            "provider": self.provider,
            "model": self.model,
            "harness": self.harness,
            "department": self.department,
            "squad_id": self.squad_id,
            "team_id": self.team_id,
            "authority": self.authority,
            "card_names": self.card_names,
            "capabilities": self.capabilities,
            "skills": self.skills,
            "semantic": self.semantic,
            "a2a": self.a2a,
            "registration": self.registration,
            "identity_invariant": self.identity_invariant,
            "authority_passport": self.authority_passport,
            "living_dock": self.living_dock,
            "nats": self.nats,
            "handoff": self.handoff,
            "sources": self.sources,
            "findings": [finding.to_dict() for finding in self.findings],
            "trust_grade": self.trust_grade,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to build Agent Card semantic links")
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _normalize_alias(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    return text


def _compact_alias(value: Any) -> str:
    return re.sub(r"[-_\s]+", "", _normalize_alias(value))


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _merge_list(target: list[str], values: list[str]) -> None:
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in target:
            target.append(clean)


def _names_from_skill_list(value: Any) -> list[str]:
    names: list[str] = []
    for item in _safe_list(value):
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("id") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _card_profile(card: dict[str, Any]) -> str:
    extended = {"skills", "security_schemes", "signatures", "supported_interfaces", "extensions"}
    if any(key in card for key in extended):
        return "a2a_1_0_extended"
    rich = {"authority", "autonomy_policy", "callsign", "canonical_substrate", "communication_channel"}
    if any(key in card for key in rich):
        return "operator_mirror"
    return "a2a_legacy"


def _semantic_indexes(repo_root: Path) -> dict[str, Any]:
    objects_payload = _load_yaml(repo_root / "docs/ontology/semantic_objects.yaml")
    aliases_payload = _load_yaml(repo_root / "docs/ontology/semantic_aliases.yaml")
    objects = [item for item in _safe_list(objects_payload.get("objects")) if isinstance(item, dict)]
    object_by_id = {str(item.get("id") or ""): item for item in objects if item.get("id")}

    active_aliases: dict[str, str] = {}
    aliases_by_target: dict[str, list[str]] = {}
    for item in _safe_list(aliases_payload.get("aliases")):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "active")
        if status in {"deprecated", "forbidden"}:
            continue
        alias = str(item.get("alias") or "")
        canonical_id = str(item.get("canonical_id") or "")
        if alias and canonical_id:
            norm = _normalize_alias(alias)
            active_aliases[norm] = canonical_id
            aliases_by_target.setdefault(canonical_id, [])
            if alias not in aliases_by_target[canonical_id]:
                aliases_by_target[canonical_id].append(alias)

    forbidden_aliases: dict[str, dict[str, str]] = {}
    for obj in objects:
        canonical_id = str(obj.get("id") or "")
        for alias in _safe_list(obj.get("forbidden_aliases")):
            if alias:
                forbidden_aliases[_normalize_alias(alias)] = {
                    "alias": str(alias),
                    "canonical_id": canonical_id,
                    "reason": "object forbidden_aliases",
                }
    for item in _safe_list(aliases_payload.get("forbidden_aliases")):
        if not isinstance(item, dict):
            continue
        alias = str(item.get("alias") or "")
        if alias:
            forbidden_aliases[_normalize_alias(alias)] = {
                "alias": alias,
                "canonical_id": str(item.get("canonical_id") or ""),
                "reason": str(item.get("reason") or "forbidden alias"),
            }

    return {
        "object_by_id": object_by_id,
        "active_aliases": active_aliases,
        "aliases_by_target": aliases_by_target,
        "forbidden_aliases": forbidden_aliases,
    }


def _resolve_semantic(
    candidates: list[str],
    semantic_indexes: dict[str, Any],
) -> dict[str, Any]:
    active_aliases: dict[str, str] = semantic_indexes["active_aliases"]
    object_by_id: dict[str, dict[str, Any]] = semantic_indexes["object_by_id"]
    aliases_by_target: dict[str, list[str]] = semantic_indexes["aliases_by_target"]

    for candidate in candidates:
        canonical_id = active_aliases.get(_normalize_alias(candidate))
        if not canonical_id:
            continue
        obj = object_by_id.get(canonical_id, {})
        return {
            "canonical_object_id": canonical_id,
            "canonical_name": obj.get("canonical_name", ""),
            "api_name": obj.get("api_name", ""),
            "lifecycle": obj.get("lifecycle", ""),
            "owner_surface": obj.get("owner_surface", ""),
            "source_path": obj.get("source_path", ""),
            "orientation_route": obj.get("orientation_route", ""),
            "aliases": aliases_by_target.get(canonical_id, []),
        }
    return {}


def _forbidden_hits(
    candidates: list[str],
    semantic_indexes: dict[str, Any],
) -> list[dict[str, str]]:
    forbidden_aliases: dict[str, dict[str, str]] = semantic_indexes["forbidden_aliases"]
    hits: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        norm = _normalize_alias(candidate)
        compact = _compact_alias(candidate)
        for key, record in forbidden_aliases.items():
            if norm == key or compact == _compact_alias(key):
                marker = f"{record.get('alias')}:{record.get('canonical_id')}"
                if marker not in seen:
                    seen.add(marker)
                    hits.append(record)
    return hits


def _record_for(records: dict[str, AgentCardProjection], agent_uid: str) -> AgentCardProjection:
    clean = str(agent_uid or "").strip() or "unknown"
    if clean not in records:
        records[clean] = AgentCardProjection(agent_uid=clean)
    return records[clean]


def _card_agent_uid(card: dict[str, Any]) -> str:
    metadata = _safe_dict(card.get("metadata"))
    return str(metadata.get("agent_uid") or card.get("agent_uid") or card.get("agent") or card.get("name") or "").strip()


def _candidate_names_from_card(path: Path, card: dict[str, Any]) -> list[str]:
    metadata = _safe_dict(card.get("metadata"))
    candidates = [
        path.stem,
        str(card.get("name") or ""),
        str(card.get("agent_uid") or ""),
        str(metadata.get("agent_uid") or ""),
        str(metadata.get("display_name") or ""),
        str(metadata.get("callsign") or ""),
    ]
    return [item for item in candidates if item]


def _apply_card(
    records: dict[str, AgentCardProjection],
    path: Path,
    card: dict[str, Any],
    semantic_indexes: dict[str, Any],
) -> None:
    metadata_value = card.get("metadata")
    metadata = _safe_dict(metadata_value)
    agent_uid = _card_agent_uid(card)
    record = _record_for(records, agent_uid)
    record.add_source("a2a_card", path)

    if metadata_value is not None and not isinstance(metadata_value, dict):
        record.add_finding(
            "warning",
            "metadata_not_object",
            path,
            "card metadata should be an object so identity fields survive projection",
        )

    name = str(card.get("name") or path.stem)
    if name and name not in record.card_names:
        record.card_names.append(name)
    record.display_name = record.display_name or str(metadata.get("display_name") or card.get("display_name") or name)
    record.callsign = record.callsign or str(metadata.get("callsign") or card.get("callsign") or name)
    record.role = record.role or str(card.get("role") or metadata.get("role") or "")
    record.status = record.status or str(card.get("status") or metadata.get("status") or "")
    record.endpoint = record.endpoint or str(card.get("endpoint") or "")
    record.provider = record.provider or str(card.get("provider") or metadata.get("llm_provider") or "")
    record.model = record.model or str(card.get("model") or metadata.get("model_identity") or metadata.get("llm_model_declared") or "")
    record.harness = record.harness or str(metadata.get("harness") or card.get("harness") or "")
    record.department = record.department or str(metadata.get("department") or card.get("department") or "")
    record.squad_id = record.squad_id or str(metadata.get("squad_id") or card.get("squad_id") or "")
    record.team_id = record.team_id or str(metadata.get("team_id") or card.get("team_id") or "")
    record.authority = record.authority or str(metadata.get("authority") or card.get("authority") or "")

    skills = _names_from_skill_list(card.get("skills"))
    capabilities = _names_from_skill_list(card.get("capabilities"))
    _merge_list(record.skills, skills)
    _merge_list(record.capabilities, capabilities or skills)

    top_level_keys = sorted(str(key) for key in card.keys())
    metadata_keys = sorted(str(key) for key in metadata.keys())
    record.a2a.update(
        {
            "profile": _card_profile(card),
            "card_count_for_agent": len(record.sources.get("a2a_card", [])),
            "top_level_keys": top_level_keys,
            "metadata_keys": metadata_keys,
            "auth_type": card.get("auth_type", ""),
            "version": card.get("version", ""),
            "created_at": card.get("created_at", ""),
            "updated_at": card.get("updated_at", ""),
            "security_schemes_declared": bool(card.get("security_schemes")),
            "signatures_declared": bool(card.get("signatures")),
            "digest": _sha256_file(path),
        }
    )

    candidates = _candidate_names_from_card(path, card)
    if not record.semantic:
        record.semantic = _resolve_semantic(candidates, semantic_indexes)
    for hit in _forbidden_hits(candidates, semantic_indexes):
        record.add_finding(
            "error",
            "forbidden_live_card_alias",
            path,
            f"{hit.get('alias')!r} is forbidden for {hit.get('canonical_id')}: {hit.get('reason')}",
        )

    nats_subject = (
        metadata.get("canonical_transport_subject")
        or metadata.get("nats_subject")
        or metadata.get("transport_subject")
        or ""
    )
    if not nats_subject and str(card.get("endpoint") or "").startswith("nats://"):
        nats_subject = str(card.get("endpoint")).rsplit("/", 1)[-1]
    if nats_subject:
        record.nats.setdefault("subjects", [])
        if nats_subject not in record.nats["subjects"]:
            record.nats["subjects"].append(nats_subject)


def _registration_files(dharma_home: Path) -> list[Path]:
    return sorted((dharma_home / "external_agents").glob("*/registration.json"))


def _apply_registration(records: dict[str, AgentCardProjection], path: Path) -> None:
    try:
        payload = _load_json(path)
    except Exception as exc:
        record = _record_for(records, path.parent.name)
        record.add_finding("error", "registration_parse", path, type(exc).__name__)
        return
    if not isinstance(payload, dict):
        record = _record_for(records, path.parent.name)
        record.add_finding("error", "registration_shape", path, "registration must be an object")
        return

    agent_uid = str(payload.get("agent_uid") or path.parent.name)
    record = _record_for(records, agent_uid)
    record.add_source("registration", path)
    record.registration = {
        "path": str(path),
        "digest": _sha256_file(path),
        "status": payload.get("status", ""),
        "registration_source": payload.get("registration_source", ""),
        "created_at": payload.get("created_at", ""),
        "updated_at": payload.get("updated_at", ""),
        "autonomy_policy": payload.get("autonomy_policy", {}),
        "workspace_policy": payload.get("workspace_policy", {}),
        "memory_namespace": payload.get("memory_namespace", ""),
        "trace_identity": payload.get("trace_identity", ""),
    }
    record.display_name = str(payload.get("display_name") or record.display_name or agent_uid)
    record.callsign = str(payload.get("callsign") or record.callsign or agent_uid)
    record.role = str(payload.get("role") or record.role or "")
    record.status = str(payload.get("status") or record.status or "")
    record.endpoint = record.endpoint or str(payload.get("endpoint") or "")
    record.model = record.model or str(payload.get("model_identity") or "")
    record.harness = record.harness or str(payload.get("harness") or "")
    record.department = record.department or str(payload.get("department") or "")
    record.squad_id = record.squad_id or str(payload.get("squad_id") or "")
    record.team_id = record.team_id or str(payload.get("team_id") or "")
    record.authority = record.authority or str(payload.get("authority") or "")
    _merge_list(record.capabilities, [str(item) for item in _safe_list(payload.get("capabilities"))])

    invariant = payload.get("identity_invariant")
    if invariant and not record.identity_invariant:
        _apply_identity_invariant(record, path, invariant)


def _apply_identity_invariant(record: AgentCardProjection, path: Path, payload: Any) -> None:
    validation = validate_identity_invariant(payload)
    digest = payload.get("digest") if isinstance(payload, dict) else ""
    record.identity_invariant = {
        "path": str(path),
        "digest": digest,
        "valid": bool(validation.get("valid")),
        "errors": validation.get("errors", []),
        "schema_version": payload.get("schema_version", "") if isinstance(payload, dict) else "",
        "serial": payload.get("serial", "") if isinstance(payload, dict) else "",
        "authority_floor": payload.get("authority_floor", "") if isinstance(payload, dict) else "",
        "memory_namespace": payload.get("memory_namespace", "") if isinstance(payload, dict) else "",
        "trace_identity": payload.get("trace_identity", "") if isinstance(payload, dict) else "",
    }
    if not validation.get("valid"):
        record.add_finding(
            "error",
            "identity_invariant_invalid",
            path,
            "; ".join(str(item) for item in validation.get("errors", [])),
        )


def _apply_identity_invariant_file(records: dict[str, AgentCardProjection], path: Path) -> None:
    try:
        payload = _load_json(path)
    except Exception as exc:
        record = _record_for(records, path.parent.name)
        record.add_finding("error", "identity_invariant_parse", path, type(exc).__name__)
        return
    agent_uid = str(payload.get("agent_uid") or path.parent.name) if isinstance(payload, dict) else path.parent.name
    record = _record_for(records, agent_uid)
    record.add_source("identity_invariant", path)
    _apply_identity_invariant(record, path, payload)


def _apply_passport(records: dict[str, AgentCardProjection], path: Path) -> None:
    try:
        payload = _load_json(path)
    except Exception as exc:
        record = _record_for(records, path.parent.parent.name)
        record.add_finding("warning", "passport_parse", path, type(exc).__name__)
        return
    agent_uid = str(payload.get("agent_uid") or path.parent.parent.name) if isinstance(payload, dict) else path.parent.parent.name
    record = _record_for(records, agent_uid)
    record.add_source("authority_passport", path)
    record.authority_passport = {
        "path": str(path),
        "digest": _sha256_file(path),
        "status": payload.get("status", "") if isinstance(payload, dict) else "",
        "authority": payload.get("authority", "") if isinstance(payload, dict) else "",
        "allowed_capabilities": payload.get("allowed_capabilities", []) if isinstance(payload, dict) else [],
        "gated_capabilities": payload.get("gated_capabilities", []) if isinstance(payload, dict) else [],
        "forbidden_capabilities": payload.get("forbidden_capabilities", []) if isinstance(payload, dict) else [],
    }


def _apply_living_dock(records: dict[str, AgentCardProjection], path: Path) -> None:
    try:
        payload = _load_json(path)
    except Exception:
        payload = {}
    agent_uid = str(payload.get("agent_uid") or path.parent.name) if isinstance(payload, dict) else path.parent.name
    record = _record_for(records, agent_uid)
    record.add_source("living_dock", path)
    record.living_dock = {
        "path": str(path.parent),
        "identity_file": str(path),
        "status": payload.get("status", "") if isinstance(payload, dict) else "",
        "memory_namespace": payload.get("memory_namespace", "") if isinstance(payload, dict) else "",
        "home_dock": payload.get("home_dock", "") if isinstance(payload, dict) else "",
        "exists": True,
    }
    record.display_name = record.display_name or str(payload.get("display_name") or payload.get("callsign") or agent_uid)
    record.callsign = record.callsign or str(payload.get("callsign") or agent_uid)


def _finalize_record(record: AgentCardProjection) -> None:
    if not record.sources.get("a2a_card"):
        record.add_finding(
            "warning",
            "missing_live_a2a_card",
            record.sources.get("registration", [""])[0] if record.sources.get("registration") else "",
            "agent has registration or LivingDock evidence but no live A2A card",
        )
    if len(record.sources.get("a2a_card", [])) > 1:
        record.add_finding(
            "error",
            "duplicate_live_card_agent_uid",
            ", ".join(record.sources.get("a2a_card", [])),
            "multiple live A2A card files resolve to the same agent_uid",
        )
    if not record.semantic:
        record.add_finding(
            "warning",
            "semantic_commons_unresolved",
            ", ".join(record.sources.get("a2a_card", []) or record.sources.get("registration", [])),
            "agent identity did not resolve to a Semantic Commons object",
        )
    if record.registration and record.endpoint and record.registration.get("path"):
        # Endpoint mismatch is advisory because some cards intentionally expose
        # a public contact endpoint while registration stores a local bootstrap.
        pass

    errors = [finding for finding in record.findings if finding.severity == "error"]
    if errors:
        record.trust_grade = "quarantine"
    elif record.sources.get("a2a_card") and record.registration and record.identity_invariant.get("valid") and record.semantic:
        record.trust_grade = "verified"
    elif record.sources.get("a2a_card") and record.registration:
        record.trust_grade = "registered"
    elif record.sources.get("a2a_card"):
        record.trust_grade = "discovery"
    else:
        record.trust_grade = "evidence_only"

    record.handoff = {
        "public_card_ready": bool(record.sources.get("a2a_card")) and record.trust_grade != "quarantine",
        "extended_card_ready": bool(record.registration) and bool(record.identity_invariant),
        "operator_card_ready": bool(record.sources),
        "suggested_subjects": [
            f"dharma.agent_card.{record.agent_uid}.public",
            f"dharma.agent_card.{record.agent_uid}.extended",
            f"dharma.agent_card.{record.agent_uid}.status",
            f"dharma.agent_card.{record.agent_uid}.handoff",
        ],
    }


def build_agent_card_index(
    *,
    repo_root: Path | str,
    dharma_home: Path | str | None = None,
    cards_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Build a read-only Agent Card projection over local identity surfaces."""
    repo = Path(repo_root)
    home = Path(dharma_home) if dharma_home is not None else dharma_state_dir("DHARMA_HOME")
    cards = Path(cards_dir) if cards_dir is not None else home / "a2a" / "cards"
    semantic_indexes = _semantic_indexes(repo)
    records: dict[str, AgentCardProjection] = {}
    global_findings: list[AgentCardFinding] = []
    card_file_count = 0

    if cards.exists():
        for path in sorted(cards.glob("*.json")):
            card_file_count += 1
            try:
                payload = _load_json(path)
            except Exception as exc:
                finding = AgentCardFinding(
                    severity="error",
                    check="card_parse",
                    agent_uid=path.stem,
                    path=str(path),
                    detail=type(exc).__name__,
                )
                global_findings.append(finding)
                continue
            if not isinstance(payload, dict):
                global_findings.append(
                    AgentCardFinding(
                        severity="error",
                        check="card_shape",
                        agent_uid=path.stem,
                        path=str(path),
                        detail="card JSON must be an object",
                    )
                )
                continue
            _apply_card(records, path, payload, semantic_indexes)

    for path in _registration_files(home):
        _apply_registration(records, path)
    for path in sorted((home / "external_agents").glob("*/identity_invariant.json")):
        _apply_identity_invariant_file(records, path)
    for path in sorted((home / "external_agents").glob("*/authority/passport.json")):
        _apply_passport(records, path)
    for root in sorted((home / "agents").glob("*")):
        if not root.is_dir():
            continue
        for filename in ("identity.json", "living_agent.json"):
            path = root / filename
            if path.exists():
                _apply_living_dock(records, path)
                break

    for record in records.values():
        _finalize_record(record)

    projections = sorted(records.values(), key=lambda item: item.agent_uid)
    all_findings = global_findings[:]
    for projection in projections:
        all_findings.extend(projection.findings)

    severity_counts: dict[str, int] = {}
    for finding in all_findings:
        severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "repo_root": str(repo),
        "dharma_home": str(home),
        "cards_dir": str(cards),
        "summary": {
            "status": "fail" if severity_counts.get("error", 0) else "pass",
            "card_file_count": card_file_count,
            "agent_count": len(projections),
            "finding_count": len(all_findings),
            "error_count": severity_counts.get("error", 0),
            "warning_count": severity_counts.get("warning", 0),
            "severity_counts": severity_counts,
            "trust_grade_counts": _count_by([item.trust_grade for item in projections]),
        },
        "agents": [projection.to_dict() for projection in projections],
        "findings": [finding.to_dict() for finding in all_findings],
    }


def _count_by(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def render_agent_card_index_markdown(index: dict[str, Any]) -> str:
    summary = _safe_dict(index.get("summary"))
    lines = [
        "# Agent Card Meishi Index",
        "",
        f"Generated: `{index.get('generated_at', '')}`",
        f"Status: `{summary.get('status', '')}`",
        f"Cards: `{summary.get('card_file_count', 0)}`",
        f"Agents: `{summary.get('agent_count', 0)}`",
        f"Findings: `{summary.get('finding_count', 0)}`",
        "",
        "## Agents",
        "",
        "| Agent | Display | Role | Status | Trust | Card Sources | Registration | Semantic |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for agent in _safe_list(index.get("agents")):
        if not isinstance(agent, dict):
            continue
        sources = _safe_dict(agent.get("sources"))
        semantic = _safe_dict(agent.get("semantic"))
        lines.append(
            "| {agent_uid} | {display_name} | {role} | {status} | {trust} | {cards} | {registration} | {semantic} |".format(
                agent_uid=agent.get("agent_uid", ""),
                display_name=agent.get("display_name", ""),
                role=agent.get("role", ""),
                status=agent.get("status", ""),
                trust=agent.get("trust_grade", ""),
                cards=len(_safe_list(sources.get("a2a_card"))),
                registration="yes" if sources.get("registration") else "no",
                semantic=semantic.get("canonical_object_id", "") or "unresolved",
            )
        )
    lines.extend(["", "## Findings", ""])
    findings = [item for item in _safe_list(index.get("findings")) if isinstance(item, dict)]
    if not findings:
        lines.append("No findings.")
    else:
        lines.append("| Severity | Check | Agent | Detail |")
        lines.append("| --- | --- | --- | --- |")
        for finding in findings:
            detail = str(finding.get("detail", "")).replace("|", "\\|")
            lines.append(
                f"| {finding.get('severity', '')} | {finding.get('check', '')} | {finding.get('agent_uid', '')} | {detail} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_agent_card_index_reports(index: dict[str, Any], out_dir: Path | str) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    index_path = out / "index.json"
    findings_path = out / "findings.json"
    markdown_path = out / "index.md"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    findings_path.write_text(
        json.dumps(index.get("findings", []), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_agent_card_index_markdown(index), encoding="utf-8")
    return {
        "index_json": str(index_path),
        "findings_json": str(findings_path),
        "index_markdown": str(markdown_path),
    }

