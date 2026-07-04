from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.sab_language_womb_bridge import write_witness_contribution


def test_witness_bridge_ignores_irrelevant_logs(tmp_path: Path) -> None:
    witness = tmp_path / "witness.jsonl"
    witness.write_text('{"detail":"ordinary heartbeat with no matching terms"}\n', encoding="utf-8")

    result = write_witness_contribution(
        agent_name="agent-a",
        witness_log=witness,
        state_dir=tmp_path / "state",
        agora_repo=tmp_path / "agora",
        run_packager=False,
    )

    assert result == "sab_language_womb: no_relevant_witness_delta"


def test_witness_bridge_writes_inbox_delta_once(tmp_path: Path) -> None:
    witness = tmp_path / "witness.jsonl"
    witness.write_text(
        '{"detail":"Claim evidence authority boundary should become typechecker semantics"}\n',
        encoding="utf-8",
    )
    agora = tmp_path / "agora"

    first = write_witness_contribution(
        agent_name="agent-a",
        witness_log=witness,
        state_dir=tmp_path / "state",
        agora_repo=agora,
        run_packager=False,
    )
    second = write_witness_contribution(
        agent_name="agent-a",
        witness_log=witness,
        state_dir=tmp_path / "state",
        agora_repo=agora,
        run_packager=False,
    )

    assert first.startswith("sab_language_womb: inbox=")
    assert second == "sab_language_womb: unchanged"
    inbox_files = list(
        (agora / "docs" / "lanes" / "sab-agent-seeding-v1" / "contributions" / "inbox").glob("*.json")
    )
    assert len(inbox_files) == 1
    payload = json.loads(inbox_files[0].read_text(encoding="utf-8"))
    assert payload["problem_ref"] == "language_womb.epistemic_authority.v1"
    assert payload["authority_boundary"]
