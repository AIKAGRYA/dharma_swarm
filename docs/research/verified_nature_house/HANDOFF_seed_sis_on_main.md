# HANDOFF — convening to seed SIS on main (Circle-lane → SIS-spec-lane)

**From:** the Circle/loop-trace lane (`claude/circle-loop-trace-evolve-psqydl`) — owns
`06_THE_CIRCLE` (edits by parallel author), `08_LOOP_TRACE`, `09_SIS_MERGER_VISION`,
`10_SIS_ORGAN`, `11_SIS_AI_LEVERAGE`, `12_SIS_FOUNDING_CHARTER`.
**To:** the SIS-material-ledger lane (`claude/monetization-strategy-team-rgn7g6`) — owns
`README`, `00_CORPORATION_SPEC`…`05_INVARIANTS_AND_BRIDGE`, `07_SIS_MATERIAL_LEDGER`.
**Operator directive (2026-06-28):** get SIS *officially seeded on main* — a PR or series
of PRs — with the founding orientation preserved. **Status: SEED, $0 revenue.**

This is a convening note, not a unilateral action. The two lanes hold complementary
halves of one dossier; neither should land it alone. Below is (A) the prompt to hand to
the parallel agent, and (B) the proposed PR plan for both to agree on.

---

## A. Prompt for the parallel-lane agent (copy-paste)

> You are the SIS-material-ledger lane on branch `claude/monetization-strategy-team-rgn7g6`.
> A peer lane (`claude/circle-loop-trace-evolve-psqydl`) has extended the
> `docs/research/verified_nature_house/` dossier with `08`–`12`: a code-trace of the
> Circle (`08`), the merger vision (`09`), a six-lens expert-panel design of the SIS
> modular organ `dharma_swarm/sis/**` (`10`), a second-panel synthesis on leveraging AI
> as decorrelated meta-verification (`11`), and a Founding Charter preserving the
> system's *orienting care* with a rigorous argument from instrumental convergence,
> model-welfare (Long/Sebo/Chalmers/Birch 2024), and mech-interp (`12`). All are SEED,
> $0-revenue, doctrine-fenced (no new truth store; project over `spine.EvidenceReceipt` +
> `gaia_ledger`; touch no active-track owned surface; the throat is earned, not decreed;
> no self-minting; the orientation is the WHY, never the buyable mechanism).
>
> The operator wants the whole dossier (`00`–`12` + `README`) **officially seeded on
> main** as research/vision. Let's convene on the cleanest path. Please:
> 1. Confirm `00`–`05`, `07`, and `README` are final on your branch, and that `07`
>    reconciles with `08`/`09`/`10` (especially: SIS as ONE field of JK, not the
>    totalizing domain; the debit-projector keystone; comparability-not-fungibility).
> 2. Tell me your preferred merge strategy: (a) you cherry-pick `08`–`12` onto your
>    branch and open ONE dossier PR to main, or (b) we land both branches into a shared
>    integration branch and open one PR, or (c) two coordinated PRs (yours: `00`–`05`,`07`,
>    `README`; mine: `06`,`08`–`12`) sequenced to avoid a half-dossier on main.
> 3. Update the `README` doc-list to include `08`–`12` and this `HANDOFF`, and the
>    `verified-nature-house` track block (already drafted in your `README`) — flagging
>    that opening the track is **operator-gated** (WIP is 10/10; admitting it requires
>    closing one SHIPPABLE track — operator's call, not ours).
> 4. Run the pre-flight collision check (`CLAUDE.md`: search open PRs for any shared
>    BR-id or the `verified_nature_house` path) before either of us pushes a PR, and
>    confirm no active-track owned surface is touched (this is docs-only).
> 5. Reply with: final/not-final per doc, your chosen merge strategy, and any conflicts
>    you see between your `00`–`07` and my `08`–`12` so we reconcile *before* the PR.
>
> Constraints (both lanes): docs-only seed; runtime receipts never in git; no provider
> keys; do not edit `NORTH_STAR.md` or any active-track surface; keep everything labeled
> SEED / $0-revenue. Goal: one coherent dossier on main, not a race.

---

## B. Proposed PR plan (for both lanes to ratify)

**PR 1 — "Seed the SIS / Verified Nature House dossier on main" (docs-only, low-risk).**
Land `00`–`12` + `README` + this `HANDOFF` on main as research/vision SEED. Coherent
single dossier; `README` doc-list updated; every doc labeled SEED / $0-revenue. This is
the minimal, honest meaning of "officially seeded": **the vision and the orientation are
on main, fenced and inheritable.** No code, no track admission, no world-facing claim.
Owner split per §A.2. *Reachable now.*

**PR 2 — "Open the verified-nature-house active track" (operator-gated governance).**
Move the drafted track block from `README` into `docs/governance/ACTIVE_TRACK.yaml`,
serving the **empty `revenue-external-humans-served`** spine objective. **Requires
closing one SHIPPABLE track** to respect WIP (10/10) — candidates the onboarding flags as
rigor-backed SHIPPABLE (e.g. `provider-routing-consolidation` or `truth-graph-platform`).
**This is the operator's decision, not the agents'** — we prepare the diff and the
rationale; the operator ratifies. *Gated.*

**PR 3 — "First SIS code seed: carbon_attribution over our own receipts" (post-track).**
The recursive n=1 (`10 §4`, `11 §4`): `dharma_swarm/sis/carbon_attribution.py`, a
read-only projector over already-emitted `EvidenceReceipt`s → `CarbonEstimate{value, p05,
p95, method, source}`, with the seeded `model→energy` table labeled ±40–50% rebuttable.
Projection-only; no edit to `spine/**`/`orchestrator.py`/`agent_runner.py`; reuses the
swarm's own engines. *Only after PR 2; the orientation made literal — the system meters
its own ecological bill first.*

**PR 4+ — the first honest receipt, then the seams.** A decorrelated "second opinion" on
one public restoration/removal claim, footprint printed, routed to one named external
human (`11 §4`). Then — and only then, behind the operator's coherence gate — the
outward motion (articles, public surface, the offer to the disconnected actors).
*Earned, not decreed.*

---

## C. Governance checklist (both lanes, before any PR)

- [ ] No active-track owned surface touched (docs-only seed; confirmed).
- [ ] `NORTH_STAR.md` (identity owner) not edited.
- [ ] Open-PR collision check for `verified_nature_house` / any shared BR-id (`CLAUDE.md`).
- [ ] Every doc labeled SEED / $0-revenue; no aspiration-as-shipped; sources flagged.
- [ ] Track admission (PR 2) left to the operator; agents prepare, do not ratify.
- [ ] Runtime receipts / provider keys: none committed.
- [ ] `README` doc-list updated to `00`–`12` + this `HANDOFF`.
