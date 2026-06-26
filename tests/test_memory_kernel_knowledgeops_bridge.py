"""PR 4 verifier — the KnowledgeOps -> MemoryKernel promotion bridge.

Drives the existing executable smoke (scripts/memory_kernel_knowledgeops_bridge_smoke.py)
in-process against tmp output paths. This is the higher-level reuse path the
Idea Spark memory bridge is the per-candidate analog of: it proves the bridge
emits a REVIEWED canonical receipt with knowledgeops linkage and zero blocked
receipts. Deterministic, no-network.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from dharma_swarm.memory_kernel import load_promotion_status

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SMOKE = _REPO_ROOT / "scripts" / "memory_kernel_knowledgeops_bridge_smoke.py"


def _load_smoke():
    spec = importlib.util.spec_from_file_location("_mk_knowledgeops_bridge_smoke", _SMOKE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_knowledgeops_bridge_smoke_is_promotion_ready(tmp_path, capsys) -> None:
    smoke = _load_smoke()
    write_out = tmp_path / "write_receipts.jsonl"
    decision_out = tmp_path / "promotion_decisions.jsonl"
    canonical_out = tmp_path / "reviewed_canonical_receipts.jsonl"
    request_out = tmp_path / "knowledgeops_requests.jsonl"
    receipt_out = tmp_path / "knowledgeops_receipts.jsonl"

    code = smoke.main(
        [
            "--repo-root",
            str(tmp_path),
            "--write-receipt-out",
            str(write_out),
            "--decision-out",
            str(decision_out),
            "--canonical-receipt-out",
            str(canonical_out),
            "--knowledgeops-request-out",
            str(request_out),
            "--knowledgeops-receipt-out",
            str(receipt_out),
            "--fail-on-blocked",
        ]
    )
    assert code == 0, capsys.readouterr().out

    payload = json.loads(capsys.readouterr().out)
    assert payload  # non-empty JSON summary printed
    assert canonical_out.exists()
    status = load_promotion_status(canonical_out)
    assert status.promotion_ready is True
    assert status.blocked_receipt_count == 0
    assert status.latest_canonical_receipt_id
