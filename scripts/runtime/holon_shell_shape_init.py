#!/usr/bin/env python3
"""Initialize the canonical LivingDock shell shape for one HOLON."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.holon_bridge import AGENTS_ROOT  # noqa: E402
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now  # noqa: E402

SCHEMA_VERSION = "dharma.holon_shell_shape_init.v1"
_AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{0,95}$")
SANCTUM_PATHS = ("codex", "vault", "dojo", "ingest_gate", "tools", "receipts")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def _safe_token(value: object) -> str:
    token = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in str(value or ""))
    return token.strip("_-")[:96] or "unknown"


def init_holon_shell_shape(
    name: str,
    *,
    agents_root: Path = AGENTS_ROOT,
    session_id: str = "",
) -> dict[str, Any]:
    if not _AGENT_NAME_RE.fullmatch(name or ""):
        raise ValueError("invalid holon name")
    home = agents_root / name
    identity = home / "identity.json"
    living_agent = home / "living_agent.json"
    missing_core = [str(path) for path in (identity, living_agent) if not path.exists()]
    if missing_core:
        raise FileNotFoundError(f"canonical LivingDock core missing: {', '.join(missing_core)}")

    created: list[str] = []
    preserved: list[str] = []
    for directory in [
        home / "dialogue",
        home / "dialogue" / "conversation_receipts",
        *(home / "sanctum" / relative for relative in SANCTUM_PATHS),
    ]:
        existed = directory.exists()
        directory.mkdir(parents=True, exist_ok=True)
        (preserved if existed else created).append(str(directory))

    observed_at = utc_now()
    operator_session = {
        "schema_version": SCHEMA_VERSION,
        "holon": name,
        "session_id": session_id or f"holon-shell-shape-{observed_at}",
        "observed_at": observed_at,
        "event": "shell_shape_initialized",
        "claim_scope": {
            "livingdock_shape_only": True,
            "service_heartbeat_claim": False,
            "transport_heartbeat_claim": False,
            "dialogue_model_reply_claim": False,
        },
    }
    operator_session["record_hash"] = stable_payload_hash(operator_session)
    _append_jsonl(home / "dialogue" / "operator_sessions.jsonl", operator_session)

    relationship_memory = {
        "schema_version": SCHEMA_VERSION,
        "holon": name,
        "session_id": operator_session["session_id"],
        "observed_at": observed_at,
        "event": "relationship_memory_initialized",
        "operator_relation": "read_only_shell_reference",
        "claim_scope": {"memory_seed_only": True},
    }
    relationship_memory["record_hash"] = stable_payload_hash(relationship_memory)
    _append_jsonl(home / "dialogue" / "relationship_memory.jsonl", relationship_memory)

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "holon": name,
        "session_id": operator_session["session_id"],
        "observed_at": observed_at,
        "created_paths": created,
        "preserved_paths": preserved,
        "operator_session_path": str(home / "dialogue" / "operator_sessions.jsonl"),
        "relationship_memory_path": str(home / "dialogue" / "relationship_memory.jsonl"),
        "claim_scope": {
            "livingdock_shape_only": True,
            "heartbeat_claim": False,
            "semantic_receipt_claim": False,
            "domain_receipt_claim": False,
        },
    }
    receipt["receipt_hash"] = stable_payload_hash(receipt)
    receipt_path = home / "sanctum" / "receipts" / f"{observed_at}-{_safe_token(name)}-shell-shape.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--agents-root", type=Path, default=AGENTS_ROOT)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    receipt = init_holon_shell_shape(args.name, agents_root=args.agents_root, session_id=args.session_id)
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"HOLON shell shape initialized: {receipt['receipt_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
