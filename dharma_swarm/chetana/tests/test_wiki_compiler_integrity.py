from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.chetana import safe_write as safe_write_module
from dharma_swarm.chetana import wiki_compiler as wiki_compiler_module
from dharma_swarm.chetana.wiki_compiler import (
    IntegrationPlanError,
    compile_integration_plan,
)

from .test_wiki_compiler import _sha256, _write, _write_plan


@pytest.fixture(autouse=True)
def _configured_authority_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHETANA_CANONICAL_LEDGER_ROOTS", str(tmp_path))
    monkeypatch.setenv("CHETANA_AUDITED_SOURCE_ROOTS", str(tmp_path))


def test_directory_swap_cannot_redirect_compiler_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    outside = tmp_path / "outside"
    _write(outside / "metric.md", page.read_text(encoding="utf-8"))
    detached = wiki / "concepts-detached"
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_stage = safe_write_module._stage_text
    swapped = False

    def stage_then_swap(parent_fd: int, filename: str, text: str, *, mode: int) -> str:
        nonlocal swapped
        temporary = real_stage(parent_fd, filename, text, mode=mode)
        if not swapped:
            swapped = True
            (wiki / "concepts").rename(detached)
            (wiki / "concepts").symlink_to(outside, target_is_directory=True)
        return temporary

    monkeypatch.setattr(safe_write_module, "_stage_text", stage_then_swap)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert (outside / "metric.md").read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert (detached / "metric.md").read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_post_replace_directory_swap_cannot_report_false_compile_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(concepts / "metric.md", "AUROC 0.909\n")
    log = _write(wiki / "log.md", "prior receipt\n")
    detached = wiki / "concepts-detached"
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_replace = safe_write_module.os.replace
    calls = 0

    def replace_then_swap(
        source_name: str,
        target_name: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        real_replace(
            source_name,
            target_name,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        if calls == 1:
            concepts.rename(detached)
            concepts.mkdir()
            _write(concepts / "metric.md", "AUROC 0.909\n")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_then_swap)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert (detached / "metric.md").read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert log.read_text(encoding="utf-8") == "prior receipt\n"


def test_preopen_root_swap_cannot_redirect_compiler_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    _write(wiki / "log.md", "prior receipt\n")
    detached = tmp_path / "wiki-detached"
    outside = tmp_path / "outside"
    outside_page = _write(outside / "concepts" / "metric.md", "AUROC 0.909\n")
    outside_log = _write(outside / "log.md", "prior receipt\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_apply = safe_write_module.apply_anchored_text_changes
    swapped = False

    def swap_then_apply(*args, **kwargs) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            wiki.rename(detached)
            wiki.symlink_to(outside, target_is_directory=True)
        real_apply(*args, **kwargs)

    monkeypatch.setattr(
        wiki_compiler_module, "apply_anchored_text_changes", swap_then_apply
    )

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert (detached / "concepts" / "metric.md").read_text() == "AUROC 0.909\n"
    assert (detached / "log.md").read_text() == "prior receipt\n"
    assert outside_page.read_text() == "AUROC 0.909\n"
    assert outside_log.read_text() == "prior receipt\n"


def test_temporarily_hidden_manifest_is_an_anchored_compile_precondition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    _write(wiki / "log.md", "prior receipt\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    manifest = wiki / "MANIFEST.jsonl"
    manifest.write_text("{}\n", encoding="utf-8")
    hidden = wiki / "MANIFEST.hidden"
    real_governing = wiki_compiler_module.governing_manifest_paths

    def hide_during_check(roots):
        manifest.rename(hidden)
        try:
            return real_governing(roots)
        finally:
            hidden.rename(manifest)

    monkeypatch.setattr(
        wiki_compiler_module, "governing_manifest_paths", hide_during_check
    )

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text() == "AUROC 0.909\n"
    assert (wiki / "log.md").read_text() == "prior receipt\n"
    assert manifest.exists()


def test_evidence_change_during_page_replace_rolls_back_pages_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    log = _write(wiki / "log.md", "prior receipt\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_replace = safe_write_module.os.replace
    calls = 0

    def replace_then_change_evidence(
        source_name,
        target_name,
        *,
        src_dir_fd=None,
        dst_dir_fd=None,
    ):
        nonlocal calls
        calls += 1
        real_replace(
            source_name,
            target_name,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        if calls == 1:
            source.write_text("C05: attacker replacement\n", encoding="utf-8")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_then_change_evidence)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert log.read_text(encoding="utf-8") == "prior receipt\n"


def test_evidence_cannot_alias_the_implicit_wiki_log_output(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(wiki / "log.md", "## Audited\n\nC05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        authority="audited-source",
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="implicit write targets"):
        compile_integration_plan(plan, wiki_root=wiki)

    assert source.read_text(encoding="utf-8").startswith("## Audited")
    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_receipt_and_pages_rollback_together_after_post_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    log = _write(wiki / "log.md", "prior receipt\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_replace = safe_write_module.os.replace
    calls = 0

    def replace_log_then_raise(
        source_name: str,
        target_name: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        real_replace(
            source_name,
            target_name,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        if calls == 2:
            raise OSError("post-log-replace failure")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_log_then_raise)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert log.read_text(encoding="utf-8") == "prior receipt\n"
