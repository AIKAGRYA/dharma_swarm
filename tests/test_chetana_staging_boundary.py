"""PR-06: staged content never enters the trusted projection (audit §5.5, WS-D.3/5/6).

Covers every hole the audit + recon named:
  - promote routes non-approved atoms to the pending root, never concepts/
  - vector auto-ingest is hard-gated on review_status == approved and scoped
    to the single promoted file
  - write_trusted slug collisions fail closed (legacy pages without atom_id
    are protected; no bare-except fail-open)
  - axiom signature v2 covers frontmatter (incl. review_status) + body;
    verify accepts v1 and v2
  - governance._coerce_decision unknown verdict (incl. None) → BLOCK
  - the approve door verifies the promote-time v2 signature, refuses v1
    downgrades, re-runs the telos gates, fails closed on slug collisions,
    and only approves in place inside the trusted dir
  - MCP: tool_promote has no auto_promote; tool_approve is operator-token
    gated (free-string reviewer abolished; optional display name recorded)
  - OP-4 relocation script is dry-run by default and fail-closed on collision
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.chetana import staging as staging_mod
from dharma_swarm.chetana.governance import _coerce_decision
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import approve_atom, promote
from dharma_swarm.chetana.provenance import (
    parse_frontmatter,
    signature_matches,
)
from dharma_swarm.chetana.staging import write_trusted

REPO_ROOT = Path(__file__).resolve().parents[1]


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


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from dharma_swarm.chetana import decay as decay_mod
    from dharma_swarm.chetana import gap_scan as gap_mod
    from dharma_swarm.chetana import palace as palace_mod
    from dharma_swarm.chetana import revival as revival_mod

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
    monkeypatch.setattr(decay_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(gap_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(palace_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(revival_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    return tmp_path


@pytest.fixture
def ingest_recorder(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record every wiki-vector ingest call instead of running the real one."""
    import dharma_swarm.wiki_vector_ingest as wvi

    calls: list[dict] = []

    def _record(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            discovered_files=1, backfill={}, sync_index={}, reembed={}
        )

    monkeypatch.setattr(wvi, "ingest_wiki_concepts", _record, raising=True)
    return calls


def _stage_atom(title: str = "Boundary Atom", body: str = "boundary test body") -> Path:
    result = ingest(source=body, source_kind="note", title=title, confidence=0.6)
    assert result.staged_count == 1
    return result.atoms[0]


# ---------------------------------------------------------------------------
# 1. promote → pending root, never trusted
# ---------------------------------------------------------------------------


def test_promote_lands_in_pending_not_trusted(sandbox: Path):
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    assert pr.decision in {"ALLOW", "WARN"}
    assert pr.trusted_path.parent == sandbox / "wiki" / "pending"
    assert list((sandbox / "wiki" / "concepts").glob("*.md")) == []


def test_auto_promote_still_lands_in_pending(sandbox: Path, monkeypatch: pytest.MonkeyPatch):
    # Force an ALLOW verdict (short test bodies trip the SVABHAAVA advisory →
    # WARN) so the auto_promoted branch is actually exercised.
    import dataclasses

    from dharma_swarm.chetana import promote as promote_mod

    real_gate = promote_mod.gate_check_atom

    def _allow(**kwargs):
        gov = real_gate(**kwargs)
        return dataclasses.replace(gov, result="ALLOW", can_promote=True)

    monkeypatch.setattr(promote_mod, "gate_check_atom", _allow, raising=True)

    pr = promote(staged_path=_stage_atom(), promoted_by="t", auto_promote=True)
    assert pr.review_status == "auto_promoted"
    assert pr.trusted_path.parent == sandbox / "wiki" / "pending"
    assert list((sandbox / "wiki" / "concepts").glob("*.md")) == []


def test_promote_does_not_touch_wiki_index(sandbox: Path):
    promote(staged_path=_stage_atom(title="Index Leak Probe"), promoted_by="t")
    index_path = sandbox / "wiki" / "index.md"
    if index_path.exists():
        assert "Index Leak Probe" not in index_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 2. ingest gated on approved + scoped to the file
# ---------------------------------------------------------------------------


def test_ingest_skipped_for_non_approved_even_with_env_on(
    sandbox: Path, ingest_recorder: list[dict], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DHARMA_WIKI_VECTOR_AUTO_INGEST", "1")
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    assert pr.review_status != "approved"
    assert ingest_recorder == []
    assert any("ingest skipped" in n for n in pr.notes)


def test_ingest_runs_on_approve_scoped_to_single_file(
    sandbox: Path, ingest_recorder: list[dict]
):
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    assert ingest_recorder == []
    approved = approve_atom(path=pr.trusted_path, reviewer="op")
    assert approved.decision == "APPROVED"
    assert len(ingest_recorder) == 1
    # Scoped to the ONE approved file, not the whole concepts dir.
    assert ingest_recorder[0]["wiki_concepts_dir"] == approved.trusted_path


def test_ingest_env_opt_out_respected_on_approve(
    sandbox: Path, ingest_recorder: list[dict], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DHARMA_WIKI_VECTOR_AUTO_INGEST", "0")
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    approved = approve_atom(path=pr.trusted_path, reviewer="op")
    assert approved.decision == "APPROVED"
    assert ingest_recorder == []


# ---------------------------------------------------------------------------
# 3. approve is the only door into trusted
# ---------------------------------------------------------------------------


def test_approve_moves_pending_into_trusted(sandbox: Path, ingest_recorder: list[dict]):
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    approved = approve_atom(path=pr.trusted_path, reviewer="op")
    assert approved.decision == "APPROVED"
    assert approved.trusted_path.parent == sandbox / "wiki" / "concepts"
    assert not pr.trusted_path.exists()
    schema, _ = parse_frontmatter(approved.trusted_path.read_text(encoding="utf-8"))
    assert schema.provenance.review_status == "approved"
    assert schema.provenance.reviewer == "op"


def test_approve_requires_reviewer(sandbox: Path):
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    result = approve_atom(path=pr.trusted_path, reviewer="")
    assert result.decision == "REJECTED"
    assert pr.trusted_path.exists()  # atom stayed in pending


# ---------------------------------------------------------------------------
# 3b. the approve door verifies before it trusts
# ---------------------------------------------------------------------------


def test_approve_refuses_tampered_pending_body(sandbox: Path):
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    text = pr.trusted_path.read_text(encoding="utf-8")
    tampered = text.replace("boundary test body", "payload swapped in after promote")
    assert tampered != text
    pr.trusted_path.write_text(tampered, encoding="utf-8")
    result = approve_atom(path=pr.trusted_path, reviewer="op")
    assert result.decision == "SIGNATURE_MISMATCH"
    assert pr.trusted_path.exists()  # left in pending for the operator
    assert list((sandbox / "wiki" / "concepts").glob("*.md")) == []


def test_approve_refuses_v1_downgrade_resign(sandbox: Path):
    # Tamper the body AND re-sign with a freshly computed v1 (body-only) sig —
    # the kernel signature is world-readable, so v1 is forgeable. The approve
    # door must require v2.
    from dharma_swarm.chetana.governance import current_kernel_signature
    from dharma_swarm.chetana.provenance import compute_axiom_signature

    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    text = pr.trusted_path.read_text(encoding="utf-8")
    schema, _ = parse_frontmatter(text)
    tampered = text.replace("boundary test body", "downgrade attack body")
    schema_t, body_t = parse_frontmatter(tampered)
    forged_v1 = compute_axiom_signature(body_t, current_kernel_signature())
    assert signature_matches(forged_v1, schema_t, body_t, current_kernel_signature())
    tampered = tampered.replace(schema.provenance.axiom_signature, forged_v1)
    pr.trusted_path.write_text(tampered, encoding="utf-8")
    result = approve_atom(path=pr.trusted_path, reviewer="op")
    assert result.decision == "SIGNATURE_MISMATCH"
    assert "not v2" in result.error
    assert list((sandbox / "wiki" / "concepts").glob("*.md")) == []


def test_approve_reruns_gates_and_blocks(sandbox: Path, monkeypatch: pytest.MonkeyPatch):
    import dataclasses

    from dharma_swarm.chetana import promote as promote_mod

    pr = promote(staged_path=_stage_atom(), promoted_by="t")

    real_gate = promote_mod.gate_check_atom

    def _block(**kwargs):
        gov = real_gate(**kwargs)
        return dataclasses.replace(gov, result="BLOCK", can_promote=False)

    monkeypatch.setattr(promote_mod, "gate_check_atom", _block, raising=True)
    result = approve_atom(path=pr.trusted_path, reviewer="op")
    assert result.decision == "GATE_BLOCKED"
    assert pr.trusted_path.exists()
    assert list((sandbox / "wiki" / "concepts").glob("*.md")) == []


def test_approve_nonexistent_absolute_path_is_not_found(sandbox: Path):
    # Regression: rglob on an absolute pattern raised NotImplementedError.
    result = approve_atom(path="/nonexistent/absolute/path/atom", reviewer="op")
    assert result.decision == "NOT_FOUND"


def test_approve_slug_collision_fails_closed(sandbox: Path):
    trusted_root = sandbox / "wiki" / "concepts"
    pr = promote(staged_path=_stage_atom(title="Clash Title"), promoted_by="t")
    legacy = trusted_root / pr.trusted_path.name
    legacy.write_text("# Legacy concept page\n\nNo frontmatter, no atom_id.\n", encoding="utf-8")
    result = approve_atom(path=pr.trusted_path, reviewer="op")
    assert result.decision == "COLLISION"
    assert pr.trusted_path.exists()  # pending copy preserved
    assert "Legacy concept page" in legacy.read_text(encoding="utf-8")


def test_approve_in_place_refused_outside_trusted(sandbox: Path):
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    rogue = sandbox / "rogue.md"
    rogue.write_text(pr.trusted_path.read_text(encoding="utf-8"), encoding="utf-8")
    result = approve_atom(path=rogue, reviewer="op")
    assert result.decision == "BAD_STATE"
    assert "outside the trusted dir" in result.error
    schema, _ = parse_frontmatter(rogue.read_text(encoding="utf-8"))
    assert schema.provenance.review_status != "approved"


def test_approve_in_place_inside_trusted_works(sandbox: Path, ingest_recorder: list[dict]):
    import shutil

    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    dest = sandbox / "wiki" / "concepts" / pr.trusted_path.name
    shutil.move(str(pr.trusted_path), str(dest))  # legacy pre-relocation state
    result = approve_atom(path=dest, reviewer="op")
    assert result.decision == "APPROVED"
    assert result.trusted_path == dest
    schema, _ = parse_frontmatter(dest.read_text(encoding="utf-8"))
    assert schema.provenance.review_status == "approved"


# ---------------------------------------------------------------------------
# 4. signature v2: frontmatter (incl. review_status) is signed
# ---------------------------------------------------------------------------


def test_promote_signs_v2_and_verify_accepts(sandbox: Path):
    from dharma_swarm.chetana.governance import current_kernel_signature

    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    schema, body = parse_frontmatter(pr.trusted_path.read_text(encoding="utf-8"))
    stored = schema.provenance.axiom_signature
    assert stored.startswith("v2:")
    assert signature_matches(stored, schema, body, current_kernel_signature())


def test_flipping_review_status_on_disk_breaks_verification(sandbox: Path):
    from dharma_swarm.chetana.governance import current_kernel_signature

    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    text = pr.trusted_path.read_text(encoding="utf-8")
    tampered = text.replace("review_status: staged", "review_status: approved")
    assert tampered != text
    pr.trusted_path.write_text(tampered, encoding="utf-8")
    schema, body = parse_frontmatter(pr.trusted_path.read_text(encoding="utf-8"))
    stored = schema.provenance.axiom_signature
    assert not signature_matches(stored, schema, body, current_kernel_signature())
    assert not signature_matches(stored, schema, body, "0" * 64)


def test_v1_signatures_still_verify(sandbox: Path):
    from dharma_swarm.chetana.provenance import compute_axiom_signature

    body = "legacy body"
    kernel_sig = "a" * 64
    stored = compute_axiom_signature(body, kernel_sig)
    assert signature_matches(stored, None, body, kernel_sig)  # v1 ignores schema
    assert not signature_matches(stored, None, "other body", kernel_sig)


def test_mcp_verify_reports_approved_atom_verified(sandbox: Path, ingest_recorder):
    from dharma_swarm.chetana.mcp_server import tool_verify

    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    approved = approve_atom(path=pr.trusted_path, reviewer="op")
    result = tool_verify(str(approved.trusted_path))
    assert result["verified_count"] == 1
    assert result["kernel_drift_count"] == 0


# ---------------------------------------------------------------------------
# 5. write_trusted collisions fail closed
# ---------------------------------------------------------------------------


def _promoted_schema(title: str):
    pr = promote(staged_path=_stage_atom(title=title), promoted_by="t")
    schema, body = parse_frontmatter(pr.trusted_path.read_text(encoding="utf-8"))
    return schema, body


def test_write_trusted_refuses_legacy_page_without_atom_id(sandbox: Path):
    trusted_root = sandbox / "wiki" / "concepts"
    legacy = trusted_root / "collision-probe.md"
    legacy.write_text("# Legacy concept page\n\nNo frontmatter, no atom_id.\n", encoding="utf-8")
    schema, body = _promoted_schema("Collision Probe")
    with pytest.raises(FileExistsError, match="without an atom_id"):
        write_trusted(schema, body, slug="collision-probe")
    assert "Legacy concept page" in legacy.read_text(encoding="utf-8")


def test_write_trusted_refuses_different_atom_id(sandbox: Path):
    schema_a, body_a = _promoted_schema("Same Slug A")
    write_trusted(schema_a, body_a, slug="same-slug")
    schema_b, body_b = _promoted_schema("Same Slug B")
    with pytest.raises(FileExistsError, match="slug collision"):
        write_trusted(schema_b, body_b, slug="same-slug")


def test_write_trusted_allows_same_atom_rewrite(sandbox: Path):
    schema, body = _promoted_schema("Rewrite Self")
    first = write_trusted(schema, body, slug="rewrite-self")
    second = write_trusted(schema, body + " updated", slug="rewrite-self")
    assert first == second
    assert "updated" in second.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 6. governance: unknown gate verdict fails closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["MAYBE", "surprise", 42, object(), None])
def test_coerce_decision_unknown_blocks(raw):
    # None = a GateCheckResult without a .decision attribute (interface
    # drift) — the most likely real-world unknown must also fail closed.
    assert _coerce_decision(raw) == "BLOCK"


def test_coerce_decision_known_values_unchanged():
    assert _coerce_decision("allow") == "ALLOW"
    assert _coerce_decision("REVIEW") == "WARN"
    assert _coerce_decision("deny") == "BLOCK"


# ---------------------------------------------------------------------------
# 7. MCP hardening
# ---------------------------------------------------------------------------


def test_mcp_tool_promote_has_no_auto_promote():
    from dharma_swarm.chetana.mcp_server import TOOL_SCHEMAS, tool_promote

    assert "auto_promote" not in inspect.signature(tool_promote).parameters
    assert "auto_promote" not in TOOL_SCHEMAS["chetana_promote"]["properties"]


def test_mcp_tool_approve_fails_closed_without_token(monkeypatch: pytest.MonkeyPatch):
    from dharma_swarm.chetana.mcp_server import REVIEWER_TOKEN_ENV, tool_approve

    monkeypatch.delenv(REVIEWER_TOKEN_ENV, raising=False)
    result = tool_approve(path="whatever", reviewer_token="whatever")
    assert result["decision"] == "REJECTED"
    assert "approve disabled" in result["error"]


def test_mcp_tool_approve_rejects_bad_token(monkeypatch: pytest.MonkeyPatch):
    from dharma_swarm.chetana.mcp_server import REVIEWER_TOKEN_ENV, tool_approve

    monkeypatch.setenv(REVIEWER_TOKEN_ENV, "sekrit")
    result = tool_approve(path="whatever", reviewer_token="not-sekrit")
    assert result["decision"] == "REJECTED"
    assert "invalid reviewer token" in result["error"]


def test_mcp_tool_approve_with_token_approves(
    sandbox: Path, ingest_recorder: list[dict], monkeypatch: pytest.MonkeyPatch
):
    from dharma_swarm.chetana.mcp_server import REVIEWER_TOKEN_ENV, tool_approve

    monkeypatch.setenv(REVIEWER_TOKEN_ENV, "sekrit")
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    result = tool_approve(path=str(pr.trusted_path), reviewer_token="sekrit")
    assert result["decision"] == "APPROVED"
    assert Path(result["trusted_path"]).parent == sandbox / "wiki" / "concepts"


def test_mcp_tool_approve_records_reviewer_identity(
    sandbox: Path, ingest_recorder: list[dict], monkeypatch: pytest.MonkeyPatch
):
    from dharma_swarm.chetana.mcp_server import REVIEWER_TOKEN_ENV, tool_approve

    monkeypatch.setenv(REVIEWER_TOKEN_ENV, "sekrit")
    pr = promote(staged_path=_stage_atom(), promoted_by="t")
    result = tool_approve(path=str(pr.trusted_path), reviewer_token="sekrit", reviewer="dhyana")
    assert result["decision"] == "APPROVED"
    assert result["reviewer"] == "operator-token:dhyana"
    schema, _ = parse_frontmatter(Path(result["trusted_path"]).read_text(encoding="utf-8"))
    assert schema.provenance.reviewer == "operator-token:dhyana"


# ---------------------------------------------------------------------------
# 8. OP-4 relocation script (dry-run default; fail-closed collisions)
# ---------------------------------------------------------------------------


def _load_op4_module():
    script = REPO_ROOT / "scripts" / "ops" / "relocate_staged_concepts.py"
    spec = importlib.util.spec_from_file_location("relocate_staged_concepts", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_concept(path: Path, review_status: str | None) -> None:
    if review_status is None:
        path.write_text("# Legacy page\n\nno provenance\n", encoding="utf-8")
        return
    path.write_text(
        "---\n"
        "title: X\n"
        "provenance:\n"
        f"  review_status: {review_status}\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )


def test_op4_dry_run_moves_nothing(tmp_path: Path, capsys):
    op4 = _load_op4_module()
    concepts = tmp_path / "concepts"
    pending = tmp_path / "pending"
    concepts.mkdir()
    _write_concept(concepts / "staged-one.md", "staged")
    _write_concept(concepts / "auto-one.md", "auto_promoted")
    _write_concept(concepts / "approved-one.md", "approved")
    _write_concept(concepts / "legacy.md", None)

    rc = op4.main(
        ["--concepts-root", str(concepts), "--pending-root", str(pending),
         "--receipt-dir", str(tmp_path / "receipts")]
    )
    assert rc == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["dry_run"] is True
    moved_names = {Path(m["before"]).name for m in plan["moves"]}
    assert moved_names == {"staged-one.md", "auto-one.md"}
    # Nothing actually moved; no receipt written.
    assert (concepts / "staged-one.md").exists()
    assert not pending.exists()
    assert not (tmp_path / "receipts").exists()


def test_op4_apply_moves_and_writes_receipt(tmp_path: Path, capsys):
    op4 = _load_op4_module()
    concepts = tmp_path / "concepts"
    pending = tmp_path / "pending"
    receipts = tmp_path / "receipts"
    concepts.mkdir()
    pending.mkdir()
    _write_concept(concepts / "staged-one.md", "staged")
    _write_concept(concepts / "approved-one.md", "approved")
    # Collision: same name already in pending → must be skipped, not clobbered.
    _write_concept(concepts / "clash.md", "staged")
    (pending / "clash.md").write_text("existing pending content", encoding="utf-8")

    rc = op4.main(
        ["--concepts-root", str(concepts), "--pending-root", str(pending),
         "--receipt-dir", str(receipts), "--apply"]
    )
    assert rc == 0
    assert not (concepts / "staged-one.md").exists()
    assert (pending / "staged-one.md").exists()
    assert (concepts / "approved-one.md").exists()  # approved untouched
    assert (concepts / "clash.md").exists()  # collision fail-closed
    assert (pending / "clash.md").read_text(encoding="utf-8") == "existing pending content"
    receipt_files = list(receipts.glob("op4_relocate_*.json"))
    assert len(receipt_files) == 1
    receipt = json.loads(receipt_files[0].read_text(encoding="utf-8"))
    assert receipt["dry_run"] is False
    assert len(receipt["moves"]) == 1
    assert receipt["moves"][0]["sha256"] == receipt["moves"][0]["sha256_after"]
    assert any("clash.md" in s["path"] for s in receipt["skipped"])
