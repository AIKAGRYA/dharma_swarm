from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.runtime import a2a_inbox_quarantine


def _write_inbox_file(root: Path, agent: str, name: str, text: str = "packet") -> Path:
    path = root / agent / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_dry_run_does_not_move_files(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    packet = _write_inbox_file(inboxes, "fable_composer", "packet.json")

    receipt = a2a_inbox_quarantine.run_quarantine(
        inboxes_root=inboxes,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        agents=set(),
        filenames=set(),
        apply=False,
        include_recent=True,
        recent_hours=24.0,
    )

    assert receipt["status"] == "DRY_RUN"
    assert receipt["candidate_count"] == 1
    assert receipt["moved_count"] == 0
    assert packet.exists()
    assert Path(receipt["receipt_path"]).is_file()


def test_apply_moves_files_and_leaves_readme(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    packet = _write_inbox_file(inboxes, "fable_composer", "packet.json")

    receipt = a2a_inbox_quarantine.run_quarantine(
        inboxes_root=inboxes,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        agents={"fable_composer"},
        filenames=set(),
        apply=True,
        include_recent=True,
        recent_hours=24.0,
    )

    assert receipt["status"] == "APPLIED"
    assert receipt["moved_count"] == 1
    assert not packet.exists()
    moved_to = Path(receipt["moved"][0]["to"])
    assert moved_to.is_file()
    assert moved_to.read_text(encoding="utf-8") == "packet"
    readme = inboxes / "fable_composer" / "README.md"
    assert readme.is_file()
    assert "A2A Inbox Quarantine" in readme.read_text(encoding="utf-8")
    saved = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
    assert saved["moved_count"] == 1


def test_recent_files_are_skipped_by_default(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    packet = _write_inbox_file(inboxes, "codex_composer", "new.json")

    receipt = a2a_inbox_quarantine.run_quarantine(
        inboxes_root=inboxes,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        agents=set(),
        filenames=set(),
        apply=True,
        include_recent=False,
        recent_hours=24.0,
    )

    assert receipt["candidate_count"] == 0
    assert receipt["moved_count"] == 0
    assert receipt["skipped"][0]["reason"] == "recent_file_skipped"
    assert packet.exists()


def test_apply_moves_directories_too(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    nested = inboxes / "opus_composer" / ".acks" / "ack.json"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("ack", encoding="utf-8")

    receipt = a2a_inbox_quarantine.run_quarantine(
        inboxes_root=inboxes,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        agents={"opus_composer"},
        filenames=set(),
        apply=True,
        include_recent=True,
        recent_hours=24.0,
    )

    assert receipt["moved_count"] == 1
    assert receipt["candidate_counts_by_agent"] == {"opus_composer": 1}
    assert not nested.parent.exists()
    moved_dir = Path(receipt["moved"][0]["to"])
    assert moved_dir.is_dir()
    assert (moved_dir / "ack.json").read_text(encoding="utf-8") == "ack"


def test_old_files_are_selected_when_recent_filter_excludes_only_new(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    packet = _write_inbox_file(inboxes, "codex_composer", "old.json")
    old = 60 * 60 * 48
    os.utime(packet, (packet.stat().st_atime - old, packet.stat().st_mtime - old))

    receipt = a2a_inbox_quarantine.run_quarantine(
        inboxes_root=inboxes,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        agents=set(),
        filenames=set(),
        apply=False,
        include_recent=False,
        recent_hours=24.0,
    )

    assert receipt["candidate_count"] == 1
    assert receipt["skipped_count"] == 0


def test_filename_filter_moves_only_matching_files(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    target = _write_inbox_file(inboxes, "fable_composer", "broadcast.json")
    other = _write_inbox_file(inboxes, "fable_composer", "direct.json")

    receipt = a2a_inbox_quarantine.run_quarantine(
        inboxes_root=inboxes,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        agents=set(),
        filenames={"broadcast.json"},
        apply=True,
        include_recent=True,
        recent_hours=24.0,
    )

    assert receipt["candidate_count"] == 1
    assert receipt["moved_count"] == 1
    assert not target.exists()
    assert other.exists()
    assert receipt["filename_filter"] == ["broadcast.json"]
    assert any(item["reason"] == "filename_filter_mismatch" for item in receipt["skipped"])
