"""PR 3 verifier — candidate -> Chetana staged atom (gated, non-bypass).

Deterministic, no-network (temp Chetana roots). Proves:
- a candidate becomes a STAGED (untrusted) atom carrying corr/candidate ids;
- the bulk cron promoter refuses lifecycle-governed atoms;
- promotion to trusted goes only through the gated chetana.promote path.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

from dharma_swarm.chetana.provenance import parse_frontmatter
from dharma_swarm.idea_spark.chetana_adapter import (
    IDEA_SPARK_LIFECYCLE_TAG,
    promote_candidate_atom,
    stage_candidate,
)
from dharma_swarm.idea_spark.fixtures import NOTE_FIXTURE
from dharma_swarm.idea_spark.projection import candidate_from_operator_receipt

FIXED_NOW = "2026-06-26T00:00:00Z"
_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def chetana_tmp(tmp_path, monkeypatch):
    """Redirect Chetana roots + stigmergy + signed kernel to a tmp tree."""
    from dharma_swarm.chetana import staging as staging_mod

    staging_root = tmp_path / "staging"
    quarantine_root = tmp_path / "quarantine"
    wiki_root = tmp_path / "wiki"
    trusted_root = wiki_root / "concepts"
    for directory in (staging_root, quarantine_root, wiki_root, trusted_root):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(staging_mod, "STAGING_ROOT", staging_root, raising=True)
    monkeypatch.setattr(staging_mod, "QUARANTINE_ROOT", quarantine_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)

    try:  # keep emit_mark from polluting the operator's real marks.jsonl
        from dharma_swarm import stigmergy as stig

        monkeypatch.setattr(stig, "_DEFAULT_BASE", tmp_path / "stig", raising=False)
        monkeypatch.setattr(stig, "_default_store", None, raising=False)
    except Exception:
        pass

    try:  # keep witness logs in the sandbox
        from dharma_swarm.chetana import governance as gov

        monkeypatch.setattr(gov, "WITNESS_DIR", tmp_path / "witness", raising=False)
    except Exception:
        pass

    from dharma_swarm import dharma_kernel as kernel_mod

    kernel_path = tmp_path / "kernel.json"
    asyncio.run(kernel_mod.KernelGuard(kernel_path).save(kernel_mod.DharmaKernel.create_default()))
    monkeypatch.setattr(kernel_mod, "_DEFAULT_KERNEL_PATH", kernel_path, raising=True)

    return tmp_path


def _candidate():
    receipt = NOTE_FIXTURE.build_receipt()
    return candidate_from_operator_receipt(
        receipt, claim=NOTE_FIXTURE.content, domain="tooling", now=FIXED_NOW
    )


def _load_consume_review_marks():
    path = _REPO_ROOT / "scripts" / "consume_review_marks.py"
    spec = importlib.util.spec_from_file_location("_consume_review_marks_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage_candidate_lands_untrusted(chetana_tmp) -> None:
    candidate = _candidate()
    staged = stage_candidate(candidate)
    assert staged.path.exists()
    assert str(chetana_tmp / "staging") in str(staged.path)
    # Untrusted: no provenance block.
    schema, _body = parse_frontmatter(staged.path.read_text(encoding="utf-8"))
    assert schema is not None
    assert schema.provenance is None
    # No trusted atom was written.
    trusted_dir = chetana_tmp / "wiki" / "concepts"
    assert list(trusted_dir.glob("*.md")) == []


def test_staged_atom_carries_correlation_and_candidate_ids(chetana_tmp) -> None:
    candidate = _candidate()
    staged = stage_candidate(candidate)
    text = staged.path.read_text(encoding="utf-8")
    assert IDEA_SPARK_LIFECYCLE_TAG in text
    assert f"corr:{candidate.correlation_id}" in text
    assert f"candidate:{candidate.candidate_id}" in text
    schema, _ = parse_frontmatter(text)
    assert f"corr:{candidate.correlation_id}" in schema.tags


def test_bulk_promoter_refuses_lifecycle_atoms(chetana_tmp) -> None:
    candidate = _candidate()
    staged = stage_candidate(candidate)
    crm = _load_consume_review_marks()
    meta = crm.parse_frontmatter(staged.path.read_text(encoding="utf-8"))
    assert meta is not None
    assert crm.is_lifecycle_governed(meta) is True
    ok, reason = crm.should_promote(meta, 0.0, has_independent_review=True)
    assert ok is False
    assert "chetana.promote" in reason


def test_promotion_goes_through_the_gate(chetana_tmp) -> None:
    candidate = _candidate()
    staged = stage_candidate(candidate)
    result = promote_candidate_atom(staged.path, auto_promote=True)
    assert result.decision in {"ALLOW", "WARN", "BLOCK"}
    # The staged file is consumed by the gated promote (not left dangling).
    assert not staged.path.exists()
    if result.decision != "BLOCK":
        assert result.trusted_path is not None and result.trusted_path.exists()
        schema, _ = parse_frontmatter(result.trusted_path.read_text(encoding="utf-8"))
        # Trusted atoms carry provenance (the gate ran).
        assert schema is not None and schema.provenance is not None


def test_promotion_fails_closed_without_valid_kernel(chetana_tmp, monkeypatch) -> None:
    # Pin the fail-closed invariant: with no valid signed kernel the real gate
    # must BLOCK (never silently mint a trusted atom).
    from dharma_swarm import dharma_kernel as kernel_mod

    candidate = _candidate()
    staged = stage_candidate(candidate)
    monkeypatch.setattr(
        kernel_mod, "_DEFAULT_KERNEL_PATH", chetana_tmp / "no_such_kernel.json", raising=True
    )
    result = promote_candidate_atom(staged.path, auto_promote=True)
    assert result.decision == "BLOCK"
    assert result.trusted_path is None
    # Nothing reached the trusted tier.
    assert list((chetana_tmp / "wiki" / "concepts").glob("*.md")) == []
