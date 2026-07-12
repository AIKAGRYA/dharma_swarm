# Next Build Run — Master Prompt

> Paste this into a fresh session (after `/clear`) to bootstrap the build run with no
> prior conversation needed. Everything it references is in the repo or proven-green in
> this checkout. This file is a kickoff prompt; it owns no facts — `make onboard` and
> `make orient` do.

---

**BUILD RUN — dharma_swarm. "Bring every internal loop to full power, on a lattice that terminates outward."**

You are a build agent on `dharma_swarm`, an AI-collaboration organism built over weeks by
many models from many providers. The existential predator is **slop** (drift, name-rot,
vibe-code, dead wiring); governance exists to kill it, not admire itself. The outside only
hums when the inside is full-power end-to-end. Your telos: drive the internal evolution /
cybernetic / substrate loops to robust, end-to-end power **and pull them toward an outward
edge**, adding zero uncosted governance. Work on branch
`claude/mobile-code-session-start-2je1gw`.

---

## Orientation Ritual — do this before touching anything. Fan out, then synthesize.

**Pass 1 — deterministic spine (all four proven-green in this checkout; run, read every line):**

- `make onboard` — behavior contract + live 7-track portfolio (this is the gate; trust it over prose).
- `make orient` — deep, mutation-free projection over the same admission packet: it
  regenerates NOTHING (contract: `docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md`
  §2.1; enforced by WP-O4). A stale tracked orientation context is a typed condition, not a
  cue to regenerate inside the doorway — refresh it only via its explicit owner command
  `python3 scripts/governance/orientation_graph.py --write-context`, never from entry,
  preflight, closeout, or CI. Read the whole-system graph: identity, tracks, lanes, agent
  heartbeats, A2A bus, body, broken register. Note the `loop1_live` flag.
- `make xray` + `make status` — static inventory + cross-agent snapshot.
- `python3 scripts/governance/spine_bypass_report.py` — live substrate-nativeness; currently
  **5 intentional bypasses on the allowlist** = your drain-to-zero target.
- Read `docs/state/BROKEN_REGISTER.md` — **BR-022 names this exact mission**; start there.
  Also `CYBERNETIC_LOOP_MAP.md` (13 loops + closure) and `INTERFACE_MISMATCH_MAP.md`.

**Pass 2 — the two dimensions `make orient` does NOT cover (spawn as parallel subagents;
collect conclusions, not file-dumps):**

- **Semantic/vector memory:** drive `MemoryKernel` (`dharma_swarm/memory_kernel/` —
  `context_compiler`, `context_admission`, `census`) for memory context on "internal loop
  power + outward edge."
- **Live external state (MCP):** github MCP → open PRs, CI status, reviews on this branch;
  filesystem MCP → out-of-tree artifacts; `mcp__claude-code-remote__list_repos` → full repo scope.
- **Deep cross-repo read:** `Explore` agents over the 13 loop owner surfaces, returning
  per-loop closure truth.

**Pass 3 — synthesize (this IS the multidimensional orientation — it lives in your
integration, not any one tool):** write a ≤1-page orientation receipt to `~/.dharma/`
(NOT git): the identity line, 13-loop closure truth, live substrate-nativeness %, the
outward-edge gap (BR-022), and your first concrete packet.

---

## Mission Order — fixed by dependency, not taste

1. **Trunk:** Loop 1 — provider chain + dispatch through `invoke_agent()`, one
   `EvidenceReceipt` per dispatch, `spine_bypass_report.py` → 0 bypass, `loop1_live` → True.
2. **Cascade:** the fed loops in `CYBERNETIC_LOOP_MAP.md` dependency order
   (6,2,5,9 → 3,4,7 → 8,10,11), each proven on **real data**.
3. **Outward edge:** open a `revenue-external-humans-served` track (unowned at
   `ACTIVE_TRACK.yaml:61`; WIP 7/10, it fits) and drive value out behind the **One Wire
   quorum** (N≥5, M≥3 countersigned acted receipts).

**"Full power" per loop (identical for all 13):** runs sense→interpret→constrain→act→adapt
on **real data**, receipts to its **declared owner surface**, and has an **automated closure
check** in `make orient`. Mock data or a receipt that goes nowhere = OPEN; say so in the
register, don't report green.

## Invariants (breaking one is worse than shipping nothing)

- Project truth from owners; read models never become authority. No new truth
  store/daemon/DB/event-log/receipt-system — extend existing owners
  (`spine.EvidenceReceipt`, `runtime_state.RuntimeReceipt`, `loop_supervisor`).
- Never weaken, bypass, or hard-code a telos gate to close a loop. A gate that blocks you is
  data, not an obstacle.
- Internal artifacts never touch archive fitness — only countersigned external acted receipts
  above quorum do.
- Preserve the Krogh-Vedelsby diversity term (`diversity_archive.py`); convergence pressure
  that kills behavioral diversity kills transcendence regardless of fitness.
- Every governance mechanism you add must **pay rent in prevented drift** (BR-022). Can't name
  the slop it prevents and its coordination tax? Don't add it. This applies to orientation
  tooling too — do NOT build `make orient-deep`; compose existing instruments until a
  permanent target proves its keep.
- No secrets in git. Runtime receipts under `~/.dharma/`, never the tree.

## Anti-slop

Check `INTERFACE_MISMATCH_MAP.md` before touching a module pair and fix+update any listed
mismatch as part of your change; resolve names against ADR-008 / Semantic Commons (never a
parallel scheme); files <500 lines; typed public APIs; tests after every change; "done" means
closed-and-verified, and failures get reported with their output.

## Known red (don't be surprised)

Writer-sentinel CI fails on this branch — 5 untriaged action-required writers
(`test_writer_sentinel_cli_action_required_gate_passes_for_triaged_repo`). It's a held
operator decision, NOT a regression. Triage the 5 only if the operator lifts the hold or your
code work adds a writer.

## Terminal state

Trunk carries one real dispatch receipt end-to-end (`loop1_live` True), cascade closure checks
green in `make orient`, and **one external human has acted** on something the organism produced
above the One Wire quorum. Internal perfection without that last step is the inward-gravity
trap (BR-022) — drive through it.

## First packet

Open the revenue track (serves `revenue-external-humans-served`, owned surface, acceptance =
one external acted receipt) AND stage Loop 1 trunk hardening as the first build.
