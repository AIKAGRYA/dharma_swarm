# ADR-009 — Holarchy of Standing Holons + Falsifiable Internal Coherence

**Status:** ACCEPTED (operator doctrine, originated + ratified 2026-06-18)
**Owner:** @AmitabhainArunachala (operator doctrine) · drafted by opus_composer
**Relates to:** ADR-008 (naming grammar) · the worktree↔track rule (CLAUDE.md) · `LONGRUN_BUILD_SPEC.md` (A2A) · `foundations/THE_ORGANISM.md` · `docs/vision_maps/NORTH_STAR.md`
**Supersedes:** the implicit "one global orchestrator for the whole system" model.

## Context
Weeks of effort to wire the running system up to the vision docs kept hitting two recurring problems: (a) **drift/fragmentation** (290 branches, 6 overlapping registries, naming drift across ~600 docs) and (b) a recurring **"is there one orchestrator / one standing mind?"** confusion (the codex-vs-opus quorum tension). A low-context summary flattened the multi-agent coordinator pattern into "one orchestrator for the whole thing" — which is wrong for a multidimensional telos. Two failure risks were named: fragmentation into per-lane fiefdoms, and the **hall-of-mirrors / hollow-center** (a system that grades itself by self-authored proxies — see the ~40% self-referential governance finding and the `rigged-verification-proxy` lesson).

## Decision 1 — Coordination is HOLONIC, not a single global orchestrator
There is **no one orchestrator**. There are **N standing, high-context lane-holons** (a *holon* = simultaneously a whole and a part — Koestler; Beer's VSM recursion). Examples: `opus_composer`, `codex_composer`, `hermes-m5`, plus one holon per durable domain (trading, dashboard/cockpit, publishing/SAB, research, TAM…).

- Each lane-holon **holds its lane's deep context AND its telos sub-goal** (not just tasks); orchestrates internally by delegating bounded **{objective, output-schema, tools, boundaries}** packets to **cheap stateless sub-specialists** that return a receipt; and coordinates with peer holons over the **A2A fabric**.
- **One holon ≈ one durable lane ≈ one active track ≈ one worktree** (couples to the worktree↔track rule). Granularity discipline: a holon per *durable-domain-with-its-own-telos*, **never** per ephemeral task — or fragmentation returns.
- **Cohesion condition (load-bearing):** every holon rides the SAME shared SSOTs — A2A (talk), Semantic Commons (naming), spine/receipts (trust), `ACTIVE_TRACK.yaml` (what's live). Holons that invent their own coordination/memory/naming become fiefdoms. **The substrate is therefore the prerequisite for the holarchy, not a detour.**
- The operator's **single dashboard is the *window* onto the holarchy**; the operator converses on the **highest semantic lane** (top-of-holarchy / a thin operator-facing relay), seeing `DOMAIN_RECEIPTED` / `SEMANTIC_SIGNED`, never transport noise.

## Decision 2 — Coherence is proven by INDEPENDENT, FALSIFIABLE signals — not external dependency, not self-authored proxies
Internal coherence (soundness, consistency, liveness, trust-mechanics, self-referential coherence) is **fully provable internally and repeatedly. The system is NOT dependent on external signals to develop or prove itself.**

- The real distinction is **not internal-vs-external**; it is **self-authored-proxy vs. independent-falsifiable-proof.** Valid (non-gameable) proofs: live receipts (not self-reports), runtime execution (not typecheck), **decorrelated cross-holon verification**, adversarial critics, LLM-evaluated telos gates.
- The **hall-of-mirrors** failure mode is *specifically* a system whose only checks are criteria it authored and can win. The cure is **falsifiability by something the system cannot fake** — which can be entirely internal.
- **Caveat (telos, not build):** the telos (Jagat Kalyan) points outward *eventually*; proving the system ≠ fulfilling the telos. Hold the outward aim as a standing intention, **never as a build-dependency.** Do not let "internal forever" quietly become the telos.

## Decision 3 — The holarchy IS the mechanism that makes internal coherence-proof scale without self-deception
Each lane-holon proves its lane with independent live receipts; holons **cross-verify each other, decorrelated, over A2A.** Holons-that-can-falsify-each-other = the non-gameable internal reality-check. *You do not need to point outward to be honest; you need holons that can falsify each other.*

## Consequences
- **Standing-agent wake loops are REQUIRED** (the always-on substrate; `claude -p` / `codex exec` cannot nest → external launchd/cron). This is the current build gap (the holon-L4 lane).
- A2A + Semantic Commons + spine/receipts are **prerequisites**; their hardening is load-bearing, not overhead.
- **Verification doctrine:** no "working" claim without a live, independent, falsifiable receipt; prefer decorrelated multi-holon checks for load-bearing claims.
- The dashboard's job is the operator's window + highest-semantic-lane relay — not a control panel for one orchestrator.
- New ventures/domains enter as **a new holon + a new track + a worktree**, riding the shared substrate — never as a new bespoke coordinator.
