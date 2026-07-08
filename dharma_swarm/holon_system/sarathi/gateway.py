"""Read-only Sarathi gateway snapshot.

This is *not* the full apex gateway loop. It is the smallest repo-owned source
module that makes the existing runtime wrapper useful for remote operation:

- read current Sarathi/holon-system state;
- classify whether Sarathi may honestly be called alive;
- optionally write a finite operator brief into Sarathi's runtime outbox;
- perform no model calls, no source mutation, no external send, and no approval.

The real loop that selects and acts on one lane remains gated behind the proof
gates in docs/sarathi_apex_build/06_PROOF_GATES.md.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm import holon_health
from dharma_swarm.holon_bridge import load_holon

DHARMA_HOME = Path.home() / ".dharma"
SARATHI_HOME = DHARMA_HOME / "agents" / "sarathi"
SARATHI_OUTBOX = SARATHI_HOME / "outbox"
SARATHI_NEST = DHARMA_HOME / "external_agents" / "sarathi" / "nest"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _exists(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists(), "is_dir": path.is_dir()}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _runtime_surfaces() -> dict[str, dict[str, Any]]:
    return {
        "a2a_state": _exists(DHARMA_HOME / "a2a_bus" / "state" / "sarathi.json"),
        "a2a_inbox": _exists(DHARMA_HOME / "a2a_bus" / "inboxes" / "sarathi"),
        "bridge_heartbeat": _exists(DHARMA_HOME / "a2a_bus" / "bridge_heartbeats" / "sarathi.json"),
        "gateway_wrapper": _exists(SARATHI_HOME / "gateway" / "sarathi_gateway.py"),
        "holarchy_contract": _exists(SARATHI_HOME / "HOLARCHY_CONTRACT.md"),
        "sub_holon_roster": _exists(SARATHI_HOME / "SUB_HOLON_ROSTER.yaml"),
        "service_heartbeats": _exists(SARATHI_HOME / "service_heartbeats.jsonl"),
        "outbox": _exists(SARATHI_OUTBOX),
    }


def _wake_status() -> dict[str, Any]:
    status = _read_json(SARATHI_NEST / "status.json")
    latest = _read_json(SARATHI_NEST / "latest_receipt.json")
    return {
        "status_path": str(SARATHI_NEST / "status.json"),
        "latest_receipt_path": str(SARATHI_NEST / "latest_receipt.json"),
        "wake_loop_active": bool(status.get("wake_loop_active")),
        "latest_status": (status.get("latest_receipt") or latest).get("status"),
        "latest_receipt_id": (status.get("latest_receipt") or latest).get("receipt_id"),
        "raw_status_present": bool(status),
    }


def _load_holon_summary() -> dict[str, Any]:
    try:
        holon = load_holon("sarathi")
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "name": holon.name,
        "provider_type": holon.provider_type,
        "model": holon.model,
        "runtime_model_resolution": holon.identity.get("_runtime_model_resolution"),
    }


def gateway_snapshot() -> dict[str, Any]:
    """Return a read-only Sarathi readiness snapshot suitable for phone/SSH use."""

    surfaces = _runtime_surfaces()
    status = holon_health.holon_status("sarathi")
    wake = _wake_status()
    missing = [name for name, item in surfaces.items() if not item["exists"]]
    service_alive = bool(status.get("service_alive"))
    wake_loop_active = bool(wake.get("wake_loop_active"))
    alive = service_alive and wake_loop_active
    return {
        "schema_version": "dharma.sarathi.gateway_snapshot.v1",
        "generated_at": _now(),
        "mode": "read_only_snapshot",
        "sarathi_alive": alive,
        "alive_verdict": (
            "alive" if alive else "not_alive_no_service_or_wake_loop_proof"
        ),
        "may_claim_wake_loop_active": wake_loop_active,
        "may_execute_unattended": False,
        "authority": {
            "floor": "read_only_snapshot",
            "ceiling": "no_irreversible_action_no_external_send_no_self_approval",
        },
        "load_holon": _load_holon_summary(),
        "holon_status": status,
        "wake_status": wake,
        "runtime_surfaces": surfaces,
        "missing_surfaces": missing,
        "next_required_steps": [
            "create/prove service heartbeat for sarathi gateway",
            "write repo-owned pulse/brief/roster modules behind the reversibility gate",
            "prove phone/outbox egress with a delivered or pullable brief",
            "run lease-backed overnight proof before wake_loop_active=true",
        ],
    }


def render_operator_brief(snapshot: Mapping[str, Any]) -> str:
    missing = ", ".join(snapshot.get("missing_surfaces") or []) or "none"
    model = (snapshot.get("load_holon") or {}).get("model", "unknown")
    provider = (snapshot.get("load_holon") or {}).get("provider_type", "unknown")
    wake = snapshot.get("wake_status") or {}
    return "\n".join(
        [
            "# Sarathi remote readiness brief",
            "",
            f"- Generated: `{snapshot.get('generated_at')}`",
            f"- Verdict: **{snapshot.get('alive_verdict')}**",
            f"- Model route: `{provider}/{model}`",
            f"- Wake loop active: `{snapshot.get('may_claim_wake_loop_active')}`",
            f"- Latest wake receipt: `{wake.get('latest_receipt_id')}` status=`{wake.get('latest_status')}`",
            f"- Missing runtime surfaces: `{missing}`",
            "",
            "## Highest-priority next action",
            "",
            "Before remote departure confidence: prove a Sarathi service heartbeat + a pullable/delivered brief. Do not flip `wake_loop_active=true` until an overnight lease-backed run leaves receipts.",
            "",
            "## Hard safety boundary",
            "",
            "This snapshot sends nothing, approves nothing, spends nothing, mutates no source, and does not claim Sarathi is alive.",
            "",
        ]
    )


def write_operator_brief(outbox: Path | None = None) -> dict[str, Any]:
    snapshot = gateway_snapshot()
    outbox = outbox or SARATHI_OUTBOX
    outbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = outbox / f"sarathi-readiness-{stamp}.json"
    md_path = outbox / f"sarathi-readiness-{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_operator_brief(snapshot), encoding="utf-8")
    return {
        "schema_version": "dharma.sarathi.operator_brief_write.v1",
        "generated_at": snapshot["generated_at"],
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "alive_verdict": snapshot["alive_verdict"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Sarathi gateway snapshot")
    parser.add_argument("--brief", action="store_true", help="write a pullable operator brief into the Sarathi outbox")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)

    payload = write_operator_brief() if args.brief else gateway_snapshot()
    if args.json or args.brief:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_operator_brief(payload))
    return 0


__all__ = [
    "gateway_snapshot",
    "main",
    "render_operator_brief",
    "write_operator_brief",
]


if __name__ == "__main__":
    raise SystemExit(main())
