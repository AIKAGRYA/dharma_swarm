"""Focused tests for deterministic, marker-bounded backlink reconciliation."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from dharma_swarm.chetana import backlinks as backlinks_module
from dharma_swarm.chetana import safe_write as safe_write_module
from dharma_swarm.chetana.backlinks import (
    BACKLINKS_BEGIN,
    BACKLINKS_END,
    BacklinkError,
    BacklinkPlanStaleError,
    apply_backlink_plan,
    plan_backlinks,
    reconcile_backlinks,
    select_backlink_changes,
)


def _page(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.resolve()


def _block(*targets: str) -> str:
    links = "\n".join(f"- [[{target}]]" for target in targets)
    return f"## Backlinks\n\n{BACKLINKS_BEGIN}\n{links}\n{BACKLINKS_END}\n"


def test_false_backlinks_removed_and_missing_backlinks_added(tmp_path: Path) -> None:
    concepts = tmp_path / "wiki" / "concepts"
    source = _page(concepts, "source.md", "# Source\n\nSee [[Target Page]].\n")
    stale = _page(concepts, "stale.md", "# Stale\n")
    target = _page(
        concepts,
        "target-page.md",
        "# Target\n\n" + _block("stale"),
    )

    plan = plan_backlinks([concepts])

    assert plan.scanned_count == 3
    assert plan.edge_count == 1
    assert plan.inbound_by_page[target] == (source,)
    assert plan.false_count == 1
    assert plan.missing_count == 1
    assert plan.changed_count == 1

    applied = apply_backlink_plan(plan)
    assert applied.applied is True
    assert applied.written_count == 1
    rewritten = target.read_text(encoding="utf-8")
    assert "[[source]]" in rewritten
    assert "[[stale]]" not in rewritten
    assert stale.read_text(encoding="utf-8") == "# Stale\n"


def test_generated_backlink_links_never_manufacture_edges(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    alpha = _page(root, "concepts/alpha.md", "# Alpha\n\n" + _block("beta"))
    beta = _page(root, "concepts/beta.md", "# Beta\n")

    plan = plan_backlinks([root])

    assert plan.edge_count == 0
    assert plan.inbound_by_page[alpha] == ()
    assert plan.inbound_by_page[beta] == ()
    assert plan.false_count == 1
    assert plan.missing_count == 0
    assert plan.changed_paths == (alpha,)


def test_authored_related_frontmatter_creates_an_edge_but_recovery_metadata_does_not(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    authored = _page(
        root,
        "authored.md",
        "---\nrelated: [target]\n---\n\n# Authored\n",
    )
    recovered = _page(
        root,
        "recovered.md",
        "---\n"
        "epistemic_status: orphan-recovered\n"
        "related: [target]\n"
        "ideation_seeds: ['Manufactured [[target]] prompt']\n"
        "---\n\n# Recovered\n",
    )
    target = _page(root, "target.md", "# Target\n")

    report = plan_backlinks([root])

    assert report.inbound_by_page[target] == (authored,)
    assert recovered not in report.inbound_by_page[target]


def test_authored_related_frontmatter_creates_an_edge_with_crlf(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    authored = _page(
        root,
        "authored.md",
        "---\r\nrelated: [target]\r\n---\r\n\r\n# Authored\r\n",
    )
    target = _page(root, "target.md", "# Target\n")

    report = plan_backlinks([root])

    assert report.inbound_by_page[target] == (authored,)


def test_virtual_page_participates_in_plan_but_standalone_apply_refuses(
    tmp_path: Path,
) -> None:
    concepts = tmp_path / "wiki" / "concepts"
    target = _page(concepts, "target.md", "# Target\n")
    proposed = concepts / "proposed.md"

    report = plan_backlinks(
        [concepts], virtual_pages={proposed: "# Proposed\n\nSee [[target]].\n"}
    )

    assert report.virtual_paths == (proposed.resolve(),)
    assert report.inbound_by_page[target] == (proposed.resolve(),)
    assert proposed.resolve() in report.page_text
    with pytest.raises(BacklinkError, match="virtual-page"):
        apply_backlink_plan(report)
    assert not proposed.exists()


def test_environment_selected_manifest_blocks_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    manifest = root / "signed-trust-projection.jsonl"
    manifest.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("DHARMA_WIKI_MANIFEST", str(manifest))
    plan = plan_backlinks([root])

    with pytest.raises(BacklinkError, match="page-plus-manifest"):
        apply_backlink_plan(plan)

    assert target.read_text(encoding="utf-8") == "# Target\n"


def test_wikilinks_in_fenced_or_inline_code_do_not_create_edges(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    source = _page(
        root,
        "source.md",
        "# Source\n\n`[[target]]`\n\n```md\n[[target]]\n```\n",
    )
    target = _page(root, "target.md", "# Target\n")

    report = plan_backlinks([root])

    assert report.edge_count == 0
    assert report.inbound_by_page[target] == ()
    assert report.inbound_by_page[source] == ()


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    before = target.read_bytes()

    report = reconcile_backlinks([root])

    assert report.applied is False
    assert report.changed_count == 1
    assert report.written_count == 0
    assert target.read_bytes() == before


def test_apply_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")

    first = reconcile_backlinks([root], apply=True)
    first_bytes = target.read_bytes()
    second = reconcile_backlinks([root], apply=True)

    assert first.written_count == 1
    assert second.changed_count == 0
    assert second.written_count == 0
    assert target.read_bytes() == first_bytes


def test_apply_preserves_page_permissions(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    target.chmod(0o640)

    reconcile_backlinks([root], apply=True)

    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_multi_page_apply_rolls_back_after_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source-a.md", "# A\n\n[[target-a]]\n")
    _page(root, "source-b.md", "# B\n\n[[target-b]]\n")
    target_a = _page(root, "target-a.md", "# Target A\n")
    target_b = _page(root, "target-b.md", "# Target B\n")
    before = {path: path.read_bytes() for path in (target_a, target_b)}
    plan = plan_backlinks([root])
    real_replace = os.replace
    calls = 0

    def fail_second_replace(
        source: str | Path,
        target: str | Path,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected replacement failure")
        real_replace(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(backlinks_module.os, "replace", fail_second_replace)

    with pytest.raises(BacklinkError, match="prior writes rolled back"):
        apply_backlink_plan(plan)

    assert target_a.read_bytes() == before[target_a]
    assert target_b.read_bytes() == before[target_b]
    assert not tuple(root.glob(".*.tmp"))


def test_rollback_preserves_a_noncooperative_concurrent_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source-a.md", "# A\n\n[[target-a]]\n")
    _page(root, "source-b.md", "# B\n\n[[target-b]]\n")
    target_a = _page(root, "target-a.md", "# Target A\n")
    target_b = _page(root, "target-b.md", "# Target B\n")
    target_b_before = target_b.read_text(encoding="utf-8")
    plan = plan_backlinks([root])
    real_replace = os.replace
    calls = 0

    def edit_then_fail(
        source: str | Path,
        target: str | Path,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            target_a.write_text("# Concurrent human edit\n", encoding="utf-8")
            raise OSError("injected replacement failure")
        real_replace(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(backlinks_module.os, "replace", edit_then_fail)

    with pytest.raises(BacklinkError, match="changed again after write"):
        apply_backlink_plan(plan)

    assert target_a.read_text(encoding="utf-8") == "# Concurrent human edit\n"
    assert target_b.read_text(encoding="utf-8") == target_b_before


def test_apply_fails_closed_when_an_authored_source_drifts(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    source = _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    plan = plan_backlinks([root])
    source.write_text("# Source\n\nThe link was removed.\n", encoding="utf-8")

    with pytest.raises(BacklinkPlanStaleError, match="stale"):
        apply_backlink_plan(plan)

    assert target.read_text(encoding="utf-8") == "# Target\n"


def test_directory_swap_cannot_redirect_backlink_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    source = _page(concepts, "source.md", "# Source\n\n[[target]]\n")
    target = _page(concepts, "target.md", "# Target\n")
    outside = tmp_path / "outside"
    _page(outside, "source.md", source.read_text(encoding="utf-8"))
    _page(outside, "target.md", target.read_text(encoding="utf-8"))
    detached = wiki / "concepts-detached"
    plan = plan_backlinks([concepts])
    real_stage = safe_write_module._stage_text
    swapped = False

    def stage_then_swap(parent_fd: int, filename: str, text: str, *, mode: int) -> str:
        nonlocal swapped
        temporary = real_stage(parent_fd, filename, text, mode=mode)
        if not swapped:
            swapped = True
            concepts.rename(detached)
            concepts.symlink_to(outside, target_is_directory=True)
        return temporary

    monkeypatch.setattr(safe_write_module, "_stage_text", stage_then_swap)

    with pytest.raises(BacklinkError, match="backlink apply failed"):
        apply_backlink_plan(plan)

    assert (outside / "target.md").read_text(encoding="utf-8") == "# Target\n"
    assert (detached / "target.md").read_text(encoding="utf-8") == "# Target\n"


def test_post_replace_directory_swap_cannot_report_false_backlink_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    _page(concepts, "source.md", "# Source\n\n[[target]]\n")
    target = _page(concepts, "target.md", "# Target\n")
    detached = wiki / "concepts-detached"
    plan = plan_backlinks([concepts])
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
            _page(concepts, "source.md", "# Source\n\n[[target]]\n")
            _page(concepts, "target.md", "# Target\n")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_then_swap)

    with pytest.raises(BacklinkError, match="backlink apply failed"):
        apply_backlink_plan(plan)

    assert target.read_text(encoding="utf-8") == "# Target\n"
    assert (detached / "target.md").read_text(encoding="utf-8") == "# Target\n"


def test_preopen_root_swap_cannot_redirect_backlink_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    _page(concepts, "source.md", "# Source\n\n[[target]]\n")
    target = _page(concepts, "target.md", "# Target\n")
    detached = tmp_path / "wiki-detached"
    outside = tmp_path / "outside"
    outside_source = _page(
        outside / "concepts", "source.md", "# Source\n\n[[target]]\n"
    )
    outside_target = _page(outside / "concepts", "target.md", "# Target\n")
    plan = plan_backlinks([concepts])
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
        backlinks_module, "apply_anchored_text_changes", swap_then_apply
    )

    with pytest.raises(BacklinkError, match="backlink apply failed"):
        apply_backlink_plan(plan)

    assert (detached / "concepts" / "target.md").read_text() == "# Target\n"
    assert target.read_text() == "# Target\n"
    assert outside_source.read_text() == "# Source\n\n[[target]]\n"
    assert outside_target.read_text() == "# Target\n"


def test_core_apply_refuses_more_than_twenty_five_pages(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    sources = []
    targets = []
    for index in range(26):
        sources.append(_page(root, f"source-{index}.md", f"[[target-{index}]]\n"))
        targets.append(_page(root, f"target-{index}.md", f"# Target {index}\n"))
    plan = select_backlink_changes(plan_backlinks([root]), targets)

    with pytest.raises(BacklinkError, match="25-page migration limit"):
        apply_backlink_plan(plan)

    assert all(BACKLINKS_BEGIN not in target.read_text() for target in targets)


def test_standalone_apply_refuses_to_invalidate_signed_provenance(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(
        root,
        "target.md",
        "---\nprovenance:\n  axiom_signature: v2:" + "a" * 64 + "\n---\n\n# Target\n",
    )
    plan = plan_backlinks([root])

    with pytest.raises(BacklinkError, match="invalidate signed provenance"):
        apply_backlink_plan(plan)

    assert BACKLINKS_BEGIN not in target.read_text()


def test_untouched_corpus_edit_during_replace_rolls_back_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    guard = _page(root, "guard.md", "# Guard\n")
    plan = plan_backlinks([root])
    real_replace = safe_write_module.os.replace
    calls = 0

    def replace_then_edit_guard(*args, **kwargs) -> None:
        nonlocal calls
        calls += 1
        real_replace(*args, **kwargs)
        if calls == 1:
            guard.write_text("# Guard\n\n[[target]]\n", encoding="utf-8")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_then_edit_guard)

    with pytest.raises(BacklinkError, match="corpus drifted"):
        apply_backlink_plan(plan)

    assert BACKLINKS_BEGIN not in target.read_text()
    assert "[[target]]" in guard.read_text()


def test_corpus_membership_change_during_replace_rolls_back_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    late = root / "late.md"
    plan = plan_backlinks([root])
    real_replace = safe_write_module.os.replace
    calls = 0

    def replace_then_add_page(*args, **kwargs) -> None:
        nonlocal calls
        calls += 1
        real_replace(*args, **kwargs)
        if calls == 1:
            late.write_text("# Late\n\n[[target]]\n", encoding="utf-8")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_then_add_page)

    with pytest.raises(BacklinkError, match="membership changed"):
        apply_backlink_plan(plan)

    assert BACKLINKS_BEGIN not in target.read_text()
    assert late.exists()


def test_temporarily_hidden_manifest_is_pinned_as_an_absence_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    plan = plan_backlinks([root])
    manifest = root / "MANIFEST.jsonl"
    manifest.write_text("{}\n", encoding="utf-8")
    hidden = root / "MANIFEST.hidden"
    real_active = backlinks_module._active_manifest_paths

    def hide_during_check(roots):
        manifest.rename(hidden)
        try:
            return real_active(roots)
        finally:
            hidden.rename(manifest)

    monkeypatch.setattr(backlinks_module, "_active_manifest_paths", hide_during_check)

    with pytest.raises(BacklinkError, match="backlink apply failed"):
        apply_backlink_plan(plan)

    assert BACKLINKS_BEGIN not in target.read_text()
    assert manifest.exists()


def test_apply_refuses_to_invalidate_active_trust_manifest(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    (root / "MANIFEST.jsonl").write_text("{}\n", encoding="utf-8")
    plan = plan_backlinks([root])

    with pytest.raises(BacklinkError, match="page-plus-manifest"):
        apply_backlink_plan(plan)

    assert target.read_text(encoding="utf-8") == "# Target\n"


def test_nested_root_cannot_bypass_an_ancestor_trust_manifest(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    nested = wiki / "concepts" / "nested"
    _page(nested, "source.md", "# Source\n\n[[target]]\n")
    target = _page(nested, "target.md", "# Target\n")
    (wiki / "concepts" / "MANIFEST.jsonl").write_text("{}\n", encoding="utf-8")
    plan = plan_backlinks([nested])

    with pytest.raises(BacklinkError, match="page-plus-manifest"):
        apply_backlink_plan(plan)

    assert target.read_text(encoding="utf-8") == "# Target\n"


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_missing_or_empty_root_is_not_a_false_green_check(
    tmp_path: Path, kind: str
) -> None:
    root = tmp_path / kind
    if kind == "empty":
        root.mkdir()

    with pytest.raises(BacklinkError, match="does not exist|no eligible markdown"):
        plan_backlinks([root])


def test_normalized_slug_and_path_aliases_resolve(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    connections = wiki / "connections"
    source = _page(
        connections,
        "Bridge Note.md",
        "# Bridge\n\n[[CONCEPTS/R V_Metric.md#Evidence|the metric]]\n",
    )
    target = _page(concepts, "R V Metric.md", "# R V Metric\n")

    report = plan_backlinks([concepts, connections])

    assert report.edge_count == 1
    assert report.unresolved_count == 0
    assert report.inbound_by_page[target] == (source,)
    assert report.missing_count == 1


def test_empty_inbound_removes_existing_marker_block(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    target = _page(
        root, "target.md", "# Target\n\nProse remains.\n\n" + _block("missing")
    )

    report = reconcile_backlinks([root], apply=True)

    assert report.false_count == 1
    assert report.changed_count == 1
    rewritten = target.read_text(encoding="utf-8")
    assert "Prose remains." in rewritten
    assert BACKLINKS_BEGIN not in rewritten
    assert BACKLINKS_END not in rewritten


def test_live_heading_before_marker_is_absorbed_without_duplication(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n\n" + _block("stale"))

    reconcile_backlinks([root], apply=True)

    rewritten = target.read_text(encoding="utf-8")
    assert rewritten.count("## Backlinks") == 1
    assert rewritten.count(BACKLINKS_BEGIN) == 1
    assert rewritten.index("## Backlinks") < rewritten.index(BACKLINKS_BEGIN)
    assert "[[source]]" in rewritten
    assert "[[stale]]" not in rewritten


def test_strict_manual_backlink_section_is_safely_migrated(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    stale = _page(root, "stale.md", "# Stale\n")
    target = _page(
        root,
        "target.md",
        "# Target\n\n## Backlinks\n\n- [[stale]]\n",
    )

    report = reconcile_backlinks([root], apply=True)

    rewritten = target.read_text(encoding="utf-8")
    assert report.false_count == 1
    assert report.missing_count == 1
    assert report.inbound_by_page[stale] == ()
    assert rewritten.count("## Backlinks") == 1
    assert BACKLINKS_BEGIN in rewritten
    assert "[[source]]" in rewritten
    assert "[[stale]]" not in rewritten


def test_empty_manual_backlink_section_is_absorbed_without_duplicate_heading(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n\n## Backlinks\n")

    reconcile_backlinks([root], apply=True)

    rewritten = target.read_text(encoding="utf-8")
    assert rewritten.count("## Backlinks") == 1
    assert rewritten.count(BACKLINKS_BEGIN) == 1
    assert "[[source]]" in rewritten


def test_resolved_root_alias_matches_resolved_discovered_pages(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    _page(root, "source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "target.md", "# Target\n")
    alias = tmp_path / "wiki-alias"
    alias.symlink_to(root, target_is_directory=True)

    report = reconcile_backlinks([alias], apply=True)

    assert report.content_roots == (root.resolve(),)
    assert report.written_count == 1
    assert "[[source]]" in target.read_text(encoding="utf-8")


def test_non_strict_backlink_section_is_authored_content_and_untouched(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    target = _page(
        root,
        "target.md",
        "# Target\n\n## Backlinks\n\nCurated explanation.\n\n- [[stale]]\n",
    )
    stale = _page(root, "stale.md", "# Stale\n")
    before = target.read_bytes()

    report = reconcile_backlinks([root], apply=True)

    assert target.read_bytes() == before
    assert BACKLINKS_BEGIN not in target.read_text(encoding="utf-8")
    assert report.inbound_by_page[stale] == (target,)


def test_excluded_directories_are_never_scanned_or_written(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    source = _page(root, "concepts/source.md", "# Source\n\n[[target]]\n")
    target = _page(root, "concepts/target.md", "# Target\n")
    excluded = [
        _page(root, "raw/raw-note.md", "[[target]]\n"),
        _page(root, "_meta/report.md", "[[target]]\n"),
        _page(root, "pending/draft.md", "[[target]]\n"),
        _page(root, "backup/snapshot.md", "[[target]]\n"),
        _page(root, "generated-2026/index.md", "[[target]]\n"),
    ]
    excluded_before = {path: path.read_bytes() for path in excluded}

    report = reconcile_backlinks([root], apply=True)

    assert report.scanned_count == 2
    assert report.inbound_by_page[target] == (source,)
    assert all(path.read_bytes() == excluded_before[path] for path in excluded)


def test_scoped_plan_writes_only_explicit_page_but_keeps_corpus_guard(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    alpha = _page(root, "alpha.md", "# Alpha\n\n[[beta]]\n")
    beta = _page(root, "beta.md", "# Beta\n")
    gamma = _page(root, "gamma.md", "# Gamma\n\n[[beta]]\n")
    full = plan_backlinks([root])

    scoped = select_backlink_changes(full, [beta])
    applied = apply_backlink_plan(scoped)

    assert applied.written_count == 1
    assert "[[alpha]]" in beta.read_text(encoding="utf-8")
    assert "[[gamma]]" in beta.read_text(encoding="utf-8")
    assert BACKLINKS_BEGIN not in alpha.read_text(encoding="utf-8")
    assert BACKLINKS_BEGIN not in gamma.read_text(encoding="utf-8")

    fresh = plan_backlinks([root])
    guarded = select_backlink_changes(fresh, [alpha])
    gamma.write_text("# Gamma changed after planning\n", encoding="utf-8")
    with pytest.raises(BacklinkPlanStaleError, match="stale"):
        apply_backlink_plan(guarded)
