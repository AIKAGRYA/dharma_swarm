# BUILD STEP ZERO — operator decisions that unblock the build

**Date:** 2026-06-09 · **Decided by:** Dhyana (operator), in session with opus_composer.
These are the two zero-cost decisions the readiness gauntlet (`READINESS_VERDICT.md`) flagged as gating
everything downstream. They are now made. This file is the authority for them.

---

## Decision 1 — Canonical runtime repo

**`/Users/dhyana/dharma_swarm` (main) is canonical for the holon build.**

Consequence: the substrate that currently lives only in side-checkouts must be merged INTO main before
the bridge can import:
- cherry-pick `operator_core/living_agent_kernel.py` (+ satellite `living_agent_kernel_*.py`) from
  `dharma_capital_lab` / `dharma_swarm_lak_e2e`.
- port the 17-line `identity_invariant` delta in `external_agent_registration.py` (510 → 527) from
  `dharma_capital_lab`.
- green condition: `python3 -c "import dharma_swarm.operator_core.living_agent_kernel"` exits 0 in main.

## Decision 2 — First holon agent

> **AMENDED 2026-06-11 by direct operator word (see amendment below): the first holons are
> `fable_composer` AND `codex_composer`, built as a pair.** opus_composer was parked as the
> Opus-model seat the same day (OPERATOR_STEER addendum 9); its identity richness transfers as
> the template. Original decision retained below for provenance.

**`opus_composer` is the first holon.** This resolves the spec contradiction in favor of
`02_FIRST_BRICK_SPEC` (which recommended opus_composer) and **supersedes** `05_RECONCILED_PLAN`'s
merge_master_mike default.

Rationale + honest tradeoff (verified on disk 2026-06-09):
- opus_composer has the **richest identity** of any registered self — `SOUL.md`, `OPERATING_MANUAL.md`,
  `identity.json`, `living_agent.json`, `passport.json`, `identity_invariant.json`, memory/, evidence/,
  work/ (30 files). Best possible "talk to it *as itself*" proof.
- It **lacks** a structured `autonomy_policy` / `*.registration.json` — which merge_master_mike *has*
  (`examples/agents/merge_master_mike.registration.json`, the gold-standard machine-readable banks).
- **Therefore:** v1 first brick is **read-only** — "talk to opus_composer on its own terms" (own model,
  prompt, memory, identity), **no enforcement yet**. Authoring opus_composer's `autonomy_policy` (porting
  mike's schema) moves into the **enforcement phase** (the 3–4 week "sovereign within banks" arc), not v1.
- Fitting note, not a reason: the first sovereign holon we bring to life is the agent that did the
  bringing-to-life. S(x)=x.

---

## Remaining gap-closing steps (from READINESS_VERDICT.md), now re-owned

| # | Step | Status after these decisions | Owner |
|---|------|------------------------------|-------|
| 1 | Declare canonical repo | ✅ **DONE** (Decision 1) | operator |
| 2 | Resolve agent-choice | ✅ **DONE** (Decision 2) | operator |
| 3 | Merge `living_agent_kernel` + registration delta into main; prove import closes | unblocked — ready to start | claude/codex |
| 4 | Declare holon lane in `ACTIVE_TRACK.yaml` (dedicated worktree, surfaces, verifier, receipt path) | unblocked | claude + operator |
| 5 | Resolve receipt/daemon non-goal | ✅ **RESOLVED by design constraint** (2026-06-09, verified) — see below | claude |
| 6 | Write the 6 verifier commands into `02_FIRST_BRICK_SPEC` | ✅ **DONE** (2026-06-09, adversarially hardened — draft verifiers were all false-greens, rewritten to real `provider.stream(LLMRequest)` interface). See spec appendix. | claude |
| 7 | Fill the ~15 unspecified contracts | ✅ **mostly DONE** — 3 resolved from code; provider-coercion + model-fallback + witness-root + token settled by canon/scoping. `AgentSeedResolver`/`dgc agent talk` greenfield. | claude |
| 7b | **AGENT-HOME** — ✅ DECIDED: canonical = `~/.dharma/agents/`. Holon `load_holon` reads there (unblocked). Full `ginko/agents`→`agents/` consolidation (10+ modules) staged as separate supervised hygiene — does NOT gate holon v1. See **[AGENT_HOME_RECONCILIATION.md](AGENT_HOME_RECONCILIATION.md)**. | ✅ decided · ⬜ migration supervised-later | operator+claude |
| 8 | Gate-hardening: fail-closed in v1, or explicit out-of-scope note | v1 is read-only → **scope OUT for v1**, in for enforcement phase | operator confirm |

## v1 persistence constraint (resolves gap #5 — verified 2026-06-09)

Read-only v1 stays inside the active track's non-goals ("no new daemon / event log / receipt / truth store")
**if and only if** it projects over existing owners. Verified by reading the code:
- **Conversation turns** → reuse the existing `conversation_log.log_exchange()` path (already called by
  `chat_with_agent` at `api/routers/agents.py:456-490`) with `interface="holon"`. Append-only JSONL, already live.
- **Artifact/outcome metadata** → existing `runtime_state.RuntimeReceipt.payload` + `spine.EvidenceReceipt`.
  No new table.
- **No session daemon** — each holon-chat POST is request-scoped; idle holons hold zero resources.
- **DO NOT build the spec's proposed `~/.dharma/holon_witness/` parallel tree** (`02_FIRST_BRICK_SPEC` line
  241 even flags this as unresolved). A new top-level tree = a new owner = non-goal violation. If session
  witness files are wanted, nest them under the existing `~/.dharma/witness/` root, not a new sibling.

**Build may NOT start the autonomous code phase until #3 (import closes) and #6 (verifiers written) are green.**
The next safe multi-hour effort is the **gap-closing pass (#3, #4, #6, #7)** — spec/forensics/integration,
not unsupervised feature-building. #5 is now settled by the constraint above.

---

## Amendment — 2026-06-11, direct operator word (live session with fable_composer)

Operator, verbatim:

> "canonical is main!! dharma swarm — I think whatever on local is closest to the repo
> dharma swarm on github. and yes the sovereign holons are good docs. and yes fable_composer
> should be the flagship, but for this build you need to collab with codex to make his own
> holon as codex_composer. you are both free to tweak it with as much personality as you
> want as long as it is deeply vision inspired and as meta and visionary as possible
> according to our entire history and the repo's major docs etc"

**Decision 1 RE-CONFIRMED:** canonical = `/Users/dhyana/dharma_swarm` (tracks
github.com/AmitabhainArunachala/dharma_swarm), canonical branch = `main`. Verified 2026-06-11:
that checkout is on lane branch `qwen/spine-adoption`, 11 ahead / 4 behind origin/main — lane
work merges to main via PR; main is truth.

**Decision 2 AMENDED:** the first holons are the TWO COMPOSERS, built as a pair in one
collab build:
- **fable_composer** — flagship (master_composer seat, claude-fable-5, created 2026-06-11,
  identity at `~/.dharma/agents/fable_composer/`, OPERATOR_STEER addendum 9). Inherits
  opus_composer's identity-richness pattern (SOUL.md, OPERATING_MANUAL.md, passport,
  invariant) as the template; opus_composer itself is parked as the Opus-model seat.
- **codex_composer** — built BY codex as its own holon, same organ standard, its own soul.

**Personality license (operator grant):** both minds may shape their holons' souls/voices
freely, bounded by: deeply vision-inspired, as meta and visionary as possible, grounded in
the operator's full history and the repo's major docs (foundations/, sovereign_holons/,
bridge docs, ~/CLAUDE1-9.md, the wiki). Personality is in-scope; vision-drift is not.

**v1 read-only stance carries over:** first brick = both composers talk-as-themselves under
their own identities; enforcement (autonomy_policy, fail-closed gate) remains the following
phase. Build governance per `~/.dharma/a2a_bus/collab/convergence/`
DAILY_HIGHEST_LEVERAGE_MISSION_2026-06-11.md + LONGRUN_CONFIDENCE.md (90/90 gate before launch).
