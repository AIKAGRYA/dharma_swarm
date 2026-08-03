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
    assert "MAY belong to other agents" in unenforced
    assert "agent_not_allowed" not in unenforced, (
        "brief claims agent filtering ran when isolation was not applied"
    )


def test_durable_brief_withholds_memory_payloads_by_default():
    """Devin (security), twice. The supported entrypoint reads with
    include_content=True and the daemon persists every brief under the state
    root, so embedding the pack verbatim writes memory payloads to disk each
    wake cycle. Disclosing that did not reduce the footprint; the default now
    withholds content and the operator opts in."""
    payload = "SECRET-ATOM-TEXT"
    default = build_operator_brief(
        memory=MemoryRecall(status=RECALL_USED, excerpt=f"# pack\n{payload}")
    )
    assert payload not in default, "memory payload written to a durable brief by default"
    assert "withheld from this durable brief" in default

    opted_in = build_operator_brief(
        memory=MemoryRecall(status=RECALL_USED, excerpt=f"# pack\n{payload}"),
        include_memory_content=True,
    )
    assert payload in opted_in and "written to disk" in opted_in


def test_isolation_claim_is_keyed_on_scoped_semantics_not_applied():
    """Devin, second false-isolation claim on the same line. Under the legacy
    escape hatch the policy reports applied=True with semantics='legacy' while
    the budget runs isolation_mode='unrestricted' and owner filtering is
    skipped — so keying the ENFORCED claim on `applied` printed a guarantee
    that did not hold. Only *_scoped semantics actually filter by owner."""
    legacy = build_operator_brief(
        memory=MemoryRecall(
            status=RECALL_USED,
            metadata={
                "isolation_applied": True,
                "isolation_semantics": "legacy",
                "allowed_agent_ids": ["sarathi"],
            },
        )
    )
    assert "Isolation NOT ENFORCED" in legacy
    assert "agent_not_allowed" not in legacy, (
        "brief promises owner filtering under legacy semantics, where it does not run"
    )
    assert "MAY belong to other agents" in legacy


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


def test_daemon_backstop_reports_a_raised_read_as_read_failed():
    """Devin P1, third instance of the same collapse. The backstop `except`
    around `recall_memory` catches a read that RAN and raised, and an earlier
    revision routed it through `_unavailable_recall` — which the brief renders
    as "the organ could not be loaded, so no read was attempted". False for
    this path, and exactly what
    `test_brief_never_reports_a_failed_read_as_never_attempted` forbids; that
    test simply did not reach the daemon's own backstop.

    Both helpers must exist and be used for their own case: `unavailable` for
    import/construction failures, `read_failed` for a read that broke.
    """
    daemon_src = (REPO_ROOT / "scripts" / "runtime" / "sarathi_wake_daemon.py").read_text()
    assert "_read_failed_recall" in daemon_src, (
        "no read_failed-shaped helper; a raised read is being reported as an "
        "unloadable organ"
    )

    tree = ast.parse(daemon_src)
    # The backstop handler around recall_memory must not yield `unavailable`.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        calls_recall = any(
            isinstance(n, ast.Call) and getattr(n.func, "id", None) == "recall_memory"
            for n in ast.walk(node)
        )
        if not calls_recall:
            continue
        for handler in node.handlers:
            used = {
                getattr(n.func, "id", None)
                for n in ast.walk(handler)
                if isinstance(n, ast.Call)
            }
            assert "_unavailable_recall" not in used, (
                "the recall backstop yields `unavailable`; a read that ran and "
                "raised must be `read_failed` or the brief says no read was attempted"
            )


ALL_STATUSES = (RECALL_NOT_CONFIGURED, RECALL_UNAVAILABLE, RECALL_READ_FAILED, RECALL_USED)

# The claim each status makes to an operator. If a status renders text carrying
# another status's claim, the two have collapsed.
_CLAIMS = {
    RECALL_NOT_CONFIGURED: "No read was attempted",
    RECALL_UNAVAILABLE: "could not be loaded",
    RECALL_READ_FAILED: "the read raised",
    RECALL_USED: "Consulted through MemoryKernel",
}


def test_every_status_renders_distinctly_and_claims_only_its_own_fact():
    """Exhaustive over ALL four statuses, not just the one most recently fixed.

    Scope, measured rather than assumed: this covers the RENDERING axis only.
    Run against the pre-fix revisions of this PR it does NOT reproduce the three
    status collapses, because those were producer-side — the daemon selecting
    the wrong status for a fault — and the brief rendered whatever status it was
    handed correctly. `test_daemon_has_a_distinct_producer_for_each_fault_status`
    is the one that catches those (verified: it fails against both
    `cf237b74~1` and `3b80f156~1`).

    This test guards the other direction: that no future edit makes two statuses
    render the same text, or lets one carry another's claim.
    """
    rendered = {
        status: build_operator_brief(
            memory=MemoryRecall(status=status, detail="DETAIL-TOKEN", metadata={})
        )
        for status in ALL_STATUSES
    }

    # 1. Every status is rendered, and distinctly.
    assert len(set(rendered.values())) == len(ALL_STATUSES), (
        "two statuses render identically; an operator cannot tell them apart"
    )

    # 2. Each carries its OWN claim...
    for status, text in rendered.items():
        assert _CLAIMS[status] in text, f"{status} does not state its own outcome"

    # 3. ...and none carries another's. This is the collapse check.
    for status, text in rendered.items():
        for other, claim in _CLAIMS.items():
            if other == status:
                continue
            assert claim not in text, (
                f"the {status!r} brief contains the {other!r} claim {claim!r} — "
                f"these two outcomes have collapsed into each other"
            )

    # 4. A fault must carry its detail; an absence has none to carry.
    for status in (RECALL_UNAVAILABLE, RECALL_READ_FAILED):
        assert "DETAIL-TOKEN" in rendered[status], (
            f"{status} drops the error detail, so the fault exists only in stderr"
        )


def test_daemon_has_a_distinct_producer_for_each_fault_status():
    """The daemon must not reuse one helper for two different faults — that is
    how `unavailable` came to stand in for `read_failed`."""
    daemon_src = (REPO_ROOT / "scripts" / "runtime" / "sarathi_wake_daemon.py").read_text()
    tree = ast.parse(daemon_src)
    helpers = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.endswith("_recall")
    }
    assert "_unavailable_recall" in helpers and "_read_failed_recall" in helpers

    # Each helper hands back exactly one status, and not the other's.
    for name, expected in (
        ("_unavailable_recall", "unavailable"),
        ("_read_failed_recall", "read_failed"),
    ):
        produced = {
            kw.value.value
            for n in ast.walk(helpers[name])
            for kw in getattr(n, "keywords", [])
            if kw.arg == "status" and isinstance(kw.value, ast.Constant)
        }
        assert produced == {expected}, (
            f"{name} produces {produced or 'nothing'}, expected {{'{expected}'}}"
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
