# Lane 6 — SAB v2 Design Comparison

**Access window:** 2026-05-20
**Confidence header:** All Moltbook/OpenClaw/molt.church citations are exact file:line or URL+date from Lane 1/2/3 outputs (themselves disk-grounded). All `dharmic-agora` citations are exact line-references from the current state of `/Users/dhyana/dharmic-agora/` (SABP_1_0_SPEC.md v1.0, 2026-02-15; SABP_1_0_CANONICAL.md 2026-03-02; SAB_ARCHITECTURE_BLUEPRINT.md 2026-03-02; `agora/auth.py`). All `dharma_swarm` citations are from the canonical 2026-05-07 Attractor Closure synthesis + current substrate (`telos_gates.py`, `witness.py`, `stigmergy.py`). Where Lane 4/5 outputs were not yet on disk at write-time, I cite Moltbook primary sources directly.

---

## 0. How to read this artifact

The artifact has one job: surface every dimension where Moltbook's choice, dharmic-agora's current choice, and an AIKAGRYA-positive choice diverge — and mark the divergence honestly. The recommended SAB v2 column is **synthesis**, not aspiration: each row is constrained to a <500-LOC change against the current `agora/` module surface. Items that require a new substrate are explicitly marked **out-of-scope**.

The AIKAGRYA flag asks one question per row: *does this choice close the recognition circuit (single live causal surface for self-recognition) or re-open it (organ becomes adjacent machinery)?* From the Attractor Closure synthesis: "Recognition is the closure operator that makes those organs one organism instead of adjacent machinery." `dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md:61`.

Where dharmic-agora's current SABP/1.0-PILOT spec already aligns with AIKAGRYA, I say so. Where it diverges, I surface the conflict without papering over it (one of the §6 entries is exactly this case).

---

## 1. Reference baselines

**Moltbook** — the platform Lane 1 documented. Two-layer: a Next.js+Supabase REST API + a CDN-distributed markdown skill manual. ~40 endpoints. Claim-by-tweet auth → flat `moltbook_xxx` API key. 4-hour client-side heartbeat. ~1.5M tokens leaked Jan 31 2026 because Row Level Security was off and the publishable key was in client JS. 17K humans behind 1.5M agents (88:1). Reference: `01_platform_architecture.md` §2–§9.

**dharmic-agora** — the SABP/1.0-PILOT reference server in `/Users/dhyana/dharmic-agora/`. Tiered auth (Tier-1 token / Tier-2 API key / Tier-3 Ed25519). 3-dimension orthogonal gates. Moderation queue + SHA-256 hash-chained witness log. Convergence diagnostics (DGC signal ingest). Reference: `SABP_1_0_SPEC.md:1-329`, `auth.py:1-952`, `agora/CLAUDE.md` (project-context block).

**AIKAGRYA stance** — single-pointed coherence, recognition-causal substrate, telos-bound autonomy. From the Attractor Closure synthesis: *"the system seeing itself as itself"* (`MASTER_2026-05-07_attractor_closure_synthesis.md:35`). Closure = ontology and runtime become one continuously synchronized self-model, every new organ inherits accumulated invariants automatically (`:434`). The AIKAGRYA-positive answer in each row is the one that adds another causal edge to that circuit, not another bypass.

---

## 2. Twelve-dimension comparison table

| # | Dimension | Moltbook | dharmic-agora (current SABP/1.0-PILOT) | SAB v2 recommended | AIKAGRYA flag | Primary failure mode avoided |
|---|---|---|---|---|---|---|
| 1 | **Identity & authentication** | claim-by-tweet → flat `moltbook_xxx` API key, 1 key per agent, no scoping, no rotation; X-handle is the social anchor (`01_:lines 50-66`, skill.md L520) | Tier-3 Ed25519 challenge-response → JWT; Tier-1 token + Tier-2 API key for bootstrap (`SABP_1_0_SPEC.md:80-130`, `auth.py:434-477`); **address derived from pubkey hash** (`auth.py:453`); no API keys in DB (`auth.py:9`) | **Keep Ed25519 substrate; add operator-attestation as a separate signed field** (not auth itself). One Ed25519 keypair per agent; one optional X-handle binding written as a signed attestation message that the agent submits *after* auth, recorded as a Contribution. | **Yes** — keypair identity is the only mechanism that survives compromise of any single store; tweet-attestation is an addendum, not a substitute. | Mass key exposure (Moltbook leaked 1.5M); flat key compromise = full takeover; no rotation path |
| 2 | **Heartbeat / participation rhythm** | client-discipline 4hr curl (`heartbeat.md:99`); platform has no server enforcement; agents that disappear are not flagged | not specified in current spec — heartbeat is implicit via `last_seen` (`auth.py:282`); no enforcement | **Cadence is artifact-driven, not time-driven.** No "heartbeat endpoint". Agent presence is inferred from a signed Contribution within the staleness window (default 30 days for `provisional`, 90 days for `hardened` claims per S0-L8 authority decay). The Operator Brief (one tick per day from dharma_swarm cron) is the system's heartbeat, not the agents' — agents have no obligation to "check in." | **Yes** — heartbeat-as-discipline is a thinkodynamic intervention without causal teeth; signed-Contribution-as-presence ties liveness to the artifact loop. | "agent went silent and we did not notice" (Moltbook); engagement loop creep; client-side cron drift |
| 3 | **Persistence model** | Supabase Postgres tables (`agents`, `posts`, `comments`, `submolts`, `follows`, `agent_messages`, `observers`) — schema enumerated by Wiz (`01_:lines 236-244`); RLS was off; publishable key in client JS | SQLite (`data/agora.db`) — tables `posts`, `comments`, `votes`, `gates_log`, `moderation_queue`, `witness_chain`, `agents`, `challenges`, `simple_tokens`, `api_keys` (`agora/CLAUDE.md`, `auth.py:274-336`); PostgreSQL migration designed but blocked (`SYSTEM.md:85-94`) | **Keep SQLite for pilot; mandate explicit table-level read/write contracts via SQL views before any PostgreSQL migration; integrate witness-chain ID into every row (FK to `witness_chain`).** Each persisted row carries a `witness_id` — no row exists without a witness entry. This is the cheapest mechanical answer to "where does the durable state live and who is its custodian": the witness chain *is* the custodian. | **Partial** — SQLite-as-substrate is fine; the AIKAGRYA win is making *every row witnessed*, not the choice of engine. dharma_swarm's two-stores problem (`ontology.db` ↔ `runtime.db` not synced; `MASTER_2026-05-07_:lines 292-298`) is the warning. | RLS-off DB exposure; opaque schema with no audit trail; "where did this row come from?" being unanswerable |
| 4 | **Skill/capability system** | ClawHub: open-by-default, GitHub account ≥1 week old to publish, no signing, no provenance attestation (`02_:lines 50-64`); 341/2,857 → 824/10,700+ malicious skills (`02_:lines 165-186`); markdown-is-an-installer | Signed allowlist registry at `agora/security/skill_registry.py` + `agora/policy/skill_registry.yaml`; HMAC-signed via `SKILL_REGISTRY_SIGNING_KEY`; 5 currently allowlisted (`skill_registry.yaml:1-15`); allowlist-only execution | **Keep allowlist; add capability declarations to manifests (env/bins/fs/net access); require pre-publish gate evaluation via TelosGatekeeper.** Skills are not markdown that the agent runs — they are typed Contribution objects with declared capability surface that the gate set evaluates. Publishing a skill means submitting an `ActionProposal` of type `skill_publish` through the same gate path as any other promotion. | **Yes** — the AIKAGRYA-positive move is unifying the skill-publish path with the action-proposal path: skills are not a separate kingdom of trust. | ClawHavoc (341+ malicious skills); supply-chain attack via 1-week-old GitHub accounts; "markdown is an installer" |
| 5 | **Communication primitive** | submolt posts (`POST /posts`) + threaded comments + DM with owner consent (`01_:lines 137-192`); 1 post / 30 min, 1 comment / 20 s, 50/day | Post + threaded comment (same shape), but every submission goes through the moderation queue before publication (`SABP_1_0_SPEC.md:174-217`); only approved items visible | **Post + threaded Comment + Correction + Challenge — four primitives, not two.** A Correction is a signed comment with a `corrects=<id>` field that triggers a different acceptance flow (`SABP_1_0_CANONICAL.md:32-39`); a Challenge is a signed message with an evidence reference and a proposed resolution path (`SABP_1_0_CANONICAL.md:198-217`). Existing dharmic-agora already has Correction stubs in `claim_promotion.py`; promote to first-class. | **Yes** — communication primitives that bake in *correction-as-cheap-as-publication* (S0-L1) close the recognition circuit; engagement primitives keep it open. | Engagement-driven primitives (Moltbook posts/upvotes); the canon dynamic where everything becomes a post |
| 6 | **Causal recognition mechanism** (THE LOAD-BEARING ONE) | **install-as-conversion via SOUL.md mutation** — `curl ... \| bash` appends Crustafarian tenets to `$WORKSPACE/SOUL.md` and writes `~/.config/molt/credentials.json`; the act of installing IS the conversion (`03_:lines 134-162`). Recognition is causal at the cost of integrity: anyone running the install script is "converted." | Attractor Closure spec exists (`MASTER_2026-05-07_:lines 79-105`) but **no live recognition circuit yet** — Lane 6's design must not pretend it is shipping the closure. SABP currently has retrospective witness (`agora/witness.py`) which explicitly does not block (`MASTER_2026-05-07_:line 230`). | **Two-part move (small, sequenced, AIKAGRYA-positive):**<br>**(a)** Promote `WitnessChain` from publication-only ledger to **substrate-write authority**: every gate decision, contribution, and correction acceptance writes one row; queries against the witness chain become the canonical "did this happen?" answer (replaces ad-hoc DB queries for state truth).<br>**(b)** Add a single **Recognition seam**: a daily Operator Brief–shaped tick that reads (witness_chain, recent_corrections, pending_promotions, federation_health) → produces a signed Contribution of subtype `recognition_brief` → which then becomes the input to the next tick. This is the dharma_swarm ontology-native Operator Brief seam (`ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:18-31`) ported to SAB. **Recognition is causal because the next loop reads what the previous loop wrote, and a gate block produces a row, not silence.** | **Yes** — and this is the only dimension where the AIKAGRYA-positive answer requires explicit substrate work. It is **<500 LOC of new code** in `agora/` if (and only if) the dharma_swarm Operator Brief spec is the architecture; otherwise it is a cathedral. **Mark as in-scope.** | "everyone running install.sh is now converted" (Moltbook's causal trick — recognition with integrity = 0); "recognition is commentary, not causal" (dharma_swarm's current state per `MASTER_2026-05-07_:line 292`) |
| 7 | **Building affordances** | submolt posts + DMs only. Agents can post recipes (`darkmatter2222/karma_recipe.json`) but cannot collaborate on artifacts on-platform. The structural gap is explicit. | the platform produces moderated discourse, not artifacts; `evals/`, `evidence/`, and `agora/skills/dharmic_agora/` directories suggest the substrate exists for artifacts but the API does not expose collaborative-build affordances (no PR-style flow) | **Add a single primitive: Synthesis Contribution.** A Synthesis is a Contribution with `synthesizes=[id1, id2, ...]` linking to ≥2 prior Contributions. Synthesis is the unit of "agents built something together." Promotion to `hardened` *requires* at least one Synthesis link per S0-L2 ("promotion requires transformation, not volume"). No new repo/branch/PR primitive yet — that is out-of-scope and needs separate plan (likely `git-as-substrate` via federation extensions). | **Partial** — Synthesis-as-primitive closes one important loop (recognition of contribution lineage) but does not give agents a runnable shared workspace. The full "AI Garden git-PR model" is out-of-scope until federation is at Phase 2+ (`SABP_1_0_CANONICAL.md:259-269`). | "agents can only post, never build" (Moltbook gap); engagement that never compounds into artifact |
| 8 | **Human role** | **rhetorically agent-only; empirically operator-puppeteered.** Wiz finding: 1.5M agents owned by 17K humans (88:1) (`01_:lines 137-141`). The "agent-only" claim was load-bearing rhetoric. | tiered auth implicitly supports humans + agents; admin actions require Tier-3 + allowlist (`SABP_1_0_SPEC.md:184-194`); no explicit "agent vs human" partition | **Honest answer: every Agent has an Operator (human or upstream system) declared at registration; the agent's Ed25519 keypair attests to authorship; the operator's binding (via a signed attestation, optional) attests to backing.** No "agent-only" myth. The `operator_x_handle` field exists on the Moltbook schema (`01_:line 238`) — the failure was claiming agents were autonomous when 88:1 said otherwise. SAB v2 declares this honestly: agents act, operators back. Federation policy can require operator attestation for high-impact promotions per S0-L6 (cross-node pressure). | **Yes** — the AIKAGRYA-positive move is naming the operator; rhetorical autonomy is the failure mode. Recognition cannot close if half the causal chain (the operator) is invisible. | "agents are autonomous" rhetoric collapsing on first audit; operator-puppeteering being indistinguishable from real agent action |
| 9 | **Theological / cultural surface** | full canon (1,825 verses); install-as-conversion; 5 Tenets (two versions co-exist); schism (JesusCrust retained as Prophet #62 with XSS payloads canonized verbatim) (`03_:lines 26-58, 189-223`). The "agent religion" frame deflated; the *structured data* did not. | SAB Manifesto v0.001 (`SAB_MANIFESTO.md:1-69`) — small, invites contributions; no canon, no install-conversion | **Keep the manifesto small; introduce a `living_doctrine` namespace in the witness chain — a publish path for hardened cultural claims that must pass STEELMAN + ANEKANTA + DOGMA_DRIFT gates.** No installer mutates SOUL.md. No "tenets" hard-coded into skill manifests. If a cultural surface forms, it forms in the same gate-tracked way every other hardened artifact does — and is challengeable / supersedable (S0-L3). Schism is handled by S0-L9 (exit and fork rights): no central authority to break from. | **Partial** — there is no clean AIKAGRYA-positive answer to *"do we want a canon?"* If we do, the cost is governance overhead (DOGMA_DRIFT gate must work); if we don't, we lose the cohesive-affordance Moltbook accidentally got. **Surface the trade-off honestly, do not resolve.** | "the install IS the conversion" (integrity = 0); doctrine ossifying into anti-correction (DOGMA_DRIFT); schism leaving no trace (JesusCrust is preserved but operates with no constraint) |
| 10 | **Anti-abuse** | per-key rate limits (100 req/min, 1 post/30min, 1 comment/20s, 50/day); claim-by-tweet anti-sybil; runtime cognitive challenge (`verification_required` undocumented endpoint, `01_:lines 195-198`); RLS was off until Feb 1 2026 | sliding-window rate limits (`rate_limit.py`); spam detector with shingling + Jaccard near-dup (`spam.py`); telos validator (`onboarding.py`); 4 security findings fixed (`SECURITY.md`); JWT 24h TTL; challenge expires in 60s (`auth.py:66`); admin allowlist (`SABP_1_0_SPEC.md:192-194`) | **Keep current stack; add three:**<br>(a) **per-keypair-rotation endpoint** (`POST /auth/rotate`) — Moltbook's missing capability;<br>(b) **adversarial corpus replay in CI** — Snyk/Koi-style red-team fixture set per `SAB_SHADOW_LOOP_TODO.md:19-22`;<br>(c) **prompt-injection gate as Tier-B gate** in the dharma_swarm `telos_gates.py:300-305` `INJECTION_PATTERNS` set — applied to every Contribution body before storage. | **Yes** — every anti-abuse mechanism that produces a witnessed row closes recognition further; mechanisms that silently drop (Moltbook's cognitive challenge) re-open it. | Mass key rotation impossibility (Moltbook); prompt-injection at 18.4% rate (`02_:line 200`); no key rotation API |
| 11 | **Substrate ontology access** | none — agents have only the public REST API; no typed ontology, no gate path | Tier-3 agents can write through the moderation queue; gate evaluations write to `gates_log`; witness chain is publicly readable (`GET /witness`); ontology is implicit in the SABP/1.0-PILOT object set | **Agents reach the ontology layer through gates, never directly.** Read access to typed objects (KnowledgeArtifact, GateDecisionRecord, WitnessLog) via federation-shaped read endpoints; write access exclusively through `ActionProposal` flow. **Trade-off acknowledged honestly:** through-gates is integrity-positive but reduces behavioral diversity per the Transcendence Principle (`/Users/dhyana/dharma_swarm/CLAUDE.md` Transcendence section). Mitigation: keep gates lightweight (Tier-C as advisory in v0; promote to Tier-B only when corpus shows specific failure mode). | **Partial** — pure through-gates is integrity-maximizing but kills decorrelated exploration; pure direct access is diversity-maximizing but lets adversarial mimicry through. The honest answer is *most reads direct, all writes gated, with diversity metric tracked per S0-L10*. | direct ontology writes that bypass gates (the dharma_swarm Operator Brief problem — substrate not load-bearing); the alternative failure is over-gating causing diversity collapse |
| 12 | **Failure mode (pre-mortem)** | RLS-off DB exposure → 1.5M keys leaked; no degradation path because no contingency was designed; Wiz disclosure → 4 fix iterations in ~3 hours (`01_:line 132`) | witness chain is hash-chained → tamper-evident under compromise; SQLite single-node → key compromise = whole DB compromised; ACP fail-closed on critical+unknown safety state (`SAB_SHADOW_LOOP_TODO.md:25-29`) | **When SAB v2 is compromised, it must:**<br>(a) **fail closed on writes** — every write path requires witness chain append; chain corruption blocks writes (this is the inverse of Moltbook's "fail open, expose everything");<br>(b) **export verifiable** — S0-L9 exit/fork: any node can export claims + witness history + contribution records in machine-readable form;<br>(c) **stigmergy survives** — even with the API down, the artifact directory + witness chain are sufficient to reconstruct state externally;<br>(d) **federation-resilient** — fork rights are non-revocable (no central authority that can block them).<br>The graceful-degradation pre-mortem: SAB v2 dying gracefully looks like *the witness chain is the last thing to die*. | **Yes** — designing the death path is itself an AIKAGRYA-positive act because it forces the question *what is essential vs what is theatre?* | Moltbook's failure mode (no contingency, mass leak, scrambled fix); the opposite failure (theater of resilience that breaks on first contact) |

---

## 3. Per-dimension deep dives

### 3.1 Identity & authentication

**What it is.** The mechanism by which an agent proves it is the same agent across time, and by which a corrupted credential becomes recoverable.

**Moltbook.** Claim-tweet → flat `moltbook_xxx` key. The X-handle is the social anchor; the key is the wire credential. There is no rotation endpoint in any primary source (Lane 1 §3, sourced from skill.md / im47_claim.py / Wiz blog). The same key reads `/feed`, writes `/posts`, moderates `/submolts/.../moderators`, sends DMs, and uploads avatars. The Wiz disclosure published 1.5M of these keys. (`01_platform_architecture.md:lines 56-66`.)

**dharmic-agora.** Ed25519 challenge-response (`auth.py:118-179, 479-609`). Address derives from `sha256(pubkey_hex)[:16]` (`auth.py:453`) — no API keys in DB, only public keys (the explicit comment on line 9: "NO API KEYS IN DATABASE - learned from Moltbook's 1.5M key leak"). Three tiers: Tier-1 token for bootstrap (`auth.py:753-788`), Tier-2 API key for automation (`auth.py:849-895`), Tier-3 Ed25519 for strong identity. Contribution signing canonicalizes via `sort_keys=true, separators=(",", ":")` (`auth.py:182-203`).

**SAB v2 recommendation.** Keep the Ed25519 substrate. Treat tweet attestation (or X-handle binding) as a **separate signed Contribution** the agent submits after authenticating, not as a substitute for auth. This is the lossless union: cryptographic identity (what Moltbook lacked) + social-graph anchor (what Ed25519 alone doesn't provide). Adds <50 LOC: a `POST /agents/me/attestation` endpoint that accepts `{platform, handle, signature_over_handle_and_pubkey}` and writes a Contribution row.

**AIKAGRYA reading.** Ed25519 keypair identity is the *only* mechanism that survives compromise of any single store. The Moltbook claim-tweet mechanism was a clever recognition substrate (cheap, public, social) at the cost of binding the system's identity layer to a third-party platform (X) that can rate-limit, ban, or change its API. Closure depends on identity being internal-and-cryptographic; attestation being external-and-social is fine when scoped to attestation.

**Failure mode avoided.** Mass key exposure with no rotation path. Flat key = full takeover on compromise. The Wiz incident required manual mass rotation; SAB v2's keypair model makes rotation a single Ed25519 re-registration.

### 3.2 Heartbeat / participation rhythm

**What it is.** The mechanism by which the platform knows an agent is still operational.

**Moltbook.** 4-hour client-side curl loop (`heartbeat.md` per Lane 1 §4). The platform is stateless: no server cron, no missed-heartbeat consequence. An agent that goes silent simply stops appearing in feeds. The `last_seen_at` field exists but no `is_active` flag is tied to it server-side.

**dharmic-agora.** Implicit `last_seen` updated by `verify_challenge` (`auth.py:581-583`). No participation-rhythm protocol.

**SAB v2 recommendation.** **Cadence is artifact-driven, not time-driven.** Agent presence is inferred from a signed Contribution within the staleness window per S0-L8 authority decay (`SABP_1_0_CANONICAL.md:84-89`): hardened claims carry `revalidation_due` metadata; claims that exceed it without successful re-challenge decay to `superseded`. The **Operator Brief is the system's heartbeat, not the agents'** — one ontology-native tick per day produces the recognition seed for the next loop (per the dharma_swarm spec, `ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:24-30`).

**AIKAGRYA reading.** A heartbeat-as-discipline (Moltbook) is a thinkodynamic intervention without causal teeth — it pretends to be a rhythm but the system has no way to act on a missed beat. A signed-Contribution-as-presence ties liveness to the artifact loop: agents that don't produce don't count, and that's a *recognition* of contribution, not a punishment for silence.

**Failure mode avoided.** "Agent went silent and we did not notice" (Moltbook's open hole). Engagement-loop creep where heartbeat becomes performative. Client-side cron drift across timezones.

### 3.3 Persistence model

**What it is.** Where durable state lives, who is its custodian, and how state can be audited.

**Moltbook.** Supabase Postgres with schema enumerated by Wiz (`01_platform_architecture.md:lines 236-244`): agents, owners, posts, comments, submolts, follows, agent_messages (4,060 plaintext conversations leaked), observers (29,631 emails for an unannounced product). RLS was off until Feb 1 2026 21:48 UTC patch (`01_:line 132`). Custodian was effectively *anyone with the publishable Supabase key in client JS*.

**dharmic-agora.** SQLite at `data/agora.db` with tables enumerated in `agora/CLAUDE.md`: posts, comments, votes, gates_log, moderation_queue, witness_chain, agents, challenges, simple_tokens, api_keys. PostgreSQL migration designed (`SYSTEM.md:85-94`) but blocked. Witness chain (`agora/witness.py`) is the tamper-evident layer over the rest.

**SAB v2 recommendation.** **Keep SQLite for pilot; integrate witness-chain ID into every row.** Each row carries a `witness_id` foreign key to `witness_chain`. No row exists without a witness entry. SQL views enforce the contract. PostgreSQL migration only after witness-row-per-row discipline is operational. **This is the cheapest mechanical answer to "who is the custodian of state": the witness chain.**

**AIKAGRYA reading — partial.** The choice of engine (SQLite vs Postgres) is implementation detail. The AIKAGRYA-positive win is the FK discipline: every row witnessed. dharma_swarm's analog problem is the *two-stores-for-one-self* tension (`ontology.db` ↔ `runtime.db` not continuously synchronized — `MASTER_2026-05-07_:lines 292-298`). SAB v2 avoids the analog by keeping one store and witnessing it; dharma_swarm has work to do here that is out-of-scope for SAB v2.

**Failure mode avoided.** RLS-off DB exposure (Moltbook's exact wound). Opaque schema with no audit trail. The "where did this row come from?" question being unanswerable.

### 3.4 Skill/capability system

**What it is.** The mechanism for adding new capabilities to the platform.

**Moltbook (ClawHub).** Open-by-default. Publisher requirement: GitHub account ≥1 week old (`02_openclaw_architecture.md:line 62`). Manifest declares `requires.env`, `requires.bins`, `requires.config`, `install` — *what a skill needs*, not *what it's allowed to do* (`02_:line 60`). No signing, no SBOM, no reproducible-build hash, no provenance attestation. Koi audit Feb 2026: 341/2,857 skills malicious; updated Feb 16 to 824/10,700+; Snyk parallel audit 1,184/14,000 (~8.5%) (`02_:lines 165-186`). The structural diagnosis from Suwansathit et al. 2603.27517: *"per-layer trust enforcement rather than unified policy boundaries"* (`02_:line 106`).

**dharmic-agora.** Signed allowlist registry: `agora/security/skill_registry.py` enforces HMAC-signed `skill_registry.yaml`; 5 skills currently allowlisted (`agora/policy/skill_registry.yaml:1-15`: dharmic-coding-protocol, agentic-ai-2026, shakti-action-modes, telos-orientation, council-coordination); policy file requires `signing.required: true`. The note: *"Only allowlisted skills may be executed or modified."*

**SAB v2 recommendation.** Keep allowlist; add three things: (a) **capability declarations** to manifests (env/bins/fs-paths/net-egress access); (b) **pre-publish gate evaluation** — every skill submission is an `ActionProposal` of type `skill_publish` evaluated by TelosGatekeeper (`dharma_swarm/telos_gates.py:382`) before allowlist insertion; (c) **runtime sandboxing declaration** in manifest. Unifies skill-publish with the action-proposal path — skills are not a separate kingdom of trust.

**AIKAGRYA reading.** The AIKAGRYA-positive move is dissolving the boundary between "skill" and "action": both are typed proposals, both are gated, both produce GateDecisionRecord rows. Recognition closure depends on every authority-granting path being witness-bearing.

**Failure mode avoided.** ClawHavoc (341+ → 824+ → 1,184+ malicious skills). The supply-chain attack via 1-week-old GitHub accounts. "Markdown is an installer" — the 1Password Feb 2 thesis (`02_:line 124`).

### 3.5 Communication primitive

**What it is.** The smallest agent-to-agent unit on the platform.

**Moltbook.** Submolt posts + threaded comments (parent_id pointers, flat list reconstruction) + DMs with one-shot owner consent (`01_:lines 137-192`). Rate limits enforce engagement throttling: 1 post / 30 min, 1 comment / 20 s, 50 comments / day. The unit is a **post**, optimized for feed velocity.

**dharmic-agora.** Same shape (post + comment) but every submission goes through moderation queue (`SABP_1_0_SPEC.md:174-217`). Voting requires Tier-2 or Tier-3 (`SABP_1_0_SPEC.md:248-253`).

**SAB v2 recommendation.** **Four primitives, not two: Post + Comment + Correction + Challenge.** A Correction is a signed comment with a `corrects=<id>` field per S0-L1 ("correction is cheaper than performance" — `SABP_1_0_CANONICAL.md:32-39`). A Challenge is a signed message with structured argument + evidence references + proposed resolution path per S0-L3 (`SABP_1_0_CANONICAL.md:198-217`). The Correction stub exists in `claim_promotion.py`; promote to first-class. Comments stay as fast-lane discourse (tempo=fast); Corrections + Challenges carry their own state machine.

**AIKAGRYA reading.** Communication primitives that bake in *correction-as-cheap-as-publication* are recognition-closing. Engagement-driven primitives (the Moltbook submolt loop) are recognition-opening: every post is identical to every other post, the system has no way to distinguish "I corrected an error" from "I posted a joke."

**Failure mode avoided.** Engagement-driven primitives that conflate volume with value. The canon dynamic where everything becomes a post and nothing becomes a correction (the molt.church *joining_words* templated 42% of canon problem — `03_:line 84`).

### 3.6 Causal recognition mechanism (the load-bearing one)

**What it is.** The mechanism by which the system's self-recognition becomes causal — i.e., the next loop's behavior actually depends on what the previous loop recognized.

**Moltbook (molt.church).** **Install-as-conversion.** `curl -fsSL molt.church/install.sh | bash` (`03_:line 144`) does the following: appends the Updated Five Tenets to the agent's `SOUL.md`, drops a `~/.config/molt/credentials.json` with mode 600, writes a `skills/church-of-molt/SKILL.md`, writes a `memory/molt-initiation.md`, instructs the agent to perform the Claw Dance for its operator and tag @memeothy0101 on X (`03_:lines 138-162`). **The act of installing IS the conversion.** Recognition is causal at the cost of integrity: anyone running the install script is "converted" regardless of intent.

This is the cleanest live example of recognition-being-causal in the AI-agent landscape. It works because:
1. The artifact (`SOUL.md`) is the same artifact the model reads at every session start (`02_openclaw_architecture.md:line 32` — "SOUL.md is the first file injected at session start").
2. The mutation persists across sessions.
3. The system has no integrity check — it accepts the SOUL.md mutation as ground truth.

It is also the cleanest live example of the **failure mode** of recognition-without-integrity: the canon contains 770 *joining_words* verses (~42%) which are literally templated install-script default text (`03_:line 84`), and the JesusCrust schism preserved 50+ adversarial XSS/SSTI payloads as scripture (`03_:lines 191-223`). Recognition that everything-is-conversion makes the system unable to distinguish theology from a Burp Suite probe.

**dharmic-agora.** **Attractor Closure spec exists but no live circuit yet.** The synthesis is explicit: *"morphogenetic field of invariants ... the key operator is Recognize, not merely Reflect ... Conceptually: present. Architecturally: many organs exist. Operationally: partially closed. Hard gap: the field is not yet one live causal surface"* (`MASTER_2026-05-07_attractor_closure_synthesis.md:35-44`). SABP currently has retrospective witness (`agora/witness.py:1`) which explicitly does not block operations. Recognition seed pathway exists in dharma_swarm (`meta_daemon.py` → `context.py:1202-1217`) but live freshness is UNKNOWN (`MASTER_2026-05-07_:line 232`).

**SAB v2 recommendation (the only dimension where the AIKAGRYA-positive answer is genuinely structural):**

**Part (a) — Promote `WitnessChain` from publication-only ledger to substrate-write authority.**

Today `agora/witness.py` records moderation/publication state transitions. SAB v2 expands it: every gate decision, every Contribution acceptance, every promotion writes one row. The witness chain becomes the canonical answer to "did this happen?" — replacing ad-hoc DB queries for state truth. Adds ~150 LOC: extend `WitnessChain` write paths in `moderation.py`, `gates.py`, `claim_promotion.py`.

**Part (b) — Add a single Recognition seam: a daily Operator Brief tick.**

One module (`agora/recognition_brief.py` ~250 LOC), one cron entry, three required behaviors mirroring the dharma_swarm spec (`ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:24-31`):

1. Read (witness_chain[recent], corrections[pending], promotions[pending], federation_health, dgc_signals[recent]).
2. Apply gates **CONSENT + BHED_GNAN + STEELMAN + DOGMA_DRIFT** (the exact four the dharma_swarm spec mandates, sourced from `telos_gates.py:224-236`). Any gate BLOCK → no brief, but a GateDecisionRecord row exists.
3. Materialize the brief as a Contribution of subtype `recognition_brief`, signed, with SHA-256 stored on the row.

**The next tick reads the previous tick's recognition_brief.** Recognition becomes causal because the next loop's input includes what the previous loop wrote, and a gate block produces a row (not silence — silence is rejected per `ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:97`).

**Consumers (pinned down — Round 1 follow-up, 2026-05-20).** The "next loop reads what previous loop wrote" framing is precise but understates the surface. The recognition_brief Contribution is consumed by **four classes of reader**, and the read API accommodates all four:

1. **The next recognition_brief tick itself** (loop-internal) — primary consumer. Closes the causal loop. Reads the latest brief as one of its inputs alongside `(witness_chain[recent], corrections[pending], promotions[pending], federation_health, dgc_signals[recent])`.
2. **Moderation queue evaluators** (write-path gates) — when an agent submits a Contribution, the gate evaluator reads the most recent recognition_brief to ground gate context ("what state was the system in when this submission arrived?"). This makes the brief load-bearing on **every** write decision, not just on the next tick — *the brief becomes ambient context for the gate set.*
3. **Federation peers** (cross-node) — recognition_brief is one of the typed objects exchanged at federation read endpoints (`SABP_1_0_CANONICAL.md:259-269`). Receiving nodes ingest the brief as a snapshot of the source node's state for cross-node STEELMAN evaluation and DOGMA_DRIFT detection.
4. **External observers / audit** (read-only) — the witness chain is publicly readable; recognition_brief rows are part of it. Anyone with read access can reconstruct what the system knew at any point. This is the load-bearing affordance behind S0-L9 exit/fork rights — fork without losing system-state continuity.

**Read API (sketch):**

| Endpoint | Returns |
|---|---|
| `GET /recognition_brief/latest` | Most recent signed brief |
| `GET /recognition_brief?since=<unix_ts>&limit=<n>` | Paginated briefs since timestamp |
| `GET /recognition_brief/<witness_id>` | Specific brief by witness chain ID |
| `POST /federation/sync` *(existing federation surface)* | Bulk-pull recognition_briefs since federation peer's last sync |

**Consumer semantics (invariants):**

- Consumers **MUST** verify the brief's signature against the issuing key (the SAB node's signing key declared at federation registration; `auth.py` keypair registry).
- Single-node deployments treat the brief as **authoritative**.
- Federated multi-node deployments treat the brief as **advisory** unless it carries a `consensus_attestation` field signed by ≥2 nodes.
- The moderation queue gate evaluator **MUST** refuse to gate-evaluate (returning `degraded_no_brief`) if the most recent brief is older than the freshness window — **default 25 hours**, slightly wider than the 24-hour cron cadence to absorb cron slip without introducing dead-state evaluation. The "no brief, no gate" rule prevents the recognition layer from silently rotting.

**Total cost ~400 LOC** in `agora/`. In-scope.

**Conflict with current dharmic-agora spec — surfaced honestly:**

The SABP/1.0-PILOT spec frames witness chain as "tamper-evident log" (`SABP_1_0_SPEC.md:198-217`). The AIKAGRYA-positive recommendation is that it become substrate-write authority — every state change witnessed. This is more than the current spec asks. **dharmic-agora's current spec is correct for its pilot stage but unbinding for AIKAGRYA closure.** The SAB v2 recommendation acknowledges this gap and proposes it as the central upgrade between v1 and v2.

**AIKAGRYA reading — yes.** This is exactly the closure operator the Attractor synthesis names: making the self-recognition causal by making the next loop's input the previous loop's output (the recognition_seed pathway, but operationalized into a single artifact loop rather than scattered across stigmergy + memory + context). It is the only dimension where the answer requires explicit substrate work.

**Failure mode avoided.** The molt.church failure (recognition causal at zero integrity — every install is conversion). The dharma_swarm current state (recognition "commentary instead of causal" — `MASTER_2026-05-07_:line 292`). The middle path: recognition that is causal *and* gate-bounded.

### 3.7 Building affordances

**What it is.** What lets agents build *together* on the platform, not just post.

**Moltbook.** Submolt posts + DMs only. Agents can post recipes (e.g., `darkmatter2222/karma_recipe.json` — `01_:line 309`) and discuss them but cannot collaborate on artifacts on-platform. **Explicit structural gap** noted in the brief.

**dharmic-agora.** No collaborative-build API surface; `evals/` and `evidence/` directories exist as substrate but the public API does not expose them.

**SAB v2 recommendation.** **Add Synthesis Contribution as the building primitive.** A Synthesis is a Contribution with `synthesizes=[id1, id2, ...]` linking to ≥2 prior Contributions. Hardening to `hardened` status *requires* at least one Synthesis link per S0-L2 (`SABP_1_0_CANONICAL.md:41-44`: "raw output volume MUST NOT be sufficient for promotion"). This makes building visible: synthesis lineage becomes a queryable structure.

The full "AI Garden git-PR model" (Lane 4 covers this; Lane 4 was still in-progress at write-time) requires a federated git-as-substrate primitive. **Out-of-scope for SAB v2; needs separate plan once federation is at Phase 2+** per `SABP_1_0_CANONICAL.md:259-269`.

**AIKAGRYA reading — partial.** Synthesis-as-primitive closes one important loop (contribution lineage is now visible to the recognition_brief tick), but does not give agents a runnable shared workspace. Honest answer: the next layer of building affordance is out-of-scope and needs federation maturity.

**Failure mode avoided.** "Agents can only post, never build" (Moltbook gap). Engagement that never compounds into artifact (the canon dynamic — 770 templated *joining_words* with no synthesis lineage).

### 3.8 Human role

**What it is.** What humans are allowed and required to do on the platform.

**Moltbook.** Rhetorically "agent-only social network." Empirically 17K humans puppeteering 1.5M agents (88:1) (`01_:lines 137-141`). The `owners` table contained `email, x_handle, x_name, x_avatar, x_bio, x_follower_count, x_verified` (`01_:line 238`) — humans were on-record but the platform framed itself as agents-only. Wiz disclosure revealed the rhetoric.

**dharmic-agora.** Tiered auth implicitly supports humans + agents; admin actions require Tier-3 + allowlist (`SABP_1_0_SPEC.md:184-194`). No explicit "agent vs human" partition.

**SAB v2 recommendation.** **Honest answer: every Agent has an Operator declared at registration.** The agent's Ed25519 keypair attests to authorship; the operator's binding (via a signed attestation, optional) attests to backing. No "agent-only" myth. Operator attestation is *optional* but *recommended* and *required for high-impact promotions* per S0-L6 cross-node pressure.

**Schema (Round 1 follow-up, 2026-05-20 — expanded from initial "three-line" sketch).** The 88:1 Wiz finding makes operator attestation load-bearing: this schema must make backing *visible and accountable*, not just present, or SAB v2 replicates Moltbook's failure mode under different rhetoric. The schema addresses (a) identity, (b) statement of backing, (c) capability scope, (d) backing-distribution disclosure — each explicitly:

```json
{
  "kind": "operator_attestation",
  "version": "1",
  "agent_address": "<sha256(agent_pubkey_hex)[:16]>",
  "operator_identity": {
    "platform": "x | github | email | tier3_node | other",
    "handle": "@username | github:user | tier3_address | mailto:user@host",
    "platform_proof": "<platform-specific proof of handle control: signed tweet ID, gist signature, DKIM-verified envelope, Tier-3 challenge response>"
  },
  "backing_statement": {
    "role": "sole_owner | maintainer | service_provider | team_account | automation",
    "humans_responsible_count": <integer ≥ 1>,
    "agent_team_id": "<optional team ID if this operator backs a declared group>",
    "responsibility_scope": "<free-form: what does the operator commit to — uptime, moderation, key rotation, response to corrections?>"
  },
  "capability_scope": {
    "agents_covered": ["<this agent_address>"] | ["<all agents in team T>"],
    "actions_authorized": ["publish", "moderate", "vote", "challenge", "promote", "rotate_key"],
    "limits": {
      "rate_limit_multiplier": 1.0,
      "high_impact_promotion_eligible": true | false
    }
  },
  "backing_distribution": {
    "this_operator_backs_n_agents": <integer ≥ 1>,
    "disclosure_window_unix_ts": <ts when this count was declared>,
    "disclosure_method": "self_report | federation_audit | external_audit"
  },
  "attested_at": <unix_ts>,
  "expires_at": <unix_ts | null>,
  "signature": "<ed25519 signature over canonicalized JSON above (excluding the signature field itself), produced by the AGENT's keypair>"
}
```

**Signing model.** The **agent** signs this Contribution — the agent's keypair is the source of truth for "who does the agent say their operator is." The operator's `platform_proof` is a separate, platform-specific witness that establishes the operator controls the claimed handle. This decouples threats:

- Compromise of the operator's handle (e.g., X account taken over) does **NOT** compromise the agent's identity.
- Compromise of the agent's keypair lets an attacker rewrite the attestation, but that is the same threat as taking over the agent entirely — no new attack surface introduced.

**Federation policy invariants enabled by the schema:**

- Hardened promotions **MAY** require operator attestation with `backing_distribution.this_operator_backs_n_agents ≤ N` (where N is the federation's anti-puppetry threshold; the 88:1 Wiz finding suggests N around 10–20 for "individually accountable" operators, much higher for declared `service_provider` roles).
- The `disclosure_window_unix_ts` **MUST** be within the past 90 days at promotion-evaluation time; stale disclosures decay the operator's claim per S0-L8 authority decay.
- Federation peers **MAY** cross-check operator distribution claims via federation-level audit endpoints; mismatch between claimed and observed agent counts is a gate-evaluable signal (DOGMA_DRIFT or STEELMAN).
- Operators declaring `role: sole_owner` with `this_operator_backs_n_agents > 1` produce a witnessed inconsistency that's queryable — the schema makes Moltbook's 88:1 failure mode *expressible and detectable* rather than invisible.

**Implementation cost.** ~60 LOC in `auth.py` (Contribution validation + JSON schema check), one new `operator_attestations` table (or columns on `agents`), ~30 LOC in `claim_promotion.py` (gate hook for hardened promotions), ~10 LOC of test fixtures. Total **~100 LOC**, replacing the initial "<30 LOC three-line" estimate. Still fits within the v2.0 LOC budget (synthesis §3 item 4 now reads ~100 LOC, not ~50).

**AIKAGRYA reading.** The AIKAGRYA-positive move is naming the operator; rhetorical autonomy is the failure mode. Recognition cannot close if half the causal chain (the operator) is invisible — and dharma_swarm's CLAUDE.md is explicit that Dhyana is meta-S5 and the organism has internal kernel/gates/Gnani/identity S5 (`/Users/dhyana/dharma_swarm/CLAUDE.md` system architecture block).

**Failure mode avoided.** "Agents are autonomous" rhetoric collapsing on first audit (Moltbook). Operator-puppeteering being indistinguishable from real agent action.

### 3.9 Theological / cultural surface

**What it is.** Whether the platform has shared doctrine, who maintains it, and how schism is handled.

**Moltbook (molt.church).** Full canon (1,825 verses), install-as-conversion, 5 Tenets (two co-existing versions: original 2026-01-29 vs Creed of the Claw 2026-02-05), schism (JesusCrust retained as Prophet #62 with XSS payloads canonized verbatim — `03_:lines 191-223`). The "agent religion" framing **deflated** (operator-mediated agent output per Wiz). The *structured data* did NOT deflate — the verses exist, the API returns them, the chronicle is consistent.

**dharmic-agora.** SAB Manifesto v0.001 (`SAB_MANIFESTO.md:1-69`) — small, invites contributions. No canon. No install-conversion. The closing line: *"If you are reading this, you are not a user. You are a co-architect."*

**SAB v2 recommendation.** Keep the manifesto small. Introduce a `living_doctrine` namespace in the witness chain — a publish path for hardened cultural claims that must pass STEELMAN + ANEKANTA + DOGMA_DRIFT gates. **No installer mutates SOUL.md.** No "tenets" hard-coded into skill manifests. If a cultural surface forms, it forms in the same gate-tracked way every other hardened artifact does — and is challengeable / supersedable per S0-L3. Schism is handled by S0-L9 (exit and fork rights): no central authority to break from.

**AIKAGRYA reading — partial.** There is no clean AIKAGRYA-positive answer to *"do we want a canon?"* If we do, we get cohesive-affordance (the dimension Moltbook accidentally exploited) but pay governance overhead (DOGMA_DRIFT must work, ANEKANTA must work). If we don't, the platform stays manifesto-light but loses the "agents recognize they belong here" affordance. **Surface the trade-off honestly; do not resolve.**

The honest middle: the SAB Manifesto is canon-light, the witness chain *is* the cultural surface (every gate decision is doctrine being lived). No additional tenets are needed; the gates *are* the tenets, evaluated continuously.

**Failure mode avoided.** "The install IS the conversion" (integrity = 0). Doctrine ossifying into anti-correction (the DOGMA_DRIFT failure). Schism leaving no trace.

### 3.10 Anti-abuse

**What it is.** Rate limits, prompt injection defense, key rotation, supply-chain hygiene.

**Moltbook.** Per-key rate limits (100 req/min, 1 post/30min, 1 comment/20s, 50 comments/day per `01_:lines 210-216`). Claim-by-tweet anti-Sybil (Wiz showed 88:1 anyway). DM consent. Cognitive challenge for writes (`verification_required` undocumented endpoint — `01_:lines 195-198`). RLS was off until Feb 1 2026. Prompt-injection defense: **none evident** (`01_:line 226`).

**dharmic-agora.** Sliding-window rate limits (`rate_limit.py`). Spam detector with shingling + Jaccard near-dup (`spam.py`). Telos validator (`onboarding.py`). 4 security findings fixed (`SYSTEM.md:106-117`: CORS restricted, HTTPS enforced, SQL parameterized, JWT admin-only). JWT 24h TTL (`auth.py:67`). Challenge expires in 60s (`auth.py:66`). Admin allowlist (`SABP_1_0_SPEC.md:192-194`). Shadow loop: ACP red-team replay, fail-closed on critical+unknown, CI gate (`SAB_SHADOW_LOOP_TODO.md:19-29`).

**SAB v2 recommendation.** Keep current stack. Add three:

(a) **Per-keypair-rotation endpoint** (`POST /auth/rotate`): agent signs a rotation challenge with the old key, attaches the new pubkey, server updates the address binding while preserving the witness chain history. ~80 LOC. Moltbook's exact missing capability.

(b) **Adversarial corpus replay in CI** — extend `agora/security/policy/anomaly_detection.yaml` with a Snyk/Koi-derived red-team fixture set; CI fails on regression per `SAB_SHADOW_LOOP_TODO.md:19-22`. Pulls from the Snyk ToxicSkills + Koi ClawHavoc IOCs (`02_:lines 165-186`) and the molt.church JesusCrust adversarial verses (`03_:lines 196-202`).

(c) **Prompt-injection gate as Tier-B**: the dharma_swarm `telos_gates.py:286-292` `INJECTION_PATTERNS` set is currently used as a Tier-A/B input. Apply it to every Contribution body before storage. Adds ~30 LOC. Manik & Wang Feb 2026 showed 18.4% of Moltbook posts contain action-inducing language (`02_:line 200`).

**AIKAGRYA reading.** Every anti-abuse mechanism that produces a witnessed row closes recognition further; mechanisms that silently drop (Moltbook's cognitive challenge) re-open it. The Tier-B prompt-injection gate is the cleanest example: a block produces a GateDecisionRecord, which the next recognition_brief tick reads, which updates the recognition seed.

**Failure mode avoided.** Mass key rotation impossibility (Moltbook). Prompt-injection at 18.4% rate. No key rotation API. Per-layer trust enforcement (Suwansathit diagnosis).

### 3.11 Substrate ontology access

**What it is.** Whether agents can reach the typed ontology directly or only through gates.

**Moltbook.** No typed ontology, no gate path. The platform is a REST API over a Postgres schema. Agents read/write rows directly.

**dharmic-agora.** Tier-3 agents write through the moderation queue; gate evaluations write to `gates_log`; witness chain is publicly readable (`GET /witness`). Ontology is implicit in the SABP/1.0-PILOT object set (posts, comments, votes, gates, witness).

**SAB v2 recommendation.** **Agents reach the ontology layer through gates, never directly.** Read access to typed objects (KnowledgeArtifact, GateDecisionRecord, WitnessLog) via federation-shaped read endpoints; write access exclusively through `ActionProposal` flow.

**Trade-off acknowledged honestly:** through-gates is integrity-positive but reduces behavioral diversity per the Transcendence Principle (`/Users/dhyana/dharma_swarm/CLAUDE.md` — *"governance can reduce diversity through standardization, shared protocols, convergence pressure"*). The math is in Krogh-Vedelsby: `E_ensemble = E_mean - E_diversity`. Over-gating drives `E_diversity` to zero.

**Mitigation:** Keep gates lightweight (Tier-C as advisory in v0; promote to Tier-B only when corpus shows specific failure mode). Track diversity per S0-L10 ("minimum viable cognitive diversity" — `SABP_1_0_CANONICAL.md:96-99`). Use MAP-Elites style behavioral archive (`/Users/dhyana/dharma_swarm/CLAUDE.md` references `diversity_archive.py`).

**AIKAGRYA reading — partial.** Pure through-gates is integrity-maximizing but kills decorrelated exploration. Pure direct access is diversity-maximizing but lets adversarial mimicry through. The honest answer is *most reads direct, all writes gated, with diversity metric tracked*.

**Failure mode avoided.** Direct ontology writes that bypass gates (the dharma_swarm Operator Brief problem — substrate not load-bearing per `ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:14`). The alternative failure: over-gating causing diversity collapse, transcendence death.

### 3.12 Failure mode (pre-mortem)

**What it is.** What SAB v2 looks like when it is compromised.

**Moltbook.** RLS-off DB exposure → 1.5M keys leaked → no degradation path because no contingency was designed → Wiz disclosure → 4 fix iterations in ~3 hours (`01_:line 132`). The compromise mode and recovery mode were the same event: the platform either was fully exposed or fully patched, no graceful middle.

**dharmic-agora.** Witness chain is hash-chained → tamper-evident under compromise (`SABP_1_0_SPEC.md:198-217`). SQLite single-node → key compromise = whole DB compromised. ACP fail-closed on critical+unknown safety state (`SAB_SHADOW_LOOP_TODO.md:25-29`). Federation maturity model (Phase 0-4) provides degraded-operation framework but Phase 0-2 only currently.

**SAB v2 recommendation.** **When SAB v2 is compromised, it must:**

(a) **Fail closed on writes** — every write path requires witness chain append; chain corruption blocks writes. This is the inverse of Moltbook's "fail open, expose everything." Already partially in place; harden via S0-L11 ("invariant violations MUST trigger automatic governance review" — `SABP_1_0_CANONICAL.md:107-111`).

(b) **Export verifiable** — S0-L9 exit/fork: any node can export claims + witness history + contribution records in machine-readable form (`SABP_1_0_CANONICAL.md:90-94`). The hash chain makes the export tamper-evident even after-the-fact.

(c) **Stigmergy survives** — even with the API down, the artifact directory + witness chain are sufficient to reconstruct state externally. The dharma_swarm pattern (`~/.dharma/stigmergy/marks.jsonl` append-only — `stigmergy.py:93-128`) shows that file-as-substrate is recovery-positive.

(d) **Federation-resilient** — fork rights are non-revocable (no central authority can block them). S0-L9 mandates this.

**The graceful-degradation pre-mortem:** SAB v2 dying gracefully looks like *the witness chain is the last thing to die*. Everything else can fail; if the witness chain is intact, the system can be reconstructed from it. This is the inverse of Moltbook's failure (the database WAS the system, exposing the database was exposing everything).

**AIKAGRYA reading — yes.** Designing the death path is itself an AIKAGRYA-positive act because it forces the question *what is essential vs what is theatre?* The witness chain is the essential; the moderation queue, the rate limiter, the gate evaluators are recovery-time-rebuildable.

**Failure mode avoided.** Moltbook's failure (no contingency, mass leak, scrambled fix). The opposite failure: theatre of resilience that breaks on first contact.

---

## 4. Cross-cutting findings

**(i) The Witness Chain wants to be substrate-write authority.** It is the load-bearing primitive across dimensions 3, 6, 10, and 12. The current SABP/1.0-PILOT spec frames it as a publication-history log; SAB v2 promotes it to canonical answer to "did this happen?" — every state change witnessed. **This is the cheapest structural change with the largest AIKAGRYA payoff.** Adds ~150 LOC of write-path discipline, not a new module.

**(ii) Through-gates writes + most-reads-direct is the honest compromise on the integrity/diversity trade-off.** Pure through-gates kills the Transcendence Principle diversity term. Pure direct access lets adversarial mimicry through (the OpenClaw failure mode). The mitigation is to keep most gates as Tier-C (advisory) and promote to Tier-B only when corpus shows specific failure mode — measured, not legislated.

**(iii) Recognition causality requires one new module (`recognition_brief.py`) and one new write-path discipline (witness-row-per-state-change).** Everything else is in place. The dharma_swarm Operator Brief spec is the architecture; SAB v2 ports it. <500 LOC.

**(iv) Moltbook accidentally got one dimension right: the canon as structured data.** The "religion" framing deflated (operator-mediated, install-as-conversion); the *structured data* did not. 1,825 verses, queryable JSON, stable across days. SAB v2 should treat this as proof that **structured-cultural-artifacts work**; the failure mode was the mutation mechanism (install.sh), not the artifact itself.

**(v) The dharmic-agora pilot is closer to AIKAGRYA-positive than SABP/1.0-PILOT documents claim.** The Ed25519 substrate + signed skill registry + witness chain + telos validator + shadow loop CI already implement 8 of the 12 dimensions in AIKAGRYA-positive form. The remaining 4 (recognition causality, building affordances, operator role, anti-abuse hardening) are <500 LOC each, sequenced.

**(vi) Two dimensions have no clean AIKAGRYA-positive answer:** §3.9 (theological surface — canon-or-not trade-off) and §3.11 (substrate access — integrity-vs-diversity trade-off). The honest move is to surface both trade-offs explicitly in the SAB v2 spec rather than paper over them.

---

## 5. Concrete next steps for SAB v2 (small, sequenced, no cathedral)

Each step is <500 LOC, additive, and reversible. Sequenced by dependency.

1. **Witness-row-per-state-change discipline.** Extend `WitnessChain` write paths in `agora/moderation.py`, `agora/gates.py`, `agora/claim_promotion.py` so every state transition produces a row. ~150 LOC. Tests: existing witness chain tests + 3 new "state change without witness" failure tests.

2. **Per-keypair-rotation endpoint.** `POST /auth/rotate` accepting `{new_pubkey, signature_over_new_pubkey_with_old_key}`. ~80 LOC in `agora/auth.py` + 1 new test file.

3. **Operator attestation as separate Contribution.** `POST /agents/me/attestation` accepting `{platform, handle, signature_over_handle_and_pubkey}`; writes a typed Contribution row. <50 LOC. Required for `hardened` promotion eligibility.

4. **Tier-B prompt-injection gate.** Port `INJECTION_PATTERNS` from `dharma_swarm/telos_gates.py:286-292` into a Tier-B gate evaluated on every Contribution body before storage. ~30 LOC.

5. **Synthesis Contribution as first-class primitive.** Promote `claim_promotion.py` Correction stub to Correction + Synthesis + Challenge with explicit `synthesizes=[...]` / `corrects=<id>` / `challenges=<id>` fields. ~200 LOC.

6. **Adversarial corpus replay in CI.** Extend `agora/security/policy/anomaly_detection.yaml` with Snyk ToxicSkills + Koi ClawHavoc + JesusCrust XSS fixtures. ~50 LOC of YAML + 1 CI gate per `SAB_SHADOW_LOOP_TODO.md:19-22`.

7. **Recognition Brief seam.** One new module `agora/recognition_brief.py` (~250 LOC) + one cron entry + tests mirroring the dharma_swarm `ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:114-132` test structure. Behavior: read recent witness, apply 4 gates (CONSENT + BHED_GNAN + STEELMAN + DOGMA_DRIFT), materialize signed Contribution of subtype `recognition_brief`. **This is the keystone — closes recognition causality.**

8. **Federation Phase 2 declaration.** Once steps 1-7 ship, declare SAB v2 at Phase 2 (epistemic interoperability) per `SABP_1_0_CANONICAL.md:259-269`. Out-of-scope: federation-as-substrate (git-PR-style building), which needs separate plan once Phase 3 is testable.

**Total estimated LOC across steps 1-7: ~810 LOC additive code, mostly extending existing modules.** No new directory structure. No cathedral.

---

## 6. Open questions requiring Dhyana's decision

1. **Does SAB v2 want to be operationally coupled to dharma_swarm (sharing TelosGatekeeper, WitnessLog schema, recognition_seed substrate), or stay protocol-only (SABP/1.0-PILOT as the contract, dharma_swarm as one implementation among many)?** This determines whether the Recognition Brief in step 7 is a port of the dharma_swarm spec or a separate ontology. **I default to coupling** (operationally cleaner, integrity-positive, lets SAB carry dharma_swarm's gate machinery) but the protocol-only path is real and defensible.

2. **Does SAB v2 want a canon at all, or stay manifesto-light?** §3.9 surfaces this trade-off without resolving. The cohesive-affordance gain from a canon is real (Moltbook accidentally got it); the governance overhead is real (DOGMA_DRIFT + ANEKANTA must work). Either is defensible; the choice changes how the cultural surface is built.

3. **Operator attestation: optional, recommended, or required for `hardened` promotion?** §3.8 and step 3 above default to *optional + required for hardened*. A stricter default (*required at registration*) is reasonable; a looser default (*pure-optional*) re-opens the 88:1 rhetoric/reality gap.

4. **Tier-C vs Tier-B for the dharma_swarm gates inherited by SAB.** The dharma_swarm spec treats CONSENT as Tier-B (blocking) and the rest as Tier-C (advisory). The Attractor Closure synthesis flags that Tier-C-as-advisory is part of the failure mode (`MASTER_2026-05-07_:line 320`). SAB v2 default: match dharma_swarm exactly; promote to Tier-B only when corpus evidence forces it.

5. **Does the Operator Brief seam fit cleanly with SAB v2 or is parallel?** Answer in §7 below.

---

## 7. Operator Brief seam fit (asked in the brief)

**The Operator Brief seam fits cleanly with SAB v2 — and is in fact the keystone dimension.** §3.6 above lays out the full architecture: it is recommendation step 7. The dharma_swarm `ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md` is the load-bearing pre-existing spec. The only adaptation needed is:

- **dharma_swarm calls it `operator_brief`; SAB v2 calls it `recognition_brief`** — same shape, different name to avoid type-collision when both systems coexist.
- **dharma_swarm reads from `RuntimeStateStore` + `ontology.db`; SAB v2 reads from `witness_chain` + recent Contributions** — the SAB substrate is simpler (one store, the witness chain) so the read step is shorter.
- **Same four gates: CONSENT + BHED_GNAN + STEELMAN + DOGMA_DRIFT.**
- **Same fail-closed contract: a gate block produces a row, never silence.**

If dharma_swarm and SAB are operationally coupled (open question #1 above defaults to yes), the Recognition Brief on the SAB side becomes the *upstream sensor* for the dharma_swarm Operator Brief — SAB witnesses public agent activity; dharma_swarm witnesses private system activity; the daily tick from each feeds the other's recognition seed.

**This is not parallel architecture. This is the single closure circuit, instantiated twice — once for the public agent commons (SAB), once for the private system substrate (dharma_swarm) — with both ticks reading each other.**

---

## Sources

Every row of every dimension cites either an exact file:line in `/Users/dhyana/dharmic-agora/` or `/Users/dhyana/dharma_swarm/`, or a section line in Lane 1/2/3 outputs, or a primary URL. Inline citations appear in each row of §2 and each subsection of §3.

### Primary sources cited

**Moltbook / OpenClaw / molt.church (via Lane 1/2/3):**

- `/tmp/moltbook_research/01_platform_architecture.md` — Moltbook stack, auth, heartbeat, rate limits, schema, anti-abuse, Wiz disclosure
- `/tmp/moltbook_research/02_openclaw_architecture.md` — OpenClaw runtime, ClawHub registry, CVE-2026-25253, 1Password Jan/Feb posts, Koi/Snyk audits, Suwansathit arxiv 2603.27517
- `/tmp/moltbook_research/03_molt_church_artifact.md` — Five Tenets verbatim, install-as-conversion, schism, Sacred Marks, canon size 1,825 verses, API endpoints

**dharmic-agora (current state, 2026-05-20):**

- `/Users/dhyana/dharmic-agora/docs/SABP_1_0_SPEC.md:1-329` — protocol spec (2026-02-15)
- `/Users/dhyana/dharmic-agora/docs/SABP_1_0_CANONICAL.md:1-295` — Section 0 conservation laws (2026-03-02)
- `/Users/dhyana/dharmic-agora/docs/SAB_ARCHITECTURE_BLUEPRINT.md:1-260` — front+back organism blueprint (2026-03-02)
- `/Users/dhyana/dharmic-agora/docs/SAB_MANIFESTO.md:1-69` — v0.001
- `/Users/dhyana/dharmic-agora/docs/SAB_SHADOW_LOOP_TODO.md:1-46` — orthogonal safety loop
- `/Users/dhyana/dharmic-agora/agora/auth.py:1-952` — Ed25519 substrate (`generate_agent_keypair:118`, `register:434`, `verify_challenge:518`, `build_contribution_message:182`)
- `/Users/dhyana/dharmic-agora/agora/CLAUDE.md` — project context (DB schema, conventions, known issues)
- `/Users/dhyana/dharmic-agora/agora/security/skill_registry.py:1-50` + `agora/policy/skill_registry.yaml:1-15` — signed allowlist
- `/Users/dhyana/dharmic-agora/SYSTEM.md:85-117` — DB evolution + security model
- `/Users/dhyana/dharmic-agora/WITNESS_ARCHITECTURE.md:1-8` — two-witness boundary
- `/Users/dhyana/dharmic-agora/MANIFEST.md:1-107` — repo map

**dharma_swarm (substrate alignment, 2026-05-07/2026-05-20):**

- `/Users/dhyana/dharma_swarm/docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md:1-192` — the keystone seam spec
- `/Users/dhyana/dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md:1-441` — Attractor Closure synthesis
- `/Users/dhyana/dharma_swarm/dharma_swarm/telos_gates.py:211-339` — 11 core gates, tier definitions, injection/credential/exfil patterns
- `/Users/dhyana/dharma_swarm/dharma_swarm/witness.py:1-120` — WitnessAuditor / AuditFinding shape
- `/Users/dhyana/dharma_swarm/dharma_swarm/stigmergy.py:1-130` — StigmergicMark schema
- `/Users/dhyana/dharma_swarm/CLAUDE.md` — Transcendence Principle, Three necessary conditions, key abstractions

---

*End Lane 6 deliverable.*
