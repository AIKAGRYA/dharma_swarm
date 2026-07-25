# Evolution Proposal Gate Contract

**Audience:** any agent (or human) writing, testing, or debugging code that puts
a `Proposal` through `DarwinEngine.gate_check` / the telos gatekeeper.

**One-line law:** a *self-mod* proposal is HARD-REJECTED whenever the gatekeeper
returns `REVIEW`, and a `REVIEW` is produced when **any** Tier-C advisory gate
flags. So a self-mod proposal must clear the **whole Tier-C battery at once** —
satisfying one gate while tripping another is the classic failure mode.

> Source of the law: WS4 in `dharma_swarm/evolution.py` (~L1543) — *"A REVIEW
> (Tier-C advisory) on a self-mod change_type is ALSO a hard reject."* This closed
> the `REVIEW → GATED → applied` bypass. It is correct, deliberate safety
> behaviour — **do not weaken it to make a test pass.**

`change_type` values treated as self-mod live in `SELF_MOD_TYPES`
(`evolution.py`); `mutation` and `sealed_packet` are members, which is why most
evolution tests hit this.

## Field map — which gate reads which field

A proposal exposes two text fields to the gatekeeper: the **description**
(`action`) and the **diff** (`content`). Each gate reads a specific field:

| Gate | Tier | Reads | Passes when |
|------|------|-------|-------------|
| `ANEKANTA` / `SVABHAAVA` | C | description **+** diff | ≥1 keyword from **each** of three epistemological frames — *mechanistic* (mechanism, computation, layer, parameter…), *phenomenological* (observer, awareness, witness, first-person…), *systems* (feedback, adaptation, resilience, network…) |
| `STEELMAN` | C | diff | contains a counterargument marker (`however`, `but `, `alternatively`, `risk:`, `downside:`, `concern:` …) — **only checked** when the description has a mutation word *and* the diff is non-empty |
| `DOGMA_DRIFT` | C | diff | if confidence markers are present, evidence markers (`tested`, `measured`, `verified`, `result:` …) are too |
| `VYAVASTHIT` | C | description | no forcing words |
| `REVERSIBILITY` | C | description | no irreversible words (else WARN) |
| `AHIMSA`, `SATYA`, `CONSENT`, `BHED_GNAN`, `WITNESS` | — | — | satisfied by default for benign proposals |

Empty-diff proposals skip `STEELMAN`/`DOGMA_DRIFT` (no content to scan), so a
frame-complete description alone is enough for them.

## The map tool — `proposal_gate_probe.py`

Don't guess. Run the probe to see exactly which gates a candidate trips:

```bash
python3 scripts/diagnostics/proposal_gate_probe.py                 # terse vs compliant samples
python3 scripts/diagnostics/proposal_gate_probe.py -d "..." --diff "+x"
```

It runs the candidate through the real `gate_check` path and prints a ✅/❌ per
gate plus the final decision. This is the reliable way to re-derive the
contract directly from the gate code if the gates change.

## The one correct way to build a passing proposal (tests)

`tests/evolution_gate_helpers.py` is the **one helper to reach for**. Use it
instead of hand-crafting descriptions:

```python
from tests.evolution_gate_helpers import (
    gate_compliant_description, tier_c_diff, gate_compliant_proposal_kwargs,
)

# no-diff proposal — frames are enough:
await engine.propose(component="x.py", change_type="mutation",
                     description=gate_compliant_description("Add logging"))

# diffed proposal — frames in description, markers in diff:
await engine.propose(component="x.py", change_type="mutation",
                     description=gate_compliant_description("Refactor parser"),
                     diff=tier_c_diff("+code"))
```

The helper is **self-validated** by `tests/test_evolution_gate_helpers.py`: if a
gate changes its requirements, that test fails loudly in the helper itself
instead of silently rotting across every dependent evolution test. It also
asserts that a *terse* proposal is still rejected, so the helper can't be masking
a gate that has gone permissive.

## Why this document exists (history)

The Tier-C battery was tightened (WS4 + the anekanta/steelman/dogma gates) after
much of the evolution test suite was written. Those tests used terse proposal
descriptions and so were rejected for reasons unrelated to what they assert
(fitness / archival / selection). They were invisible because `pytest -x` stopped
at an earlier failure. Fixing the earlier failures unmasked the whole cluster.
This contract + helper + probe exist so the landmine is **mapped once** and never
re-discovered by hand.

**See also:** `docs/state/BROKEN_REGISTER.md` (BR for the WS4 evolution-test
retrofit), `dharma_swarm/anekanta_gate.py`, `dharma_swarm/steelman_gate.py`,
`dharma_swarm/telos_gates.py`.
