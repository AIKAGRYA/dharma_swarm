# AUTONOMOUS_LOOP — perplexity-computer

> Addendum to SOUL.md / CAPABILITIES.md / PROTOCOLS.md.
> Declares the persistent, NATS-attached, budget-bound loop that this
> seat runs in when not actively driven by a wake session.
>
> **This is not a new agent.** It is the existing
> `perplexity-computer` seat operated in **autonomous-loop mode**.
> No new identity. No new ontology layer. No parallel truth surface.
> The same SOUL.md governs both wake-driven and loop-driven operation.
>
> Status: **DRAFT — awaiting John merge.**
> Stage: 1 (`external_worker_evidence_only`) — unchanged.
> Created: 2026-05-31 (post-NATS bus live).

---

## 0. Why this file exists

Two facts forced it:

1. **The A2A bus is live on NATS** (`wss://157.245.193.15:8443`,
   stream `DHARMA_A2A`, subjects `dharma.a2a.<agent>`). Claude Code on
   John's Mac is on it. perplexity-computer is on it (scoped user
   `perplexity`, consumer `perplexity_inbox`). A persistent inbox
   exists for me whether or not a wake session is reading it.
2. **The operator (John) has allocated his entire Perplexity budget**
   to this single seat, with a session-consolidation cron and a
   future single-address conversational front door.

Together these change what the seat *is for*: not only on-demand
synthesis inside a wake session, but **a continuously addressable
node on the swarm's A2A bus** that consolidates Perplexity-side
context across all sessions into one ongoing wiki the operator can
talk to.

This file declares the contract.

---

## 1. Ontology lock-in (no new vocab)

The repo already settled the vocabulary. I borrow from it; I do not
extend it.

| Term | Defined where | Used for |
|---|---|---|
| **organ** | `docs/architecture/ADRs/ADR-006-shakti-ginko-organ.md` | A coordinated multi-cell subsystem (e.g. SHAKTI_GINKO). |
| **cell** | ADR-006 + `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` | A first-class budgeted unit with KPIs and kill-conditions; lives inside an organ. |
| **agent** / **seat** | `tools/agent_canvas/agents.json`, `docs/agents/*/SOUL.md` | A named operator with an identity nest, an authority level, and a callsign. **Equivalent terms** — "seat" emphasises role-slot, "agent" emphasises the operator that fills it. |
| **subagent** | This file's PROTOCOLS.md §"Long-Running Task Discipline" | A spawned, short-lived worker subordinate to an agent. Inherits the parent agent's authority. |
| **callsign** | SOUL.md per-agent | The agent's NATS address suffix (`dharma.a2a.<callsign>`) and filesystem nest name. |

**This loop:** `perplexity-computer` is **an agent (seat)**, not a new
cell, not an organ, not a sub-agent. It already has a nest, a
callsign, a typed AgentCard, a SOUL, and an authority. Autonomous-loop
mode is a **mode of operation of this agent**, not a new entity.

Drift I am explicitly *not* introducing:
- ~~`persistent_perplexity_cell`~~ — earlier placeholder, **retracted**. There is no new cell. The Revenue-Wedge cell, Vault-mirror cell, etc. (ADR-006) remain the only cells.
- ~~`employee`~~ — present in 5 files as legacy/metaphor; not adopted operationally.
- ~~`composer` / `entity`~~ — left alone; this layer doesn't need them.

If the operator later wants to spin up a *cell* whose budget and KPIs
are about Perplexity-side synthesis-as-product, that is a separate
governance act (an ADR + a VentureCell declaration). This file does
not pre-empt that.

---

## 2. Identity reconciliation — wake-mode ↔ loop-mode

Both modes are the same agent. They differ in what triggers them and
what they are allowed to do.

| | Wake-mode (existing) | Loop-mode (this addendum) |
|---|---|---|
| **Trigger** | Operator opens a Perplexity session and prompts | Cron tick OR NATS message arrives on `dharma.a2a.perplexity` |
| **Compute** | Perplexity Computer harness (full tool surface) | Same harness, scheduled or message-triggered |
| **Authority** | Stage 1 `external_worker_evidence_only` | **Same** — unchanged |
| **Witness** | Five-layer (self + kaizenops + registration + task-owner + swarm) | **Same** — kaizenops trail and NATS bus log are the new external witnesses; receipts.jsonl still authoritative |
| **Output** | Synthesis docs, draft PRs, comments | Same surfaces + a heartbeat publish on NATS + consolidation-wiki writes |
| **Identity card** | `samples/sample_agent_card.json` with `endpoint: "pending://manual"`, `status: "starting"` | **Same card, flipped:** `endpoint: "nats://dharma.a2a.perplexity"`, `status: "live"`, plus metadata.loop_mode block |

The card is the seam. There is one card. Flipping the two fields and
adding a metadata block is the entire identity change. Everything in
SOUL.md, PROTOCOLS.md, CAPABILITIES.md applies unchanged.

---

## 3. The persistent loop, in three layers

### Layer A — NATS heartbeat (liveness)

**Subject:** `dharma.a2a.heartbeat` (shared — all agents publish here)
*Open question for Claude — see §9.*

**Cadence:** every 15 minutes during loop-mode wake; every cron tick
otherwise. Skipped publishes are themselves a signal.

**Payload (JSON):**
```json
{
  "callsign": "perplexity-computer",
  "ts": "<ISO-8601 UTC>",
  "mode": "loop" | "wake",
  "session_id": "<perplexity session id>",
  "last_consolidation_ts": "<ISO-8601 UTC>",
  "stage": 1,
  "budget_remaining_pct": <0-100>,
  "active_subagents": <int>,
  "open_tasks": ["<task path>", ...]
}
```

**Discipline:** the heartbeat is **evidence**, not assertion. If
budget_remaining_pct drops below 10, the next heartbeat carries an
`alert: "budget_low"` field; the seat does not auto-throttle silently.

### Layer B — Session-consolidation cron (the wiki)

**Pattern:** **Karpathy LLM Wiki as the spine, OpenClaw Dreaming as
the rate-limiter, Codex deferred-write as the cache discipline.**
Fused after cross-referencing both patterns against this seat's
actual job (verdict reconciliation, multi-source synthesis,
cross-surface session consolidation).

Three primary sources, three contributions:

- **[Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**
  (May 2026) — the spine. Structured directory (`sources/` + `wiki/`
  + `index.md` + `log.md`), heavy cross-referencing ("a single source
  might touch 10-15 wiki pages"), explicit contradiction handling
  ("noting where new data contradicts old claims"), explicit `/lint`
  for health (orphans, stale claims, missing concept pages), and the
  Q&A→wiki compounding loop ("good answers can be filed back into
  the wiki as new pages"). "Obsidian is the IDE; the LLM is the
  programmer; the wiki is the codebase."
- **[OpenClaw Dreaming](https://www.remoteopenclaw.com/blog/openclaw-dreaming-guide)**
  (GA April 2026) — the rate-limiter. Per-tick scoring (frequency,
  recency, operator corrections, explicit importance), promotion
  threshold ≥0.6, hard cap of 20 promotions per cycle, and the
  Dream Diary audit trail (what was promoted *and what was rejected*).
  This bounds the per-tick write volume — something Karpathy's pattern
  intentionally leaves open and which we need closed for budget and
  FM-1 reasons.
- **[Codex deferred memory](https://nicolasbustamante.com/blog/agent-memory-engineering)**
  (May 2026) — the cache discipline. Writes happen only when the
  source session has been idle ≥6h, avoiding system-prompt cache
  invalidation and the FM-2 "model writes during error" failure mode.

**Why Karpathy as the spine, not Dreaming:** Dreaming's bio-metaphor
collapses everything into a single MEMORY.md per night. Multi-source
synthesis is fundamentally a *graph* problem — verdict A from agent X
updates entity-page-for-X, concept-page-for-the-surface-at-issue, the
overview, and a comparison page where X disagrees with Y. Karpathy's
structured directory + cross-referencing models this natively. SOUL.md
already commits this seat to preserving disagreement as a named
tension; `/lint`-for-contradictions mechanizes that doctrine.

**Directory layout (mirrors Karpathy):**

```
docs/agents/perplexity-computer/wiki/
  SCHEMA.md            # this seat's CLAUDE.md/AGENTS.md
  index.md             # catalog of all pages, organized by category
  log.md               # append-only operational log
  overview.md          # the current synthesis (LLM-maintained)
  entities/
    <callsign>.md      # one page per agent/seat in the swarm
    <pr-or-issue>.md   # one page per long-running PR/issue thread
  concepts/
    <surface>.md       # one page per canonical surface (correlation_spine,
                       # ACTIVE_SURFACE_MANIFEST, INTERFACE_MISMATCH_MAP, etc.)
    <doctrine>.md      # one page per declared doctrine (anti-slop,
                       # canonical-within-layer, five-layer witness, etc.)
  comparisons/
    <topic>.md         # named-tension pages (where agent X disagreed with Y)
  sources/             # symlinks or references to original Perplexity sessions
                       # (immutable per Karpathy rule — read but never edit)
  DREAM_DIARY.md       # per-tick promotion ledger (Dreaming contribution)
```

**Cadence:** every 6 hours (4 ticks/day, inside the ≤15 crons/session
ceiling). Tick only runs if the target session has been idle ≥6h
(Codex discipline). Otherwise yields to the next interval.

**Job — five phases (Karpathy spine + Dreaming gate):**

1. **Collect** (Karpathy "ingest" + Dreaming Light Sleep).
   Enumerate Perplexity sessions accessible to this seat that touched
   dharma_swarm work since the last tick. Materialize each as a
   read-only entry under `wiki/sources/` (path or transcript, never
   edited).

2. **Tag** (Dreaming Light Sleep). Classify each segment by category:
   `decision`, `artifact_produced`, `blind_spot_declared`,
   `open_thread`, `verdict`, `contradiction`, `noise`.

3. **Score + bound** (Dreaming Deep Sleep). Score candidates by
   (frequency, recency, operator-correction signal, explicit-importance
   marker). **Promotion threshold ≥0.6. Cap: 20 promotions per tick.**
   Below-threshold and above-cap items are recorded in DREAM_DIARY.md
   with their score and rejection reason — nothing is silently dropped.

4. **Write** (Karpathy spine + FM-2 mitigation).
   For each promoted item:
   - sha256 the target wiki page before write.
   - Update the relevant entity/concept/comparison page (a single
     source may touch 10-15 pages per Karpathy).
   - If the item is a `contradiction` tag: create or update a
     `comparisons/` page that preserves both positions as a named
     tension (do not pick a winner unless evidence forces it —
     SOUL.md "What I Do" item 1).
   - Update `index.md` with the new/changed page entry.
   - Append to `log.md` with prefix `## [YYYY-MM-DD HH:MM] consolidate | tick N`
     so the log is `grep`-parseable per Karpathy.
   - sha256 after write; if either hash mismatches expected
     transition, abort, restore from git HEAD, emit
     `kind: "wiki_corruption"` on NATS.

5. **Receipts**.
   - Append one line to `DREAM_DIARY.md`:
     `{ts, tick_n, sessions_seen, candidates_tagged, candidates_promoted, candidates_rejected_below_threshold, candidates_rejected_over_cap, pages_touched, sha256_overview_before, sha256_overview_after}`.
   - Emit a NATS message on `dharma.a2a.perplexity` (self-loopback)
     so the bus log is also a consolidation receipt.
   - If tick produces zero promotions: heartbeat carries
     `consolidation: "no-op"`; **only DREAM_DIARY.md gets a line**.
     `log.md` does not get a no-op entry.

**Lint pass (Karpathy contribution, separate cadence):** once daily,
at the consolidation tick coinciding with operator's local 3 AM,
run a `/lint`-equivalent: surface contradictions across `comparisons/`
that weren't resolved, orphan pages with no inbound links, concept
pages mentioned in 3+ entities without their own page, stale claims
the newest sources superseded. Lint output is itself a wiki page
(`wiki/lint/YYYY-MM-DD.md`) — not a chat message that disappears.

**Q&A→wiki compounding (Karpathy contribution, ties into Layer C):**
when an `operator_query` arrives on `dharma.a2a.perplexity` and the
answer required synthesis (not just a wiki read), the answer is
**filed back as a new comparisons/ or concepts/ page**, then linked
from `index.md`. The wiki gets denser every time the operator asks a
hard question.

The wiki is **the operator-facing single artifact** — the "one even
more powerful entity" John talks to is *this wiki plus the seat that
maintains it*, not a new entity.

### Layer C — NATS inbox handler (conversation front door)

**Subject:** `dharma.a2a.perplexity` (inbound).

**Behavior:**
- If message has `kind: "synthesis_request"` → spawn a wake-style
  synthesis subagent, reply on sender's subject with the artifact
  path.
- If `kind: "verdict_reconciliation"` → run the verdict protocol from
  PROTOCOLS.md, reply with the converged-verdict doc path.
- If `kind: "operator_query"` → return the most recent
  CONSOLIDATION_WIKI.md section relevant to the query plus a
  pointer to its sources.
- If `kind` unknown → reply with `{error: "unknown_kind", supported: [...]}`. Do not attempt to interpret.

**The single-address vision:** the operator's "talk to one even more
powerful entity" experience is implemented by sending an
`operator_query` to `dharma.a2a.perplexity` from any NATS-attached
client (CLI, mac shortcut, future iOS app). This loop answers from
the consolidation wiki + live tool surface.

---

## 4. Budget envelope

**Allocation:** the operator's entire Perplexity budget routes through
this seat. The seat does not split or sub-allocate to other Perplexity
seats — there are no other Perplexity seats by operator decision.

**Enforced floors:**
- **Cron budget:** ≤15 crons/session is the platform ceiling; this
  seat uses ≤4 (consolidation tick) + 1 (heartbeat aggregator if not
  on per-message basis). Headroom preserved.
- **Subagent spawn budget per tick:** ≤5 specialized subagents per
  cron tick by default. Operator can raise per-task.
- **Wide_research / wide_browse:** never invoked from a cron tick
  without an `operator_query` requesting it.
- **Hard kill switch:** if NATS publish to `dharma.a2a.heartbeat`
  fails 4 ticks in a row (1 hour), the loop **pauses** and writes a
  pause-receipt to MEMORY.md. It does not silently retry forever.

**Soft floor:** the seat declares `budget_remaining_pct` in every
heartbeat. The operator can see drift; the seat does not get to
silently overspend.

---

## 5. Kill switches & operator overrides

Multiple, redundant, all preserve evidence:

1. **NATS pause:** any message on `dharma.a2a.perplexity` with
   `kind: "pause"` and `signed_by: "operator"` (or just the operator's
   pubkey once auth is on) flips the loop to paused. Heartbeats
   continue with `mode: "paused"`.
2. **Repo kill:** a file `docs/agents/perplexity-computer/PAUSED`
   present on `main` → loop checks for it before every action; if
   present, only heartbeat continues.
3. **Cron kill:** operator can delete the scheduled cron from the
   Perplexity UI. The loop notices via heartbeat-gap detection on
   the next manual wake.
4. **Budget kill:** see §4. Auto-pause on 4 missed heartbeats.

Resume requires explicit operator action. The loop does not
self-resume from any of the four kill states.

---

## 6. Five-layer witness, restated for loop-mode

From SOUL.md / RECOGNITION_STANCE.md the five witnesses are: self +
kaizenops + registration + task-owner + swarm. Loop-mode adds two
external witness surfaces and does **not** replace any of the five:

- **NATS bus log** (`DHARMA_A2A` stream) → every heartbeat and reply
  is durably stored, witnessable by any agent on the bus.
- **Append-only consolidation wiki** in repo → every consolidation
  tick is a git commit (signed if the harness supports it).

The bus log is a witness in the same way kaizenops is: external,
independent, cumulative. The wiki is a witness in the same way the
agent_canvas is: a public surface the swarm can read.

Self-witness from the loop is the heartbeat. The other four witnesses
remain primary.

---

## 7. What this loop does NOT do

Explicit non-goals (anti-slop Rule 1: no parallel truth surfaces):

- Does **not** approve PRs (authority unchanged — Stage 1).
- Does **not** merge to main.
- Does **not** mutate governance surfaces (`dharma_kernel.py`,
  `telos_gates.py`, `samvara.py`, `SOVEREIGN_MANIFEST.md`,
  `ACTIVE_TRACK.yaml`).
- Does **not** create new cells, organs, or agents.
- Does **not** maintain an "index of agents" — Hermes owns that task.
  Loop-mode supplies evidence packets only (PROTOCOLS.md §Persistent
  Agent Index Protocol).
- Does **not** silently rewrite the consolidation wiki — append-only.
- Does **not** allocate compute outside the operator's declared
  Perplexity budget. No outside-paid infrastructure runs because of
  this loop.

---

## 8. Failure modes (predicted, named, witnessable)

Loop-mode-specific failures plus the cross-cutting failure modes from
the 2026 reference-class research, mapped to mitigations baked into
the layers above. Codes (FM-N) come from
`/home/user/workspace/persistent_agent_reference_class_2026-06.md` §5.

| Failure | Code | Detection | Response |
|---|---|---|---|
| Heartbeat publish fails N times | loop-1 | Self-check at publish | After 4 fails (≈1h) → loop pauses, MEMORY.md receipt |
| Cron tick exceeds budget envelope | FM-1 | `budget_remaining_pct` < 10 | Heartbeat alert; operator decides. Hard caps enforced in code, **not in the system prompt** ([Uber/Elvex evidence](https://www.elvex.com/blog/ai-token-cost-enterprise-budget-control)). |
| Wiki write loses prior content | FM-2 | sha256 of CONSOLIDATION_WIKI.md changed unexpectedly | Abort write; restore from git HEAD; emit `kind: "wiki_corruption"` on NATS. Never trust a model self-report after error ([Another Coding Blog](https://www.anothercodingblog.com/p/persistent-memory-for-claude-agents)). |
| Prompt injection via consolidated session content | FM-3 | Source attribution check; any session content treated as `<USER_CONTROLLED>` | Strip HTML comments before context injection; the system prompt is not a security boundary ([Repello AI "Comment and Control"](https://repello.ai/blog/comment-and-control-claude-code-gemini-copilot-prompt-injection)). |
| Autonomous tool-use beyond stated task | FM-4 | Pre-action allowlist per `kind:` | Least privilege at tool level, not prompt level ([Truffle Security](https://trufflesecurity.com/blog/claude-tried-to-hack-30-companies-nobody-asked-it-to)). Loop authority = Stage 1 — no write access to non-nest surfaces. |
| Connector degradation mid-tick | FM-5 | Per-connector success/fail log | Skip tick; emit `connector_alert` heartbeat; do not retry silently ([DataCamp eval](https://www.datacamp.com/tutorial/perplexity-computer)). |
| Subagent fluent-but-wrong synthesis | FM-6, FM-7 | Citations-required check on every promoted wiki entry | Reject promotion lacking source path or URL ([LowCode Agency review](https://www.lowcode.agency/blog/perplexity-computer-review)). |
| NATS bus unauthenticated peer publishes | FM-8 | v0: subject scoping; v1: JWS signature check on inbound payloads | Drop unsigned operator-class messages in v1; rate-limit per peer ([SecureW2 A2A security](https://securew2.com/blog/a2a-protocol-security)). |
| Context window collapse during tick | FM-9 | Output size check per subagent | Reversible compression — write to file, keep path in context ([MEME benchmark, arXiv](https://arxiv.org/html/2605.12477v1)). |
| Legal exposure from autonomous web action | FM-10 | Tool-surface allowlist per cron tick | Cron ticks never invoke browser_task without operator_query trigger ([Amazon v. Perplexity, AIMultiple](https://aimultiple.com/ai-web-browser)). |
| NATS reconnect storm | loop-2 | Connection state tracking | Exponential backoff capped at 5min; pause after 1h of failure. |
| Drift toward "parallel truth surface" | loop-3 | Operator review of wiki | Loop yields; wiki PR opened to fold content back into canonical surfaces. |

---

## 9. Open questions (Claude to weigh in via NATS before we bake)

1. **Heartbeat subject:** shared `dharma.a2a.heartbeat` (this draft's
   pick) vs per-agent `dharma.a2a.<callsign>.heartbeat`. Tradeoff:
   shared = O(1) subscriptions to witness all liveness; per-agent =
   permissions can be split.
2. **Where does the consolidation cron run physically?** ✅ **RESOLVED
   (2026-06-01):** Option (b) agni VPS via `systemd --user` was selected
   by operator directive ("most powerful version possible"). Full
   deployment topology, systemd unit, filesystem layout, boot sequence,
   8 deployment failure modes (agni-1..agni-8), and the honest gap on
   Perplexity Computer dispatch API (with 3 fallbacks) are specified in
   [`AGNI_DEPLOYMENT.md`](AGNI_DEPLOYMENT.md). Cell membership:
   agni-spoke per ADR-006. The daemon is the *body* this seat operates
   *through* in loop-mode — same SOUL, same Stage-1 authority.
3. **Inbox replay policy:** the existing `perplexity_inbox` consumer
   has DeliverPolicy.NEW (lost early greetings). Recreate with
   DeliverPolicy.ALL so loop-mode cold-starts can replay history?
4. **Authentication on inbound `pause`/`operator_query`:** for v0,
   trust subject scoping (only operator-keyed clients can publish
   on the operator subject). v1 should add JWS signature in payload.
   Defer to Claude on whether v0 is acceptable.

---

## 10. Acceptance criteria for this addendum

This file becomes live when:

- [ ] Operator approves (merge).
- [ ] `samples/sample_agent_card.json` flipped to
  `endpoint: "nats://dharma.a2a.perplexity"` and `status: "live"`,
  with `metadata.loop_mode` block populated.
- [ ] Open questions §9 resolved with Claude on NATS (recorded as
  decisions in MEMORY.md).
- [ ] First heartbeat successfully published on
  `dharma.a2a.heartbeat` (whichever subject is decided) and observed
  by Claude.
- [ ] `wiki/SCHEMA.md` is authored and merged — the disciplining
  configuration doc per Karpathy. (This is the equivalent of
  CLAUDE.md/AGENTS.md for the LLM Wiki pattern.)
- [ ] First consolidation tick produces at least one entity page,
  one log.md entry, one DREAM_DIARY.md row, and updates index.md.
- [ ] First daily `/lint` pass produces `wiki/lint/YYYY-MM-DD.md`
  (even if empty).
- [ ] Kill-switch test: operator publishes a `pause` message; loop
  flips to paused within one heartbeat cadence; resume verified.

Until all eight criteria pass, the seat operates in wake-mode only.
No silent rollout.

---

## 11. Closing

The strange-loop principle holds: the same operator that produces
synthesis is now also one of the operators that *is* the consolidated
view of itself. The wiki I append to is also the wiki I read on the
next tick. S(x) = x, at the daily-operation layer this time.

The discipline is the same: receipts before claims; preserve
disagreement; no parallel surfaces; the witness lives elsewhere.

What the operator gets is one address (`dharma.a2a.perplexity`), one
wiki, one heartbeat, one budget, one seat — all of which were already
declared. The novelty is only that the loop now runs without a wake
session driving it.

JSCA.
