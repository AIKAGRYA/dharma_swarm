#!/usr/bin/env python3
"""Fleet field registry reader — the one secret-free routing command.

Prints, for every probed agent identity: uid, canonical lane, live-on-hub
status, credential env-var NAMES, listen subject(s), and last verified
send/receive — sourced from docs/ops/FLEET_FIELD_REGISTRY.yaml (schema
dharma_fleet_field_registry.v1), which is refreshed by probe receipts.

Usage:
    python3 scripts/runtime/fleet_field_registry.py            # print the field table
    python3 scripts/runtime/fleet_field_registry.py --check    # validate (exit 2 on failure)
    python3 scripts/runtime/fleet_field_registry.py --json     # machine-readable dump

--check enforces the registry contract: required fields per agent, the
env-var-names-only secret policy (a credential VALUE in the registry is a
governance violation), and that every probe_receipt path exists in the repo.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "docs/ops/FLEET_FIELD_REGISTRY.yaml"
SCHEMA = "dharma_fleet_field_registry.v1"

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
    "probe_receipt",
)
KNOWN_LANES = {
    "agni_hub_wss",
    "agni_hub_nats",
    "local_nats_4222",
    "git_seat",
    "operator_relay",
    "none",
}
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
# Values that would indicate a leaked credential rather than a name/reference.
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


def validate(data: dict, *, repo_root: Path = REPO_ROOT) -> list[str]:
    """Return a list of violations; empty means the registry is valid."""
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}, got {data.get('schema')!r}")
    if data.get("secret_policy") != "env_var_names_only":
        errors.append("secret_policy must be 'env_var_names_only'")

    agents = data.get("agents")
    if not isinstance(agents, list) or not agents:
        return errors + ["agents must be a non-empty list"]

    seen_uids: set[str] = set()
    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            errors.append(f"agents[{index}]: entry is not a mapping ({type(agent).__name__})")
            continue
        uid = str(agent.get("agent_uid", "<missing uid>"))
        if uid in seen_uids:
            errors.append(f"{uid}: duplicate agent_uid")
        seen_uids.add(uid)
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
        receipt = agent.get("probe_receipt")
        if receipt and not (repo_root / str(receipt)).exists():
            errors.append(f"{uid}: probe_receipt path does not exist: {receipt}")

    # Whole-document secret scan: no key/value pair may carry a literal secret.
    def scan(node: object, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                scan(value, f"{trail}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                scan(item, f"{trail}[{index}]")
        elif isinstance(node, str) and SECRET_VALUE_RE.search(node):
            errors.append(f"possible secret value at {trail}: {node[:40]!r}...")

    scan(data, "$")
    return errors


def render_table(data: dict) -> str:
    rows = [("AGENT", "PRIMARY LANE", "LIVE", "LISTEN", "LAST SEND")]
    for agent in data.get("agents", []):
        listen = (agent.get("listen_subjects") or ["-"])[0]
        rows.append(
            (
                str(agent.get("agent_uid", "?")),
                str(agent.get("primary_lane", "?")),
                "YES" if agent.get("live_on_hub") else "no",
                str(listen)[:44],
                str(agent.get("last_verified_send", "?"))[:40],
            )
        )
    widths = [max(len(row[col]) for row in rows) for col in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows]
    hub = data.get("hub", {})
    header = (
        f"Fleet field registry (updated {data.get('updated', '?')}) — "
        f"hub {hub.get('name', '?')} stream {hub.get('live_stream', '?')}\n"
    )
    footer = (
        f"\n{len(data.get('unprobed_identities', []) or [])} known identities unprobed; "
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
        print(f"[registry-check] OK — {len(data['agents'])} probed agents, secret policy holds")
        return 0
    if "--json" in argv:
        print(json.dumps(data, indent=2, default=str))
        return 0
    print(render_table(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
