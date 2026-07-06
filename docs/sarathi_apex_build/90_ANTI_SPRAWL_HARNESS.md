# 90 — Anti-Sprawl Harness: make `make onboard` and `make orient` insufficient by themselves

The failure pattern here is not unique to Sarathi. It is the generic pattern:
a new agent sees many plausible homes, writes one more file, names one more
seat, and the system gets another branch of reality.

The fix is not a bigger essay. The fix is a **single-home harness** that every
build must pass before it writes code.

## Root cause seen in this session

`make onboard` and `make orient` tell the agent a lot, but they do not force a
write-location decision. They orient; they do not reserve a surface.

That leaves an agent free to create:

- one more `holon_bridge.py`;
- one more identity home;
- one more runtime wrapper under `~/.dharma`;
- one more docs front door;
- one more branch/worktree with no collapse plan.

## Harness principle

Before a non-trivial build writes files, it must produce a **Surface Claim**:

```yaml
surface: sarathi_apex
custody: operator-ratified | proven | claimed | brainstorm
canonical_code_home: dharma_swarm/<one path>
canonical_runtime_home: ~/.dharma/<one path>
canonical_doc_home: docs/<one path>
duplicate_policy: forbidden | fixture-only | historical-only
allowed_new_files:
  - exact/path/or/glob
forbidden_new_files:
  - '**/holon_bridge.py' outside dharma_swarm/holon_bridge.py
  - '**/holon_runtime.py' outside dharma_swarm/holon_runtime.py
proof_before_alive:
  - test command
  - receipt path
exit_update:
  - update 00_START_HERE.md
  - update collapse/receipt doc
```

If the agent cannot fill that in, it is not ready to write code.

## Minimum local commands

Proposed future targets:

```bash
make surface-claim SURFACE=sarathi_apex
make sprawl-preflight SURFACE=sarathi_apex
make sprawl-closeout SURFACE=sarathi_apex
```

Until those targets exist, run this manual substitute at session start:

```bash
cd /Users/dhyana/dharma_swarm
make onboard
make orient
printf 'Surface: sarathi_apex\nCode home: docs/sarathi_apex_build + dharma_swarm/operator_core/reversibility_gate.py\nRuntime home: ~/.dharma/agents/sarathi (state only)\nForbidden: new holon_bridge.py, new holon_runtime.py, new orchestrator/task store/router/receipt spine\n'
find /Users/dhyana -name holon_bridge.py -o -name holon_runtime.py 2>/dev/null | wc -l
```

## Guardrails for agents

1. **No new home without a map update.** If a new directory is needed, first add it
   to the surface claim and `00_START_HERE.md`.
2. **No duplicate runtime primitive.** A file may wrap `load_holon`; it may not
   redefine it.
3. **Scratchpad TTL.** Scratch files must be named `SCRATCHPAD_<date>.md` and
   either promoted to a map/receipt or deleted by closeout.
4. **One active front door per surface.** For Sarathi, it is
   `docs/sarathi_apex_build/00_START_HERE.md`.
5. **Alive claims are typed.** `identity exists`, `load_holon works`, `wake ran`,
   `overnight proof`, and `wake_loop_active=true` are different states.
6. **Receipts over summaries.** Any claim about counts, line numbers, tests, or
   liveness must include the command or file:line anchor that produced it.
7. **Forks are explicitly named.** A branch/worktree can hold experiments, but it
   must declare whether it is canonical, candidate, fixture, or compost.

## Minimal check to add next

Add a small read-only governance script later, not in this slice, with these
assertions:

- repo runtime has exactly one `def load_holon` outside tests/fixtures;
- repo runtime has exactly one `def holon_wake_cycle` outside tests/fixtures;
- no production import uses `holon.holon_bridge`;
- every `docs/<surface>/00_START_HERE.md` has a `canonical_code_home` and
  `canonical_runtime_home` section;
- any file named `SCRATCHPAD_*.md` older than 7 days fails closeout unless it is
  listed in a receipt.

This is intentionally boring. Sprawl prevention should be boring: pick one home,
fail on duplicates, make every exception named and temporary.
