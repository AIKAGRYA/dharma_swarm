"""Tests for dharma_swarm.pending_proposals — Shakti/Darwin queue substrate.

Validates:
- append_pending_proposal single-item append
- append_pending_proposals batch append
- File creation on first write
- JSONL format correctness (one valid JSON per line)
- Custom path support
- Empty batch returns 0
- Idempotent directory creation
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.pending_proposals import (
    append_pending_proposal,
    append_pending_proposals,
)


class TestAppendPendingProposal:
    def test_single_append_creates_file(self, tmp_path):
        path = tmp_path / "proposals.jsonl"
        proposal = {"type": "mutation", "target": "cascade.py", "fitness": 0.8}
        result = append_pending_proposal(proposal, path=path)
        assert result == proposal
        assert path.exists()

    def test_single_append_jsonl_format(self, tmp_path):
        path = tmp_path / "proposals.jsonl"
        proposal = {"id": "p1", "source": "shakti"}
        append_pending_proposal(proposal, path=path)
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["id"] == "p1"

    def test_multiple_single_appends(self, tmp_path):
        path = tmp_path / "proposals.jsonl"
        append_pending_proposal({"id": "p1"}, path=path)
        append_pending_proposal({"id": "p2"}, path=path)
        append_pending_proposal({"id": "p3"}, path=path)
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3
        ids = [json.loads(line)["id"] for line in lines]
        assert ids == ["p1", "p2", "p3"]

    def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "proposals.jsonl"
        append_pending_proposal({"test": True}, path=path)
        assert path.exists()

    def test_returns_dict_copy(self, tmp_path):
        path = tmp_path / "proposals.jsonl"
        original = {"key": "value"}
        result = append_pending_proposal(original, path=path)
        assert result == original
        assert result is not original


class TestAppendPendingProposals:
    def test_batch_append(self, tmp_path):
        path = tmp_path / "proposals.jsonl"
        proposals = [
            {"id": "b1", "type": "refactor"},
            {"id": "b2", "type": "optimize"},
            {"id": "b3", "type": "test"},
        ]
        count = append_pending_proposals(proposals, path=path)
        assert count == 3
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_empty_batch_returns_zero(self, tmp_path):
        path = tmp_path / "proposals.jsonl"
        count = append_pending_proposals([], path=path)
        assert count == 0
        assert not path.exists()

    def test_batch_creates_parent_directories(self, tmp_path):
        path = tmp_path / "sub" / "proposals.jsonl"
        append_pending_proposals([{"x": 1}], path=path)
        assert path.exists()

    def test_batch_appends_to_existing(self, tmp_path):
        path = tmp_path / "proposals.jsonl"
        append_pending_proposals([{"id": "first"}], path=path)
        append_pending_proposals([{"id": "second"}, {"id": "third"}], path=path)
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_each_line_valid_json(self, tmp_path):
        path = tmp_path / "proposals.jsonl"
        proposals = [
            {"complex": {"nested": True}, "list": [1, 2, 3]},
            {"unicode": "テスト"},
        ]
        append_pending_proposals(proposals, path=path)
        for line in path.read_text().strip().splitlines():
            parsed = json.loads(line)
            assert isinstance(parsed, dict)

    def test_generator_input(self, tmp_path):
        path = tmp_path / "proposals.jsonl"

        def gen():
            for i in range(5):
                yield {"id": f"g{i}"}

        count = append_pending_proposals(gen(), path=path)
        assert count == 5
