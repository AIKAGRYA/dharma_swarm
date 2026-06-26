"""Append-only target paths for the Operator Idea Spark ingest lifecycle.

The idea_spark PROJECTION paths defined here derive from ``DHARMA_STATE_DIR``
(the One Way for ~/.dharma redirection) via the shared live-ops contract, so a
test that sets ``DHARMA_STATE_DIR`` to a tmp dir redirects these receipts with
no network and no real-state writes. No new database is introduced (spec
section 5): these are append-only JSON/JSONL projections over the existing
state root.

Scope note: ``DHARMA_STATE_DIR`` redirects ONLY these idea_spark projection
paths. The Chetana staging/wiki/quarantine roots (``staging.STAGING_ROOT`` et
al.), ``stigmergy._DEFAULT_BASE``, ``chetana.governance.WITNESS_DIR``, and
``dharma_kernel._DEFAULT_KERNEL_PATH`` are ``Path.home()``-based module
constants; a fully hermetic lifecycle run (e.g. the e2e fixture) must
monkeypatch those owners explicitly.
"""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.operator_core.live_ops_census_contract import default_state_root


def idea_spark_root(state_root: Path | None = None) -> Path:
    """Return ``<state>/meta/idea_spark`` (default state honors DHARMA_STATE_DIR)."""
    base = Path(state_root) if state_root is not None else default_state_root()
    return base / "meta" / "idea_spark"


def input_receipts_dir(state_root: Path | None = None, *, ensure: bool = False) -> Path:
    path = idea_spark_root(state_root) / "input_receipts"
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path


def candidates_path(state_root: Path | None = None, *, ensure: bool = False) -> Path:
    path = idea_spark_root(state_root) / "candidates.jsonl"
    if ensure:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def routing_receipts_dir(state_root: Path | None = None, *, ensure: bool = False) -> Path:
    path = idea_spark_root(state_root) / "routing_receipts"
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path


def lifecycle_receipts_dir(state_root: Path | None = None, *, ensure: bool = False) -> Path:
    path = idea_spark_root(state_root) / "lifecycle_receipts"
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path


def health_receipts_dir(state_root: Path | None = None, *, ensure: bool = False) -> Path:
    path = idea_spark_root(state_root) / "health"
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path


def memory_kernel_dir(state_root: Path | None = None, *, ensure: bool = False) -> Path:
    path = idea_spark_root(state_root) / "memory_kernel"
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path


def memory_write_receipts_path(state_root: Path | None = None) -> Path:
    return memory_kernel_dir(state_root) / "write_receipts.jsonl"


def memory_decisions_path(state_root: Path | None = None) -> Path:
    return memory_kernel_dir(state_root) / "promotion_decisions.jsonl"


def memory_canonical_receipts_path(state_root: Path | None = None) -> Path:
    return memory_kernel_dir(state_root) / "reviewed_canonical_receipts.jsonl"


def input_receipt_path(input_id: str, state_root: Path | None = None) -> Path:
    return input_receipts_dir(state_root) / f"{input_id}.json"


def routing_receipt_path(correlation_id: str, state_root: Path | None = None) -> Path:
    return routing_receipts_dir(state_root) / f"{correlation_id}.json"


def lifecycle_receipt_path(correlation_id: str, state_root: Path | None = None) -> Path:
    return lifecycle_receipts_dir(state_root) / f"{correlation_id}.json"
