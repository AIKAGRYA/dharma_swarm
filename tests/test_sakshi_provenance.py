"""Tests for Sakshi provenance log — append-only chain with integrity verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.correlation_context import correlation_scope_sync
from dharma_swarm.sakshi.provenance_log import (
    ProvenanceEntry,
    ProvenanceLog,
)


class TestProvenanceEntry:
    def test_compute_hash_deterministic(self) -> None:
        entry = ProvenanceEntry(
            entry_id="fixed-id",
            timestamp="2026-05-20T12:00:00+00:00",
            actor_id="devin-abc",
            actor_kind="devin",
            action="pr_created",
            target_ref="PR #318",
        )
        h1 = entry.compute_hash()
        h2 = entry.compute_hash()
        assert h1 == h2
        assert len(h1) == 16  # sha256 truncated to 16 hex chars

    def test_different_entries_different_hashes(self) -> None:
        e1 = ProvenanceEntry(
            actor_id="devin", actor_kind="devin", action="pr_created"
        )
        e2 = ProvenanceEntry(
            actor_id="copilot", actor_kind="copilot", action="pr_merged"
        )
        assert e1.compute_hash() != e2.compute_hash()


class TestProvenanceLog:
    def test_append_and_read(self, tmp_path: Path) -> None:
        log = ProvenanceLog(path=tmp_path / "prov.jsonl")
        entry = ProvenanceEntry(
            actor_id="devin-session-1",
            actor_kind="devin",
            action="pr_created",
            target_ref="PR #318",
            track_id="cockpit-control-surface-2026-05",
        )
        entry_hash = log.append(entry)
        assert entry_hash != ""

        entries = log.read_all()
        assert len(entries) == 1
        assert entries[0].actor_id == "devin-session-1"
        assert entries[0].action == "pr_created"
        assert entries[0].entry_hash == entry_hash

    def test_chain_integrity(self, tmp_path: Path) -> None:
        log = ProvenanceLog(path=tmp_path / "prov.jsonl")

        log.append(ProvenanceEntry(
            actor_id="devin", actor_kind="devin", action="pr_created",
        ))
        log.append(ProvenanceEntry(
            actor_id="human", actor_kind="human", action="pr_merged",
        ))
        log.append(ProvenanceEntry(
            actor_id="devin", actor_kind="devin", action="track_closed",
        ))

        assert log.verify_chain()
        entries = log.read_all()
        assert entries[0].previous_entry_hash == ""
        assert entries[1].previous_entry_hash == entries[0].entry_hash
        assert entries[2].previous_entry_hash == entries[1].entry_hash

    def test_chain_detects_tampering(self, tmp_path: Path) -> None:
        log_path = tmp_path / "prov.jsonl"
        log = ProvenanceLog(path=log_path)

        log.append(ProvenanceEntry(
            actor_id="a", actor_kind="devin", action="pr_created",
        ))
        log.append(ProvenanceEntry(
            actor_id="b", actor_kind="human", action="pr_merged",
        ))

        # Tamper: modify the first entry's hash in the file
        lines = log_path.read_text().splitlines()
        import json
        entry0 = json.loads(lines[0])
        entry0["entry_hash"] = "tampered_hash"
        lines[0] = json.dumps(entry0)
        log_path.write_text("\n".join(lines) + "\n")

        # Re-read with a fresh log instance
        log2 = ProvenanceLog(path=log_path)
        assert not log2.verify_chain()

    def test_read_for_actor(self, tmp_path: Path) -> None:
        log = ProvenanceLog(path=tmp_path / "prov.jsonl")
        log.append(ProvenanceEntry(
            actor_id="devin-1", actor_kind="devin", action="pr_created",
        ))
        log.append(ProvenanceEntry(
            actor_id="copilot-1", actor_kind="copilot", action="pr_created",
        ))
        log.append(ProvenanceEntry(
            actor_id="devin-1", actor_kind="devin", action="track_closed",
        ))

        devin_entries = log.read_for_actor("devin-1")
        assert len(devin_entries) == 2
        assert all(e.actor_id == "devin-1" for e in devin_entries)

    def test_read_for_track(self, tmp_path: Path) -> None:
        log = ProvenanceLog(path=tmp_path / "prov.jsonl")
        log.append(ProvenanceEntry(
            actor_id="d", actor_kind="devin", action="pr_created",
            track_id="track-a",
        ))
        log.append(ProvenanceEntry(
            actor_id="d", actor_kind="devin", action="pr_created",
            track_id="track-b",
        ))

        track_a = log.read_for_track("track-a")
        assert len(track_a) == 1

    def test_read_for_trace(self, tmp_path: Path) -> None:
        log = ProvenanceLog(path=tmp_path / "prov.jsonl")
        log.append(ProvenanceEntry(
            actor_id="codex",
            actor_kind="codex",
            action="track_opened",
            trace_id="trc-sakshi",
            trace_id_source="operator_supplied",
        ))
        log.append(ProvenanceEntry(
            actor_id="codex",
            actor_kind="codex",
            action="track_closed",
        ))

        entries = log.read_for_trace("trc-sakshi")
        assert len(entries) == 1
        assert entries[0].trace_id_source == "operator_supplied"

    def test_entry_defaults_trace_metadata_from_correlation_context(self) -> None:
        with correlation_scope_sync(trace_id="trc-sakshi-context"):
            entry = ProvenanceEntry(
                actor_id="codex",
                actor_kind="codex",
                action="track_opened",
            )

        assert entry.trace_id == "trc-sakshi-context"
        assert entry.trace_id_source == "correlation_context"

    def test_empty_log(self, tmp_path: Path) -> None:
        log = ProvenanceLog(path=tmp_path / "prov.jsonl")
        assert log.read_all() == []
        assert log.count() == 0
        assert log.verify_chain()
        assert log.last_entry() is None

    def test_count(self, tmp_path: Path) -> None:
        log = ProvenanceLog(path=tmp_path / "prov.jsonl")
        log.append(ProvenanceEntry(actor_id="a", actor_kind="devin", action="pr_created"))
        log.append(ProvenanceEntry(actor_id="b", actor_kind="human", action="pr_merged"))
        assert log.count() == 2

    def test_last_entry(self, tmp_path: Path) -> None:
        log = ProvenanceLog(path=tmp_path / "prov.jsonl")
        log.append(ProvenanceEntry(actor_id="first", actor_kind="devin", action="pr_created"))
        log.append(ProvenanceEntry(actor_id="last", actor_kind="human", action="track_closed"))
        last = log.last_entry()
        assert last is not None
        assert last.actor_id == "last"
