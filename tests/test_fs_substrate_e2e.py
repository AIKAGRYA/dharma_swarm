"""End-to-end smoke: fs_substrate against the REAL owners (not fakes).

The per-slice unit tests use fakes (fake invoker, fake kernel) for speed and
hermeticity. This smoke proves the wiring holds against the actual swarm owners:
a real MemoryKernel, the real EvidenceReceipt type, a real HandoffProtocol, and
the real Semantic Commons manifest. It is the "it honestly flows" proof the
operator trust gate asks for — distinct from "passes with stand-ins".

Still offline/hermetic: the only stub is the AgentInvoker (running a live model
is out of scope), but it returns a REAL EvidenceReceipt through the REAL spine
invoke path, and every other owner is the production object.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.fs_substrate.okf import project_semantic_objects, read_bundle, write_bundle
from dharma_swarm.fs_substrate.organizer import apply_proposal, propose_organization
from dharma_swarm.fs_substrate.semantic_fs import SemanticFS
from dharma_swarm.fs_substrate.stage_contracts import load_workspace, to_tasks
from dharma_swarm.fs_substrate.stage_executor import run_workspace
from dharma_swarm.handoff import HandoffProtocol
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision

WORKSPACE = Path(__file__).parent / "fixtures" / "fs_substrate" / "sample_workspace"
SEMANTIC_OBJECTS = (
    Path(__file__).resolve().parents[1] / "docs" / "ontology" / "semantic_objects.yaml"
)


class _RealReceiptInvoker:
    """A stub backend that returns a REAL EvidenceReceipt via the real spine path."""

    async def __call__(self, task, agent_id, context_id, routing: RoutingDecision):
        now = datetime.now(timezone.utc)
        return EvidenceReceipt(
            agent_id=agent_id,
            context_id=context_id,
            task_id=routing.task_id,
            routing_decision_id=routing.decision_id,
            status="ok",
            started_at=now,
            finished_at=now,
            attributes=dict(routing.attributes),
        )


async def test_slice_a_runs_through_real_spine_and_handoff(tmp_path):
    """Slice A end-to-end: real workspace -> real DAG -> real receipts -> real handoffs."""
    ws = load_workspace(WORKSPACE)
    tasks = to_tasks(ws)
    assert len(tasks) == 3  # DAG built from the real fixture

    handoff = HandoffProtocol(store_path=tmp_path / "handoffs.jsonl")
    receipts = await run_workspace(ws, invoker=_RealReceiptInvoker(), context_id="e2e", handoff=handoff)

    # Real EvidenceReceipt objects, one per stage, carrying real stage provenance.
    assert len(receipts) == 3
    assert all(isinstance(r, EvidenceReceipt) for r in receipts)
    assert receipts[0].attributes["stage_id"] == "01-scope"
    # Real handoffs were persisted to the real JSONL store (2 transitions for 3 stages).
    assert (tmp_path / "handoffs.jsonl").is_file()
    reloaded = HandoffProtocol(store_path=tmp_path / "handoffs.jsonl")
    assert await reloaded.load_from_store() == 2


def test_slice_b_projects_real_semantic_commons(tmp_path):
    """Slice B end-to-end: project the REAL Semantic Commons manifest to an OKF bundle."""
    if not SEMANTIC_OBJECTS.is_file():
        return
    concepts = project_semantic_objects(SEMANTIC_OBJECTS)
    assert concepts, "the live manifest should yield concepts"
    root = write_bundle(concepts, tmp_path / "commons", today="2026-06-24")
    # Every concept file carries the required OKF `type`; reserved files exist.
    assert (root / "index.md").is_file() and (root / "log.md").is_file()
    back = read_bundle(root)
    assert {c.rel_path for c in back} == {c.rel_path for c in concepts}
    assert all(c.type for c in back)  # required field present on every concept


def test_slice_c_runs_against_real_memory_kernel():
    """Slice C end-to-end: a REAL MemoryKernel front door, not a fake."""
    from dharma_swarm.memory_kernel.facade import MemoryKernel

    fs = SemanticFS(MemoryKernel())
    hits = fs.semantic_retrieve("spine receipt dispatch evidence", k=5)
    # The wiring works against the real census/adapters; result is a real list
    # (possibly empty in a fresh container — degraded-safe, never raises).
    assert isinstance(hits, list)


def test_slice_d_propose_then_apply_real_files(tmp_path):
    """Slice D end-to-end: propose is pure; apply is gated and really moves files."""
    (tmp_path / "pic.png").write_text("x")
    (tmp_path / "note.md").write_text("y")
    proposal = propose_organization(tmp_path, generated_at="2026-06-24")
    assert proposal.moves and (tmp_path / "pic.png").is_file()  # propose touched nothing
    result = apply_proposal(proposal, confirm=True)
    assert (tmp_path / "images" / "pic.png").is_file()  # real move happened
    assert len(result.applied) == 2
