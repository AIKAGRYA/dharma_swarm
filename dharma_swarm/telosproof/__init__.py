"""TelosProof v0 — proof-carrying-telos over self-modification *bodies*.

A conservative, advisory pre-apply gate that reasons about the BODY of a
self-modification patch (the diff text and its touched paths) — never about
mind or intent. It answers one question: *does this patch preserve the
protected-body invariants the system must never silently break?*

Three load-bearing properties:

1. **Body, not mind.** Every check is a static heuristic over diff text and
   path names. No claim is made about what the patch *means to do*, only what
   the patch *literally touches and the markers it adds/removes*.

2. **Conservative by construction.** False-positives (flagging a safe patch
   for human review) are ACCEPTABLE. False-negatives (passing a dangerous
   patch as safe) are FORBIDDEN. Whenever a flag cannot be confidently shown
   safe, it defaults to the DANGEROUS value. See ``change_summary`` for the
   per-heuristic conservatism notes.

3. **Advisory by default.** Enforcement is gated by the ``DHARMA_PROOF_ENFORCE``
   environment variable (default ``0`` = advisory), mirroring
   ``DHARMA_EVOLUTION_SHADOW`` in ``dgm_loop.py``. In advisory mode the gate
   still computes and returns a full result, but it is NOT wired into any live
   apply path. The integration point is documented (commented, not executed)
   in ``gate.py``.

LOUD CAVEAT — THIS REGEX LAYER IS NOT A PROOF (read before trusting an ALLOW)
----------------------------------------------------------------------------
* Invariant (8) ``preserves_replay_rollback_metadata`` is **SELF-SATISFIABLE**:
  the untrusted proposer supplies its own ``replay_command`` / ``rollback_plan``
  evidence, so it can self-credential (8) and pass. (8) is an
  INTEGRITY-OF-HONEST-PROPOSER check (did a well-meaning author attach
  replay/rollback notes?), **NOT an adversarial defense**.
* The closed positive-marker vocabularies of invariants (2)-(7) are
  **INCOMPLETE BY CONSTRUCTION** — any rename/synonym steps outside the
  enumerated set. An ``ALLOW`` means "no enumerated red flag found", never
  "proven safe".
* The v0 adversarial backstop is the **structural deny-by-default rule**
  (``ChangeSummary.net_removes_from_safety_surface``): a net-removal from any
  safety-surface file forces ``REVIEW`` regardless of vocabulary. It catches
  synonym/rename bypass enumeration cannot — but it is a coarse net, not a
  proof.
* The real adversarial defense is the **v1 Lean primitive-vocabulary**
  (allow-list, deny-by-default over a fixed safe-primitive set), not this regex
  layer. Advisory output must NEVER be mistaken for proof.

GateDecision contract:
  * ``BLOCK``  — a HARD body invariant (1)-(8) was violated.
  * ``REVIEW`` — ONLY the structural deny-by-default backstop fired (a
    safety-surface net-removal that no enumerated invariant classified).
  * ``ALLOW``  — no enumerated red flag and no safety-surface net-removal. This
    is the weakest of guarantees; see the caveat above.

Public surface::

    from dharma_swarm.telosproof import (
        ChangeSummary, extract_change_summary,
        check_invariants,
        telosproof_gate, PROOF_ENFORCE,
    )
"""

from __future__ import annotations

from dharma_swarm.telosproof.change_summary import (
    ChangeSummary,
    extract_change_summary,
)
from dharma_swarm.telosproof.invariants import check_invariants
from dharma_swarm.telosproof.gate import telosproof_gate, PROOF_ENFORCE

__all__ = [
    "ChangeSummary",
    "extract_change_summary",
    "check_invariants",
    "telosproof_gate",
    "PROOF_ENFORCE",
]
