#!/usr/bin/env python3
"""Fleet field registry reader — secret-free multi-authority runtime-cell view.

Prints uid, transport tier, semantic/effect ceiling, and readiness for every
registered agent from docs/ops/FLEET_FIELD_REGISTRY.yaml (schema v2).

Usage:
    python3 scripts/runtime/fleet_field_registry.py            # field table
    python3 scripts/runtime/fleet_field_registry.py --check    # validate (exit 2)
    python3 scripts/runtime/fleet_field_registry.py --json     # machine dump

--check enforces multi-authority records, Universal Agent Runtime Cell shape,
UID/subject/durable uniqueness, env-var-names-only secret policy, and
fail-closed readiness ceilings. No network calls; never prints secret values.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "docs/ops/FLEET_FIELD_REGISTRY.yaml"
SCHEMA_V2 = "dharma_fleet_field_registry.v2"

RUNTIME_CELL_COMPONENTS: tuple[str, ...] = (
    "agent_uid",
    "canonical_inbox_subject",
    "durable_consumer",
    "credential_principal",
    "delivery_runtime",
    "semantic_executor_mode",
    "idempotent_effect_boundary",
    "receipt_lifecycle",
    "large_artifact_lane",
    "observability_projection",
)
REQUIRED_AGENT_FIELDS = (
    "agent_uid", "runtime", "lanes_available", "primary_lane", "live_on_hub",
    "credential_env_names", "listen_subjects", "publish_subjects", "git_seat",
    "last_verified_send", "last_verified_receive", "runtime_cell",
    "transport_contact_tier", "semantic_effect_ceiling", "readiness_ceiling",
)
KNOWN_LANES = {
    "agni_hub_wss", "agni_hub_nats", "local_nats_4222", "meghadharma_nats",
    "git_seat", "operator_relay", "none",
}
AUTHORITY_ROLES = {
    "source_compatibility", "local_operator", "candidate_reference",
    "cutover_target_gated", "compatibility", "reference",
}
EVIDENCE_STATUSES = {
    "probe_backed", "probe_backed_2026_07_09", "runtime_observed_uncommitted",
    "declared", "unprobed", "reference_gap", "unknown",
}
COMPONENT_STATUSES = {
    "unknown", "unprobed", "declared", "probed", "absent",
    "runtime_observed_uncommitted",
}
SEMANTIC_EXECUTOR_MODES = {
    "always_on", "event_driven", "manual_seat", "none", "unknown", "absent",
}
TIER_ORDER: tuple[str, ...] = (
    "unprobed", "PUBLISH_ACCEPTED", "DELIVERED_TO_CONSUMER", "HANDLER_ACKED",
    "PROCESSED", "EFFECT_COMMITTED", "DOMAIN_RECEIPTED",
)
SEMANTIC_TIERS = frozenset({"PROCESSED", "EFFECT_COMMITTED", "DOMAIN_RECEIPTED"})
DELIVERY_DRAIN_CEILING = "HANDLER_ACKED"
NO_SEMANTIC_MODES = frozenset({"none", "unknown", "absent", ""})
NON_CLAIMING = frozenset({"", "null", "none", "None", "unknown", "~"})
RECEIPT_OPTIONAL_EVIDENCE = frozenset({
    "runtime_observed_uncommitted", "reference_gap", "unprobed", "unknown",
})
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
SECRET_VALUE_RE = re.compile(
    r"(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S", re.IGNORECASE
)


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    import yaml

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("registry did not parse to a mapping")
    return data


def _tier_rank(tier: str | None) -> int | None:
    if tier is None:
        return None
    text = str(tier).strip()
    if text in {"", "unknown"}:
        return None
    try:
        return TIER_ORDER.index(text)
    except ValueError:
        return None


def _min_tier(*tiers: str | None) -> str:
    ranks: list[int] = []
    for tier in tiers:
        if tier is None or str(tier).strip() in {"", "unknown"}:
            return "unknown"
        rank = _tier_rank(str(tier).strip())
        if rank is None:
            return "unknown"
        ranks.append(rank)
    return TIER_ORDER[min(ranks)] if ranks else "unknown"


def _cap_tier(tier: str, ceiling: str) -> str:
    if tier in {"unknown", "unprobed"}:
        return tier
    t_rank, c_rank = _tier_rank(tier), _tier_rank(ceiling)
    if t_rank is None or c_rank is None:
        return "unknown"
    return TIER_ORDER[min(t_rank, c_rank)]


def compute_readiness_ceiling(
    *,
    component_statuses: dict[str, str],
    semantic_executor_mode: str,
    transport_contact_tier: str,
    semantic_effect_ceiling: str,
) -> str:
    """Fail-closed readiness: min proven tier; delivery alone ≤ HANDLER_ACKED."""
    mode = (semantic_executor_mode or "unknown").strip().lower()
    transport = (transport_contact_tier or "unknown").strip()
    effect = (semantic_effect_ceiling or "unknown").strip()
    if transport in {"", "unknown"}:
        return "unknown"
    transport_capped = _cap_tier(transport, DELIVERY_DRAIN_CEILING)
    if mode in NO_SEMANTIC_MODES:
        if effect in {"", "unknown"}:
            return transport_capped
        return _min_tier(transport_capped, _cap_tier(effect, DELIVERY_DRAIN_CEILING))
    if effect in {"", "unknown"}:
        return transport_capped
    if component_statuses and any(
        component_statuses.get(k) == "unknown"
        for k in ("agent_uid", "canonical_inbox_subject", "durable_consumer")
    ):
        return "unknown"
    return _min_tier(transport_capped, effect)


def _component_status(node: Any) -> str | None:
    if isinstance(node, dict):
        status = node.get("status")
        return str(status) if status is not None else None
    return None if node is None else str(node)


def _component_value(agent: dict, name: str) -> Any:
    cell = agent.get("runtime_cell")
    if not isinstance(cell, dict):
        return None
    comps = cell.get("components")
    if not isinstance(comps, dict):
        return None
    node = comps.get(name)
    return node.get("value") if isinstance(node, dict) else None


def _is_claiming_identity(value: Any) -> bool:
    return value is not None and str(value).strip() not in NON_CLAIMING


def _scan_secrets(node: object, trail: str, errors: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _scan_secrets(value, f"{trail}.{key}", errors)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _scan_secrets(item, f"{trail}[{index}]", errors)
    elif isinstance(node, str) and SECRET_VALUE_RE.search(node):
        errors.append(f"possible secret value at {trail}: {node[:40]!r}...")


def _validate_authorities(data: dict, errors: list[str]) -> None:
    authorities = data.get("authorities")
    if not isinstance(authorities, list) or len(authorities) < 2:
        errors.append("authorities must be a list of at least two authority records")
        return
    seen: set[str] = set()
    for index, auth in enumerate(authorities):
        if not isinstance(auth, dict):
            errors.append(f"authorities[{index}]: entry is not a mapping")
            continue
        aid = auth.get("authority_id")
        if not aid:
            errors.append(f"authorities[{index}]: missing authority_id")
            continue
        aid_s = str(aid)
        if aid_s in seen:
            errors.append(f"duplicate authority_id {aid_s!r}")
        seen.add(aid_s)
        role = auth.get("role")
        if not role:
            errors.append(f"authority {aid_s}: missing role")
        elif str(role) not in AUTHORITY_ROLES:
            errors.append(f"authority {aid_s}: unknown role {role!r}")
        evidence = auth.get("evidence_status")
        if not evidence:
            errors.append(f"authority {aid_s}: missing evidence_status")
        elif str(evidence) not in EVIDENCE_STATUSES:
            errors.append(f"authority {aid_s}: unknown evidence_status {evidence!r}")


def _validate_runtime_cell_contract(data: dict, errors: list[str]) -> None:
    contract = data.get("runtime_cell_contract")
    if not isinstance(contract, dict):
        errors.append("runtime_cell_contract must be a mapping")
        return
    components = contract.get("components")
    if not isinstance(components, list):
        errors.append("runtime_cell_contract.components must be a list")
        return
    if set(components) != set(RUNTIME_CELL_COMPONENTS):
        errors.append(
            "runtime_cell_contract.components must equal the ten Universal "
            f"Agent Runtime Cell components; got {components!r}"
        )
    if contract.get("delivery_drain_ceiling") != DELIVERY_DRAIN_CEILING:
        errors.append(
            f"runtime_cell_contract.delivery_drain_ceiling must be {DELIVERY_DRAIN_CEILING!r}"
        )


def _validate_agent_runtime_cell(uid: str, agent: dict, errors: list[str]) -> None:
    cell = agent.get("runtime_cell")
    if not isinstance(cell, dict):
        errors.append(f"{uid}: runtime_cell must be a mapping")
        return
    comps = cell.get("components")
    if not isinstance(comps, dict):
        errors.append(f"{uid}: runtime_cell.components must be a mapping")
        return
    for name in RUNTIME_CELL_COMPONENTS:
        if name not in comps:
            errors.append(f"{uid}: runtime_cell missing component {name!r}")
            continue
        node = comps[name]
        if not isinstance(node, dict):
            errors.append(f"{uid}: runtime_cell.components.{name} must be a mapping")
            continue
        status = node.get("status")
        if not status:
            errors.append(f"{uid}: runtime_cell.components.{name} missing status")
        elif str(status) not in COMPONENT_STATUSES:
            errors.append(
                f"{uid}: runtime_cell.components.{name} unknown status {status!r}"
            )
    for field in ("transport_contact_tier", "semantic_effect_ceiling", "readiness_ceiling"):
        if not cell.get(field):
            errors.append(f"{uid}: runtime_cell missing {field}")
        if not agent.get(field):
            errors.append(f"{uid}: missing top-level {field}")


def _validate_semantic_ceiling(uid: str, agent: dict, errors: list[str]) -> None:
    mode = str(
        agent.get("semantic_executor_mode")
        or _component_value(agent, "semantic_executor_mode")
        or "unknown"
    ).strip().lower()
    effect = str(agent.get("semantic_effect_ceiling") or "unknown").strip()
    cell = agent.get("runtime_cell") if isinstance(agent.get("runtime_cell"), dict) else {}
    cell_effect = str(cell.get("semantic_effect_ceiling") or effect).strip()
    readiness = str(agent.get("readiness_ceiling") or "unknown").strip()
    if mode not in NO_SEMANTIC_MODES:
        return
    for label, tier in (
        ("semantic_effect_ceiling", effect),
        ("runtime_cell.semantic_effect_ceiling", cell_effect),
        ("readiness_ceiling", readiness),
    ):
        if tier in SEMANTIC_TIERS:
            errors.append(
                f"{uid}: {label}={tier!r} requires a declared semantic "
                f"executor; mode is {mode!r} (delivery drain caps at "
                f"{DELIVERY_DRAIN_CEILING})"
            )


def _validate_uniqueness(agents: list, errors: list[str]) -> None:
    seen_uids: dict[str, int] = {}
    seen_subjects: dict[str, str] = {}
    seen_durables: dict[str, str] = {}
    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            continue
        uid = str(agent.get("agent_uid", f"<missing:{index}>"))
        if uid in seen_uids:
            errors.append(f"{uid}: duplicate agent_uid")
        seen_uids[uid] = index
        subject = agent.get("canonical_inbox_subject")
        if subject is None:
            subject = _component_value(agent, "canonical_inbox_subject")
        if _is_claiming_identity(subject):
            subject_s = str(subject).strip()
            prior = seen_subjects.get(subject_s)
            if prior is not None and prior != uid:
                errors.append(
                    f"{uid}: duplicate canonical_inbox_subject {subject_s!r} "
                    f"(also claimed by {prior})"
                )
            else:
                seen_subjects[subject_s] = uid
        durable = agent.get("durable_consumer")
        if durable is None:
            durable = _component_value(agent, "durable_consumer")
        if _is_claiming_identity(durable):
            durable_s = str(durable).strip()
            prior = seen_durables.get(durable_s)
            if prior is not None and prior != uid:
                errors.append(
                    f"{uid}: duplicate durable_consumer {durable_s!r} "
                    f"(also claimed by {prior})"
                )
            else:
                seen_durables[durable_s] = uid


def validate(data: dict, *, repo_root: Path = REPO_ROOT) -> list[str]:
    """Return a list of violations; empty means the registry is valid."""
    errors: list[str] = []
    if data.get("schema") != SCHEMA_V2:
        errors.append(f"schema must be {SCHEMA_V2!r}, got {data.get('schema')!r}")
    if data.get("secret_policy") != "env_var_names_only":
        errors.append("secret_policy must be 'env_var_names_only'")
    _validate_authorities(data, errors)
    _validate_runtime_cell_contract(data, errors)

    agents = data.get("agents")
    if not isinstance(agents, list) or not agents:
        return errors + ["agents must be a non-empty list"]

    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            errors.append(
                f"agents[{index}]: entry is not a mapping ({type(agent).__name__})"
            )
            continue
        uid = str(agent.get("agent_uid", "<missing uid>"))
        for field in REQUIRED_AGENT_FIELDS:
            if field not in agent:
                errors.append(f"{uid}: missing required field {field!r}")
        for lane in agent.get("lanes_available", []) or []:
            if lane not in KNOWN_LANES:
                errors.append(f"{uid}: unknown lane {lane!r}")
        primary = agent.get("primary_lane")
        if primary is not None and primary not in KNOWN_LANES:
            errors.append(f"{uid}: unknown primary_lane {primary!r}")
        for name in agent.get("credential_env_names", []) or []:
            if not ENV_NAME_RE.match(str(name)):
                errors.append(
                    f"{uid}: credential_env_names entry {name!r} is not an "
                    "ALL_CAPS env var name (values are forbidden here)"
                )
        evidence = str(agent.get("evidence_status") or "probe_backed")
        receipt = agent.get("probe_receipt")
        if receipt:
            if not (repo_root / str(receipt)).exists():
                errors.append(f"{uid}: probe_receipt path does not exist: {receipt}")
        elif evidence not in RECEIPT_OPTIONAL_EVIDENCE:
            errors.append(f"{uid}: missing required field 'probe_receipt'")
        mode = agent.get("semantic_executor_mode")
        if mode is not None and str(mode).strip().lower() not in SEMANTIC_EXECUTOR_MODES:
            errors.append(f"{uid}: unknown semantic_executor_mode {mode!r}")
        _validate_agent_runtime_cell(uid, agent, errors)
        _validate_semantic_ceiling(uid, agent, errors)

        cell = agent.get("runtime_cell") if isinstance(agent.get("runtime_cell"), dict) else {}
        comps = cell.get("components") if isinstance(cell.get("components"), dict) else {}
        statuses = {
            name: (_component_status(comps.get(name)) or "unknown")
            for name in RUNTIME_CELL_COMPONENTS
        }
        expected = compute_readiness_ceiling(
            component_statuses=statuses,
            semantic_executor_mode=str(
                agent.get("semantic_executor_mode")
                or _component_value(agent, "semantic_executor_mode")
                or "unknown"
            ),
            transport_contact_tier=str(agent.get("transport_contact_tier") or "unknown"),
            semantic_effect_ceiling=str(agent.get("semantic_effect_ceiling") or "unknown"),
        )
        declared = str(agent.get("readiness_ceiling") or "unknown")
        exp_rank, dec_rank = _tier_rank(expected), _tier_rank(declared)
        if declared != "unknown" and expected == "unknown":
            errors.append(
                f"{uid}: readiness_ceiling {declared!r} overclaims when "
                f"computed ceiling is unknown"
            )
        elif exp_rank is not None and dec_rank is not None and dec_rank > exp_rank:
            errors.append(
                f"{uid}: readiness_ceiling {declared!r} exceeds fail-closed "
                f"computed ceiling {expected!r}"
            )

    _validate_uniqueness(agents, errors)
    _scan_secrets(data, "$", errors)
    return errors


def render_table(data: dict) -> str:
    """Render multi-authority + per-agent transport/semantic ceilings honestly."""
    authorities = data.get("authorities") or []
    if isinstance(authorities, list) and authorities:
        auth_bits = []
        for auth in authorities:
            if not isinstance(auth, dict):
                continue
            auth_bits.append(
                f"{auth.get('authority_id', '?')}[{auth.get('role', '?')}/"
                f"{auth.get('evidence_status', '?')}]"
            )
        auth_line = "authorities: " + ", ".join(auth_bits)
    else:
        hub = data.get("hub") or {}
        auth_line = f"hub {hub.get('name', '?')} stream {hub.get('live_stream', '?')}"

    rows = [("AGENT", "TRANSPORT", "SEM/EFFECT", "READINESS", "SEM-MODE", "LISTEN")]
    for agent in data.get("agents", []) or []:
        if not isinstance(agent, dict):
            continue
        listen = agent.get("listen_subjects") or ["-"]
        listen0 = str(listen[0]) if listen else "-"
        rows.append((
            str(agent.get("agent_uid", "?")),
            str(agent.get("transport_contact_tier", "unknown")),
            str(agent.get("semantic_effect_ceiling", "unknown")),
            str(agent.get("readiness_ceiling", "unknown")),
            str(agent.get("semantic_executor_mode", "unknown")),
            listen0[:40],
        ))
    widths = [max(len(row[col]) for row in rows) for col in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows]
    header = (
        f"Fleet field registry v2 (updated {data.get('updated', '?')}) — {auth_line}\n"
        "Tiers are fail-closed; unknown is not green; delivery alone ≤ HANDLER_ACKED.\n"
    )
    unprobed = data.get("unprobed_identities") or []
    footer = (
        f"\n{len(unprobed)} known identities unprobed; "
        "full detail: docs/ops/FLEET_FIELD_REGISTRY.yaml"
    )
    return header + "\n".join(lines) + footer


def main(argv: list[str]) -> int:
    data = load_registry()
    if "--check" in argv:
        errors = validate(data)
        if errors:
            for error in errors:
                print(f"[registry-check] {error}", file=sys.stderr)
            return 2
        n_auth = len(data.get("authorities") or [])
        print(
            f"[registry-check] OK — schema {SCHEMA_V2}, "
            f"{len(data['agents'])} agents, {n_auth} authorities, secret policy holds"
        )
        return 0
    if "--json" in argv:
        print(json.dumps(data, indent=2, default=str))
        return 0
    print(render_table(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
