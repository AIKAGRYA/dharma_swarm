"""Minimal standalone A2A probe surface.

This module only proves local agent reachability by LivingDock shape and emits
receipts. Parent Dharma Swarm transports can adapt this into live bus probes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from holon.receipts import build_receipt, write_receipt


@dataclass(frozen=True)
class A2AProbeResult:
    agent_uid: str
    status: str
    evidence_path: str
    receipt_path: str = ""


def discover_agents(*, agents_root: Path, limit: int = 3) -> list[str]:
    if not agents_root.exists():
        return []
    names = []
    for child in sorted(agents_root.iterdir()):
        if child.is_dir() and (child / "identity.json").exists():
            names.append(child.name)
        if len(names) >= limit:
            break
    return names


def ping_agents(
    *,
    holon_name: str,
    agents_root: Path,
    agent_uids: list[str] | None = None,
    min_agents: int = 3,
) -> list[A2AProbeResult]:
    targets = agent_uids or discover_agents(agents_root=agents_root, limit=min_agents)
    results: list[A2AProbeResult] = []
    for target in targets[:min_agents]:
        identity = agents_root / target / "identity.json"
        status = "pass" if identity.exists() else "fail"
        receipt = build_receipt(
            kind="a2a_ping",
            subject=holon_name,
            status=status,
            side_effect_key=f"a2a-ping:{holon_name}:{target}",
            payload={"target": target, "identity_path": str(identity), "identity_present": identity.exists()},
            verifier_refs=[str(identity)] if identity.exists() else [],
        )
        ref = write_receipt(receipt, agents_root=agents_root, holon_name=holon_name)
        result = A2AProbeResult(
            agent_uid=target,
            status=status,
            evidence_path=str(identity),
            receipt_path=ref["path"],
        )
        _append_ping(agents_root / holon_name / "a2a_pings.jsonl", result)
        results.append(result)
    return results


def _append_ping(path: Path, result: A2AProbeResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.__dict__, sort_keys=True) + "\n")
