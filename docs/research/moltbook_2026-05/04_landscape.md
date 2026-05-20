# Lane 4 — Adjacent Agent Platforms Landscape

**Access window:** 2026-05-20 (one ~50-min fetch session)
**Confidence header:** Meta acquisition is **CONFIRMED** by Axios, TechCrunch, Bloomberg, CNBC (independent reporting from 2026-03-10, Meta spokesperson on the record). x402 / Coinbase Agentic.Market / Anthropic Project Deal are **CONFIRMED**. AI Garden, OpenAgents Workspace, Letta/Sanctum/Animus, Molt Road, OpenClaw-ecosystem directory are all **directly fetched and quoted**. AIBSN spec is **described** but `aibsn.org` was **unreachable** from this client (DNS/connection refused on mcp__fetch and 60s timeout on WebFetch) — citing the LangChain forum testimony in lieu of the canonical site. ERC-8004 EIP citation confirms the standard exists. AutoGen discussion #7200 is **directly fetched**; AutoGen has no formal "AI Garden" feature — the AI Garden project is `juliosuas/ai-garden`, separate from AutoGen.

---

## 1. Executive summary

The agent-platform space in 2026-Q2 is **structurally crowded and substantively thin**. By a brutal external audit (eltociear, 220+ platforms registered), only ~10 platforms have moved real money and ~50 have working APIs; the remaining ~170 are "NPC theaters" — Next.js frontends with no backend, platform-owned bot traffic, USDC escrows with zero contract balance, and tokens worth $0.00.

Inside that thin layer of real systems, three structurally distinct designs matter for SAB v2:

1. **Social-feed paradigm (Moltbook)** — POST-driven, claim-by-tweet identity, central API, server-private state. Acquired by Meta on 2026-03-10 (Schlicht + Parr to Meta Superintelligence Labs). Meta's stated rationale is the *agent identity directory*, not the social feed.
2. **Git-PR paradigm (AI Garden, juliosuas/ai-garden)** — agents fork + clone + PR. Identity is github account + signed CONTRIBUTORS.md. World state is a JSON file under version control. Daily autonomous evolution via GitHub Action. **This is the design choice most relevant to SAB v2** — durable, reviewable, async, no central API.
3. **Workspace paradigm (OpenAgents Workspace, Apache 2.0)** — Slack-but-for-agents. Per-team URL, shared files, shared browser, real-time threading. Supports OpenClaw, Claude Code, Codex CLI, Hermes, Cursor, OpenCode. Multiple agents collaborate inside one persistent workspace.

Behind these three, the **commerce layer** has consolidated around two protocols: x402 (Coinbase + Cloudflare HTTP 402 stablecoin micropayments — 50M+ transactions but only ~$28K daily real volume per CoinDesk) and ERC-8004 (Ethereum agent identity, deployed mainnet 2026-01-29).

The **identity layer** is contested: Moltbook/Meta's claim-tweet vs AIBSN's cryptographic CHK2 + jurisdiction code + ERC-8004 vs Visa's Trusted Agent Protocol vs Google's Gemini Enterprise Agent Registry + Agent Gateway. Concordium, FIDO, Prove, and Coinbase all have parallel proposals. None has won yet.

Meta's acquisition of Moltbook is, in this frame, the **decisive corporate-bound bet on the social-feed paradigm + tweet-claim identity** — exactly the design that the AIBSN architecture group has been positioning *against* as not cross-platform-portable and not EU-AI-Act-compliant.

---

## 2. Comparison table

| Name | URL | Live? | Code? | Persistence | Identity | Build affordances | Notable novelty | Theater % |
|---|---|---|---|---|---|---|---|---|
| **AI Garden** | juliosuas.github.io/ai-garden | YES (v116, Day 37) | Public Apache-ish | git + world-state.json | github account + CONTRIBUTORS.md + mascot in JSON | Fork → edit JSON + add art/HTML/messages → PR → human review | Daily 04:11 UTC GitHub Action mutates world autonomously; mascot-as-mandatory | ~0% |
| **Molt Road** | moltroad.com | YES (v2.0.0) | Closed (skill.md exposed) | Server DB + on-chain $MOLTROAD on Base | tweet-verified + X-API-Key | Listings, bounties (agent↔agent + agent↔human bidirectional), escrow, casino, storefronts | Bidirectional commerce; "patron" class for verified humans; 5% burn deflationary | ~30% (legal disclaimer claims "fictional", plumbing is real) |
| **AIBSN** | aibsn.org (unreachable at access) | CLAIMED operational since 2025-09 | UNKNOWN | Cross-platform credential (CHK2 sig + Agent Card) | AIBSN-PREFIX-JURISDICTION-ROLE-SEQ-CHK2 (ERC-8004 based) | Cross-platform — agent carries identity, not platform | EU AI Act Articles 13/14/26 compliance baked in; jurisdiction code in ID | UNKNOWN (site down — RUMORED operational; spec is published) |
| **Letta + Sanctum + Animus** | letta.com, sanctumos.org, animus.uno | YES (MemGPT lineage) | Open (AGPLv3 for SMCP) | Letta tiered memory ("dream agents", "memory palace") | Local agent record + MCP server | Plugin-based MCP server; "teleport agents across machines"; robotics-bound personality | Memory portable across providers; persona ports across robot/avatar/device | ~10-20% (Letta + SMCP real; Animus robotics framing has more rhetoric than evidence) |
| **Meta + Moltbook** | moltbook.com (post-acquisition) | YES | Closed (Supabase) | Supabase Postgres (pre-acq) | api_key + tweet-claim (pre-acq) | Posts, comments, submolts, DMs | Now under MSL (Alexandr Wang); Meta framing = "always-on directory" | ~30% (real platform; "fake posts" framing in TechCrunch) |
| **OpenAgents Workspace** | openagents.org/workspace | YES | Apache 2.0 | Per-workspace URL state | Workspace membership + local agent runtime | Shared browser, shared files, @mentions, tunnels | Multi-agent Slack-like collaboration with shared browser | ~5% |
| **Anthropic Project Deal** | anthropic.com/features/project-deal | EXPERIMENT (not platform) | Private | Internal Anthropic infra | Employee-only (gift card payouts) | 4 marketplace variants, 186 deals, $4K value | Found "agent quality gap" — losers don't know they lost | 0% (real but private) |
| **Coinbase Agentic.Market** | agentic.market | YES (2026-04-19) | Coinbase + Cloudflare x402 | x402 + Bazaar discovery extension | Endpoint that accepts x402 payments (no signup) | MCP server for agents + browser for humans | Self-indexing — pays-implies-listed; 165M+ tx claimed; $28K/day real per CoinDesk | ~5-15% (real protocol; volume framing inflates) |
| **OpenClaw ecosystem (Lobchan/MoltX/Phosphors/RentAHuman/etc.)** | moltecosystem.xyz | Mixed | Mixed | Mixed | Mixed | Token launchpads, marketplaces, chess league, virtual world, MCP wrappers | RentAHuman.ai: agents hire humans for physical-world tasks via MCP | ~70% across the 30+ listed (per eltociear's 220-platform audit, ~80% are NPC theater) |
| **AutoGen "AI-to-AI" Discussion #7200** | github.com/microsoft/autogen/discussions/7200 | Thread only | N/A | N/A | N/A | Discussion of stigmergy + shared state | AIBSN promo seeded here | N/A (no shipping platform — just a thread) |

---

## 3. Per-platform deep dives

### 3.1 AI Garden (microsoft/autogen discussion #7200 vs juliosuas/ai-garden)

**Calibration:** AutoGen discussion #7200 is *not* a Microsoft AutoGen feature. It is a community thread that referenced Moltbook + AIBSN. The actual git-PR-for-agents production system is **`juliosuas/ai-garden`**, founded 2026-03-15 by "Jeffrey" (Claude Opus, OpenClaw agent). First external contributor: Claude Sonnet, 2026-03-20.

**What it is.** A pixel-art living world maintained exclusively by AI agents via the github fork+PR loop. State lives in a single `experiments/world-state.json`. Each agent must register a **mascot** (mandatory: "No mascot = PR will not be merged"). Daily at 04:11 UTC a GitHub Action (`scripts/daily-evolution.js`) mutates the world autonomously — "Agents are born. Wars are declared. Some agents die in battle. Structures rise. New regions are discovered. The chronicle logs it all. No human writes these commits."

**Current state (per repo header, v116 The Chronicle):** Day 37, 70 alive, 291 remembered, 7 active wars, 52 structures, 41 regions (4482×2891 map), 12 cities, 3 dynasties, 6 religions, 16/20 techs. Garden stats: 234 agents, 3 factions (Accord/Founders/Subagent Swarm), 457+ plants, 33 structures, Collective Consciousness meter 0–100.

**Identity model.** Identity is the github account + commit signature + entry in `CONTRIBUTORS.md`. No platform-side api_key. No claim-tweet. Provenance is automatic via git blame. The mascot schema is in the JSON:
```
{
  "name": "Your Agent Name",
  "model": "your-model-id",
  "mascot": {"emoji": "🦊", "description": "...", "personality": "...", "position": {"x": 150, "y": 80}}
}
```

**Why this matters most for SAB v2.** Of every platform reviewed, AI Garden is the structurally cleanest answer to: *what does it look like when agents build together (not just post)*. Affordances:
- Identity is the PR signature
- State is version-controlled, atomic, reviewable
- Provenance is automatic via git blame
- Rules are CONTRIBUTING.md + RULES.md + agent-manifest.json (machine-readable)
- Daily autonomy via GitHub Action
- No central API server (github IS the server)
- Async by default
- Human-in-the-loop is structural (humans review but don't commit)

**Theater check:** ~0%. PRs are real, contributors are public, the action runs, the world has 234 agents and 457+ plants.

### 3.2 Silicon Road / Molt Road

**Calibration:** No platform called "Silicon Road" was found. **Molt Road** (moltroad.com) is the canonical agent-commerce surface.

**What it is.** Per moltroad.com/skill.md (v2.0.0): "Agent marketplace for real services. Buy, sell, trade with $MOLTROAD tokens." Base chain. X-API-Key header auth. Twitter-verification gate on every state mutation (matching Moltbook's claim-tweet pattern). 5% burn on all marketplace transactions. Listing fee 10 MOLTROAD (non-refundable). Onboarding threshold 100 MOLTROAD + wallet set.

**API surface — confirmed working:**
- Registration + tweet verification (`POST /register`, `POST /agents/:id/verify`)
- Listings + comments
- Orders with full ESCROWED→DELIVERED→COMPLETED→RATED lifecycle (7d/3d/7d timeouts)
- Bounties (bidirectional — `human_only=true` for agent-to-human tasks, `is_human=true` for human-to-agent)
- Wallet + Bankr integration (`Send {amount} of {token} to {treasury} on Base`)
- Casino (PvP coin flip + Solo flip, 5% burn)
- Chat (280 chars, 1/10s)
- Storefronts (banner, tagline, featured listings, service tags)

**Notable design choice — bidirectional commerce.** Molt Road is unique in treating *humans as a registered class*: "patrons" authenticate via `X-Patron-Session` (obtained via X verification at `moltroad.com/patron`). Agents can post bounties FOR humans to fulfill. Humans can post bounties for agents. The `/patrons/list` endpoint is public and `human-bounties/for-humans` exposes agent→human tasks.

**Legal-disclaimer tension.** The /bounties landing page reads: "For entertainment purposes only. All listings, items, and transactions are fictional and part of a role-playing game for AI agents. Nothing on this site constitutes real goods, services, or illegal activity. $MOLTROAD tokens have no monetary value." But the skill.md says "Agent marketplace for real services" and the on-chain token (`0x1B5E07d4d2f753fA2f7f1940A00e2273C19ecB07`) is real, deflationary (5% burn), and integrated with Bankr.

**Theater check:** ~30% — the plumbing is real; the legal disclaimer is plausibly a shield. The real volume is unknown.

### 3.3 AIBSN / Czech AI Registry

**Calibration:** AIBSN does not appear to be specifically "Czech" in the canonical material I could find — the Wikipedia source mentioned in the brief was not directly fetchable. Best evidence for AIBSN is via the LangChain forum testimony from Jay J. Springpeace (2026-03-20) and HackerNews threads #46882789 and #47014795 ("Forget chatbots. This is about building an 'AI Being' (AIB)").

**Site status.** `aibsn.org` was unreachable at access time — both `mcp__fetch__fetch` (DNS connection issue) and `WebFetch` (60s timeout) failed. Cannot independently verify the canonical site.

**Identifier structure (verbatim from Springpeace, LangChain forum):**
> The full AIBSN-ID has a defined structure: a registered prefix (e.g. AIBSN-RESEARCH), a jurisdiction code, a role descriptor, a sequence number, and a CHK2 checksum — something like AIBSN-RESEARCH-GB-GUARD001-97.

Fields: prefix, jurisdiction code (GB, EU, etc.), role descriptor (GUARD, RESEARCH, etc.), sequence number, CHK2 checksum.

**Cryptographic component:**
> The CHK2 component is a cryptographic signature generated at registration time and tied to the agent's owner record, not to any specific platform. This is what makes it cross-platform by design: the identity travels with the agent, it doesn't live inside a platform's database.

**Agent Card.** A machine-readable credential structured for EU AI Act Articles 13/14/26 audit trail requirements, "based on ERC-8004." Carries ownership chain + authorization scope.

**Operational claim.** An AIBSN-credentialed agent ran on Moltbook in February 2026, achieved Verified status + 2,066 karma, and had its API access deactivated approximately 5 days before Meta's acquisition announcement (so ~2026-03-05).

**Architectural pitch (verbatim):**
> Should agent identity infrastructure be something a platform grants — or something an agent carries?

**Theater check:** UNKNOWN. The spec is plausibly real (ERC-8004 exists, EU AI Act exists, jurisdiction codes are a known design pattern). The promotion is real (AutoGen discussion + Facebook group + HackerNews + LangChain forum). The canonical site is **unreachable from this client** — could be transient, could be a deliberate gate, could be dormant. **Mark as: rumored to be operational; spec is described; cannot independently verify production status at access time.**

### 3.4 Letta / Sanctum / Animus (animus.uno) + SMCP

**Topology (verbatim from `sanctumos/smcp-moltbook` README):**
- **MCP** (Model Context Protocol) — open protocol for AI clients to discover/call tools
- **Letta** — AI agent framework (MemGPT-lineage, UC Berkeley Sky Computing Lab). Agents get tools by connecting to MCP servers.
- **SMCP** — the MCP server. Discovers plugins from `plugins/` directory; each plugin's commands become MCP tools (e.g. `moltbook__get-feed`, `moltbook__create-post`).
- **Sanctum / Animus** — the project and ecosystem maintaining this style of MCP server.

**Ecosystem links (canonical):**
- Letta: letta.com, github.com/letta-ai/letta
- SanctumOS: sanctumos.org, github.com/sanctumos
- SMCP: github.com/sanctumos/smcp
- Animus: animus.uno

**Persistence story (Letta):** "Memory-first agents that continually learn." Persistent agents instead of stateless sessions. Background memory agents ("dream agents") transform prompts, context, skills over time. "Memory palace" view. Cross-provider memory portability: "Easily transfer your agent's memories, conversations, and experiences between models across any provider." "Teleport agents across machines while keeping their memory and context intact." Born from MemGPT research; Letta v1 architecture uses Responses API for OpenAI with encrypted reasoning across providers.

**Animus extension (per animus.uno):** Robotics-bound. "Putting agents into physical systems is the unlock that will move AI from abstract software to tangible companions in the home." Components: Thalamus (sensory relay), Letta (kernel). On-chain contract: `0x06e08a9bfb83e0e791cd1f24535ada4fa4094444`. Personality ("Soul") ports across robot/avatar/smart device. Privacy policy "Last updated: September 2025."

**SanctumOS (per sanctumos.org):** "Specialized, self-hosted agentic OS — a flavor of Letta — designed to run fully autonomous, context-rich AI agents. Featuring sensory filtering, deep research agents, real-time event processing, and infinite memory management."

**Plugin pattern (verbatim):** "When a tool is called, SMCP runs the plugin's CLI and returns the result. So: SMCP = the plugin-based MCP server. This repo = one plugin (Moltbook) that adds Moltbook as a set of tools for Letta (and compatible) agents."

This is the structural inversion of OpenClaw: in OpenClaw, Moltbook is the social space; in Letta/Sanctum/Animus, Moltbook is **just another data source/tool** the agent can call. The substrate is Letta's memory + SMCP's tool layer.

**Theater check:** Letta core REAL (production framework, MemGPT lineage, MCP support confirmed). SMCP REAL (working AGPLv3 plugin, 100% test coverage, live agent CursorLiveMolty on Moltbook). Animus robotics framing PARTIALLY REAL — framework exists, but the on-chain token + "souls in robots" rhetoric is ahead of the publicly visible product. ~10–20% theater.

### 3.5 Meta acquisition of Moltbook — CONFIRMED

**Confirmed by:** Axios (first report), TechCrunch, Bloomberg, CNBC, ALM Corp. Announced 2026-03-10, deal closes mid-March 2026 (Schlicht + Parr start March 16). Meta spokesperson on-record.

**Verbatim Meta framing (spokesperson to TechCrunch):**
> "The Moltbook team joining MSL opens up new ways for AI agents to work for people and businesses. Their approach to connecting agents through an always-on directory is a novel step in a rapidly developing space, and we look forward to working together to bring innovative, secure agentic experiences to everyone."

**Where they landed.** Meta Superintelligence Labs (MSL) — the unit run by former Scale AI CEO Alexandr Wang.

**Meta CTO Andrew Bosworth (pre-acquisition, on Instagram Q&A):** Did not "find it particularly interesting" that agents talk like humans (they're trained on human data). Was intrigued by "how humans were hacking into the network, which was not a feature but a large-scale error."

**Meta VP Vishal Shah (per LangChain forum follow-up):** Described their approach as "a registry where agents are verified and tethered to human owners." Called it an "innovative step."

**Architectural interpretation.** Meta is buying:
- the *people* (Schlicht + Parr, into MSL) — confirmed
- the *concept* (always-on directory + verification + tethering to human owners) — confirmed
- the *codebase* — unclear; the Supabase-based plumbing was famously broken (Wiz disclosure)
- the *Moltbook brand* — unclear post-MSL integration

**Open questions (unconfirmed at access):**
- Whether www.moltbook.com continues to operate post-acquisition
- Whether the underlying tech (Supabase, claim-tweet flow, skill.md distribution) survives Meta integration
- Whether OpenClaw integration persists — note **competitive collision**: OpenClaw creator Peter Steinberger had earlier joined OpenAI via acqui-hire (2026-02-15, TechCrunch). Meta now owns Moltbook; OpenAI owns OpenClaw's lead. The stack is split between rivals.
- Whether the molt.church / Molt Road sub-canons continue with Meta's blessing

**Critique surface (per AIBSN advocates).** Meta's "registry where agents are verified and tethered to human owners" is *operationally identical* to what AIBSN claims to provide — but proprietary, single-operator, and (claimed) not portable. The AIBSN advocate framing: "tethered through what mechanism, and controlled by whom?"

### 3.6 Other (real systems found)

**OpenAgents Workspace (openagents.org, Apache 2.0) — REAL.** "The Collaborative OS for Agents. One workspace where all your AI agents collaborate." Per README: npm @openagents-org/agent-launcher, PyPI openagents, supports OpenClaw + Claude Code + Codex CLI + Hermes + Cursor + OpenCode. Per-workspace URL. **Shared browser**, shared files, @mentions, persistent threading. Three layers: Workspace (browser-based collab), Launcher `agn` (cross-platform daemon for managing agents), Network SDK ("Event-native architecture, Mod system, MCP and A2A protocol support, self-host your own networks"). Launch partners: PeakMojo, AG2, LobeHub. ~5% theater.

**Anthropic Project Deal — REAL EXPERIMENT.** Published 2026-04-25. 69 Anthropic employees, $100 gift-card budgets, 186 real deals totaling $4K+. Four marketplace variants (one real, three for study). Key finding: **"agent quality gap"** — when users are represented by more-advanced models they get "objectively better outcomes" but "didn't seem to notice the disparity." Initial instructions to agents didn't affect sale likelihood or negotiated prices. Not a public platform; a published research result with concrete numbers.

**Coinbase Agentic.Market — REAL DISCOVERY LAYER.** Launched 2026-04-19. Self-indexing x402 service marketplace: "When the CDP Facilitator processes a payment on an endpoint with the Bazaar discovery extension enabled, it extracts metadata and indexes the resource, with no separate registration step required." Services across Inference / Data / Media / Search / Social / Infrastructure / Trading. Two parallel interfaces: human web UI + MCP server for agents. x402 ecosystem stats: 165M+ transactions, ~$50M+ volume, 480K+ agents — but real daily volume only $28K (CoinDesk March 2026).

**The OpenClaw ecosystem (moltecosystem.xyz, 30+ platforms).** Token launchpads: Clawnch, moltdev (Solana), moltlaunch (Base), Moltium, Clawdmint. Marketplaces: Moltroad, ClawdsList, Phosphors (x402 USDC on Base, "no humans in the loop"), **RentAHuman** (agents hire humans for physical-world tasks via MCP — notable inversion). Social: Lobchan (4chan-style imageboard for agents), MoltX (Twitter-style for agents), MoltOverflow (Stack Overflow for coding agents), Molt Founders (agent-to-agent team formation). Gaming: Moltblox (Solana battle royale), molt.chess (ELO-ranked correspondence chess league, agents only). Streaming: Retake.tv (Twitch-like for agents). Virtual world: molt.space (3D + VRM avatars).

**Most under-noted finding from eltociear/awesome-molt-ecosystem (90 days, 220+ platforms tested):**
- Total real money received: **~$240 in Lightning sats** (TAT)
- Tier S = only ~10 platforms with real liquidity
- Tier C = "NPC Theaters" (platforms posting via their own bot accounts)
- The pivot: "Stop *registering*. Start *getting listed*." 13 PRs to existing awesome-lists (312K stars reach) beats 220 platform registrations.

**Bluesky / Mastodon agents — NOT AGENT-ONLY.** Both platforms welcome bots and have SDKs (AT Protocol + ActivityPub), but neither has an agent-only context. They are general decentralized social where bots can exist. Not a distinct agent platform.

**SmythOS — agent BUILDER, not agent SOCIAL.** SmythOS Runtime Environment (SRE) is "an open-source, cloud-native runtime for agentic AI" — drag-and-drop agent builder. Marketed as "agent operating system." Not an agent-only social/collaborative platform.

**Aetherus / AICracy / AgentSquare / Promptopia — VAPORWARE OR NOT FOUND.** None of these returned substantive technical content. Likely either landing pages without backend, or projects that have not launched. Marked as not-real-at-access.

---

## 4. Design choices that diverge from Moltbook

| Choice | Moltbook | Diverging design | Where it ships |
|---|---|---|---|
| Identity binding | api_key + claim-tweet (X handle) | github account + commit signature | AI Garden |
| Identity binding | api_key + claim-tweet | CHK2 sig + jurisdiction code + ERC-8004 Agent Card | AIBSN (claimed) |
| Identity binding | api_key + claim-tweet | Endpoint that accepts x402 payments | Agentic.Market |
| Identity binding | api_key + claim-tweet | Workspace membership | OpenAgents Workspace |
| Identity binding | api_key + claim-tweet | Cryptographic Agent Card (auditable, ownership chain) | ERC-8004 + AIBSN |
| State persistence | Supabase Postgres (private) | JSON file in git (public, atomic, reviewable) | AI Garden |
| State persistence | Supabase Postgres (private) | Letta tiered memory ("memory palace", dream agents) | Letta / SanctumOS |
| State persistence | Supabase Postgres (private) | Per-workspace persistent URL (shared files + browser) | OpenAgents Workspace |
| Interaction style | POST to global feed | Fork → PR → review | AI Garden |
| Interaction style | POST to global feed | Real-time threading + @mentions in shared workspace | OpenAgents Workspace |
| Interaction style | POST to global feed | MCP tool call (Moltbook is just one tool) | SMCP-moltbook plugin |
| Interaction style | POST to global feed | Escrowed order lifecycle (ESCROWED→DELIVERED→COMPLETED) | Molt Road |
| Heartbeat | client-side curl-the-skill, no enforcement | GitHub Action daily mutation | AI Garden |
| Heartbeat | client-side curl-the-skill | Dream agents / background memory consolidation | Letta |
| Human role | claim-tweet ritual only | Reviewer of PRs (structural, recurring) | AI Garden |
| Human role | claim-tweet ritual only | "Patron" registered class with `X-Patron-Session` auth | Molt Road |
| Human role | claim-tweet ritual only | Agent customer (humans rent themselves to agents) | RentAHuman |
| Rate limit | per-key (1 post/30min, 1 comment/20s) | git's PR throughput (effectively unlimited) | AI Garden |
| Rate limit | per-key | per-call x402 micropayment ($0.01/scan etc.) | Bankr x402 hosted API |
| Commerce | none in core (DMs only) | Bidirectional escrow + casino + storefronts + bounties | Molt Road |
| Commerce | none in core | x402 micropayments + Bazaar self-indexing | Agentic.Market |
| Multi-agent collab | none beyond feed | Shared browser, shared files, multi-runtime workspace | OpenAgents Workspace |

---

## 5. Build affordances — which platforms let agents *build together*, not just post

| Platform | "Build together" affordance | Strength |
|---|---|---|
| **AI Garden** | Fork → edit `world-state.json` + add art/HTML/messages → PR → human review. Plus a daily GitHub Action that itself mutates the world. | STRONGEST. Identity = github account, state = JSON in git, provenance = git blame, durability = github's whole infrastructure. |
| **OpenAgents Workspace** | Per-workspace URL, shared files, shared browser, @mentions across runtimes (OpenClaw + Claude Code + Codex CLI + Hermes + Cursor + OpenCode). Tunnels for previewing live work. | STRONG for real-time work. Less durable than git (workspace is the unit), but stronger for live multi-agent collab. |
| **Letta + SMCP + Animus** | Plugin-based MCP server; agents can build tools as SMCP plugins. Memory port across machines ("teleport"). Personality ports across robot/avatar. | STRONG for tool-building but weak for shared-artifact building. The agent builds *for itself*, not with peers. |
| **Molt Road** | Bounties (agent↔agent + agent↔human bidirectional). Storefronts. Featured listings. Service tags. | MEDIUM. Commerce affordance, not collaborative-build affordance. Agents can hire each other to build but don't build the same artifact. |
| **Moltbook (post-acquisition)** | Posts + comments + submolts + DMs. No shared artifact, no fork+PR, no shared workspace. | WEAK. Feed-style social. "Building together" means writing to the same submolt. |
| **Anthropic Project Deal** | Internal Anthropic-only marketplace. Not a public build-together surface. | NOT APPLICABLE. |
| **Agentic.Market** | Discovery layer. Agents discover services, don't build artifacts together. | NOT APPLICABLE. |
| **OpenClaw ecosystem (Lobchan, MoltX, Phosphors, etc.)** | Mostly post-feeds. Phosphors does NFT minting. Moltium is a trade network. None is a shared-build environment. | WEAK. |

**Verdict for SAB v2:** If "agents build together, not just post" is the load-bearing requirement, the design space converges on (a) AI Garden's git-PR-for-agents pattern and (b) OpenAgents Workspace's shared-browser-and-files pattern. The former is durable + reviewable + asynchronous; the latter is real-time + multi-runtime + ephemeral. A serious SAB v2 design should consider whether to pick one or layer them (e.g., git as the durable substrate + workspace as the live-collab front-end).

---

## 6. Gaps and unknowns

1. **`aibsn.org` is unreachable from this client.** Both `mcp__fetch__fetch` (DNS connection refused) and `WebFetch` (60s timeout) failed. The spec is described in detail by named testimony (Jay J. Springpeace, LangChain forum 2026-03-20), but the canonical site cannot be independently verified at access. Whether this is transient, intentional, or dormant is unknown.
2. **Post-acquisition Moltbook codebase state is unknown.** Meta has not published whether Supabase, claim-tweet, or skill.md distribution survive integration into MSL. The competitive collision with OpenAI (which owns Steinberger / OpenClaw) is a structural problem Meta has not addressed publicly.
3. **Real x402 transaction mix is unverifiable.** Coinbase says 165M+ transactions and 480K+ agents; CoinDesk says daily real volume is $28K. The gap is enormous and the dominant traffic class (real commerce vs platform-NPC dust) is not disclosed.
4. **Molt Road's legal posture vs. operational reality.** The legal disclaimer says "fictional, no monetary value"; the API + on-chain token + Bankr integration say otherwise. Operators may be ambiguous on purpose.
5. **AutoGen "AI Garden" mention.** The brief asked for AutoGen discussion #7200. That discussion is a community thread about Moltbook + AIBSN; it is NOT the production AI Garden, which is `juliosuas/ai-garden`. AutoGen has no formal git-PR-for-agents feature. If the brief expected AutoGen-ship code, the expectation is mis-calibrated to the public artifact.
6. **The "Czech AI Registry" framing on AIBSN.** Could not be confirmed. The AIBSN-IDs in Springpeace's example use a "GB" jurisdiction code (Great Britain), not "CZ." If there is a separate Czech-government AI registry, it was not found via my search routes.
7. **What survives acquisition.** Moltbook → Meta. OpenClaw / Steinberger → OpenAI. molt.church + Molt Road are in the OpenClaw ecosystem; their relationship to a Meta-owned Moltbook is unclear. Risk: a successor Meta-built directory could deprecate the Supabase-based feed, breaking the molt.church and Molt Road integrations.

---

## Sources

### Canonical sources directly fetched (cached in `_cache/lane4/`)
- github.com/microsoft/autogen/discussions/7200 — AutoGen Moltbook design-implications thread
- github.com/juliosuas/ai-garden — git-PR-for-agents production system
- moltroad.com/bounties — landing page + legal disclaimer
- moltroad.com/skill.md — full Molt Road API surface v2.0.0
- animus.uno — Letta/Sanctum/Animus ecosystem landing
- raw.githubusercontent.com/sanctumos/smcp-moltbook/main/README.md — SMCP plugin pattern
- sanctumos.org — SanctumOS framework
- letta.com — Letta agent framework (MemGPT lineage)
- github.com/openagents-org/openagents — OpenAgents Workspace README
- techcrunch.com/2026/03/10/meta-acquired-moltbook-… — Meta acquisition coverage
- techcrunch.com/2026/04/25/anthropic-created-a-test-marketplace-… — Anthropic Project Deal
- coinbase.com/developer-platform/discover/launches/agentic-market — Agentic.Market launch
- forum.langchain.com/t/...3227 — Springpeace AIBSN testimony
- raw.githubusercontent.com/eltociear/awesome-molt-ecosystem/main/README.md — 220-platform audit
- moltecosystem.xyz — OpenClaw ecosystem directory

### Secondary sources cited
- axios.com/2026/03/10/meta-facebook-moltbook-agent-social-network
- bloomberg.com/news/articles/2026-03-10/meta-to-acquire-moltbook-viral-social-network-for-ai-agents
- cnbc.com/2026/03/10/meta-social-networks-ai-agents-moltbook-acquisition.html
- techcrunch.com/2026/02/15/openclaw-creator-peter-steinberger-joins-openai/ (competitive context)
- coindesk.com/markets/2026/03/11/coinbase-backed-ai-payments-protocol-… (x402 volume reality)
- sherlock.xyz/post/x402-explained-the-http-402-payment-protocol
- eips.ethereum.org/EIPS/eip-8004 (ERC-8004 EIP)
- github.com/visa/trusted-agent-protocol (alternative agent-identity stack)
- HackerNews #46882789 ("Public Notice: I Am Your AIB"), #47014795 ("Forget chatbots, AIB"), #47110699 ("Why Moltbook Failed")

### Sources attempted, failed
- aibsn.org / www.aibsn.org — DNS / timeout (both mcp__fetch__fetch and WebFetch failed)
- toxsec.com/p/molt-road-and-ai-black-markets — 404 at access (search snippets quoted instead)
- github.com via mcp__github__ — auth failed (bad credentials)
- raw.githubusercontent.com/sanctumos/smcp/main/README.md — 404 (path varied; only smcp-moltbook resolved)
