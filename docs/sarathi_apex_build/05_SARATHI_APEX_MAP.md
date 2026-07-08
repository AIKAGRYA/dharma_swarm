# 05 — Sarathi Apex Map (what Sarathi is, and its target package)

**Custody: VERIFIED 2026-07-06. Sarathi is specified + partially seated; NOT alive.**

## What Sarathi is (and is not)

- **Is:** the apex continuity holon — chief-of-staff seat that holds the whole
  fleet/life map, conducts the other holons (codex/fable/fugu) and the Hermes
  field-ops organ, runs ONLY reversible-safe loops unattended, queues
  irreversible actions for the operator, and surfaces one highest-leverage lane.
- **Is NOT:** the whole build (that is the holon system); a separate
  orchestrator/router/store; "alive" because `identity.json` exists.

## Current honest status (from `01_CURRENT_STATE.md`)

- registered: yes · model `gemini-2.5-flash` · `service_alive`: no · heartbeat: none
- has: identity/mind (`~/.dharma/agents/sarathi`), committed reversibility gate,
  a `sarathi` WakeProfile in the shared wake shell, read-only proof receipts.
- missing: state file, inbox, bridge heartbeat, gateway loop, roster, contract.
- `wake_loop_active`: **false** (and must stay false until proof gate 9).

## Target source package (specified; behind proof gates 6-10)

```text
dharma_swarm/holon_system/sarathi/
  __init__.py    # IMPLEMENTED = False (present now; honest placeholder)
  gateway.py     # read-only readiness snapshot + pullable operator brief (present now)
  pulse.py       # one governed tick wrapping holon_runtime.holon_wake_cycle(planned_action=...)
  roster.py      # load + status of sub-holons (codex/fable/fugu) + hermes organ
  brief.py       # operator-facing daily brief generation
  scoreboard.py  # where Hermes still wins vs where Sarathi now wins (receipts only)
```

`gateway.py` now exists as a deliberately read-only remote-readiness primitive:
it can render a snapshot and write a finite operator brief into the Sarathi
runtime outbox. It does **not** run the apex decision loop, select/act on a lane,
send a phone message, approve work, or claim liveness. The remaining
gateway/pulse/roster/brief/scoreboard behavior is built one proof gate at a time.

## The runtime wrapper rule

The eventual `~/.dharma/agents/sarathi/gateway/sarathi_gateway.py` must be ONLY:

```python
from dharma_swarm.holon_system.sarathi.gateway import main

if __name__ == "__main__":
    main()
```

Real implementation lives in the repo; `~/.dharma` gets a shim. Never the reverse
(constraint #11).

## The one structural thing that already beats Hermes

The code-deterministic reversibility gate (`operator_core/reversibility_gate.py`,
committed `f18fe8476`): approval is a function of the action string + operator
reachability, taking NO model input by construction. A weak model resolved at 3am
cannot widen authority. `holon_runtime.holon_wake_cycle` accepts `planned_action`
and routes it through this gate before any work runs. That seam is Sarathi's apex
safety spine, and it exists and is tested today.

## Definition of "alive" (do not claim before all true)

1. `load_holon("sarathi")` from the canonical path — OK today.
2. reversibility gate blocks irreversible/unreachable actions — OK today.
3. `holon_wake_cycle` wrapped by the gate — seam exists today.
4. `sarathi` wake profile — OK today.
5. wake receipt from an unattended run within the reversible-safe envelope — NO.
6. operator-facing continuity (brief/phone/outbox) — NO.
7. `wake_loop_active` stays false until 5 and 6 — enforced.

See `06_PROOF_GATES.md` for the ordered gate list.
