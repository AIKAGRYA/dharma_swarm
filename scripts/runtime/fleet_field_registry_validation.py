"""Fleet field registry validation — structural/secret/route/receipt/agent checks."""
from __future__ import annotations
import hashlib
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from scripts.runtime.fleet_field_registry_contract import (
    API_TOKEN_SHAPE_RE, AUTHORITY_ROLES, BEARER_RE, COMPAT_ROUTE_FIELDS, COMPONENT_STATUSES,
    DELIVERY_DRAIN_CEILING, DURABLE_RE, ENV_NAME_FIELDS, ENV_NAME_RE, EVIDENCE_STATUSES,
    FRESHNESS_MAX_DAYS, IDENTITY_SOURCES, INLINE_SECRET_ASSIGN_RE, JWT_RE, KNOWN_LANES,
    NO_SEMANTIC_MODES, PRIVATE_KEY_RE, PROOF_STATUSES, RECEIPT_OPTIONAL_EVIDENCE,
    REQUIRED_AGENT_FIELDS, ROUTE_KEYS, ROUTE_PROOF_COMPONENTS, RUNTIME_CELL_COMPONENTS, SCHEMA_V2,
    SEMANTIC_EXECUTOR_MODES,
    SEMANTIC_TIERS, SHA256_RE, SUBJECT_TOKEN_RE, TIER_FIELDS, UID_RE, compute_readiness_ceiling,
    load_card_declared_routes, load_expected_identity_uids, _tier_rank,
    _component_value, _claiming, _norm, _is_secret_key,
)
def _validate_uid(uid, errors, *, label):
    if not uid or str(uid).startswith("<"):
        errors.append(f"{label}: missing or invalid agent_uid")
        return
    text = str(uid)
    if any(ch.isspace() for ch in text) or "*" in text or ">" in text:
        errors.append(f"{label}: agent_uid has whitespace or wildcards")
    if not UID_RE.match(text):
        errors.append(f"{label}: agent_uid fails stable UID grammar")
def _validate_subject(subject, errors, *, label):
    if any(ch.isspace() for ch in subject):
        errors.append(f"{label}: subject contains whitespace")
        return
    if subject.startswith(".") or subject.endswith(".") or ".." in subject:
        errors.append(f"{label}: subject has malformed separators")
        return
    tokens = subject.split(".")
    if not tokens or any(t == "" for t in tokens):
        errors.append(f"{label}: subject has empty tokens")
        return
    for token in tokens:
        if token in {"*", ">"}:
            errors.append(f"{label}: exact inbox subject must not use wildcards")
            return
        if not SUBJECT_TOKEN_RE.match(token):
            errors.append(f"{label}: subject token invalid for NATS grammar")
            return
def _validate_durable(durable, errors, *, label):
    if any(ch.isspace() for ch in durable) or any(ch in durable for ch in ".* >/\\"):
        errors.append(f"{label}: durable has whitespace or forbidden characters")
        return
    if not DURABLE_RE.match(durable):
        errors.append(f"{label}: durable fails durable grammar")
def _scan_env_names(node, trail, errors):
    if isinstance(node, list):
        for i, item in enumerate(node):
            _scan_env_names(item, f"{trail}[{i}]", errors)
    elif isinstance(node, str):
        if not ENV_NAME_RE.match(node):
            errors.append(f"{trail}: env-var-name field must be ALL_CAPS name (value redacted)")
    elif node is not None:
        errors.append(f"{trail}: env-var-name field has non-string entry")
def _scan_secrets(node, trail, errors, *, parent_key=""):
    if isinstance(node, dict):
        for key, value in node.items():
            key_s = str(key)
            in_env = parent_key in ENV_NAME_FIELDS or key_s in ENV_NAME_FIELDS
            if _is_secret_key(key_s) and not in_env:
                errors.append(f"secret-bearing key under {trail} (key/value redacted)")
                child = f"{trail}.<redacted>"
            else:
                child = f"{trail}.{key_s}"
            if key_s in ENV_NAME_FIELDS or parent_key in ENV_NAME_FIELDS:
                _scan_env_names(value, child, errors)
            else:
                _scan_secrets(value, child, errors, parent_key=key_s)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _scan_secrets(item, f"{trail}[{i}]", errors, parent_key=parent_key)
    elif isinstance(node, str) and parent_key not in ENV_NAME_FIELDS:
        if JWT_RE.search(node) or BEARER_RE.search(node) or PRIVATE_KEY_RE.search(node):
            errors.append(f"high-confidence secret value shape at {trail} (value redacted)")
        elif API_TOKEN_SHAPE_RE.search(node):
            errors.append(f"high-confidence API-token shape at {trail} (value redacted)")
        elif INLINE_SECRET_ASSIGN_RE.search(node):
            errors.append(f"secret-bearing assignment shape at {trail} (value redacted)")
def _validate_receipt_path(label, receipt, *, repo_root, errors, field="probe_receipt"):
    if not isinstance(receipt, str) or not receipt.strip():
        errors.append(f"{label}: {field} must be a non-empty string path")
        return None
    if receipt.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", receipt):
        errors.append(f"{label}: {field} must be repo-relative (absolute rejected)")
        return None
    if "\\" in receipt or any(p == ".." for p in Path(receipt).parts):
        errors.append(f"{label}: {field} path traversal or backslash rejected")
        return None
    cand = repo_root / receipt
    if cand.is_symlink():
        errors.append(f"{label}: {field} symlink rejected")
        return None
    try:
        full = cand.resolve()
        full.relative_to(repo_root.resolve())
    except ValueError:
        kind = "symlink escapes" if cand.is_symlink() else "escapes"
        errors.append(f"{label}: {field} {kind} repository root")
        return None
    if not full.exists():
        errors.append(f"{label}: {field} path does not exist")
        return None
    if not full.is_file() or full.is_symlink():
        errors.append(f"{label}: {field} is not a regular file")
        return None
    try:
        _g = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", receipt],
            check=False, capture_output=True, text=True)
        tracked = _g.returncode == 0
    except OSError:
        tracked = False
    if not tracked:
        errors.append(f"{label}: {field} is not git-tracked")
        return None
    return full
def _validate_proof_evidence(label, uid, agent, *, repo_root, errors):
    proof = agent.get("proof_evidence")
    if proof is None:
        return False
    if not isinstance(proof, dict):
        errors.append(f"{label}: proof_evidence must be a mapping")
        return False
    if str(proof.get("agent_uid") or "") != uid:
        errors.append(f"{label}: proof_evidence.agent_uid mismatch")
    observed_at = proof.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.strip():
        errors.append(f"{label}: proof_evidence.observed_at required")
        return False
    try:
        ts = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        errors.append(f"{label}: proof_evidence.observed_at is not ISO-8601")
        return False
    now = datetime.now(timezone.utc)
    if ts > now:
        errors.append(f"{label}: proof_evidence.observed_at is in the future")
        return False
    if (now - ts).total_seconds() / 86400.0 > FRESHNESS_MAX_DAYS:
        errors.append(f"{label}: proof_evidence is stale (>{FRESHNESS_MAX_DAYS}d)")
        return False
    claimed = proof.get("claimed_tier")
    if claimed is None or str(claimed).strip() in {"", "unknown"} or _tier_rank(str(claimed)) is None:
        errors.append(f"{label}: proof_evidence.claimed_tier missing/invalid")
        return False
    readiness = str(agent.get("readiness_ceiling") or "unknown")
    if readiness not in {"unknown", "unprobed"} and readiness != str(claimed):
        errors.append(f"{label}: readiness_ceiling mismatches proof_evidence.claimed_tier")
    artifact_path = proof.get("artifact_path")
    if not isinstance(artifact_path, str):
        errors.append(f"{label}: proof_evidence.artifact_path required")
        return False
    full = _validate_receipt_path(label, artifact_path, repo_root=repo_root, errors=errors, field="proof_evidence.artifact_path")
    if full is None:
        return False
    artifact_sha = proof.get("artifact_sha256")
    if not isinstance(artifact_sha, str) or not SHA256_RE.match(artifact_sha):
        errors.append(f"{label}: proof_evidence.artifact_sha256 must be 64 hex chars")
        return False
    if hashlib.sha256(full.read_bytes()).hexdigest().lower() != artifact_sha.lower():
        errors.append(f"{label}: proof_evidence.artifact_sha256 mismatch")
        return False
    return True
def _validate_route_block(label, route, *, route_label, errors):
    if not isinstance(route, dict):
        errors.append(f"{label}: {route_label} must be a mapping")
        return
    for key in ROUTE_KEYS:
        if key not in route:
            errors.append(f"{label}: {route_label} missing {key}")
        elif route[key] is not None and not isinstance(route[key], str):
            errors.append(f"{label}: {route_label}.{key} must be a string or null")
    if isinstance(route.get("inbox_subject"), str) and _claiming(route["inbox_subject"]):
        _validate_subject(route["inbox_subject"].strip(), errors, label=f"{label}:{route_label}.inbox_subject")
    if isinstance(route.get("durable_consumer"), str) and _claiming(route["durable_consumer"]):
        _validate_durable(route["durable_consumer"].strip(), errors, label=f"{label}:{route_label}.durable_consumer")
def _validate_agent_cell(label, agent, errors):
    statuses = {}
    cell = agent.get("runtime_cell")
    if not isinstance(cell, dict):
        errors.append(f"{label}: runtime_cell must be a mapping")
        return statuses
    comps = cell.get("components")
    if not isinstance(comps, dict):
        errors.append(f"{label}: runtime_cell.components must be a mapping")
        return statuses
    for name in RUNTIME_CELL_COMPONENTS:
        if name not in comps:
            errors.append(f"{label}: runtime_cell missing component {name}")
            statuses[name] = "unknown"
            continue
        node = comps[name]
        if not isinstance(node, dict):
            errors.append(f"{label}: runtime_cell.components.{name} must be a mapping")
            statuses[name] = "unknown"
            continue
        status = node.get("status")
        if not status:
            errors.append(f"{label}: runtime_cell.components.{name} missing status")
            statuses[name] = "unknown"
        elif str(status) not in COMPONENT_STATUSES:
            errors.append(f"{label}: runtime_cell.components.{name} unknown status")
            statuses[name] = "unknown"
        else:
            statuses[name] = str(status)
    for field in TIER_FIELDS:
        if not cell.get(field):
            errors.append(f"{label}: runtime_cell missing {field}")
        top, nested = agent.get(field), cell.get(field)
        if top is not None and nested is not None and str(top) != str(nested):
            errors.append(f"{label}: top-level {field} != runtime_cell.{field}")
    return statuses
def _bind_runtime_cell_values(label, agent, errors):
    cell = agent.get("runtime_cell")
    if not isinstance(cell, dict):
        return
    comps = cell.get("components")
    if not isinstance(comps, dict):
        return
    obs = agent.get("observed_effective_route") if isinstance(agent.get("observed_effective_route"), dict) else {}
    quarantined = obs.get("collision_ref") is not None
    node = comps.get("agent_uid")
    if isinstance(node, dict) and (str(node.get("status") or "") in PROOF_STATUSES or _claiming(node.get("value"))):
        if _norm(node.get("value")) != _norm(agent.get("agent_uid")):
            errors.append(f"{label}: runtime_cell.components.agent_uid value must equal agent_uid")
    node = comps.get("semantic_executor_mode")
    if isinstance(node, dict) and (str(node.get("status") or "") in PROOF_STATUSES or _claiming(node.get("value"))):
        if _norm(node.get("value")) != _norm(agent.get("semantic_executor_mode")):
            errors.append(f"{label}: runtime_cell.components.semantic_executor_mode value must equal top-level semantic_executor_mode")
    for comp_name, route_key in ROUTE_PROOF_COMPONENTS.items():
        node = comps.get(comp_name)
        if not isinstance(node, dict):
            continue
        status, val = str(node.get("status") or ""), node.get("value")
        if quarantined:
            if status in PROOF_STATUSES:
                errors.append(f"{label}: runtime_cell.components.{comp_name} cannot be probed under collision quarantine")
            if _claiming(val):
                errors.append(f"{label}: runtime_cell.components.{comp_name} cannot claim value under collision quarantine")
            continue
        if status not in PROOF_STATUSES:
            continue
        obs_val = obs.get(route_key)
        if not _claiming(obs_val):
            errors.append(f"{label}: runtime_cell.components.{comp_name} probed requires non-null observed_effective_route.{route_key}")
        elif _norm(val) != _norm(obs_val):
            errors.append(f"{label}: runtime_cell.components.{comp_name} value must equal observed_effective_route.{route_key}")
def _validate_observed_authority(label, agent, authority_ids, errors):
    obs = agent.get("observed_effective_route")
    if not isinstance(obs, dict):
        return
    if "authority_id" not in obs:
        errors.append(f"{label}: observed_effective_route missing authority_id")
        return
    obs_aid, quarantined = obs.get("authority_id"), obs.get("collision_ref") is not None
    binding = any(_claiming(obs.get(k)) for k in ROUTE_KEYS)
    if quarantined:
        if _claiming(obs_aid) and authority_ids and str(obs_aid) not in authority_ids:
            errors.append(f"{label}: observed_effective_route.authority_id unknown under quarantine")
        return
    if binding:
        if not _claiming(obs_aid):
            errors.append(f"{label}: observed_effective_route.authority_id required for non-null observed worker binding")
        elif authority_ids and str(obs_aid) not in authority_ids:
            errors.append(f"{label}: observed_effective_route.authority_id not in authorities")
        else:
            agent_aid = agent.get("authority_id")
            if agent_aid is not None and str(agent_aid) != str(obs_aid):
                errors.append(f"{label}: observed_effective_route.authority_id mismatches agent authority_id")
    elif _claiming(obs_aid) and authority_ids and str(obs_aid) not in authority_ids:
        errors.append(f"{label}: observed_effective_route.authority_id not in authorities")
def validate_registry(data, *, repo_root):
    if not isinstance(data, dict):
        return ["registry root must be a mapping"]
    errors = []
    if data.get("schema") != SCHEMA_V2:
        errors.append("schema must equal dharma_fleet_field_registry.v2 constant")
    if data.get("secret_policy") != "env_var_names_only":
        errors.append("secret_policy must be 'env_var_names_only'")
    authorities, authority_ids = data.get("authorities"), set()
    if not isinstance(authorities, list) or len(authorities) < 2:
        errors.append("authorities must be a list of at least two authority records")
    else:
        for i, auth in enumerate(authorities):
            alabel = f"authorities[{i}]"
            if not isinstance(auth, dict):
                errors.append(f"{alabel}: entry is not a mapping")
                continue
            aid = auth.get("authority_id")
            if not aid or not isinstance(aid, str):
                errors.append(f"{alabel}: missing authority_id")
                continue
            if aid in authority_ids:
                errors.append(f"{alabel}: duplicate authority_id")
            authority_ids.add(aid)
            role, evidence = auth.get("role"), auth.get("evidence_status")
            if not role:
                errors.append(f"{alabel}: missing role")
            elif str(role) not in AUTHORITY_ROLES:
                errors.append(f"{alabel}: unknown role")
            if not evidence:
                errors.append(f"{alabel}: missing evidence_status")
            elif str(evidence) not in EVIDENCE_STATUSES:
                errors.append(f"{alabel}: unknown evidence_status")
    contract = data.get("runtime_cell_contract")
    if not isinstance(contract, dict):
        errors.append("runtime_cell_contract must be a mapping")
    else:
        comps = contract.get("components")
        if not isinstance(comps, list):
            errors.append("runtime_cell_contract.components must be a list")
        elif set(comps) != set(RUNTIME_CELL_COMPONENTS):
            errors.append("runtime_cell_contract.components must equal the ten cell components")
        if contract.get("delivery_drain_ceiling") != DELIVERY_DRAIN_CEILING:
            errors.append(f"runtime_cell_contract.delivery_drain_ceiling must be {DELIVERY_DRAIN_CEILING}")
    agents = data.get("agents")
    if not isinstance(agents, list) or not agents:
        errors.append("agents must be a non-empty list")
        _scan_secrets(data, "$", errors)
        return errors
    expected_uids = load_expected_identity_uids(repo_root)
    card_routes = load_card_declared_routes(repo_root)
    present = set()
    collisions = data.get("routing_collisions")
    if collisions is not None and not isinstance(collisions, list):
        errors.append("routing_collisions must be a list")
        collisions = []
    collisions = collisions or []
    collision_ids = {str(c.get("collision_id")) for c in collisions if isinstance(c, dict) and c.get("collision_id")}
    agent_uid_set = {str(a["agent_uid"]) for a in agents if isinstance(a, dict) and a.get("agent_uid")}
    for i, coll in enumerate(collisions):
        clabel = f"routing_collisions[{i}]"
        if not isinstance(coll, dict):
            errors.append(f"{clabel}: not a mapping")
            continue
        if not coll.get("collision_id"):
            errors.append(f"{clabel}: missing collision_id")
        if coll.get("subject") and _claiming(coll.get("subject")):
            _validate_subject(str(coll["subject"]).strip(), errors, label=f"{clabel}.subject")
        members = coll.get("agents")
        if not isinstance(members, list) or len(members) < 2:
            errors.append(f"{clabel}: agents must list at least two UIDs")
        else:
            for m in members:
                if str(m) not in agent_uid_set:
                    errors.append(f"{clabel}: agent member not in agents[]")
    seen_uids, seen_subjects, seen_durables, seen_principals = {}, {}, {}, {}
    for index, agent in enumerate(agents):
        label = f"agents[{index}]"
        if not isinstance(agent, dict):
            errors.append(f"{label}: entry is not a mapping ({type(agent).__name__})")
            continue
        raw_uid = agent.get("agent_uid")
        if not isinstance(raw_uid, str):
            errors.append(f"{label}: agent_uid must be a string")
            uid = f"<missing:{index}>"
        else:
            uid = raw_uid
            _validate_uid(uid, errors, label=label)
            present.add(uid)
            if uid in seen_uids:
                errors.append(f"{label}: duplicate agent_uid")
            seen_uids[uid] = index
        for field in REQUIRED_AGENT_FIELDS:
            if field not in agent:
                errors.append(f"{label}: missing required field {field}")
        if not isinstance(agent.get("live_on_hub"), bool):
            errors.append(f"{label}: live_on_hub must be boolean")
        identity_source = str(agent.get("identity_source") or "")
        if identity_source and identity_source not in IDENTITY_SOURCES:
            errors.append(f"{label}: unknown identity_source")
        lanes = agent.get("lanes_available")
        if lanes is not None and not isinstance(lanes, list):
            errors.append(f"{label}: lanes_available must be a list")
        else:
            for lane in lanes or []:
                if lane not in KNOWN_LANES:
                    errors.append(f"{label}: unknown lane")
        primary = agent.get("primary_lane")
        if primary is not None and primary not in KNOWN_LANES:
            errors.append(f"{label}: unknown primary_lane")
        creds = agent.get("credential_env_names")
        if creds is not None and not isinstance(creds, list):
            errors.append(f"{label}: credential_env_names must be a list")
        else:
            for name in creds or []:
                if not isinstance(name, str) or not ENV_NAME_RE.match(name):
                    errors.append(f"{label}: credential_env_names entry is not a valid ALL_CAPS env var name (value redacted)")
        for list_field in ("listen_subjects", "publish_subjects"):
            if agent.get(list_field) is not None and not isinstance(agent.get(list_field), list):
                errors.append(f"{label}: {list_field} must be a list")
        authority_id = agent.get("authority_id")
        if authority_id is not None and authority_ids and str(authority_id) not in authority_ids:
            errors.append(f"{label}: authority_id not in authorities")
        evidence = str(agent.get("evidence_status") or "probe_backed")
        if evidence not in EVIDENCE_STATUSES:
            errors.append(f"{label}: unknown evidence_status")
        receipt = agent.get("probe_receipt")
        if receipt:
            _validate_receipt_path(label, str(receipt), repo_root=repo_root, errors=errors, field="probe_receipt")
        elif evidence not in RECEIPT_OPTIONAL_EVIDENCE:
            errors.append(f"{label}: missing required field probe_receipt")
        mode = agent.get("semantic_executor_mode")
        if mode is not None and str(mode).strip().lower() not in SEMANTIC_EXECUTOR_MODES:
            errors.append(f"{label}: unknown semantic_executor_mode")
        for tier_field in TIER_FIELDS:
            tier_val = agent.get(tier_field)
            if tier_val is None:
                continue
            text = str(tier_val).strip()
            if text not in {"unknown", "unprobed"} and _tier_rank(text) is None:
                errors.append(f"{label}: invalid {tier_field}")
        _validate_route_block(label, agent.get("declared_route"), route_label="declared_route", errors=errors)
        _validate_route_block(label, agent.get("observed_effective_route"), route_label="observed_effective_route", errors=errors)
        _validate_observed_authority(label, agent, authority_ids, errors)
        if agent.get("target_route") is not None:
            _validate_route_block(label, agent.get("target_route"), route_label="target_route", errors=errors)
            tr = agent.get("target_route")
            if isinstance(tr, dict) and tr.get("role") in {"observed", "live", "canonical", "effective"}:
                errors.append(f"{label}: target_route must not claim observed/live role")
        declared = agent.get("declared_route") if isinstance(agent.get("declared_route"), dict) else {}
        for top_key, route_key in COMPAT_ROUTE_FIELDS.items():
            if top_key not in agent or not declared:
                continue
            if _norm(agent.get(top_key)) != _norm(declared.get(route_key)):
                errors.append(f"{label}: top-level {top_key} != declared_route.{route_key}")
        if uid in card_routes and declared:
            card = card_routes[uid]
            if card.get("inbox_subject") and _norm(declared.get("inbox_subject")) and _norm(declared.get("inbox_subject")) != card["inbox_subject"]:
                errors.append(f"{label}: declared_route.inbox_subject does not match registration card")
            if card.get("durable_consumer") and _norm(declared.get("durable_consumer")) and _norm(declared.get("durable_consumer")) != card["durable_consumer"]:
                errors.append(f"{label}: declared_route.durable_consumer does not match card-derived durable")
        statuses = _validate_agent_cell(label, agent, errors)
        _bind_runtime_cell_values(label, agent, errors)
        mode_s = str(agent.get("semantic_executor_mode") or _component_value(agent, "semantic_executor_mode") or "unknown").strip().lower()
        effect = str(agent.get("semantic_effect_ceiling") or "unknown").strip()
        cell = agent.get("runtime_cell") if isinstance(agent.get("runtime_cell"), dict) else {}
        cell_effect = str(cell.get("semantic_effect_ceiling") or effect).strip()
        readiness = str(agent.get("readiness_ceiling") or "unknown").strip()
        if mode_s in NO_SEMANTIC_MODES:
            for tlabel, tier in (("semantic_effect_ceiling", effect), ("runtime_cell.semantic_effect_ceiling", cell_effect), ("readiness_ceiling", readiness)):
                if tier in SEMANTIC_TIERS:
                    errors.append(f"{label}: {tlabel} requires a declared semantic executor (delivery drain caps at {DELIVERY_DRAIN_CEILING})")
        has_proof = _validate_proof_evidence(label, uid, agent, repo_root=repo_root, errors=errors)
        expected = compute_readiness_ceiling(
            component_statuses=statuses, semantic_executor_mode=mode_s,
            transport_contact_tier=str(agent.get("transport_contact_tier") or "unknown"),
            semantic_effect_ceiling=str(agent.get("semantic_effect_ceiling") or "unknown"),
            identity_source=identity_source, evidence_status=evidence)
        if not has_proof and expected not in {"unknown", "unprobed"}:
            expected = "unknown"
        declared_ready = str(agent.get("readiness_ceiling") or "unknown")
        if declared_ready != expected:
            if declared_ready != "unknown" and expected == "unknown":
                errors.append(f"{label}: readiness_ceiling overclaims when computed ceiling is unknown")
            else:
                errors.append(f"{label}: readiness_ceiling does not match fail-closed computed ceiling")
        if identity_source == "runtime_observed_uncommitted" and declared_ready != "unknown":
            errors.append(f"{label}: runtime_observed_uncommitted identity must have readiness_ceiling unknown")
        if uid not in expected_uids and identity_source != "runtime_observed_uncommitted":
            errors.append(f"{label}: extra identity not in cards/roster must set identity_source: runtime_observed_uncommitted")
        obs = agent.get("observed_effective_route")
        if isinstance(obs, dict):
            coll_ref = obs.get("collision_ref")
            if coll_ref is not None and str(coll_ref) not in collision_ids:
                errors.append(f"{label}: observed_effective_route.collision_ref not present in routing_collisions")
            if coll_ref is not None:
                for key in ROUTE_KEYS:
                    if _claiming(obs.get(key)):
                        errors.append(f"{label}: observed_effective_route.{key} must be null when quarantined by collision_ref")
            for field, bucket in (("inbox_subject", seen_subjects), ("durable_consumer", seen_durables), ("credential_principal", seen_principals)):
                if not _claiming(obs.get(field)):
                    continue
                val = str(obs[field]).strip()
                prior = bucket.get(val)
                if prior is not None and prior != label:
                    if field == "inbox_subject":
                        errors.append(f"{label}: duplicate observed_effective_route.inbox_subject (also claimed by {prior}); record routing_collisions and quarantine")
                    else:
                        errors.append(f"{label}: duplicate observed_effective_route.{field} (also claimed by {prior})")
                else:
                    bucket[val] = label
    for missing in sorted(expected_uids - present):
        errors.append(f"missing runtime-cell projection for expected identity {missing!r} (union of registration cards + REGISTERED_AGENT_UIDS)")
    if "codex" in present and "codex_composer" in present:
        errors.append("codex must not appear as a second identity when codex_composer is present")
    if "hermes" in present and "hermes-m5" in present:
        errors.append("hermes must not appear as a second identity when hermes-m5 is present")
    _scan_secrets(data, "$", errors)
    return errors
