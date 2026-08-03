"""Tests for the Sarathi memory organ — governed, agent-scoped recall.

Three independent reviewers found defects in the first revision of this organ,
all of them in a degraded or read-only path. The tests below encode each one.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from dharma_swarm.holon_system.sarathi.brief import build_operator_brief
from dharma_swarm.holon_system.sarathi.memory import (
    RECALL_NOT_CONFIGURED,
    RECALL_READ_FAILED,
    RECALL_UNAVAILABLE,
    RECALL_USED,
    MemoryRecall,
    recall_memory,
    sarathi_isolation_policy,
)
from dharma_swarm.holon_system.sarathi.plan import BootPack

REPO_ROOT = Path(__file__).resolve().parents[1]


class _BrokenKernel:
    """A kernel whose surfaces raise — the read-failed path."""

    def preview_memory_pack(self, **_kw):
        raise RuntimeError("surface unreadable")

    def iter_memory_atoms(self, **_kw):
        return []


def test_recall_is_agent_scoped_not_unrestricted():
    """Greptile P1/security, with a live repro: the first revision used an
    unrestricted budget, so another agent's admissible atom entered Sarathi's
    pack — and the rendered excerpt showed no owner provenance, making foreign
    memory look like Sarathi's own recall.

    The organ now derives its policy from the kernel's own topology policy.
    `supervisor` is correct for an apex seat that delegates to sub-holons.
    """
    policy = sarathi_isolation_policy()
    assert policy.applied is True, "an unapplied policy reads everything"
    assert policy.semantics == "supervisor_scoped"
    assert policy.allowed_agent_ids == ("sarathi",), (
        "recall must be scoped to Sarathi; an empty allow-list disables ownership "
        "filtering and admits other agents' atoms"
    )
    assert not policy.warnings


def test_organ_does_not_hand_roll_a_budget():
    """The two P1s both came from a hand-rolled `MemoryContextBudget`: one flag
    no production atom can satisfy, and unrestricted isolation. The supported
    entrypoint gets both right and enforces more besides. Constructing a budget
    here again would re-open that whole class of defect."""
    from dharma_swarm.holon_system.sarathi import memory as organ

    source = inspect.getsource(organ)
    assert "MemoryContextBudget(" not in source, (
        "organ hand-rolls a MemoryContextBudget again; recall must go through "
        "build_memory_kernel_default_context so admission policy has one owner"
    )
    assert "require_context_admissible" not in source.replace("#", "", 0).split('"""')[0]


def test_every_outcome_carries_a_distinct_status():
    """Devin and Codex, independently: four situations produced an empty
    excerpt and the brief inferred "no read was attempted" from emptiness, so a
    read that ran and RAISED was reported as one that never happened."""
    from dharma_swarm.memory_kernel import MemoryKernel

    assert recall_memory(None).status == RECALL_NOT_CONFIGURED
    assert recall_memory(_BrokenKernel()).status == RECALL_READ_FAILED
    assert recall_memory(MemoryKernel(), recall_query="x").status == RECALL_USED

    failed = recall_memory(_BrokenKernel())
    assert "surface unreadable" in failed.detail, "the fault must survive to the brief"
    assert failed.consulted is False


def test_brief_never_reports_a_failed_read_as_never_attempted():
    """The durably recorded artifact is the brief. If a broken read renders the
    same as an absent kernel, the fault is invisible everywhere except the
    daemon's stderr."""
    absent = build_operator_brief(memory=MemoryRecall(status=RECALL_NOT_CONFIGURED))
    unavailable = build_operator_brief(
        memory=MemoryRecall(status=RECALL_UNAVAILABLE, detail="no module named x")
    )
    failed = build_operator_brief(
        memory=MemoryRecall(status=RECALL_READ_FAILED, detail="surface unreadable")
    )

    assert "NOT CONFIGURED" in absent and "No read was attempted" in absent
    assert "UNAVAILABLE" in unavailable and "no module named x" in unavailable
    assert "READ FAILED" in failed and "surface unreadable" in failed

    # The whole point: these must not be the same text.
    assert absent != failed != unavailable
    assert "No read was attempted" not in failed, (
        "a read that ran and raised is being reported as never attempted"
    )


def test_brief_reports_isolation_from_the_read_never_asserts_it():
    """Devin P1. The `used` branch hardcoded "supervisor-scoped ... other agents
    omitted as agent_not_allowed". That claim is false whenever the legacy
    escape hatch downgrades isolation to unrestricted, in which case
    context_admission applies NO agent filter — so the brief promised an
    isolation guarantee that did not hold, in the artifact an operator trusts
    for provenance. The metadata already carries the truth; render it."""
    enforced = build_operator_brief(
        memory=MemoryRecall(
            status=RECALL_USED,
            metadata={
                "isolation_applied": True,
                "isolation_semantics": "supervisor_scoped",
                "allowed_agent_ids": ["sarathi"],
            },
        )
    )
    assert "Isolation ENFORCED" in enforced and "supervisor_scoped" in enforced

    unenforced = build_operator_brief(
        memory=MemoryRecall(
            status=RECALL_USED,
            metadata={"isolation_applied": False, "isolation_semantics": "legacy"},
        )
    )
    assert "Isolation NOT ENFORCED" in unenforced
    assert "may belong to" in unenforced
    assert "agent_not_allowed" not in unenforced, (
        "brief claims agent filtering ran when isolation was not applied"
    )


def test_brief_discloses_that_the_pack_may_carry_content():
    """Devin (security). The supported entrypoint reads with
    include_content=True, so the excerpt carries content snippets — not the
    reference-only recall this work originally claimed — and the brief is
    persisted under the state root. Whatever the policy, the durable artifact
    must not understate what it contains."""
    rendered = build_operator_brief(
        memory=MemoryRecall(status=RECALL_USED, excerpt="# pack\nsome atom text")
    )
    assert "may include content snippets" in rendered
    assert "written to disk" in rendered


def test_kernel_construction_failure_is_a_fault_not_an_absence():
    """Devin P1. When MemoryKernel() raised, the daemon set memory_kernel=None,
    which made recall_memory return `not_configured` and the brief say "no read
    was attempted" — dropping the exception. `_unavailable_recall(detail)`
    existed for exactly this case and was not used on this path."""
    daemon_src = (REPO_ROOT / "scripts" / "runtime" / "sarathi_wake_daemon.py").read_text()
    assert "memory_unavailable_detail" in daemon_src, (
        "construction failure detail is not recorded, so it cannot reach the brief"
    )
    tree = ast.parse(daemon_src)
    guarded = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", None) == "_unavailable_recall"
        and n.args  # called WITH the recorded detail, not bare
    ]
    assert guarded, (
        "_unavailable_recall is never called with a detail; a kernel that failed "
        "to construct still reports as 'no memory configured'"
    )


def test_brief_states_admission_counts_when_consulted():
    """0 admitted must read as policy exclusion, not as memory being skipped."""
    rendered = build_operator_brief(
        memory=MemoryRecall(
            status=RECALL_USED,
            excerpt="# pack",
            metadata={"candidate_count": 13, "admitted_count": 3},
        )
    )
    assert "3 admitted of 13 candidates" in rendered


def test_boot_pack_carries_the_recall_object_not_a_bare_string():
    """Status must be a field, not an inference from text being empty."""
    assert "memory" in BootPack.__dataclass_fields__
    assert "memory_excerpt" not in BootPack.__dataclass_fields__


def test_memory_recall_reaches_the_brief_from_a_production_caller():
    """Producer + consumer control, against the `lodestone_excerpt` failure mode:
    that field was declared and then appeared exactly once in the whole repo —
    its own declaration. A field nothing writes reads as capability."""
    producers = []
    for path in (REPO_ROOT / "scripts" / "runtime").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "BootPack"
                and any(kw.arg == "memory" for kw in node.keywords)
            ):
                producers.append(path.name)
    assert producers, "no production caller populates BootPack.memory"

    from dharma_swarm.holon_system.sarathi import wake

    consumed = [
        n for n in ast.walk(ast.parse(inspect.getsource(wake)))
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", None) == "build_operator_brief"
        and any(kw.arg == "memory" for kw in n.keywords)
    ]
    assert consumed, "wake builds the brief without passing memory; recall is dropped"


def test_boot_pack_load_is_offloaded_from_the_event_loop():
    """Greptile P1, measured: the loader does blocking I/O (mailbox listing plus
    a governed read across registered surfaces) and ran inline on the asyncio
    thread, stalling delegation and control work for as long as the slowest
    surface took. An exception handler does not help — a slow read is not an
    error."""
    from dharma_swarm.holon_system.sarathi import wake

    tree = ast.parse(inspect.getsource(wake))
    offloaded = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Await)
        and isinstance(n.value, ast.Call)
        and "to_thread" in ast.dump(n.value.func)
        and "load_boot_pack" in ast.dump(n.value)
    ]
    assert offloaded, (
        "load_boot_pack is called inline on the event loop; await it via "
        "asyncio.to_thread so a slow memory surface cannot stall the wake cycle"
    )


def test_daemon_still_imports_when_the_memory_subsystem_is_broken():
    """Devin P1. The fail-open guard wrapped `MemoryKernel()` construction, but
    the organ was imported at module scope and imports `memory_kernel` at module
    scope too — so an unimportable subsystem killed the daemon during import,
    before main() ran. A guard downstream of the failure it guards is not a
    guard."""
    import builtins
    import importlib.util
    import sys

    real_import = builtins.__import__
    _BLOCKED = ("dharma_swarm.memory_kernel", "dharma_swarm.holon_system.sarathi.memory")

    def _block(name, *args, **kwargs):
        if name.startswith(_BLOCKED):
            raise ImportError("simulated broken memory subsystem")
        return real_import(name, *args, **kwargs)

    # Evict first: Python resolves a cached module WITHOUT calling __import__,
    # so with the suite's earlier imports warm the patch never fires and this
    # test passes against the broken code too — it measured nothing until the
    # eviction was added.
    evicted = {n: m for n, m in list(sys.modules.items()) if n.startswith(_BLOCKED)}
    for name in evicted:
        del sys.modules[name]

    daemon = REPO_ROOT / "scripts" / "runtime" / "sarathi_wake_daemon.py"
    builtins.__import__ = _block
    try:
        spec = importlib.util.spec_from_file_location("_sarathi_daemon_probe", daemon)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # must NOT raise
    finally:
        builtins.__import__ = real_import
        sys.modules.update(evicted)

    assert module.recall_memory is None
    # Degraded to a legible status, not to silence.
    assert module._unavailable_recall().status == RECALL_UNAVAILABLE


def test_daemon_memory_diagnostics_go_to_stderr_not_stdout():
    """Devin + Codex. `--json` prints the report as the SOLE stdout payload, so
    a diagnostic on stdout breaks `json.loads(subprocess output)` — precisely
    when memory is unavailable, which is when the fail-open path fires."""
    daemon = REPO_ROOT / "scripts" / "runtime" / "sarathi_wake_daemon.py"
    tree = ast.parse(daemon.read_text(encoding="utf-8"))

    offenders = [
        getattr(node, "lineno", "?")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "print"
        and "[sarathi]" in ast.dump(node)
        and not any(kw.arg == "file" for kw in node.keywords)
    ]
    assert not offenders, (
        f"daemon diagnostics print to stdout at line(s) {offenders}; route them to "
        f"sys.stderr so --json output stays machine-readable"
    )


def test_organ_reaches_memory_only_through_the_kernel_front_door():
    """CLAUDE.md makes MemoryKernel the canonical front door. Reaching around it
    into a store or a raw path is how a second, ungoverned memory lane gets
    built by accident."""
    from dharma_swarm.holon_system.sarathi import memory as organ

    source = inspect.getsource(organ)
    for reached_around in ("open(", "sqlite3", "aiosqlite", "Path.home()", ".jsonl"):
        assert reached_around not in source, (
            f"memory organ references {reached_around!r}; recall must go through "
            f"the MemoryKernel front door, not a store or path"
        )
