"""Tests for the Sarathi memory organ — governed recall through MemoryKernel."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from dharma_swarm.holon_system.sarathi.memory import (
    SARATHI_MEMORY_BUDGET,
    build_memory_pack,
    memory_pack_summary,
    render_memory_excerpt,
)
from dharma_swarm.holon_system.sarathi.plan import BootPack

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_no_kernel_is_not_the_same_fact_as_no_memories():
    """A deployment with no memory configured and one whose policy admitted
    nothing are different facts. Collapsing them would let an operator brief
    report "nothing recalled" when memory was never consulted at all."""
    assert build_memory_pack(None) is None
    assert render_memory_excerpt(None) == ""

    absent = memory_pack_summary(None)
    assert absent["consulted"] is False
    assert absent["admitted"] == 0

    from dharma_swarm.memory_kernel import MemoryKernel

    pack = build_memory_pack(MemoryKernel())
    assert pack is not None
    consulted = memory_pack_summary(pack)
    assert consulted["consulted"] is True
    # Same admitted count as the absent case is exactly why `consulted` exists.
    assert consulted["admitted"] >= 0
    assert absent["consulted"] != consulted["consulted"]


def test_apex_budget_refuses_projections_high_risk_and_stale():
    """The apex seat plans delegations from what it recalls, so it must not
    recall a projection of a source, a high canon/PII risk atom, or stale
    state. These are the governance knobs, asserted rather than described."""
    b = SARATHI_MEMORY_BUDGET
    assert b.require_context_admissible is True
    assert b.allow_projections is False
    assert b.allow_high_risk is False
    assert b.reject_stale is True
    assert b.include_content is False, "carry references, not payloads"
    assert b.max_admitted_atoms == 8 and b.max_total_chars == 4000


def test_reading_memory_does_not_write_memory():
    """The organ is a read. The kernel states its own contract in the pack's
    warnings; this asserts those warnings survive the organ rather than
    trusting the docstring."""
    from dharma_swarm.memory_kernel import MemoryKernel

    pack = build_memory_pack(MemoryKernel())
    assert pack is not None
    warnings = set(pack.warnings)
    assert "preview_does_not_promote_or_write_memory" in warnings
    assert "preview_only_no_runtime_prompt_injection" in warnings


def test_memory_excerpt_is_actually_populated_by_the_daemon():
    """Negative control against the `lodestone_excerpt` failure mode.

    `BootPack.lodestone_excerpt` was declared and then never populated by any
    caller -- at the time this test was written it appeared exactly once in the
    whole repo, its own declaration. A field nothing writes is decoration that
    reads as capability. This test fails if `memory_excerpt` ever becomes that:
    it requires a real production caller to pass it into a BootPack.
    """
    assert "memory_excerpt" in BootPack.__dataclass_fields__

    producers = []
    for path in (REPO_ROOT / "scripts" / "runtime").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "BootPack"
                and any(kw.arg == "memory_excerpt" for kw in node.keywords)
            ):
                producers.append(path.relative_to(REPO_ROOT).as_posix())

    assert producers, (
        "BootPack.memory_excerpt is declared but no production caller passes it. "
        "That is exactly what happened to lodestone_excerpt: a field that reads "
        "as memory capability while nothing populates it. Wire it or drop it."
    )


def test_brief_distinguishes_not_consulted_from_admitted_nothing():
    """The operator must be able to tell "no memory kernel" from "memory
    consulted, policy admitted 0 atoms". Rendering both as silence would let an
    absent kernel read as an empty memory -- a fabricated liveness claim in the
    one direction the brief is supposed to be honest about."""
    from dharma_swarm.holon_system.sarathi.brief import build_operator_brief
    from dharma_swarm.memory_kernel import MemoryKernel

    absent = build_operator_brief(memory_excerpt="")
    assert "## Memory" in absent
    assert "NOT CONSULTED" in absent

    pack = build_memory_pack(MemoryKernel())
    consulted = build_operator_brief(memory_excerpt=render_memory_excerpt(pack))
    assert "NOT CONSULTED" not in consulted
    assert "Consulted through MemoryKernel" in consulted
    assert absent != consulted


def test_wake_passes_the_boot_pack_memory_into_the_brief():
    """Consumer-side counterpart to the producer control above. A populated
    field nothing reads is still decoration, one level further along."""
    from dharma_swarm.holon_system.sarathi import wake

    tree = ast.parse(inspect.getsource(wake))
    passed = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "build_operator_brief"
        and any(kw.arg == "memory_excerpt" for kw in node.keywords)
    ]
    assert passed, (
        "wake.py builds the operator brief without passing memory_excerpt, so "
        "recall is carried into the boot pack and then dropped unread"
    )


def test_organ_reaches_memory_only_through_the_kernel_front_door():
    """CLAUDE.md makes MemoryKernel the canonical front door. The organ must not
    reach around it into a legacy store or a raw path -- that is how a second,
    ungoverned memory lane gets built by accident."""
    from dharma_swarm.holon_system.sarathi import memory as organ

    source = inspect.getsource(organ)
    for reached_around in ("open(", "sqlite3", "aiosqlite", "Path.home()", ".jsonl"):
        assert reached_around not in source, (
            f"memory organ references {reached_around!r}; recall must go through "
            f"MemoryKernel.preview_memory_pack, not a store or path"
        )
