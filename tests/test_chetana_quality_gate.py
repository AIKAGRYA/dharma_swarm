"""Tests for chetana's wiki quality/admission gate.

The gate is the ADDITIVE layer that keeps slop out of the trusted wiki:
empty-equivalent session fragments ("none recorded" / "unknown" / "N/A"),
sub-floor thin atoms, and near-duplicates are REJECTed; thin-but-real atoms
are routed to a review queue (WARN); rich curated atoms PASS.

These tests are self-contained (own sandbox + signed kernel) so they run via:
    python -m pytest tests/test_chetana_quality_gate.py -q
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import promote
from dharma_swarm.chetana.quality_gate import (
    QualityResult,
    content_hash,
    is_empty_equivalent,
    meaningful_token_count,
    quality_check_atom,
)


# A genuine, richly-linked article body (curated-tier shape). Grounded prose;
# every [[link]] is just illustrative text for the token/link counters.
REAL_ARTICLE_BODY = """\
The R_V metric measures representation-space contraction under self-referential
processing. Across eight transformer families, six contract toward a witness
attractor while [[pythia-2-8b]] expands, so the phenomenon is real but
non-universal. The primary causal site is the layer-5 residual stream with an
effect size around four, and [[head-21-at-l5]] is the first direction-specific
steering site we have isolated. R_V itself appears to be an epiphenomenal
readout rather than the underlying mechanism, which the [[geometric-lens]]
analysis supports. See also [[strange-loop]] and the [[bridge-hypothesis]] for
the contemplative-mechanistic correspondence this evidence anchors.
"""

# An empty-equivalent null-session fragment of the kind bulk-promoted as
# concepts/*turn-N.md — exactly the slop the gate exists to reject.
NULL_SESSION_BODY = """\
## Files changed
none recorded

## Summary
unknown

## Notes
N/A
"""


@pytest.fixture(autouse=True)
def _sandbox_kernel(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Real signed kernel so fail-closed chetana governance can run."""
    from dharma_swarm import dharma_kernel as kernel_mod

    kernel_path = tmp_path_factory.mktemp("kernel") / "kernel.json"
    asyncio.run(
        kernel_mod.KernelGuard(kernel_path).save(kernel_mod.DharmaKernel.create_default())
    )
    monkeypatch.setattr(kernel_mod, "_DEFAULT_KERNEL_PATH", kernel_path, raising=True)


@pytest.fixture(autouse=True)
def _sandbox_stigmergy(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    try:
        from dharma_swarm import stigmergy as stigmergy_mod
    except Exception:
        return
    sandbox = tmp_path_factory.mktemp("stigmergy")
    monkeypatch.setattr(stigmergy_mod, "_DEFAULT_BASE", sandbox, raising=True)
    monkeypatch.setattr(stigmergy_mod, "_default_store", None, raising=True)


@pytest.fixture
def chetana_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect chetana's staging / wiki / quarantine roots to a tmp tree."""
    from dharma_swarm.chetana import decay as decay_mod
    from dharma_swarm.chetana import gap_scan as gap_mod
    from dharma_swarm.chetana import palace as palace_mod
    from dharma_swarm.chetana import revival as revival_mod
    from dharma_swarm.chetana import staging as staging_mod

    staging_root = tmp_path / "staging"
    quarantine_root = tmp_path / "quarantine"
    wiki_root = tmp_path / "wiki"
    trusted_root = wiki_root / "concepts"
    for d in (staging_root, quarantine_root, wiki_root, trusted_root):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(staging_mod, "STAGING_ROOT", staging_root, raising=True)
    monkeypatch.setattr(staging_mod, "QUARANTINE_ROOT", quarantine_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(decay_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(gap_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(palace_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(
        palace_mod, "DEFAULT_PALACE_PATH", tmp_path / "memory_palace.canvas", raising=True
    )
    monkeypatch.setattr(revival_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    return tmp_path


# ---- unit: pure grading -----------------------------------------------------


def test_quality_check_rejects_null_session(tmp_path: Path):
    trusted = tmp_path / "concepts"
    trusted.mkdir()
    result = quality_check_atom(
        title="Session turn-42",
        body=NULL_SESSION_BODY,
        trusted_root=trusted,
    )
    assert isinstance(result, QualityResult)
    assert result.grade == "REJECT"
    assert "empty_equivalent" in result.reason or "too_thin" in result.reason


def test_quality_check_passes_real_article(tmp_path: Path):
    trusted = tmp_path / "concepts"
    trusted.mkdir()
    result = quality_check_atom(
        title="R_V metric", body=REAL_ARTICLE_BODY, trusted_root=trusted
    )
    assert result.grade == "PASS"
    assert result.admit is True
    assert result.meaningful_tokens >= 45
    assert result.wikilinks >= 1


def test_empty_equivalent_helpers():
    assert is_empty_equivalent("none recorded")
    assert is_empty_equivalent(NULL_SESSION_BODY)
    assert is_empty_equivalent("   \n\n## Summary\n-\n")
    assert not is_empty_equivalent(REAL_ARTICLE_BODY)
    assert meaningful_token_count(NULL_SESSION_BODY) < 25
    assert meaningful_token_count(REAL_ARTICLE_BODY) >= 45


def test_quality_check_rejects_near_duplicate(tmp_path: Path):
    trusted = tmp_path / "concepts"
    trusted.mkdir()
    # Seed an existing trusted atom with the same normalized body.
    (trusted / "existing.md").write_text(
        "---\ntitle: Existing Concept\n---\n" + REAL_ARTICLE_BODY,
        encoding="utf-8",
    )
    result = quality_check_atom(
        title="A Totally Different Title",
        body=REAL_ARTICLE_BODY,
        trusted_root=trusted,
    )
    assert result.grade == "REJECT"
    assert "near_duplicate" in result.reason


def test_content_hash_is_whitespace_insensitive():
    assert content_hash("a  b\n c") == content_hash("a b c")


# ---- integration: promote() with enforce_quality ----------------------------


def test_promote_quality_gate_rejects_null_session(chetana_sandbox: Path):
    ing = ingest(
        source=NULL_SESSION_BODY,
        source_kind="note",
        title="Session turn-99",
        confidence=0.5,
    )
    staged = ing.atoms[0]

    pr = promote(staged_path=staged, promoted_by="tester", enforce_quality=True)

    assert pr.trusted_path is None
    assert pr.review_status == "rejected"
    assert pr.quality_grade == "REJECT"
    # Nothing slop landed in the trusted concepts tier.
    concepts = chetana_sandbox / "wiki" / "concepts"
    assert list(concepts.glob("*.md")) == []
    # Staged atom preserved in quarantine for audit (reversible, not deleted).
    quarantined = list((chetana_sandbox / "quarantine").rglob("*.md"))
    assert len(quarantined) == 1


def test_promote_quality_gate_passes_real_article(chetana_sandbox: Path):
    ing = ingest(
        source=REAL_ARTICLE_BODY,
        source_kind="note",
        title="R_V Metric Curated",
        confidence=0.8,
    )
    staged = ing.atoms[0]

    pr = promote(staged_path=staged, promoted_by="tester", enforce_quality=True)

    assert pr.trusted_path is not None and pr.trusted_path.exists()
    assert pr.quality_grade == "PASS"
    # Landed in concepts/, not the review queue.
    assert pr.trusted_path.parent.name == "concepts"


def test_promote_quality_gate_routes_warn_to_review_queue(chetana_sandbox: Path):
    # Real but thin + unlinked → WARN → review queue, not concepts/.
    thin_body = (
        "Witness attractor contraction appeared during one informal afternoon "
        "probe of a single small model. The operator noted possible contraction "
        "but recorded neither effect size nor layer index nor replication across "
        "any other model family yet."
    )
    ing = ingest(
        source=thin_body,
        source_kind="note",
        title="Thin Probe Note",
        confidence=0.5,
    )
    staged = ing.atoms[0]

    pr = promote(staged_path=staged, promoted_by="tester", enforce_quality=True)

    assert pr.quality_grade == "WARN"
    assert pr.trusted_path is not None and pr.trusted_path.exists()
    assert pr.trusted_path.parent.name == "review_queue"
    # Concepts tier stays clean.
    assert list((chetana_sandbox / "wiki" / "concepts").glob("*.md")) == []


def test_promote_without_enforce_quality_is_unchanged(chetana_sandbox: Path):
    """Default (enforce_quality=False) keeps legacy behavior: even a thin atom
    promotes straight to concepts/. The gate is strictly opt-in."""
    ing = ingest(
        source="atom body for promotion",
        source_kind="note",
        title="Legacy Tiny Atom",
        confidence=0.8,
    )
    pr = promote(staged_path=ing.atoms[0], promoted_by="tester")
    assert pr.trusted_path is not None and pr.trusted_path.exists()
    assert pr.trusted_path.parent.name == "concepts"
    assert pr.quality_grade is None
