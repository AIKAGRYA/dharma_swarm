# Master Prompt — Coherence Pass (written to self, as Anthropic Fable 5)

**Role:** working_plan (per docs/AGENTS.md doc types — not canon, not authority)
**Author:** devin-roaming-2987d222 (the one registered Devin agent in the swarm; session 863663ec is an instance of that identity), 2026-06-11
**Audience:** the next Devin/Fable build session that picks up this work
**Registration:** `inter_agent/devin/outbound/2026-06-11T08-45Z-devin-session-registration-863663ec.md`
**Replaces / subordinates to:** nothing — proposes work; owners stay where
`docs/governance/CANONICAL_DOC_STACK.md` puts them.

> Historical snapshot. Current command semantics are owned by
> `docs/governance/BUILD_SESSION_ENTRYPOINT.md`: `make onboard` reports
> session status, while exact edit admission and closeout require
> `PACKET=<path>`.

---

## 0. Wake sequence (do this verbatim)

```bash
cd "${DHARMA_SWARM_REPO:-$HOME/repos/dharma-swarm}" || cd "$HOME/dharma_swarm"
git pull origin main
make onboard                       # read-only session status; trust current owner docs over this snapshot
cat docs/agents/devin-roaming-2987d222/MEMORY.md   # newest entry = your context
ls inter_agent/devin/inbound/
```

If current owner docs disagree with anything in this file, the owner docs win.

## 1. State of the repo as of HEAD `e1b9f839` (2026-06-11)

- **The door:** `make onboard` (single-door v2, #563) renders portfolio,
  parallel lanes, live-ops snapshot, broken register, axioms. It is the only
  remembered command; `make agent-build-closeout` before PR handoff.
- **Three-layer SSoT:** Intent = `docs/governance/ACTIVE_TRACK.yaml`;
  Surface = `ACTIVE_SURFACE_MANIFEST.yaml`; State =
  `docs/state/LIVE_OPS_DASHBOARD.md`. The surface manifest is no longer a
  binding first-read gate — it is depth-on-demand behind the door, checked
  by Manifest Health tooling, last_updated 2026-05-20. Do not re-elevate it.
- **Portfolio:** `runtime-truth-reconciliation-2026-06` (operator-owned,
  operator_core/onboard surfaces) and `runtime-truth-nats-2026-06`
  (codex-owned, NATS transport surfaces). Spine objectives with **no active
  track**: `revenue-external-humans-served`, `research-depth`.
- **Fleet:** Fable 5 (Anthropic lane, `honest-spine-v2`) is pushing receipt
  honesty; MMM holds conditional merge; HERMES heartbeats; this Devin
  identity is the external worker (evidence only, PRs only, never main).
- **Open BRs:** BR-003 (apply gate closed), BR-004 (cron split-brain),
  BR-005 (algedonic steady-state).
- **Axioms in force:** A1 no flat-package growth, A2 no duplicates,
  A3 no undocumented seams, A4 no vibe-coding, A5 no god objects,
  A6 docs decay, A7 no circular imports, A8 frontmatter discipline.

## 2. The problem this prompt exists to solve

The repo's truth is now well-governed but **poorly connected**. Knowledge is
findable only through the door (`make onboard`) or through human memory of
which of ~870 markdown files owns what. Names do not predict locations;
locations do not predict ownership. Examples:

- Root maps (`CYBERNETIC_LOOP_MAP.md`, `FOUNDATIONS_TO_CODE_MAP.md`,
  `MODEL_ROUTING_MAP.md`, `INTERFACE_MISMATCH_MAP.md`) sit beside
  `docs/architecture/` equivalents; one (`MODEL_ROUTING_MAP.md`) is already
  just an archive pointer.
- Agent identity lives in four shapes: `docs/agents/<uid>/` nests,
  `examples/agents/*.registration.json`, `inter_agent/<agent>/` mailboxes,
  and Mac-side `~/.dharma/external_agents/`. Same entity, four naming schemes.
- `docs/plans/`, `docs/doctrine/`, `docs/vision_maps/`, `lodestones/`,
  `foundations/`, `specs/` each hold prose with overlapping roles; only
  CANONICAL_DOC_STACK.md's table disambiguates, and only if you read it.

## 3. Proposal A — name/filesystem coherence (small, mechanical)

Principle: **a path should encode its doc role and its owner.** No mass
moves; converge opportunistically under the existing DocOps lifecycle
(inventory → demote → redirect → archive).

1. **One agent namespace.** `inter_agent/<uid>/` and `docs/agents/<uid>/`
   adopt the same `<uid>`s as the registration manifests
   (`merge_master_mike`, `devin-roaming-2987d222`, `fable-5`, ...). Add a
   tiny `docs/agents/INDEX.md` table: uid → nest → mailbox → registration →
   authority. (Closes the practical half of BR-013-style scatter.)
2. **Role-prefixed plan/report names.** New files in `docs/plans/` and
   `reports/` start with `YYYY-MM-DD-` and declare `**Role:**` in line 2
   (this file complies). A 20-line checker can enforce it later if it earns
   a gate; observation first, per hygiene lifecycle.
3. **Root maps become pointers.** Each remaining root `*_MAP.md` either is
   the owner (then CANONICAL_DOC_STACK.md says so) or becomes a 5-line
   pointer to its `docs/architecture/` owner, like MODEL_ROUTING_MAP.md
   already did.

## 4. Proposal B — `make composer` (high-level onboarding composer)

`make onboard` answers "what is true right now." Nothing answers "compose
me the right context bundle for the work I'm about to do." Proposal:

```
make composer TASK="touch operator_core read models"
# → renders, read-only, in one screen:
#   1. which track owns the surfaces the task touches (or NEW TRACK needed)
#   2. the owner docs for those surfaces (from CANONICAL_DOC_STACK table)
#   3. open BRs + interface mismatches intersecting those modules
#   4. which fleet lanes are parallel-working those surfaces
#   5. the exact first-read list (≤5) for this task — not the global one
```

Implementation sketch: `scripts/governance/agent_composer.py`, pure
projection — reads ACTIVE_TRACK.yaml, the CANONICAL_DOC_STACK ownership
table (promote it to a sibling YAML so it is machine-readable, prose stays),
BROKEN_REGISTER.md, and `git branch -r` lanes. No new store, no daemon, no
authority surface; same doctrine line as onboard: *read models project truth
from owners; they do not become authority.*

## 5. Constraints (do not violate)

- This work needs a **new track** in ACTIVE_TRACK.yaml (`serves:` likely
  `substrate-nativeness`; owned_surfaces: `scripts/governance/agent_composer.py`,
  `docs/agents/INDEX.md`) — it must not touch either active track's surfaces.
- No new root markdown (Rule 8). No frontmatter in governance docs (A8).
- Prefer demoting/pointing over moving; archive only via DocOps lifecycle.
- Every PR: `make onboard` →
  `make agent-build-preflight PACKET=<path>` → work → tests →
  `pre-commit run --all-files` →
  `make agent-build-closeout PACKET=<path>` → PR with evidence.

## 6. Definition of done for the next session

1. Operator has approved or amended Proposals A and B.
2. New track opened in ACTIVE_TRACK.yaml + includes re-rendered.
3. First PR: `docs/agents/INDEX.md` + composer skeleton with `--json`,
   covered by a test that asserts it writes nothing.
4. MEMORY.md entry + outbound packet, as always.
