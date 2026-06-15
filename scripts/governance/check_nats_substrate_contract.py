#!/usr/bin/env python3
"""Validate the NATS substrate contract wiring without requiring live NATS."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md"
MAKEFILE = REPO_ROOT / "Makefile"
ONBOARD = REPO_ROOT / "scripts" / "governance" / "agent_onboard.py"
A2A_SEND = REPO_ROOT / "scripts" / "runtime" / "a2a_send.py"
A2A_INBOX_BRIDGE = REPO_ROOT / "scripts" / "runtime" / "a2a_inbox_bridge.py"
A2A_DOMAIN_REPLY_WORKER = REPO_ROOT / "scripts" / "runtime" / "a2a_domain_reply_worker.py"
A2A_REPLY_CAPTURE = REPO_ROOT / "scripts" / "runtime" / "a2a_reply_capture.py"
NATS_STATUS = REPO_ROOT / "dharma_swarm" / "operator_core" / "nats_substrate_status.py"


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    for path in (
        SPEC_PATH,
        MAKEFILE,
        ONBOARD,
        A2A_SEND,
        A2A_INBOX_BRIDGE,
        A2A_DOMAIN_REPLY_WORKER,
        A2A_REPLY_CAPTURE,
        NATS_STATUS,
    ):
        _require(path.exists(), f"missing required NATS contract file: {path}", failures)
    if failures:
        for failure in failures:
            print(f"NATS_CONTRACT_FAIL {failure}", file=sys.stderr)
        return 1

    spec = _read(SPEC_PATH)
    makefile = _read(MAKEFILE)
    onboard = _read(ONBOARD)
    a2a_send = _read(A2A_SEND)
    a2a_inbox_bridge = _read(A2A_INBOX_BRIDGE)
    a2a_domain_reply_worker = _read(A2A_DOMAIN_REPLY_WORKER)
    a2a_reply_capture = _read(A2A_REPLY_CAPTURE)
    nats_status = _read(NATS_STATUS)

    required_spec_phrases = [
        "Filesystem and SQLite buses: compatibility mirrors",
        "PUBLISH_ACCEPTED",
        "DELIVERED_TO_CONSUMER",
        "HANDLER_ACKED",
        "DOMAIN_RECEIPTED",
        "`PUBLISH_ACCEPTED` alone is not live human-usable contact",
        "scripts/runtime/a2a_send.py",
        "CLI fallback can prove at most `PUBLISH_ACCEPTED`",
        "scripts/runtime/a2a_inbox_bridge.py",
        "It is not a semantic peer reply",
        "scripts/runtime/a2a_domain_reply_worker.py",
        "target-owned reply artifact",
        "scripts/runtime/a2a_reply_capture.py",
        "NO_REPLY",
    ]
    for phrase in required_spec_phrases:
        _require(phrase in spec, f"spec missing required phrase: {phrase}", failures)

    _require("nats-substrate-contract:" in makefile, "Makefile missing nats-substrate-contract target", failures)
    _require("governance-all:" in makefile and "nats-substrate-contract" in makefile, "governance-all does not include nats-substrate-contract", failures)
    _require("NATS_SUBSTRATE_MASTER_SPEC.md" in onboard, "onboard does not render canonical NATS spec path", failures)
    _require("classify_contact_evidence" in a2a_send, "a2a_send missing contact evidence classifier", failures)
    _require("NATS_CLI_JETSTREAM_PUB_ACK" in a2a_send, "a2a_send missing governed NATS CLI fallback receipt marker", failures)
    _require("live_contact_claim" in a2a_send, "a2a_send receipts do not expose live_contact_claim", failures)
    _require("DELIVERED_AND_ACKED" in a2a_inbox_bridge, "a2a_inbox_bridge missing delivered-and-acked status", failures)
    _require("semantic_reply_claim" in a2a_inbox_bridge, "a2a_inbox_bridge can overclaim semantic replies", failures)
    _require("target-owned" in a2a_domain_reply_worker, "a2a_domain_reply_worker missing target-owned boundary", failures)
    _require("DOMAIN_REPLY_PUBLISHED" in a2a_domain_reply_worker, "a2a_domain_reply_worker missing publish status", failures)
    _require("dharma.a2a.domain_receipt.v1" in a2a_domain_reply_worker, "a2a_domain_reply_worker missing typed domain receipt schema", failures)
    _require("NO_REPLY" in a2a_reply_capture, "a2a_reply_capture missing honest no-reply status", failures)
    _require("DOMAIN_RECEIPTED" in a2a_reply_capture, "a2a_reply_capture missing domain receipt status", failures)
    _require("docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md" in nats_status, "nats_substrate_status points at the wrong spec path", failures)

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from dharma_swarm.operator_core.nats_substrate_status import probe_nats_substrate

    unavailable = probe_nats_substrate(endpoint="nats://127.0.0.1:1", verify_ack=True).to_dict()
    _require(unavailable["ack_verified"] is False, "unreachable NATS endpoint reported ack_verified=True", failures)
    _require(
        unavailable["code"] in {"NATS_UNAVAILABLE", "NATS_ACK_FAILED", "NATS_CLIENT_MISSING"},
        f"unexpected unreachable NATS code: {unavailable['code']}",
        failures,
    )
    _require(
        unavailable["spec_path"] == "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
        f"probe reports wrong spec_path: {unavailable['spec_path']}",
        failures,
    )

    if failures:
        for failure in failures:
            print(f"NATS_CONTRACT_FAIL {failure}", file=sys.stderr)
        return 1
    print("NATS_CONTRACT_OK docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
