from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.runtime import a2a_reset_quorum_consumers


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.info_calls = 0

    def __call__(
        self,
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if command[4:6] == ["consumer", "info"]:
            self.info_calls += 1
            pending = 2 if self.info_calls == 1 else 0
            payload = {
                "name": command[7],
                "config": {
                    "filter_subject": "dharma.a2a.fable_composer",
                    "deliver_policy": "new",
                    "ack_policy": "explicit",
                    "max_deliver": 5,
                },
                "delivered": {"stream_seq": 8106914},
                "num_pending": pending,
                "num_ack_pending": 0,
                "num_redelivered": 0,
                "num_waiting": 0,
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        return subprocess.CompletedProcess(command, 0, "ok", "")


def test_parse_target() -> None:
    target = a2a_reset_quorum_consumers.parse_target(
        "fable_composer_inbox=dharma.a2a.fable_composer"
    )

    assert target.consumer == "fable_composer_inbox"
    assert target.filter_subject == "dharma.a2a.fable_composer"


def test_build_reset_receipt_applies_delete_and_recreate() -> None:
    runner = FakeRunner()
    target = a2a_reset_quorum_consumers.ResetTarget(
        consumer="fable_composer_inbox",
        filter_subject="dharma.a2a.fable_composer",
    )

    receipt = a2a_reset_quorum_consumers.build_reset_receipt(
        targets=[target],
        context="agni-wss",
        stream="DHARMA_A2A",
        apply=True,
        timeout_s=30,
        max_deliver=5,
        max_pending=1000,
        runner=runner,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert receipt["status"] == "APPLIED"
    assert receipt["production_claim"] is False
    assert receipt["stream_messages_mutated"] is False
    assert receipt["summary"]["after_pending_total"] == 0
    assert runner.commands[1][4:6] == ["consumer", "rm"]
    assert runner.commands[2][4:6] == ["consumer", "add"]


def test_dry_run_does_not_mutate() -> None:
    runner = FakeRunner()
    target = a2a_reset_quorum_consumers.ResetTarget(
        consumer="fable_composer_inbox",
        filter_subject="dharma.a2a.fable_composer",
    )

    receipt = a2a_reset_quorum_consumers.build_reset_receipt(
        targets=[target],
        context="agni-wss",
        stream="DHARMA_A2A",
        apply=False,
        timeout_s=30,
        max_deliver=5,
        max_pending=1000,
        runner=runner,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert receipt["status"] == "DRY_RUN"
    assert all(command[4:6] == ["consumer", "info"] for command in runner.commands)


def test_write_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    payload = {"schema_version": a2a_reset_quorum_consumers.SCHEMA_VERSION}

    a2a_reset_quorum_consumers.write_receipt(receipt_path, payload)

    assert json.loads(receipt_path.read_text(encoding="utf-8")) == payload
