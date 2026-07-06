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

---

## Front-door + holon-system rules (added 2026-07-06, V1 organization pass)

These make it impossible to quietly scatter the build again:

1. **No new Sarathi/holon doc outside `docs/sarathi_apex_build/` unless linked
   from `README.md`.** The README numbered read order (00-07, 90) is canonical.
   A new doc must either take a number or be linked under "supporting/historical".
2. **No new runtime script without a repo source owner.** Logic lives in
   `dharma_swarm/holon_system/...`; `~/.dharma` gets a thin `import main` shim.
3. **No new identity home.** Use `~/.dharma/agents/<uid>`. Do not add a fifth
   home next to `agents` / `ginko/agents` / `docs/agents` / `external_agents`.
4. **No new router / orchestrator / task store / A2A bus / receipt spine**
   (constraint #9). New organ code is a facade/wrapper over the canonical owner
   listed in `03_HOLON_SYSTEM_CODE_MAP.md`.
5. **No "alive" claim without a receipt/heartbeat.** `service_alive`/`wake_loop_active`
   are receipt-backed (proof gates 4/9), never identity-doc-backed.
6. **Every new artifact is classified** as exactly one of: code, runtime, doc,
   receipt, archive (see `02_CODEBASE_RUNTIME_BOUNDARY.md`).

### The `holon_system` facade rule

`dharma_swarm/holon_system/` is a navigation + compatibility layer. Its modules
MUST re-export existing symbols by identity, never reimplement them.
`tests/test_holon_system_imports.py` enforces this with `is`-identity asserts:
if a facade drifts into a copy, the test fails. The `sarathi/` subpackage must
keep `IMPLEMENTED = False` until proof gates 6-10 are met.

### Executable enforcement

```bash
.venv/bin/python -m pytest tests/test_holon_system_imports.py -q  # facades == canonical
python3 scripts/governance/sprawl_guard.py                        # singleton/dup/copy-drift
```

---

## The guard now runs at the moment you already perform (added 2026-07-06)

Root cause the operator named directly: *"I run `make onboard` / `make orient`
before most builds and yet there is still this much sprawl."* The reason was
mechanical, not motivational: **`sprawl_guard.py` existed but was wired into no
Makefile target, no pre-commit hook, no CI.** Orientation *described* reality; it
never *failed* when a duplicate primitive was created. Doc 90 called for wiring;
it had not been done.

Fix (the smallest possible; no new machinery, no "eighth version"):

- `make onboard` and `make orient` now call the guard **advisory-only** (prefixed
  with `-` so a finding prints but never blocks orientation — those targets still
  exit 0). You now *see* the sprawl every single time you orient.
- `make sprawl-guard` is the **blocking** gate: it exits non-zero on any finding.
  This is the one target to add to pre-commit / CI so a build *fails* the moment
  a declared singleton is duplicated.

```bash
make onboard        # orientation + advisory sprawl report (exit 0)
make orient         # whole-system view + advisory sprawl report (exit 0)
make sprawl-guard   # THE gate: non-zero exit on any A1/A2 finding
```

To extend coverage beyond holons, add one entry to `SINGLETON_SYMBOLS` (or
`FORBIDDEN_IMPORTS` / `COPY_WATCHLIST`) in `scripts/governance/sprawl_guard.py`.
That single registry is the generic anti-sprawl surface for the whole repo — it
is not holon-specific. This is the harness the operator asked for: pick one home,
declare the singleton once, and let a boring deterministic gate fail on the
139th copy instead of a human noticing it three weeks later.
