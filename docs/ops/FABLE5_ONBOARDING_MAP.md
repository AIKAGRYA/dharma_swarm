# Fable 5 Onboarding Map

**Status:** operational route and preclean receipt, not authority.  
**Snapshot:** 2026-06-11, generated from live `make onboard`, git status, GitNexus, Context+, and canonical docs.  
**Authority:** when this map conflicts with `make onboard`, `ACTIVE_TRACK.yaml`, `ACTIVE_SURFACE_MANIFEST.yaml`, git, or runtime receipts, this map loses.

## First Command

```bash
cd /Users/dhyana/dharma_swarm
make onboard
```

Then run the same command in the near-main integration lane before comparing claims:

```bash
cd /Users/dhyana/dharma_swarm_main
make onboard
```

Do not read the repo from a cold start. Run `make onboard` for compact,
read-only session status. Use `make organism-status` for the deeper organism
projection. Before editing, bind a packet and run
`make agent-build-preflight PACKET=<path>`; onboarding status alone is not edit
permission.

## First Five Surfaces

Read only these before action:

1. `make onboard` output
2. `CLAUDE.md`
3. `docs/governance/SOVEREIGN_MANIFEST.md`
4. `docs/governance/ACTIVE_TRACK.yaml`
5. `docs/governance/ANTI_SLOP_RULES.md`

Everything else below is depth-on-demand. Do not make this file a sixth first-read surface; use it as a route after the five surfaces above.

## Fable 5 Identity And Boundary

Fable's repo identity is `fable_5_cursor`.

Existing evidence:

| Surface | Meaning |
|---|---|
| `examples/agents/fable_5_cursor.registration.json` | Registered identity, summon contract, A2A subject, authority boundary |
| `inter_agent/fleet/2026-06-11T0220Z-fable-5-cursor-registration-announcement.md` | Fleet announcement and NATS delivery receipt pointer |
| `docs/evidence/2026-06-10_chat_fable_evidence.md` | Earlier Fable audit with operational-floor findings |

Authority boundary: Fable may inspect, dispatch bounded read/review workers, synthesize, packetize, recommend, and send/receive A2A. Fable may not merge, approve PRs, push, mark human approval, expose secrets, mutate telos/kernel/protected substrate, or bypass governance without explicit operator authorization.

## Worktree Map

| Worktree | Current role | Fable should do |
|---|---|---|
| `/Users/dhyana/dharma_swarm` | Primary qwen/Fable lane on `qwen/spine-adoption`; dirty and ahead/behind; contains Fable identity and broad exploratory work | Read first for Fable-specific context, but treat dirty files as live user/agent work |
| `/Users/dhyana/dharma_swarm_main` | Near-main integration lane on `holon/spine-v1`; cleaner, ahead of origin/main, current control-surface/A2A/runtime-truth work | Use as mainline comparison and implementation sanity check |
| `/Users/dhyana/dharma_swarm_live` | daemon/seat lane per onboarding output | Treat as operational state lane; do not mutate for onboarding cleanup |
| `/Users/dhyana/ds_stitch_receipts` | receipts and handoff persistence lane | Read for receipts when needed; do not treat as source code canon |

Current divergence to keep explicit:

- `dharma_swarm` `make onboard` reports 4 active tracks, 3 shippable, and spine-adoption at 5/8.
- `dharma_swarm_main` `make onboard` reports 2 active tracks, both shippable.
- GitNexus indexes `/Users/dhyana/dharma_swarm` but is 4 commits behind HEAD. Use it for orientation only.
- `docs/state/LIVE_OPS_DASHBOARD.md` is useful context but stale by onboarding's own warning; trust `make onboard`, git, runtime receipts, and generated evidence first.

## Classification

| Bucket | Contents | Fable stance |
|---|---|---|
| Pure working essence | `make onboard`, `CANONICAL_DOC_STACK.md`, `ACTIVE_TRACK.yaml`, `ACTIVE_SURFACE_MANIFEST.yaml`, anti-slop rules, correlation spine doctrine, runtime truth packets, model/key routing | Preserve and use. Do not duplicate. |
| Working but active | `holon/spine-v1` control surface, A2A send/receipt work, AgentOps/ds-goal panels, runtime truth projection tests | Verify from tests and receipts before summarizing as done. |
| Semi-working or dormant | Spine dispatch adoption, A2A bridge production callers, receipt fill rate, live ops dashboard freshness, cross-worktree governance drift | Label honestly as partial, dormant, or stale. |
| Needs-to-work next | Close shippable tracks through `ACTIVE_TRACK.yaml`, reconcile qwen/main active-track rendering, refresh managed blocks, update stale live ops state, clarify Fable's route | Queue as governed cleanup; do not hand-edit generated blocks. |
| Slop/bloat/decay | Duplicate old CLAUDE packs, `DHARMA_SWARM_CLAUDE.md` as older repo-specific snapshot, generated report floods, stale handoffs, work-packet spam, duplicate worktrees, outdated counts, trust-language docs | Pointerize, archive, or quarantine only after link and ownership review. |

## Do Not Duplicate These Substrates

| Need | Existing owner |
|---|---|
| Current active work | `docs/governance/ACTIVE_TRACK.yaml` |
| Declared surfaces and state dirs | `ACTIVE_SURFACE_MANIFEST.yaml` |
| Live-state projection | `make onboard`, `docs/state/LIVE_OPS_DASHBOARD.md`, runtime receipts |
| A2A transport decision | `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` |
| Runtime truth packets | `dharma_swarm/operator_core/*`, `scripts/governance/agent_onboard.py` |
| Dispatch proof | `dharma_swarm/spine/receipt.py` |
| Runtime persistence | `dharma_swarm/runtime_state.py` |
| Memory context | `dharma_swarm/memory_kernel/` |
| Model/key routing | `docs/ops/MODEL_KEY_ROUTING.md`, `dharma_swarm/api_keys.py`, `dharma_swarm/runtime_provider.py` |
| Agent hygiene | `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md` and pattern catalog |

## Immediate Cleanup Queue

Safe documentation and orientation moves:

1. Keep this file as a route, not an authority surface.
2. Keep `docs/ops/AGENT_ONBOARDING.md` as the generic first stop and point Fable-specific readers here.
3. Refresh managed active-track blocks only with `python3 scripts/governance/render_active_track_includes.py`; never hand-edit them.
4. Run `python3 scripts/governance/render_active_track_includes.py --check` before claiming rendered governance is coherent.
5. Treat bulk report/work-packet cleanup as a separate governed cleanup pass with receipts, not as onboarding prep.

Operator decisions still needed:

- Which lane is Fable's operational base after qwen/Fable identity work is reconciled with `holon/spine-v1`.
- Whether to close the shippable tracks now or leave them open until a broader branch convergence.
- Whether to execute the existing worktree cleanup scripts; they are designed to preserve bundles, but they still alter worktree layout.

## Verification For This Map

Minimum checks after editing onboarding surfaces:

```bash
cd /Users/dhyana/dharma_swarm
make onboard
python3 scripts/governance/render_active_track_includes.py --check
python3 scripts/governance/check_track_status.py
```

If the edit broadens beyond docs, also run:

```bash
make hygiene-check
make agent-build-closeout PACKET=<path>
```
