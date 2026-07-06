from __future__ import annotations

from pathlib import Path

from scripts.runtime.a2a_phase_a_dlq_fixture import run_dlq_fixture


async def test_phase_a_dlq_fixture_writes_typed_receipt(tmp_path: Path) -> None:
    proof = await run_dlq_fixture(receipt_root=tmp_path / "dlq_receipts")

    assert proof["status"] == "pass"
    assert proof["dlq_publish"]["payload_schema"] == "dharma.nats.dlq_failure.v1"
    assert proof["dlq_publish"]["operator_blocker"] == "NATS_MAX_DELIVER_EXHAUSTED"
    assert proof["dlq_publish"]["delivery_count"] == 3
    assert proof["broker_side_effect"]["original_message_acked"] == 1
    assert proof["broker_side_effect"]["original_message_nacked"] == 0
    assert proof["broker_side_effect"]["infinite_redelivery_prevented"] is True
    assert any(
        receipt["receipt_type"] == "nats_consume" and receipt["status"] == "dlq"
        for receipt in proof["runtime_receipts"]
    )
    assert Path(proof["receipt_path"]).exists()
