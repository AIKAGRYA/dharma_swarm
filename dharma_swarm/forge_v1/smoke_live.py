"""Forge v1 — ONE live frontier-model call, proven end-to-end.

Runs a single real model call through the offline harness on the ADD_TASK
fixture (a trivial '-' vs '+' bug) and prints: the parsed patch, the REAL
token count the provider reported, and the verifier's pass/fail (which runs
the HIDDEN gold test in an isolated sandbox — never an agent self-report).

This SPENDS real tokens. Run it deliberately, not in CI:

    PYTHONPATH=. /Users/dhyana/dharma_swarm/.venv/bin/python \
        -m dharma_swarm.forge_v1.smoke_live

A correct model fixes the bug -> verify True with tokens > 0.
"""
from __future__ import annotations

import sys

from dharma_swarm.forge_v1.fixtures import ADD_TASK
from dharma_swarm.forge_v1.harness import verify
from dharma_swarm.forge_v1.providers import LiveModel, PoolCompletion


def main(model_id: str = "gpt-5") -> int:
    print(f"[smoke_live] one REAL call: model={model_id} task={ADD_TASK.name}")
    model = LiveModel(PoolCompletion(model_id), name=model_id)
    cand = model.propose(ADD_TASK, 0)

    fn = next(iter(cand.patch))
    patch = cand.patch[fn]
    snippet = patch.strip().splitlines()
    snippet = "\n".join(snippet[:6]) + ("\n  ..." if len(snippet) > 6 else "")

    ok = verify(ADD_TASK, cand.patch)

    print(f"[smoke_live] parsed patch ({fn}):\n{snippet}")
    print(f"[smoke_live] REAL tokens (prompt+completion): {cand.tokens}")
    print(f"[smoke_live] verify(gold test) -> {ok}")

    if ok and cand.tokens > 0:
        print("[smoke_live] RESULT: live call produced a VERIFIED patch ✓")
        return 0
    print("[smoke_live] RESULT: live call did NOT produce a verified patch ✗")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "gpt-5"))
