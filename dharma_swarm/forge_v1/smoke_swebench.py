"""Forge v1 — REAL SWE-bench Docker verifier PROOF.

Runnable proof that the official swebench Docker harness, wired behind
`swebench_real.verify_prediction`, discriminates correctly on a REAL
SWE-bench-Verified instance:

    gold patch  -> resolved == True
    empty patch -> resolved == False

This is SLOW and requires Docker (amd64 emulation on Apple silicon). It pulls a
multi-GB prebuilt image on first run. Artifacts go to ~/.dharma (never the repo).

Usage:
    PYTHONPATH=. python dharma_swarm/forge_v1/smoke_swebench.py [instance_id]

Default instance: psf__requests-2317 (small, fast environment, 1 FAIL_TO_PASS).
"""
from __future__ import annotations

import sys
import time

# When run as a file (`python dharma_swarm/forge_v1/smoke_swebench.py`), Python
# puts THIS directory on sys.path[0]. That makes the sibling `swebench.py`
# (the offline fixtures module) shadow the real `swebench` PyPI library and
# break the adapter's imports. Drop the script dir so the library wins.
# (Running `python -m dharma_swarm.forge_v1.smoke_swebench` avoids this entirely.)
import os as _os

_here = _os.path.dirname(_os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if _os.path.abspath(p or ".") != _here]

from dharma_swarm.forge_v1.swebench_real import (
    verified_instances,
    verify_prediction,
    instance_image_key,
)

DEFAULT_INSTANCE_ID = "psf__requests-2317"


def main(instance_id: str = DEFAULT_INSTANCE_ID) -> int:
    print(f"[smoke] loading SWE-bench-Verified instance: {instance_id}")
    instances = verified_instances(instance_ids=[instance_id])
    if not instances:
        print(f"[smoke] FAIL: instance {instance_id} not found in dataset")
        return 2
    instance = instances[0]
    gold_patch = instance["patch"]
    print(f"[smoke] repo={instance['repo']} base_commit={instance['base_commit'][:12]}")
    print(f"[smoke] image={instance_image_key(instance)}")
    print(f"[smoke] gold patch length={len(gold_patch)} chars")

    # --- gold patch -> expect resolved=True ---
    print("\n[smoke] === GOLD PATCH RUN (expect resolved=True) ===")
    t0 = time.time()
    gold_resolved = verify_prediction(instance, gold_patch)
    t_gold = time.time() - t0
    print(f"[smoke] gold  -> resolved={gold_resolved}  ({t_gold:.1f}s)")

    # --- empty patch -> expect resolved=False ---
    print("\n[smoke] === EMPTY PATCH RUN (expect resolved=False) ===")
    t1 = time.time()
    empty_resolved = verify_prediction(instance, "")
    t_empty = time.time() - t1
    print(f"[smoke] empty -> resolved={empty_resolved}  ({t_empty:.1f}s)")

    wall = time.time() - t0
    ok = (gold_resolved is True) and (empty_resolved is False)
    print("\n" + "=" * 60)
    print(f"[smoke] instance_id      : {instance_id}")
    print(f"[smoke] gold  -> resolved: {gold_resolved}  (expected True)")
    print(f"[smoke] empty -> resolved: {empty_resolved}  (expected False)")
    print(f"[smoke] wall-clock total : {wall:.1f}s "
          f"(gold {t_gold:.1f}s, empty {t_empty:.1f}s)")
    print(f"[smoke] VERDICT          : {'PASS (verifier discriminates)' if ok else 'FAIL'}")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    iid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INSTANCE_ID
    raise SystemExit(main(iid))
