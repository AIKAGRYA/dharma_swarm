from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_packet_provenance import (
    append_witness,
    check_packet_provenance,
    classify_files,
    has_bypass_reason,
    packet_ids_from_message,
    target_covers_path,
)


def _write_packet(packet_dir: Path, packet_id: str, target: str) -> Path:
    path = packet_dir / f"{packet_id}.json"
    path.write_text(
        json.dumps(
            {
                "prompt_hash": packet_id,
                "target": {"path": target},
                "lane": {"lane_id": "dead_code_removal"},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_packet_ids_from_message_reads_multiple_ids() -> None:
    message = "fix thing\n\nPacket-Id: abcdef123456\nPacket-Id: 0123456789abcdef\n"

    assert packet_ids_from_message(message) == ["abcdef123456", "0123456789abcdef"]


def test_hot_governance_path_requires_packet() -> None:
    requirements = classify_files(["docs/governance/PROMPT_GOVERNANCE.md"])

    assert requirements[0].required is True
    assert requirements[0].reason == "hot_or_governance_path"


def test_reports_and_tests_are_exempt() -> None:
    requirements = classify_files(
        [
            "reports/governance/probe.md",
            "tests/test_packet_provenance.py",
            "docs/notes.md",
        ]
    )

    assert [item.required for item in requirements] == [False, False, False]


def test_risky_source_message_requires_packet_but_allows_bypass() -> None:
    requirements = classify_files(
        ["dharma_swarm/vector_store.py"],
        message_text="refactor dead code cleanup",
    )

    assert requirements[0].required is True
    assert requirements[0].bypass_allowed is True


def test_diff_removed_function_requires_packet() -> None:
    diff = """diff --git a/dharma_swarm/vector_store.py b/dharma_swarm/vector_store.py
--- a/dharma_swarm/vector_store.py
+++ b/dharma_swarm/vector_store.py
@@ -1 +0,0 @@
-def old_function():
"""

    requirements = classify_files(
        ["dharma_swarm/vector_store.py"],
        name_status={"dharma_swarm/vector_store.py": "M"},
        diff_text=diff,
    )

    assert requirements[0].required is True


def test_packet_target_file_covers_exact_file() -> None:
    assert target_covers_path("dharma_swarm/vector_store.py", "dharma_swarm/vector_store.py")
    assert not target_covers_path("dharma_swarm/vector_store.py", "dharma_swarm/file_lock.py")


def test_packet_target_directory_covers_nested_file() -> None:
    assert target_covers_path("dharma_swarm", "dharma_swarm/vector_store.py")


def test_check_passes_when_packet_covers_hot_path(tmp_path: Path) -> None:
    packet_id = "abcdef1234567890"
    _write_packet(tmp_path, packet_id, "docs/governance")

    result = check_packet_provenance(
        files=["docs/governance/PROMPT_GOVERNANCE.md"],
        message_text=f"update prompt governance\n\nPacket-Id: {packet_id}\n",
        packet_dir=tmp_path,
    )

    assert result["valid"] is True
    assert result["required_count"] == 1


def test_check_fails_when_packet_does_not_cover_required_file(tmp_path: Path) -> None:
    packet_id = "abcdef1234567890"
    _write_packet(tmp_path, packet_id, "dharma_swarm/vector_store.py")

    result = check_packet_provenance(
        files=["docs/governance/PROMPT_GOVERNANCE.md"],
        message_text=f"update prompt governance\n\nPacket-Id: {packet_id}\n",
        packet_dir=tmp_path,
    )

    assert result["valid"] is False
    assert result["uncovered_required_files"][0]["path"] == "docs/governance/PROMPT_GOVERNANCE.md"


def test_bypass_reason_covers_only_bypass_allowed_source(tmp_path: Path) -> None:
    message = "refactor source\n\nPacket-Bypass-Reason: one line safe local typo cleanup\n"

    assert has_bypass_reason(message)
    source_result = check_packet_provenance(
        files=["dharma_swarm/vector_store.py"],
        message_text=message,
        packet_dir=tmp_path,
    )
    hot_result = check_packet_provenance(
        files=["docs/governance/PROMPT_GOVERNANCE.md"],
        message_text=message,
        packet_dir=tmp_path,
    )

    assert source_result["valid"] is True
    assert hot_result["valid"] is False


def test_append_witness_writes_jsonl(tmp_path: Path) -> None:
    witness_path = tmp_path / "packet_provenance.jsonl"
    result = check_packet_provenance(files=["tests/test_packet_provenance.py"], message_text="")

    append_witness(result, witness_path=witness_path, source="unit-test")

    row = json.loads(witness_path.read_text(encoding="utf-8"))
    assert row["source"] == "unit-test"
    assert row["valid"] is True
    assert row["message"] == "packet provenance not required for this change"
    assert "timestamp_utc" in row
