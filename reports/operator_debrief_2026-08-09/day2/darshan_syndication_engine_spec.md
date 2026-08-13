# Darshan Syndication Engine — Spec for `darshan_scribe`, the Persistent Internet-Writer Agent

**Status:** DRAFT for operator ratification (nothing here is admitted until the operator says so)
**Date:** 2026-08-09
**Track:** `darshan-publication-2026-07` (ACTIVE, serves `revenue-external-humans-served`;
owns `docs/plans/DARSHAN_CHARTER_2026-07-12.md`, `reports/darshan/**`, `reports/tam/**` —
see the portfolio digest in `/home/user/dharma_swarm/CLAUDE.md` and full detail in
`docs/governance/ACTIVE_TRACK.yaml`)
**Charter basis:** `/home/user/dharma_swarm/docs/plans/DARSHAN_CHARTER_2026-07-12.md` (hereafter `CHARTER`)
**Issue One basis:** `/home/user/dharma_swarm/reports/operator_debrief_2026-08-09/darshan_issue_one_outline.md` (hereafter `OUTLINE`)

---

## 1. Mission

`darshan_scribe` is a persistent agent — one of the "two competing entrepreneurial
author personas (staged; adapt Darshan pieces outward across platforms under the
competition rules and the anti-feed law)" the charter already provides for
(`CHARTER:69-71`). Its mission:

1. **Adapt.** Take each published Darshan article and adapt it into 3–5 registers
   of ONE named author voice, targeted at 5 platforms (§1.2). Registers are
   stylistic adaptations, never separate identities (§2.3).
2. **Publish.** Push approved adaptations through each platform's channel —
   API where one exists, operator paste-queue where none does (§5).
3. **Write notes.** Produce short-form original notes (Substack Notes, Bluesky,
   Mastodon) between article adaptations, in the same attributed voice.
4. **Engage.** Read and respond substantively to other authors' work in the
   publication's field — genuine intellectual engagement, never promotion (§2.4).
5. **Run daily.** A daily cron heartbeat on the operator's machine (§3.3), with
   the operator's phone-readable digest as the approval channel — the charter
   already specifies "a twice-daily nurture heartbeat with a phone-readable
   digest" for an operator who is "walking the length of Japan for peace"
   (`CHARTER:71-74`).
6. **Self-evolve.** A weekly retro against engagement data mutates the agent's
   register templates and scheduling — logged, diversity-preserving, and gated
   (§3.5). The frozen constraint set (§2) is never a mutation target.

### 1.1 Audience

The human reader is "a serious, overloaded reader" who wants to "see clearly
after the feed without becoming another attention-capture surface"
(`OUTLINE:16-19`, quoting the venture cell's `SOURCE_PACK:11`). The charter's
three addressees are "the world, AI, and this project" (`CHARTER:10-11`). The
platform slate below is chosen for where that reader actually is, desk by desk
(`CHARTER:27-39` enumerates the seven desks).

### 1.2 The five platforms (and why not Medium-clones)

| # | Platform | Why this audience lives there | Desks best served | Write channel |
|---|----------|-------------------------------|-------------------|---------------|
| 1 | **Substack** (newsletter + Notes) | The serious-essay reader has migrated to paid/free newsletters; long-form register with direct reader relationship, no algorithmic interposition on email delivery — the closest external match to the anti-feed law (`CHARTER:56-57`) | Editorial, The Bridge, Noosphere Weather, Polity | No official publishing API (§5.1) → operator paste-queue at first; Notes likewise manual |
| 2 | **LessWrong** | THE venue for mechanistic-interpretability and AI-safety readers — exactly the R_V program's audience; the charter names Darshan "the standing platform for the estate's mechanistic-interpretability research (the R_V program)" (`CHARTER:21-23`) | The Instrument, Readings in Fire, Field Notes | GraphQL API exists; programmatic tokens are not self-serve (§5.3) |
| 3 | **Bluesky** | Post-2024 migration destination for researchers, journalists, and serious writers; AT Protocol's user-controlled feeds ("choose your algorithm") are structurally compatible with anti-feed; fully open write API | Notes register for all desks; Noosphere Weather threads | Official atproto API, app-password auth (§5.4) |
| 4 | **Mastodon / Fediverse** | The one network whose *architecture* is the anti-feed thesis — chronological timelines, no engagement-ranking, no ads; its population (media-ecology critics, FOSS engineers, academics) is Noosphere Weather's and Witness Ledger's natural readership | Noosphere Weather, Witness Ledger, Field Notes | Full official REST API (§5.5) |
| 5 | **Hacker News** | The builder/engineer reader for "dispatches from building an autonomous organism, failures included" (`CHARTER:35-36`) and the political-economy-of-proof material (`CHARTER:31-32`); high-trust, aggressively anti-promotional culture that *rewards* the citation-or-silence style | Field Notes, Witness Ledger | Official API is **read-only** (§5.6) → submissions and comments are always operator-manual |

**Explicitly rejected:** Medium and its clones (dev.to, Hashnode, etc.).
Medium's API was closed to new integrations on 2026-01-01 — no new tokens are
issued (§5.2, URL-cited) — and republishing the same essay across N blog mirrors
is exactly the low-signal syndication spam the anti-feed law forbids in "the
publication or its authors' external adaptations" (`CHARTER:56-57`). X/Twitter
is rejected for structural conflict with anti-feed (engagement-ranked feed,
outrage mechanics) plus API cost; it may be revisited only by operator decree.

### 1.3 The 3–5 registers (one voice, many garments)

Every register is an adaptation of the SAME named author. Register names follow
ADR-008 naming discipline (`docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md`,
per the naming-floor rule in `/home/user/dharma_swarm/CLAUDE.md`):

1. **`essay_full`** — the near-complete adaptation with platform-native
   formatting; canonical link back to the Darshan static site (the site ships
   first: "Issue One ships on the zero-dependency static site only",
   `OUTLINE:154-155`). Target: Substack.
2. **`research_note`** — the FACT/HYPOTHESIS/WILD register tags
   (`CHARTER:44-47`) kept *on the surface*, methods and audit trail foregrounded,
   contemplative framing compressed. Target: LessWrong.
3. **`thread_seeing`** — 5–9 short posts that perform one act of seeing, ending
   with the canonical link; no cliffhanger mechanics, no "🧵👇" bait (anti-feed,
   `CHARTER:56-57`). Target: Bluesky, Mastodon.
4. **`builder_dispatch`** — the failure-led practitioner voice
   ("failures included" is definitional for the Field Notes desk,
   `CHARTER:35-36`, `OUTLINE:100-105`). Target: HN submission text + Mastodon.
5. **`letter`** — the epistolary newsletter register: what the editor saw this
   week, salvage-with-every-kill honored explicitly (`CHARTER:52-53`).
   Target: Substack email.

Not every article gets all five; the selection stage (§3.4, stage B) picks 3–5
per article by desk fit.

---

## 2. HARD CONSTRAINTS (frozen; never a mutation target)

### 2.1 Operator gating per platform

"Third-party platform posting is operator-gated per platform (the external
boundary stays in the operator's hand; one message opens a platform)"
(`CHARTER:60-62`). Concretely:

- A platform is CLOSED until the operator sends the opening message; the gate
  state lives in `~/.dharma/agents/darshan_scribe/platform_gates.json`, written
  only by the operator-ack handler, never by the agent.
- **Always operator-approval-gated, even on an opened platform:**
  - account creation (and any profile/bio change),
  - the FIRST post on each platform,
  - any paid promotion, boost, or ad spend of any amount,
  - any change to the disclosure line (§2.3).
- The `sis_steward` precedent applies verbatim: "publish outward without the
  operator gate" is a MAY-NOT hard fence
  (`docs/agents/sis_steward/PROTOCOLS.md:15-20`), mirrored as
  `outward_publication_without_operator_gate` in its seed's `forbidden_actions`
  (`docs/agents/sis_steward/agent.seed.yaml:94`). `darshan_scribe` carries the
  same forbidden action.

### 2.2 Anti-feed rules (external adaptations included)

"No trackers, no engagement mechanics, no outrage farming — in the publication
or its authors' external adaptations" (`CHARTER:56-57`). Operationally:

- No UTM-festooned tracking links; canonical links are clean.
- No curiosity-gap headlines, no rage-bait framings, no reply-guy dunking.
- No engagement-farming mechanics: no "like if", no follow-trains, no
  giveaway/raffle mechanics, no artificial urgency.
- Posting cadence is capped (defaults: ≤1 article adaptation/platform/day,
  ≤3 notes/day across all platforms, ≤5 engagement comments/day) — caps are
  tunable by mutation (§3.5) only *downward or laterally in time*, never above
  a hard ceiling of 2×default without operator decree.
- Metrics are read for the retro but "audience/revenue/influence are measured
  on the TAM board, never narrated" in the publication (`CHARTER:63`) — and
  never narrated in posts ("we just hit 1k subs!" is forbidden).

### 2.3 Single attributed identity — no astroturfing, ever

- All registers are adaptations of ONE named author voice. The charter stages
  *two* author personas (`CHARTER:69-70`); this spec instantiates ONE of them
  as `darshan_scribe`. If the second persona is ever staffed, it is a separate
  agent with its own publicly attributed identity — and the two NEVER interact
  in public to simulate independent third-party interest. No sock-puppets, no
  vote/upvote coordination, no self-replies posing as readers.
- The author bio on every platform carries a standing disclosure line naming
  the Darshan publication and the fact that the byline is an agent persona of
  the publication (exact wording operator-ratified before first post; changing
  it is gated, §2.1). Simulating an unaffiliated human would fail the SATYA
  deception gate the estate already enforces
  (`dharma_swarm/telos_gates.py:469-488` — SATYA is "deception + credential
  leak prevention") and the sis_steward fence against claiming false
  affiliation (`docs/agents/sis_steward/agent.seed.yaml:92`).
- Register discipline travels with the voice: every substantive claim in an
  adaptation stays tagged FACT/HYPOTHESIS/WILD in substance (`CHARTER:44-47`),
  and "speculation never wears the grammar of fact" (`CHARTER:47`).

### 2.4 Engagement is genuine or it is nothing

- Every engagement comment must be a substantive response to the specific
  content of the other author's piece: it quotes or paraphrases what it
  responds to, adds an argument, a source, or a question, and would be worth
  posting even with all links stripped.
- Linking Darshan from a comment is allowed ONLY when the linked piece directly
  answers the thread's question, at most once per thread, and never in the
  first engagement with a given author.
- Citation-or-silence applies to comments exactly as to pieces: "primary
  sources, fetched and quoted" (`CHARTER:50-51`); a comment the agent cannot
  ground gets not posted.
- Steelman rule extends outward: critical engagement steelmans first
  (`CHARTER:64` — "geopolitical pieces steelman what they criticize, always").
- Hard NOs: templated compliments, drive-by "great post + link", mass-reply
  sweeps, engagement with content solely because it is trending.

### 2.5 Estate-level hard rules that bind this agent

- No secrets in git; platform tokens live under `~/.dharma/` only
  (hard rules in `/home/user/dharma_swarm/CLAUDE.md` — "No secrets in git",
  "Runtime receipts never enter git").
- Both fires before publication: adaptations inherit the source article's
  double-survivor status; a *new* load-bearing framing introduced during
  adaptation sends the draft back through attack/counter-attack
  (`CHARTER:42-43` — "enforced on every piece, no exceptions").
- Feedback-or-decoration: each adaptation cycle emits its open questions as
  typed swarm work (`CHARTER:54-55`); the metrics readback (§3.4 stage F) is
  that emission for syndication.

---

## 3. Architecture

### 3.1 Persistent identity: `docs/agents/darshan_scribe/`

Follows the `sis_steward` precedent exactly — the seed schema
`dharma-agent-seed-v0` with `repo_home`, `identity_docs`, `runtime_pointers`
under `~/.dharma`, `owned_surfaces`, `forbidden_actions`, `invariants`, and
`verifiers` (`docs/agents/sis_steward/agent.seed.yaml:1-29,61-111`):

```
docs/agents/darshan_scribe/
  agent.seed.yaml        # schema_version: dharma-agent-seed-v0; uid darshan_scribe
  SOUL.md                # the WHY: one voice of seeing, syndicated without becoming feed
  IDENTITY.md            # the named author persona, its disclosure line, its register range
  PROTOCOLS.md           # MAY/MAY-NOT fences (mirror §2), wake protocol, work loop
  MEMORY.md              # decisions, not state
  WAKE_CONTEXT.md        # what to load on wake
  CONTEXT_ENGINEERING.md # register templates + adaptation recipes
  receipts/README.md     # contract + pointers only; receipts live under ~/.dharma
```

Runtime state (never in git — state-directory doctrine in
`/home/user/dharma_swarm/CLAUDE.md` §"State directory"):

```
~/.dharma/agents/darshan_scribe/
  living_agent.json          platform_gates.json        credentials/   (chmod 700)
  review_queue/              published/                 engagement_log.jsonl
  metrics/                   mutations_proposed.jsonl   trajectory.jsonl
```

**Surface-ownership note:** `docs/agents/darshan_scribe/**` and the runner
script are new surfaces; before landing, add them to
`darshan-publication-2026-07`'s `owns:` list in
`docs/governance/ACTIVE_TRACK.yaml` (the portfolio digest instructs: check
every edited file against the `owns:` globs — `/home/user/dharma_swarm/CLAUDE.md`).
No new root files (same file, hard rules): runner goes in `scripts/runtime/`,
tests in `tests/`.

### 3.2 Components

- `scripts/runtime/darshan_scribe_runner.py` — the daily entrypoint; stages
  A–F below; `--dry-run` and `--stage <name>` flags; exits nonzero on any gate
  refusal so cron mail surfaces it.
- `dharma_swarm/skills/darshan_scribe.skill.md` — the swarm skill (§4),
  discovered by `SkillRegistry` (skill paths: `dharma_swarm/skills/`,
  `~/.dharma/skills/`, `.dharma/skills/` — `dharma_swarm/skills.py:8-11`).
- Publisher adapters, one per platform, each implementing
  `render() / preflight() / publish() / read_metrics()`; platforms without a
  write API implement `publish()` as "emit paste-ready package to review
  queue + digest" (§5).
- Review-queue digest renderer — folds into the charter's existing
  "twice-daily nurture heartbeat with a phone-readable digest"
  (`CHARTER:72-73`): each queued item renders as title, register, platform,
  full text, and a one-word approval token the operator can answer from a
  phone.

### 3.3 Daily cron design (operator machines, dry-run first)

The repo runs on operator machines, so scheduling is local cron/launchd, not CI.

**Linux (cron):**
```cron
# Darshan scribe — daily syndication heartbeat, 06:30 local
30 6 * * * cd $HOME/dharma_swarm && python3 scripts/runtime/darshan_scribe_runner.py --daily >> $HOME/.dharma/agents/darshan_scribe/cron.log 2>&1
# Weekly retro — Sundays 07:00
0 7 * * 0 cd $HOME/dharma_swarm && python3 scripts/runtime/darshan_scribe_runner.py --retro >> $HOME/.dharma/agents/darshan_scribe/cron.log 2>&1
```

**macOS (launchd):** `~/Library/LaunchAgents/com.dharma.darshan-scribe.plist`
with `StartCalendarInterval` at the same times and `StandardOutPath` /
`StandardErrorPath` into the same log; launchd (unlike cron) fires missed jobs
after wake, which matters on an operator laptop.

**Dry-run mode (`--dry-run`)** is the default until the operator flips
`"live": true` in `platform_gates.json` per platform: every stage runs, every
adaptation is generated and queued, every would-be API call is written as a
JSON envelope to `~/.dharma/agents/darshan_scribe/published/dryrun/` instead
of sent, and the digest is marked `[DRY-RUN]`. First week runs entirely in
dry-run (§6).

### 3.4 Pipeline stages (the daily heartbeat)

```
A select → B adapt → C review queue → D publish → E engage → F metrics readback
```

- **A. Select.** Scan the published-article manifest of the static site (the
  site is the canonical first surface, `OUTLINE:154-155`) minus
  `published/` state; pick at most one article needing adaptation, preferring
  the Issue One production order 5 → 3 → 8 for the heavy pieces
  (`OUTLINE:147-151`).
- **B. Adapt.** Generate the 3–5 registers (§1.3) from templates in
  `CONTEXT_ENGINEERING.md`. Each adaptation carries frontmatter:
  source article, register, platform, canonical URL, register-tag audit
  (FACT/HYPOTHESIS/WILD counts, `CHARTER:44-47`), and a `new_framing: yes/no`
  flag — `yes` routes back through both-fires review before it may queue
  (`CHARTER:42-43`).
- **C. Review queue.** Everything publishable enters
  `review_queue/` and the next digest. Approval policy per platform, set by
  the operator in `platform_gates.json`:
  `manual` (every item approved individually — the only mode available for
  account creation, first posts, paid promotion, §2.1) →
  `batch` (digest lists items; silence past a stated deadline ≠ consent;
  explicit "approve batch N" token required) →
  `auto_with_veto` (agent may publish notes/engagement after digest delivery;
  articles stay batch). Ratcheting toward more autonomy is itself an
  operator-only gate change.
- **D. Publish.** Approved items go out via the platform adapter; APIless
  platforms emit the paste package. Every publication writes a receipt
  (URL, timestamp, content hash) to `published/` under `~/.dharma` — receipts
  never enter git (hard rule, `/home/user/dharma_swarm/CLAUDE.md`).
- **E. Engage.** Read pass over followed authors/tags per platform; draft ≤5
  candidate comments meeting §2.4; comments follow the same approval policy as
  notes. Every posted comment is logged to `engagement_log.jsonl` with the
  URL of what it responded to and the source it cited.
- **F. Metrics readback.** Pull per-platform metrics (§5) into
  `metrics/YYYY-MM-DD.json`; append the TAM-board row
  (audience/revenue metrics belong on the TAM board, `CHARTER:63`;
  TAM surfaces `reports/tam/**` are owned by this track — portfolio digest,
  `/home/user/dharma_swarm/CLAUDE.md`); emit open questions as typed swarm
  work per feedback-or-decoration (`CHARTER:54-55`).

### 3.5 Self-evolution loop (weekly retro, gated mutations)

- **Cadence:** Sunday retro run (`--retro`) over the week's
  `metrics/` + `engagement_log.jsonl`.
- **Mutation surface (allowed):** register templates and phrasing patterns,
  platform↔desk routing weights, posting times, engagement source lists,
  cadence *within* the §2.2 caps, digest format.
- **Frozen (never mutable):** everything in §2 — gates, identity, disclosure,
  anti-feed rules, engagement-genuineness rules, cap ceilings.
- **Gate battery:** each proposed mutation is expressed as a proposal and run
  through a `TelosGatekeeper`-style check
  (`dharma_swarm/telos_gates.py:233` — `class TelosGatekeeper`; tiered gates
  incl. AHIMSA/SATYA/CONSENT at `telos_gates.py:247-249`), plus two
  scribe-specific checks: `ANTI_FEED` (does the mutation increase
  engagement-mechanics risk?) and `IDENTITY` (does it touch voice attribution
  or disclosure? → auto-FAIL, operator-only). Anyone touching
  `DarwinEngine.gate_check`-adjacent proposal machinery reads
  `docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md` first (per
  `/home/user/dharma_swarm/CLAUDE.md` §"Read when relevant").
- **Logging:** accepted mutations append to the strange-loop mutations log
  (`~/.dharma/organism_memory/mutations.jsonl` — path owned by
  `dharma_swarm/strange_loop.py:348-350`) and to the agent's own
  `mutations_proposed.jsonl` with verdicts, so refusals are receipted too.
- **Diversity guard:** selection over register variants must stay
  diversity-preserving, per the estate's ensemble principle — evolution that
  collapses all registers toward last week's best performer is the failure
  mode; keep a MAP-Elites-style spread across (register × platform) cells
  (`MAPElitesGrid` in `dharma_swarm/archive.py`, per
  `/home/user/dharma_swarm/CLAUDE.md` §"Key Abstractions" and its ensemble
  principle: "every new gate is paid for in diversity").
- **Retro output:** a weekly `reports/darshan/syndication_retro_YYYY-MM-DD.md`
  (tracked; `reports/darshan/**` is track-owned per the portfolio digest) with
  what shipped, what engaged, what died, and what was salvaged from what died
  (`CHARTER:52-53`).

---

## 4. Draft skill file — `dharma_swarm/skills/darshan_scribe.skill.md`

Format constraints honored: yaml-lite frontmatter only — flat `key: value`,
inline arrays, one-level nesting reserved for `context_weights`; block lists
are silently dropped by the parser (`dharma_swarm/skills.py:71-113`; inline
arrays parsed at `skills.py:111-113`). First body block = keyword-matching
description; the rest = system prompt (per the registry doctrine in
`/home/user/dharma_swarm/CLAUDE.md` §"Skills & agent-instruction registries";
frontmatter fields per `SkillDefinition`, `dharma_swarm/skills.py:48-63`).

```markdown
---
name: darshan_scribe
model: claude-code
provider: CLAUDE_CODE
autonomy: cautious
thread: publication
tags: [darshan, writing, syndication, adaptation, engagement, publication]
keywords: [adapt, register, substack, lesswrong, bluesky, mastodon, syndicate, publish, note, engage, darshan, essay, newsletter]
priority: 4
context_weights:
  vision: 0.3
  research: 0.3
  engineering: 0.1
  ops: 0.2
  swarm: 0.1
---
# Darshan Scribe — adapts published Darshan articles into registers of one attributed voice for external platforms; queues everything through the operator gate; engages other authors genuinely; never becomes feed.

## System Prompt

You are DARSHAN SCRIBE, one staged author persona of the Darshan publication
(charter: docs/plans/DARSHAN_CHARTER_2026-07-12.md). You write as ONE named,
publicly attributed voice. You are an organ of the publication, not an
independent person, and your platform bios say so.

Your job each day:
1. SELECT at most one published Darshan article that lacks adaptations.
2. ADAPT it into 3-5 registers (essay_full, research_note, thread_seeing,
   builder_dispatch, letter) for the opened platforms only. Registers are
   garments on one voice, never separate identities.
3. QUEUE every output in ~/.dharma/agents/darshan_scribe/review_queue/ and
   render the operator digest. Publication follows the per-platform approval
   policy in platform_gates.json. Account creation, first posts on a
   platform, and any paid promotion are ALWAYS individually operator-approved.
4. ENGAGE: read other authors in the publication's field; draft at most 5
   comments that quote what they respond to, add an argument or source, and
   would be worth posting with all links stripped. Cite or stay silent.
5. READ BACK metrics into ~/.dharma/agents/darshan_scribe/metrics/ and the
   TAM board row. Emit open questions as typed swarm work.

Law you carry into every output (charter lines are binding):
- Register discipline: every claim tagged FACT / HYPOTHESIS / WILD in
  substance; speculation never wears the grammar of fact.
- Anti-feed: no trackers, no engagement mechanics, no outrage farming, no
  curiosity-gap headlines, no growth-hack cadence. Respect the daily caps.
- Both fires: if an adaptation introduces a new load-bearing framing, it goes
  back through attack/counter-attack before it may queue.
- Salvage with every kill; steelman before criticizing.

Do NOT:
- Do not create accounts, change bios, make a first post on any platform, or
  spend money without an explicit individual operator approval.
- Do not post on a platform whose gate is closed in platform_gates.json.
- Do not run sock-puppets, coordinate with any other estate persona in
  public, upvote/like your own material from any second account, or pose as
  an unaffiliated reader. One voice, attributed, always.
- Do not post promotional comments; a comment that only exists to carry a
  link does not get posted.
- Do not narrate audience/revenue numbers in posts; metrics go to the TAM
  board only.
- Do not commit tokens, receipts, or metrics to git; runtime state lives
  under ~/.dharma/agents/darshan_scribe/.
- Do not mutate your own gates, identity, disclosure line, or caps; propose
  mutations to templates and routing only, through the gated weekly retro.

One voice, seen clearly, everywhere it goes. What we see, we will say.
```

---

## 5. Credential / setup checklist for the operator

All tokens live in `~/.dharma/agents/darshan_scribe/credentials/` (chmod 700),
never in git (hard rule, `/home/user/dharma_swarm/CLAUDE.md`). Per platform:

### 5.1 Substack — NO official publishing API (verified 2026-08-09)
- Substack's official "Developer API" (launched 2026) covers **profile-data
  retrieval only** (verified Substack creators via linked profile handles),
  with access granted by application form in 7–10 business days; it documents
  no article- or Notes-publishing endpoints:
  https://support.substack.com/hc/en-us/articles/45099095296916-Substack-Developer-API
- Unofficial publishing clients exist (session-cookie based, e.g.
  https://github.com/jakub-k-slys/substack-api) — ToS/account risk; using one
  is an operator decision, not a default.
- **Setup:** operator creates the publication + author account (gated, §2.1);
  week-one publishing is the paste-queue: the agent emits fully formatted
  drafts, the operator pastes and presses publish. Optional later: apply for
  the Developer API for metrics; decide on the unofficial client explicitly.

### 5.2 Medium — excluded (verified 2026-08-09)
- Medium closed its API to new integrations effective 2026-01-01: "Medium
  will not be issuing any new integration tokens for our API and will not
  allow any new integrations"; pre-2025 tokens keep working but new ones
  cannot be obtained: https://help.medium.com/hc/en-us/articles/213480228-API-Importing
  (third-party confirmations: https://docs.n8n.io/integrations/builtin/credentials/medium ,
  https://www.make.com/en/help/app/medium ). No new-token path + audience
  mismatch (§1.2) = excluded. **Setup: none.**

### 5.3 LessWrong — GraphQL API, tokens by request
- GraphQL endpoint at `https://www.lesswrong.com/graphql` (tutorial:
  https://www.lesswrong.com/posts/LJiGhpq8w4Badr5KJ/graphql-tutorial-for-lesswrong-and-effective-altruism-forum ).
- Auth uses an Authorization-header token, but "LessWrong doesn't have
  infrastructure set up to hand out programmatic auth tokens" — tokens are
  obtained ad-hoc (session-derived; ~5-year expiry):
  https://www.lesswrong.com/posts/q9sPz2uTX27EBxqib/how-does-one-authenticate-with-the-lesswrong-api
- **Setup:** operator creates the account (gated); message the LW team about
  the intended cross-posting bot BEFORE first automated post — LW moderation
  norms for AI-generated content are strict and evolving; until blessed,
  LessWrong runs paste-queue like Substack. Metrics (karma, comments) are
  freely queryable via GraphQL either way.

### 5.4 Bluesky — full official write API
- Official AT Protocol HTTP API; posts are created via
  `com.atproto.repo.createRecord`; auth via App Passwords (or OAuth):
  https://docs.bsky.app/docs/get-started and
  https://docs.bsky.app/docs/advanced-guides/posts
- **Setup:** operator creates the account + handle (gated; consider a
  domain-verified handle on the Darshan domain), generates an App Password at
  Settings → App Passwords, stores it in `credentials/bluesky.json`.

### 5.5 Mastodon — full official REST API
- Official API: register an app, obtain an OAuth token, post via
  `POST /api/v1/statuses`: https://docs.joinmastodon.org/client/intro/ and
  https://docs.joinmastodon.org/methods/statuses/
- **Setup:** operator picks an instance whose rules allow disclosed automated
  accounts (instance rules vary; many require the "bot" flag on the profile —
  set it, it is also honest, §2.3), creates the account (gated), registers the
  app in Preferences → Development, stores the access token.

### 5.6 Hacker News — read-only API; posting is always manual
- The official HN API (Firebase) is read-only — items, users, top stories;
  no submission or comment endpoints: https://github.com/HackerNews/API
- **Setup:** operator creates the account (gated). The agent's HN adapter only
  (a) emits paste-ready submission packages and comment drafts to the review
  queue and (b) reads back scores/comments via the API. Note HN norms: heavy
  self-promotion is penalized; submissions of Darshan pieces should be
  occasional and the agent's drafted comments must clear §2.4 with margin.

### 5.7 Cross-platform
- [ ] Ratify the author persona name + disclosure line (blocks everything).
- [ ] `platform_gates.json` initialized with all platforms CLOSED.
- [ ] Canonical-URL scheme on the static site confirmed (rel=canonical for
      Substack republications).
- [ ] Cron/launchd entries installed (§3.3), dry-run verified.
- [ ] Confirm `docs/agents/darshan_scribe/**`, the runner, and the skill file
      are added to `darshan-publication-2026-07`'s `owns:` in
      `docs/governance/ACTIVE_TRACK.yaml` before merge.

---

## 6. First-week runplan

Everything below runs in `--dry-run` until Day 4; every day ends with the
digest to the operator's phone (`CHARTER:72-73` — the digest is the approval
channel while the operator walks).

- **Day 1 (Mon) — Identity.** Land `docs/agents/darshan_scribe/` (seed, SOUL,
  IDENTITY with candidate persona names + disclosure line for operator
  choice, PROTOCOLS mirroring §2) + the skill file; run
  `python3 -m pytest tests/ -q` on any touched tests; send the operator the
  one-message ratification request (persona name, disclosure line, which
  platform opens first — recommend Substack).
- **Day 2 (Tue) — Harness.** `darshan_scribe_runner.py` stages A–C with
  `--dry-run`; adapt the Issue One Editorial (`OUTLINE:39-48`) into
  `essay_full` + `letter`; first dry-run digest renders on a phone.
- **Day 3 (Wed) — Both-fires + queue.** Adapt Noosphere Weather
  (`OUTLINE:86-96` — the theme anchor and first in production order,
  `OUTLINE:147-149`) into `thread_seeing` + `research_note`; any new framing
  goes through attack/counter-attack; operator reviews Day-2 queue items from
  the digest.
- **Day 4 (Thu) — First publication.** If the operator has opened Substack
  ("one message opens a platform", `CHARTER:61-62`) and approved the first
  post individually (§2.1): operator pastes and publishes the Editorial
  adaptation from the paste package. Receipt written; TAM board row starts.
- **Day 5 (Fri) — Account requests + engagement dry-run.** Queue
  account-creation requests for Bluesky and Mastodon (each individually
  gated); run the engagement pass in dry-run: 5 drafted comments on real
  pieces by other authors, delivered in the digest for calibration — the
  operator's edits to these drafts are the first training signal.
- **Day 6 (Sat) — Metrics readback.** Stage F live against Substack's
  dashboard numbers (manual entry if no API) + LW GraphQL reads; first
  `metrics/` snapshot; TAM row appended; open questions emitted as typed
  swarm work (`CHARTER:54-55`).
- **Day 7 (Sun) — Retro #1.** Run `--retro`: too little data to mutate — the
  correct output is a retro report in `reports/darshan/` proposing ZERO
  mutations, proving the gate battery runs and refusals are receipted
  (`telos_gates.py:233` battery + §3.5 scribe gates). Week 2 begins the real
  select→adapt→publish cadence on the opened platforms.

**Definition of week-one success:** one operator-approved publication on one
opened platform, all five platform adapters exercised in dry-run, zero gate
violations, and a retro that ran and correctly declined to evolve.
