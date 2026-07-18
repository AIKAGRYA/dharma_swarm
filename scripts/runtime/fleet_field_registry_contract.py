"""Fleet field registry contract — public schema, readiness, loaders (no heavy validators)."""
from __future__ import annotations

import ast
import json
import re

SCHEMA_V2 = "dharma_fleet_field_registry.v2"
RUNTIME_CELL_COMPONENTS = (
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
    "agent_uid",
    "runtime",
    "lanes_available",
    "primary_lane",
    "live_on_hub",
    "credential_env_names",
    "listen_subjects",
    "publish_subjects",
    "git_seat",
    "last_verified_send",
    "last_verified_receive",
    "runtime_cell",
    "transport_contact_tier",
    "semantic_effect_ceiling",
    "readiness_ceiling",
    "identity_source",
    "declared_route",
    "observed_effective_route",
)
KNOWN_LANES = {
    "agni_hub_wss",
    "agni_hub_nats",
    "local_nats_4222",
    "meghadharma_nats",
    "git_seat",
    "operator_relay",
    "none",
}
AUTHORITY_ROLES = {
    "source_compatibility",
    "local_operator",
    "candidate_reference",
    "cutover_target_gated",
    "compatibility",
    "reference",
}
EVIDENCE_STATUSES = {
    "probe_backed",
    "probe_backed_2026_07_09",
    "runtime_observed_uncommitted",
    "declared",
    "unprobed",
    "reference_gap",
    "unknown",
}
COMPONENT_STATUSES = {
    "unknown",
    "unprobed",
    "declared",
    "probed",
    "absent",
    "runtime_observed_uncommitted",
}
NON_PROOF_STATUSES = frozenset(
    {"unknown", "unprobed", "declared", "absent", "runtime_observed_uncommitted"}
)
PROOF_STATUSES = frozenset({"probed"})
SEMANTIC_EXECUTOR_MODES = {
    "always_on",
    "event_driven",
    "manual_seat",
    "none",
    "unknown",
    "absent",
}
IDENTITY_SOURCES = {
    "card",
    "roster",
    "card_and_roster",
    "runtime_observed_uncommitted",
}
TIER_ORDER = (
    "unprobed",
    "PUBLISH_ACCEPTED",
    "DELIVERED_TO_CONSUMER",
    "HANDLER_ACKED",
    "PROCESSED",
    "EFFECT_COMMITTED",
    "DOMAIN_RECEIPTED",
)
SEMANTIC_TIERS = frozenset({"PROCESSED", "EFFECT_COMMITTED", "DOMAIN_RECEIPTED"})
DELIVERY_DRAIN_CEILING = "HANDLER_ACKED"
NO_SEMANTIC_MODES = frozenset({"none", "unknown", "absent", ""})
NON_CLAIMING = frozenset({"", "null", "none", "None", "unknown", "~"})
RECEIPT_OPTIONAL_EVIDENCE = frozenset(
    {"runtime_observed_uncommitted", "reference_gap", "unprobed", "unknown"}
)
ROUTE_KEYS = ("inbox_subject", "durable_consumer", "credential_principal")
ROUTE_PROOF_COMPONENTS = {
    "canonical_inbox_subject": "inbox_subject",
    "durable_consumer": "durable_consumer",
    "credential_principal": "credential_principal",
}
COMPAT_ROUTE_FIELDS = {
    "canonical_inbox_subject": "inbox_subject",
    "durable_consumer": "durable_consumer",
    "credential_principal": "credential_principal",
}
TIER_FIELDS = ("transport_contact_tier", "semantic_effect_ceiling", "readiness_ceiling")
ENV_NAME_FIELDS = frozenset(
    {"credential_env_names", "env_var_name", "env_var_names", "credential_env_name"}
)
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
UID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
DURABLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,127}$")
SUBJECT_TOKEN_RE = re.compile(r"^[A-Za-z0-9_=@,-]+$")
SECRET_KEY_EXACT = frozenset(
    {
        "password",
        "passwd",
        "token",
        "secret",
        "api_key",
        "api-key",
        "authorization",
        "private_key",
        "private-key",
        "client_secret",
        "client-secret",
        "access_key",
        "access-key",
    }
)
SECRET_KEY_SUFFIX_RE = re.compile(
    r"(?:_password|_passwd|_token|_secret|_api_key|_api-key|_private_key|_private-key)$",
    re.I,
)
SECRET_POLICY_ALLOW_KEYS = frozenset({"secret_policy"})
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{12,}")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")
API_TOKEN_SHAPE_RE = re.compile(
    r"(?i)\b(?:sk|pk|rk|ghp|gho|ghu|ghs|ghr|xox[baprs]|AKIA)[A-Za-z0-9_\-]{12,}\b"
)
INLINE_SECRET_ASSIGN_RE = re.compile(
    r"(?i)(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S+"
)
FRESHNESS_MAX_DAYS = 180
SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")


class RegistryError(Exception):
    """Controlled registry load/parse failure (CLI → exit 2)."""


def _tier_rank(tier):
    if tier is None:
        return None
    text = str(tier).strip()
    if text in {"", "unknown"}:
        return None
    try:
        return TIER_ORDER.index(text)
    except ValueError:
        return None


def _min_tier(*tiers):
    ranks = []
    for tier in tiers:
        if tier is None or str(tier).strip() in {"", "unknown"}:
            return "unknown"
        rank = _tier_rank(str(tier).strip())
        if rank is None:
            return "unknown"
        ranks.append(rank)
    return TIER_ORDER[min(ranks)] if ranks else "unknown"


def _cap_tier(tier, ceiling):
    if tier in {"unknown", "unprobed"}:
        return tier
    t_rank, c_rank = _tier_rank(tier), _tier_rank(ceiling)
    if t_rank is None or c_rank is None:
        return "unknown"
    return TIER_ORDER[min(t_rank, c_rank)]


def compute_readiness_ceiling(
    *,
    component_statuses,
    semantic_executor_mode,
    transport_contact_tier,
    semantic_effect_ceiling,
    identity_source=None,
    evidence_status=None,
):
    if (identity_source or "").strip() == "runtime_observed_uncommitted":
        return "unknown"
    if (evidence_status or "").strip() == "runtime_observed_uncommitted":
        return "unknown"
    for name in RUNTIME_CELL_COMPONENTS:
        status = (component_statuses.get(name) or "unknown").strip()
        if status in NON_PROOF_STATUSES or status not in PROOF_STATUSES:
            return "unknown"
    mode = (semantic_executor_mode or "unknown").strip().lower()
    transport = (transport_contact_tier or "unknown").strip()
    effect = (semantic_effect_ceiling or "unknown").strip()
    if transport in {"", "unknown", "unprobed"} or _tier_rank(transport) is None:
        return "unknown"
    if mode in NO_SEMANTIC_MODES:
        capped = _cap_tier(transport, DELIVERY_DRAIN_CEILING)
        if effect in {"", "unknown", "unprobed"}:
            return capped
        return _min_tier(capped, _cap_tier(effect, DELIVERY_DRAIN_CEILING))
    if effect in {"", "unknown", "unprobed"}:
        return _cap_tier(transport, DELIVERY_DRAIN_CEILING)
    return _min_tier(transport, effect)


def _subject_from_mailbox(mailbox):
    if not mailbox:
        return None
    text = mailbox.strip()
    if text.lower().startswith("nats://"):
        rest = text[7:]
        if "/" in rest and not rest.startswith("dharma."):
            rest = rest.split("/", 1)[1]
        return rest or None
    return text if text.startswith("dharma.") else None



def _is_secret_key(key):
    k = str(key).strip().lower()
    if k in SECRET_POLICY_ALLOW_KEYS:
        return False
    if k in SECRET_KEY_EXACT:
        return True
    if SECRET_KEY_SUFFIX_RE.search(k):
        return True
    for sk in SECRET_KEY_EXACT:
        if k.startswith(sk + "_") or k.startswith(sk + "-"):
            return True
    return False

def _component_value(agent, name):
    cell = agent.get("runtime_cell")
    if not isinstance(cell, dict):
        return None
    comps = cell.get("components")
    if not isinstance(comps, dict):
        return None
    node = comps.get(name)
    return node.get("value") if isinstance(node, dict) else None


def _claiming(value):
    if value is None:
        return False
    text = str(value).strip()
    return text not in NON_CLAIMING and text.lower() != "null"


def _norm(value):
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in NON_CLAIMING or text.lower() == "null" else text


def load_expected_identity_uids(repo_root):
    uids = set()
    cards = repo_root / "examples" / "agents"
    if cards.is_dir():
        for path in sorted(cards.glob("*.registration.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and data.get("agent_uid"):
                uids.add(str(data["agent_uid"]).strip())
    presence = repo_root / "dharma_swarm" / "a2a" / "agent_presence.py"
    if presence.is_file():
        try:
            tree = ast.parse(presence.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            tree = None
        if tree is not None:
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "REGISTERED_AGENT_UIDS":
                        try:
                            value = ast.literal_eval(node.value)
                        except (ValueError, TypeError):
                            value = None
                        if isinstance(value, (list, tuple)):
                            uids.update(
                                str(x).strip() for x in value if isinstance(x, str)
                            )
    return uids


def load_card_declared_routes(repo_root):
    out = {}
    cards = repo_root / "examples" / "agents"
    if not cards.is_dir():
        return out
    for path in sorted(cards.glob("*.registration.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not data.get("agent_uid"):
            continue
        uid = str(data["agent_uid"]).strip()
        mailbox = str(data.get("mailbox") or data.get("endpoint") or "").strip()
        subject = _subject_from_mailbox(mailbox)
        callsign = str(data.get("callsign") or uid).strip()
        durable = f"{callsign.replace('-', '_')}_inbox" if subject else None
        for key in ("durable_consumer", "durable", "inbox_durable"):
            if data.get(key):
                durable = str(data[key]).strip()
                break
        out[uid] = {"inbox_subject": subject, "durable_consumer": durable}
    return out


def load_registry_data(path):
    try:
        import yaml
    except ImportError as exc:
        raise RegistryError("yaml loader unavailable") from exc
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryError(
            f"registry read error at {path.name}: {type(exc).__name__}"
        ) from None
    try:
        data = yaml.safe_load(raw)
    except Exception:
        raise RegistryError(f"registry parse error at {path.name}: YAMLError") from None
    if not isinstance(data, dict):
        raise RegistryError("registry did not parse to a mapping")
    return data


def validate_registry(data, *, repo_root):
    """Lazy public wrapper — avoids circular import; preserves negative-control API."""
    from scripts.runtime.fleet_field_registry_validation import (
        validate_registry as _validate_registry,
    )

    return _validate_registry(data, repo_root=repo_root)


validate = validate_registry
