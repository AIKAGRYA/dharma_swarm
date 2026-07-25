"""Loop 1 closure-run harness: state-dir resolution.

The load-bearing invariant is that a *witnessed* closure must land its
EvidenceReceipt in the canonical runtime.db that `make orient` reads. The
Phase 1b "NOT CLOSED" verdict was caused precisely by a green closure written
to a sandbox tempdir orient never consults. These tests pin the resolution:
``--canonical`` targets the canonical state dir (sourced from the runtime_state
owner, not a literal), the bare default is a non-canonical sandbox, and an
explicit path equal to the canonical one is recognised as canonical.

No network, no swarm boot — only the pure state-dir resolver is exercised.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest
import json
import sqlite3
from scripts.loop1_closure_run import _read_served_provider_truth

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/loop1_closure_run.py"


def _load():
    spec = importlib.util.spec_from_file_location("loop1_closure_run", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_canonical_state_dir_matches_orient_runtime_db():
    """The harness's canonical state dir must be the grandparent of the same
    DEFAULT_RUNTIME_DB orient projects loop1_live from — so a SwarmManager
    booted there writes to the file orient reads."""
    mod = _load()
    from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

    state_dir = mod._canonical_state_dir()
    assert (Path(state_dir) / "state" / "runtime.db").resolve() == Path(
        DEFAULT_RUNTIME_DB
    ).resolve()


def test_canonical_flag_targets_canonical():
    mod = _load()
    args = argparse.Namespace(canonical=True, state_dir=None)
    state_dir, is_canonical = mod._resolve_state_dir(args)
    assert is_canonical is True
    assert Path(state_dir).resolve() == mod._canonical_state_dir().resolve()


def test_default_is_non_canonical_sandbox():
    """Bare default must be a sandbox — closing there is NOT witnessed by
    orient, and main() warns. This is the Phase 1b footgun guard."""
    mod = _load()
    args = argparse.Namespace(canonical=False, state_dir=None)
    state_dir, is_canonical = mod._resolve_state_dir(args)
    assert is_canonical is False
    assert Path(state_dir).exists()  # tempdir created


def test_explicit_path_equal_to_canonical_is_canonical():
    mod = _load()
    canon = str(mod._canonical_state_dir())
    args = argparse.Namespace(canonical=False, state_dir=canon)
    _state_dir, is_canonical = mod._resolve_state_dir(args)
    assert is_canonical is True


def test_canonical_and_state_dir_are_mutually_exclusive():
    mod = _load()
    args = argparse.Namespace(canonical=True, state_dir="/tmp/somewhere")
    with pytest.raises(SystemExit):
        mod._resolve_state_dir(args)


def test_loop1_closure_run_counts_served_provider_truth(tmp_path):
    state_dir = tmp_path / "loop1"
    db = state_dir / "state" / "runtime.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        create table delegation_runs (
            run_id text primary key,
            status text,
            metadata_json text,
            receipt_json text
        );
        create table runtime_receipts (
            receipt_id text primary key,
            run_id text,
            payload_json text
        );
        """
    )
    conn.execute(
        "insert into delegation_runs values (?, ?, ?, ?)",
        (
            "run_1",
            "completed",
            json.dumps(
                {
                    "actual_served_provider": "ollama",
                    "actual_served_model": "qwen3-coder",
                }
            ),
            json.dumps({"provider": "orchestrator", "model": ""}),
        ),
    )
    conn.execute(
        "insert into delegation_runs values (?, ?, ?, ?)",
        (
            "run_2",
            "completed",
            "{}",
            json.dumps({"provider": "ollama", "model": "llama3.2"}),
        ),
    )
    conn.execute(
        "insert into runtime_receipts values (?, ?, ?)",
        (
            "rr_1",
            "run_1",
            json.dumps({"served_provider": "ollama", "served_model": "qwen3-coder"}),
        ),
    )
    conn.commit()
    conn.close()

    truth = _read_served_provider_truth(state_dir)

    assert truth["exists"] is True
    assert truth["completed_runs_with_truth"] == 2
    assert truth["delegation_receipts_with_truth"] == 1
    assert truth["runtime_receipts_with_truth"] == 1
    assert truth["sample"]["served_provider"] == "ollama"
