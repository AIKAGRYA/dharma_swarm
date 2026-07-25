"""PR-07: `chetana verify --mode production` + MCP verdict (audit §5.6, WS-D.4).

Per bucket:
  - approved + verified corpus passes production mode (exit 0)
  - synthetic legacy corpus (pre-chetana pages, no provenance): compat keeps
    the L352-353 exit rule (0), production exits non-zero
  - kernel-drift: compat 0, production non-zero
  - review_status != approved (verified sig): compat 0, production non-zero
  - zero-sig / schema-error: both modes non-zero
  - unavailable kernel: production fails closed even on an empty corpus
  - mcp tool_verify: verdict/verdict_reasons/unapproved fields per mode;
    unknown mode raises
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.chetana import staging as staging_mod
from dharma_swarm.chetana.cli import build_parser
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.mcp_server import tool_verify
from dharma_swarm.chetana.promote import approve_atom, promote
from dharma_swarm.chetana.provenance import (
    AtomProvenance,
    FrontmatterSchema,
    GateCheckRecord,
    assemble_atom,
    compute_axiom_signature_v2,
    new_atom_id,
    now_iso,
)


@pytest.fixture(autouse=True)
def _sandbox_stigmergy(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    from dharma_swarm import stigmergy as stigmergy_mod

    sandbox = tmp_path_factory.mktemp("stigmergy")
    monkeypatch.setattr(stigmergy_mod, "_DEFAULT_BASE", sandbox, raising=True)
    monkeypatch.setattr(stigmergy_mod, "_default_store", None, raising=True)


@pytest.fixture(autouse=True)
def _sandbox_kernel(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    from dharma_swarm import dharma_kernel as kernel_mod

    kernel_path = tmp_path_factory.mktemp("kernel") / "kernel.json"
    asyncio.run(kernel_mod.KernelGuard(kernel_path).save(kernel_mod.DharmaKernel.create_default()))
    monkeypatch.setattr(kernel_mod, "_DEFAULT_KERNEL_PATH", kernel_path, raising=True)


@pytest.fixture(autouse=True)
def _stub_vector_ingest(monkeypatch: pytest.MonkeyPatch):
    import dharma_swarm.wiki_vector_ingest as wvi

    monkeypatch.setattr(
        wvi,
        "ingest_wiki_concepts",
        lambda **kwargs: SimpleNamespace(discovered_files=1, backfill={}, sync_index={}, reembed={}),
        raising=True,
    )


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    staging_root = tmp_path / "staging"
    quarantine_root = tmp_path / "quarantine"
    wiki_root = tmp_path / "wiki"
    trusted_root = wiki_root / "concepts"
    pending_root = wiki_root / "pending"
    for d in (staging_root, quarantine_root, wiki_root, trusted_root, pending_root):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(staging_mod, "STAGING_ROOT", staging_root, raising=True)
    monkeypatch.setattr(staging_mod, "QUARANTINE_ROOT", quarantine_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_PENDING_ROOT", pending_root, raising=True)
    return tmp_path


def _current_kernel_sig() -> str:
    from dharma_swarm import dharma_kernel as kernel_mod

    return asyncio.run(kernel_mod.KernelGuard().load()).signature


def _verify_exit(mode: str = "compat", path: str | None = None) -> int:
    argv = ["verify"]
    if path:
        argv.append(path)
    argv.extend(["--mode", mode])
    args = build_parser().parse_args(argv)
    return args.func(args)


def _write_synthetic_atom(
    trusted_root: Path,
    *,
    review_status: str = "approved",
    sign_kernel: str | None = None,
    zero_sig: bool = False,
    slug: str = "synthetic-atom",
) -> Path:
    fm = FrontmatterSchema(
        title=f"Synthetic {slug}",
        atom_id=new_atom_id(),
        type="atomic",
        confidence=0.7,
        source=[
            {
                "kind": "note",
                "path": "synthetic",
                "captured": "2026-07-25",
                "captured_by": "test",
            }
        ],
        provenance=AtomProvenance(
            promoted_by="test",
            promoted_at=now_iso(),
            gate_check=GateCheckRecord(result="ALLOW", checked_at=now_iso()),
            axiom_signature="0" * 64,
            review_status=review_status,
        ),
        stale_after="2099-01-01",
    )
    body = "synthetic body\n"
    if not zero_sig:
        sig = compute_axiom_signature_v2(fm, body, sign_kernel or _current_kernel_sig())
        fm = fm.model_copy(
            update={"provenance": fm.provenance.model_copy(update={"axiom_signature": sig})}
        )
    path = trusted_root / f"{slug}.md"
    path.write_text(assemble_atom(fm, body), encoding="utf-8")
    return path


def _write_legacy_page(trusted_root: Path, slug: str) -> Path:
    path = trusted_root / f"{slug}.md"
    path.write_text(
        "---\ntitle: Legacy Concept\ntags: [wiki]\n---\n\n# Legacy\n\npre-chetana content\n",
        encoding="utf-8",
    )
    return path


def _approved_pipeline_atom(title: str = "Verify Prod Atom") -> Path:
    result = ingest(source="verify production body", source_kind="note", title=title, confidence=0.6)
    assert result.staged_count == 1
    pr = promote(staged_path=result.atoms[0], promoted_by="t")
    assert pr.decision in {"ALLOW", "WARN"}
    ar = approve_atom(path=pr.trusted_path, reviewer="operator")
    assert ar.decision == "APPROVED", ar.error
    return ar.trusted_path


# ---------------------------------------------------------------------------
# CLI exit semantics per bucket
# ---------------------------------------------------------------------------


def test_production_passes_on_approved_verified_corpus(sandbox: Path):
    _approved_pipeline_atom()
    assert list(staging_mod.list_trusted()), "pipeline atom must land in trusted"
    assert _verify_exit("compat") == 0
    assert _verify_exit("production") == 0


def test_synthetic_legacy_corpus_compat_passes_production_fails(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    for i in range(3):
        _write_legacy_page(trusted, f"legacy-{i}")
    # today's L352-353 rule: pre-chetana atoms are tolerated
    assert _verify_exit("compat") == 0
    # production: no-provenance is a hard fail
    assert _verify_exit("production") == 1


def test_kernel_drift_fails_production_only(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    _write_synthetic_atom(trusted, sign_kernel="d" * 64, slug="drifted")
    assert _verify_exit("compat") == 0
    assert _verify_exit("production") == 1


def test_unapproved_review_status_fails_production_only(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    _write_synthetic_atom(trusted, review_status="auto_promoted", slug="auto-promoted")
    # signature verifies, so compat sees a clean corpus
    assert _verify_exit("compat") == 0
    assert _verify_exit("production") == 1


def test_zero_sig_fails_both_modes(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    _write_synthetic_atom(trusted, zero_sig=True, slug="zero-signed")
    assert _verify_exit("compat") == 1
    assert _verify_exit("production") == 1


def test_schema_error_fails_both_modes(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    (trusted / "broken.md").write_text("no frontmatter here at all\n", encoding="utf-8")
    assert _verify_exit("compat") == 1
    assert _verify_exit("production") == 1


def test_kernel_unavailable_fails_production_even_on_empty_corpus(
    sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from dharma_swarm import dharma_kernel as kernel_mod

    monkeypatch.setattr(
        kernel_mod, "_DEFAULT_KERNEL_PATH", tmp_path / "missing-kernel.json", raising=True
    )
    assert _verify_exit("compat") == 0
    assert _verify_exit("production") == 1


def test_single_path_target_production(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    good = _write_synthetic_atom(trusted, slug="good-approved")
    bad = _write_synthetic_atom(trusted, review_status="staged", slug="staged-leak")
    assert _verify_exit("production", str(good)) == 0
    assert _verify_exit("production", str(bad)) == 1


# ---------------------------------------------------------------------------
# MCP tool_verify verdict field
# ---------------------------------------------------------------------------


def test_tool_verify_production_verdict_and_reasons(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    _write_synthetic_atom(trusted, slug="approved-ok")
    _write_synthetic_atom(trusted, sign_kernel="d" * 64, slug="drifted")
    _write_synthetic_atom(trusted, review_status="auto_promoted", slug="auto-promoted")

    out = tool_verify(mode="production")
    assert out["mode"] == "production"
    assert out["verdict"] == "fail"
    assert out["verified_count"] == 2  # approved-ok + auto-promoted (sig-valid)
    assert out["kernel_drift_count"] == 1
    assert out["unapproved_count"] == 1
    assert any("kernel-drift" in r for r in out["verdict_reasons"])
    assert any("unapproved" in r for r in out["verdict_reasons"])
    assert out["buckets"]["unapproved"], "unapproved bucket must list the atom"


def test_tool_verify_compat_verdict_ignores_legacy_and_drift(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    _write_legacy_page(trusted, "legacy-page")
    _write_synthetic_atom(trusted, sign_kernel="d" * 64, slug="drifted")

    compat = tool_verify(mode="compat")
    assert compat["verdict"] == "pass"
    assert compat["verdict_reasons"] == []

    prod = tool_verify(mode="production")
    assert prod["verdict"] == "fail"


def test_tool_verify_production_verdict_passes_clean(sandbox: Path):
    trusted = sandbox / "wiki" / "concepts"
    _write_synthetic_atom(trusted, slug="only-approved")
    out = tool_verify(mode="production")
    assert out["verdict"] == "pass"
    assert out["verdict_reasons"] == []


def test_tool_verify_unknown_mode_raises(sandbox: Path):
    with pytest.raises(ValueError, match="unknown verify mode"):
        tool_verify(mode="promiscuous")
