"""Concurrent machine-receipt appends must not fork the hash chain.

``append_machine_receipt`` used to do a lock-free read-modify-write: two racing
appenders both read the same tail digest ``D``, both linked to it, and the next
read raised at the forked link -> the whole audit log became permanently
unreadable. One racing append bricked every future read. The append now runs
its read-tail -> link -> write section under an advisory file lock.

Oracle is process-level: the advisory ``flock`` is host-local; it protects the
single-host Mac-hub model (dozens of agents, one shared receipt path), not
multi-container / NFS writers.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dharma_swarm.spine.receipt import _read_verified_machine_receipt_chain

_REPO_ROOT = Path(__file__).resolve().parents[1]

_APPENDER_SRC = """
import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from dharma_swarm.spine.receipt import VerifiedMachineReceipt, append_machine_receipt

log = Path({log!r})
worker_id = {worker_id}
count = {count}
for i in range(count):
    append_machine_receipt(
        VerifiedMachineReceipt(
            claim_id="w{worker_id}-i%d" % i, command="run", exit_code=0
        ),
        path=log,
    )
"""


def test_concurrent_appends_never_corrupt_chain(tmp_path: Path) -> None:
    log = tmp_path / "concurrent.jsonl"
    n_workers = 8
    per_worker = 15

    procs = []
    for worker_id in range(n_workers):
        src = _APPENDER_SRC.format(
            root=str(_REPO_ROOT),
            log=str(log),
            worker_id=worker_id,
            count=per_worker,
        )
        procs.append(subprocess.Popen([sys.executable, "-c", src]))

    for proc in procs:
        assert proc.wait(timeout=120) == 0, "an appender subprocess failed"

    # A single torn or forked link makes the whole chain unreadable; the reader
    # raises. Reaching this assertion at all proves the chain stayed intact.
    rows = _read_verified_machine_receipt_chain(log)
    assert len(rows) == n_workers * per_worker

    claim_ids = {row["claim_id"] for row in rows}
    assert len(claim_ids) == n_workers * per_worker, "some appends were lost or overwritten"
