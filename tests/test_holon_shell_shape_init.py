from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime.holon_shell_shape_init import init_holon_shell_shape


def test_init_holon_shell_shape_creates_canonical_paths_and_receipt(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    home = agents_root / "codex_composer"
    home.mkdir(parents=True)
    (home / "identity.json").write_text('{"agent_uid":"codex_composer"}\n', encoding="utf-8")
    (home / "living_agent.json").write_text('{"agent_uid":"codex_composer"}\n', encoding="utf-8")

    receipt = init_holon_shell_shape(
        "codex_composer",
        agents_root=agents_root,
        session_id="test-shell",
    )

    for relative in [
        "dialogue/operator_sessions.jsonl",
        "dialogue/relationship_memory.jsonl",
        "dialogue/conversation_receipts",
        "sanctum/codex",
        "sanctum/vault",
        "sanctum/dojo",
        "sanctum/ingest_gate",
        "sanctum/tools",
        "sanctum/receipts",
    ]:
        assert (home / relative).exists()
    assert receipt["schema_version"] == "dharma.holon_shell_shape_init.v1"
    assert receipt["claim_scope"]["heartbeat_claim"] is False
    receipt_path = Path(receipt["receipt_path"])
    assert receipt_path.exists()
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["holon"] == "codex_composer"
    assert payload["session_id"] == "test-shell"


def test_init_holon_shell_shape_requires_existing_livingdock_core(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    (agents_root / "codex_composer").mkdir(parents=True)

    try:
        init_holon_shell_shape("codex_composer", agents_root=agents_root)
    except FileNotFoundError as exc:
        assert "identity.json" in str(exc)
        assert "living_agent.json" in str(exc)
    else:
        raise AssertionError("expected missing core files to fail")
