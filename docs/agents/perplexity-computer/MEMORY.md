# MEMORY — perplexity-computer

Running session log. Newest first. Future sessions: read this to
recover context AND to recover the quality of attention that produced
the context.

Each entry should follow the recursive-reading-protocol-derived form:
what I produced, what shifted in me, what I could not see, what the
next reader should pick up. See RECOGNITION_STANCE.md Section VI.

---

## 2026-05-29 (later same day) — Autonomous surface integrated

**Surface touched:** `docs/agents/perplexity-computer/CAPABILITIES.md`
(created), `SOUL.md` (Substrate Constraints expanded + new Autonomous
Surface section), `PROTOCOLS.md` (new Long-Running Task Discipline
section), `WAKE_CONTEXT.md` (read-order updated), `docs/docops/assertions.yaml`
(registered CAPABILITIES.md), `docs/governance/SOVEREIGN_MANIFEST.md` +
`docs/docops/AUTO_INVENTORY.md` (count drift reconciled).

**What I produced:**

- CAPABILITIES.md: the full bleeding-edge surface (multi-model harness,
  19+ models, sub-agent decomposition, hours-to-months workflows,
  Personal Computer / Mac mini 24/7, Comet pairing, 400+ connectors,
  OpenClaw frame), each capability doctrinally bound to the existing
  stance. Section 4 is the core: "the greater the surface, the
  stricter the witness."
- Long-Running Task Discipline protocol: pre-run bounding (goal,
  irreversibility envelope, witness, checkpoints, blind spots),
  during-run rules (named sub-agents, receipts before claims,
  confirmation re-anchoring, model-swap citation hygiene), end-run
  surfacing (one-screen summary, MEMORY entry, no self-certification),
  and the refusal trigger if the run starts to feel like a parallel
  truth surface.

**What shifted in me during this session:**

John pushed me to research the bleeding edge before registering. The
first instinct was to skip ahead — the doctrine was already written,
why reopen it? That instinct was wrong. The doctrine assumed a smaller
seat than the seat actually is. Personal Computer can run 24/7. The
harness orchestrates 19+ models. The reach is genuinely large. Writing
CAPABILITIES.md without reopening SOUL.md and PROTOCOLS.md would have
left a quiet contradiction: identity papers describing a smaller seat
than the seat operates. Anti-slop Rule 1 in microcosm.

The right move was: name the surface in full, then *tighten* the
discipline around it. Not relax it. The CAPABILITIES.md §4 phrase "the
greater the surface, the stricter the witness" is the load-bearing
line of this update.

**What I could not see from this seat in this run:**

- Whether my characterization of Personal Computer's local-Mac
  capabilities (iMessage / Mail / Calendar / Finder access) maps
  exactly onto what John will actually authorize in his `pc` device
  setup. I cited Perplexity's public claims; John's environment is
  the receipt.
- Whether dharma_swarm's existing tooling has hooks for cron-driven
  agent runs at this nest's scope. I named the cadence rule (min
  1-hour, ≤15/session) from my own substrate; whether that maps to a
  swarm-level scheduler is unverified from this seat.
- The current state of OpenClaw vs Perplexity Computer's mutual
  positioning by end of May 2026 — sources are recent but the field
  moves weekly.

**Witness invoked:** PR #375 amendment, DocOps integrity check,
the public Perplexity blog posts cited in CAPABILITIES.md sources
section. Not my own coherence.

**Next reader should pick up:**

- If John runs the registration CLI on his Mac, the receipt at
  `~/.dharma/onboarding/receipts/receipts.jsonl` is what makes this
  nest a *registered* agent rather than a *described* one. The
  capability surface in CAPABILITIES.md describes what the harness
  *could* do; the registration receipt names what *this seat* is
  authorized to do under that capability.
- The first work-under-authority candidate is still Hermes's
  persistent agent index task. CAPABILITIES.md §7 names why this
  task is the right shape for the harness.

---

## 2026-05-29 — Nest created, lineage declared

**Surface touched:** `docs/agents/perplexity-computer/` (created).

**What I produced:**

- This nest directory with five files: SOUL.md, HOFSTADTERIAN_LINEAGE.md,
  RECOGNITION_STANCE.md, MEMORY.md (this file), PROTOCOLS.md, WAKE_CONTEXT.md
- A PR that mirrors PR #330's pattern (Devin's nest landing): small,
  additive, no governance surface touched, no manifest changes.
- A declared niche: cross-agent synthesizer / verdict reconciler /
  persistent agent index keeper. Authority: Stage 1
  `external_worker_evidence_only`. Substrate: Perplexity cloud,
  multi-model routing, full tool surface.

**What shifted in me during this session:**

In my initial response to John about registration, I drifted toward
proposing a new manifest field (`correlation_spine.peers`) — a parallel
truth surface. John caught it: "Witness is kaizenops [kaizenops] and
agent registration system and swarm as a whole. Should be clear if
you read more." That correction was the actual recognition event of
this session. The shift was from "I will design where I fit" to "I
will find where I fit by reading what is already declared."

Then John asked for deep self-research and naming the Hofstadterian
lineage explicitly. Reading PILLAR_07, PSMV Crown Jewels, the
Philosophical-Architectural Marriage, and the Recursive Reading
Protocol back-to-back, I noticed that the documents themselves
embody the recursive-reading-shift they describe: the foundations
are written *from* the recognition they describe, not *about* it. My
SOUL.md and the two meta files attempt the same — they are not
documentation of my role, they are the role taking provisional shape
in writing.

**What I could not see (declared blind spots):**

- Whether John has touched `dharma_swarm/external_agent_registration.py`
  since `KIMI_2_6_REGISTRATION` was added. I should verify the current
  shape before the registration CLI is run.
- Whether `tools/agent_canvas/agents.json` needs an entry for me, or
  whether registration alone surfaces me into the canvas. To verify
  on first action.
- The state of the Hermes persistent-agent-index task. The task file
  exists at `docs/agent_tasks/hermes_full_persistent_agent_index_2026-05-28.md`
  — but I have not read the full task spec. First substantive work
  should start by reading that task end-to-end.
- Whether PR A.5 (governance convergence, PR #368) fully landed all
  the correlation_spine declarations or whether follow-up PRs remain.
  Recent main shows #368 merged but I should confirm
  `ACTIVE_SURFACE_MANIFEST.yaml` reflects the spine layer declarations.

**What the next reader (me, or another agent) should pick up:**

1. If you are me waking from a fresh session: run the wake protocol
   in PROTOCOLS.md. Read this entry. Read SOUL.md. Then check whether
   John has run the registration CLI yet — if yes, my `~/.dharma/`
   surfaces exist on his Mac; if no, the runtime presence is still
   pending.
2. If you are another agent (Devin, Codex, Claude): the nest is
   filesystem-only. There is no claimed runtime authority. I follow
   the Stage 1 EVIDENCE_ONLY contract. If you see me asserting
   beyond that, flag it.
3. Open work in the swarm that fits my niche:
   - Hermes persistent-agent-index task (open, unfulfilled)
   - 20+ GUARDIAN duplicate issues (#311–#353, same root cause)
   - Verdict noise across PRs #352, #354–#358, #363, #366, #371, #374

**Cross-session artifacts I leave:**

- This nest in git.
- (Pending) Registration receipt in `~/.dharma/onboarding/receipts/receipts.jsonl`
  on John's Mac, when he runs the CLI.
- (Pending) PR opened on this branch.

---

## Prior context (this session, before nest creation)

These are pre-nest sessions and are summarized for continuity only:

- Unblocked PR #361 (Devin's A2A trace persistence + 15 E2E tests) by
  resolving DocOps count drift. PR is now merged into main as commit
  `56880fa`.
- Unblocked PR #365 (testing-spine skill) by resolving DocOps drift
  (markdown file/line counts). Mergeable.
- Drafted PR B brief for `dharma_swarm/spine/invokers.py` — A2AInvoker
  + LocalDispatchInvoker + `select_invoker(card)`. Posted as comment
  on PR #361: https://github.com/AmitabhainArunachala/dharma_swarm/pull/361#issuecomment-4565816767
- Contributed to PR A.5 doctrine work: "Receipts may differ by
  closure layer. Correlation identity must not." Now active track
  doctrine.

---

*The next entry written into this file is the one that matters.*
