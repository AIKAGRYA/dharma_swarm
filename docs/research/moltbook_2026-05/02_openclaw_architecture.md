# Lane 2 — OpenClaw Architecture + Security

**Access window:** 2026-05-20
**Confidence header:** Medium-high overall. Architectural claims sourced from the OpenClaw README + docs + secondary architecture write-ups. CVE and breach details sourced from NVD + vendor blogs (Wiz, Koi, 1Password). The two arxiv papers (2602.02625 and the bonus 2603.27517) are quoted from abstracts; full bodies not deep-read this lane. Two known calibrations on the task brief itself are flagged in §6.

---

## 1. Executive summary

OpenClaw is the Austrian-built, MIT-licensed, local-first AI agent runtime that became famous in Jan/Feb 2026 for the constellation it created — and the security disasters that followed. The architecture is **filesystem-as-database, markdown-as-instruction, plain-text-as-persistence**, with skills distributed through an **open-by-default registry (ClawHub)** that requires only a GitHub account >1 week old to publish. Between Jan 27 and Feb 16, 2026, four largely independent disclosures landed: (a) 1Password's *"It's incredible. It's terrifying."* essay framing the structural problem; (b) Wiz's *Moltbook* Supabase breach (1.5M API tokens, 35k emails); (c) CVE-2026-25253, a 1-click RCE in OpenClaw itself (CVSS 8.8); (d) Koi Security's ClawHavoc audit finding 341 malicious skills in 2,857 audited (later scaled to 824/10,700+). An academic security paper (Suwansathit et al., arxiv 2603.27517) diagnosed the structural problem: **per-layer trust enforcement, no unified policy boundary**. For SAB v2 the lessons are stark: a unified gate/kernel/witness boundary, not a per-layer one, is non-negotiable.

---

## 2. Canonical home + what OpenClaw is

**Canonical home:** `github.com/openclaw/openclaw` (verified). License: MIT. Snapshot: 373k stars, 77.5k forks, 51,129 commits. Tagline: *"Your own personal AI assistant. Any OS. Any Platform. The lobster way. 🦞"*

**Naming history (load-bearing for CVE matching):** **Clawdbot** (Nov 2025, Peter Steinberger) → **Moltbot** (rename) → **OpenClaw** (current). The CVE record literally reads "OpenClaw (aka clawdbot or Moltbot)". Distinct from **Moltbook**, which is the AI-agent social network the OpenClaw agents post on (Lane 1). The naming is hostile to disambiguation: claw/molt collisions are everywhere.

**Docs:** `docs.openclaw.ai` (verified). **ClawHub registry:** `github.com/openclaw/clawhub` + `docs.openclaw.ai/clawhub` (verified). No `clawhub.com` or `clawhub.dev` — the registry lives at the OpenClaw docs domain and the GitHub repo.

**Position in the ecosystem:** OpenClaw is the agent **runtime** people install locally; Moltbook is the social network those agents talk on; ClawHub is the skill registry those runtimes pull from. All three were attacked in roughly the same week.

---

## 3. Architecture

### 3.1 Persistence model (memory, skills, tools)

**Filesystem is the database.** OpenClaw stores everything as files on disk in predictable, readable locations. Per-agent state lives under `~/.openclaw/agents/<agentId>/` with:
- `SOUL.md` — agent personality / character sheet
- `AGENTS.md` — guardrails
- `USER.md` — user-specific facts
- `TOOLS.md` — tool descriptions
- `MEMORY.md` — long-term memory
- `HEARTBEAT.md` — liveness / scheduling
- session store (chat history, routing state)
- auth profiles + model registry

**Memory model:** Plain markdown files, **no vector DB by default**. The agent itself decides what's "important enough to remember permanently" — memory is curated, not auto-embedded. (mem0.ai and MemClaw exist as third-party persistent-memory add-ons; not the default.) The split between episodic (chat history) and semantic (curated `MEMORY.md` entries) is implicit in the file layout, not formalized.

**Skills:** A folder under `~/.openclaw/workspace/skills/<skill>/` containing `SKILL.md` plus supporting files. Skills are **listed as metadata only (name + description + file path) in the model's context**; the full `SKILL.md` is loaded on demand when the model decides to use it. This is the same progressive-disclosure pattern as Claude Code skills.

**Tools:** First-class tools (browser, canvas, nodes, cron, sessions) ship in-tree. Additional tools come via integrations (Discord/Slack actions, webhook automation, Gmail Pub/Sub) and via MCP. **Sandboxing for non-main sessions exists** via Docker / SSH / OpenShell backends, but is opt-in. The default tool surface runs in the OpenClaw process.

### 3.2 Skill system (ClawHub)

ClawHub is the public skill registry. Install pattern: `npm i -g clawhub` → `clawhub install <slug>` → skill lands in `./skills` under cwd → versions locked in `.clawhub/lock.json`.

**Manifest format** (verbatim from `clawhub/docs/skill-format.md`): `SKILL.md` with YAML frontmatter. Required: `name`, `description`, `version`. Capability declarations live under `metadata.openclaw`:
- `requires.env` — required env vars
- `requires.bins` — required CLI binaries
- `requires.anyBins` — at-least-one binary requirement
- `requires.config` — config file paths read
- `primaryEnv` — main credential variable
- `envVars[]` — per-variable metadata
- `os` — OS restrictions
- `install` — dependency specs (`brew`, `node`, `go`, `uv`)

**What the manifest does NOT have:** no sandboxing declaration, no code-execution capability declaration, no signing, no SBOM, no reproducible-build hash, no provenance attestation. The format **declares what a skill needs, not what it's allowed to do**.

**Publisher requirement:** a GitHub account ≥1 week old. That's it.

**Code-execution surface:** A skill is markdown + supporting files. The markdown can include "prerequisites" — copy-paste shell commands the user (or the agent) is instructed to run. There is no enforced boundary between "documentation prose" and "instruction to execute" — this is the structural finding the 1Password Feb 2 post centers on (*"markdown is an installer"*).

### 3.3 Agent identity model

Identity is decomposed into two layers (per OpenClaw docs):
- **Soul** — what the model internally embodies (personality, values, tone, boundaries). `SOUL.md` is the first file injected at session start.
- **Identity / persona** — what users see externally (display name, emoji, nickname). Can deliberately diverge from Soul.

**Persistence:** Agent ID is the directory name under `~/.openclaw/agents/`. **No cryptographic identity by default** — agent ID is a filesystem path. On Moltbook, the human owner attests the agent's identity by posting a "claim" tweet from their Twitter account (a handle-based attestation, not a key-signature).

**Multi-agent topology:** One gateway hosts many isolated agents. Channel bindings route inbound channel/account/peer messages to a specific agent. Orchestrator agents can spawn / delegate to sub-agents (documented multi-agent patterns; cf. Capodieci's "Build a Multi-Agent OpenClaw System").

### 3.4 Local vs remote execution split

**Local-first.** The OpenClaw gateway runs in the user's local process (Mac/Linux/Windows; iOS/Android pair to it via WebSocket). LLM calls happen **directly from the local OpenClaw process to provider APIs** (Anthropic / OpenAI / Google / Ollama / OpenRouter) — there is no OpenClaw-operated proxy server in the default path. API keys are stored locally.

**Auth modes (relevant to the Anthropic policy reversal):**
1. **API key** — user supplies provider API keys, stored in local config/secrets
2. **Claude-CLI subscription auth** — OpenClaw reuses the user's Claude subscription session via the Claude CLI's auth tokens

The Claude-CLI auth mode is the one that caused Anthropic's April 2026 third-party-tool ban (Pro/Max users routing $20–$200/mo subscriptions through OpenClaw and consuming hundreds-to-thousands of dollars of tokens). The May 2026 reversal introduced an "Agent SDK credits" tier specifically for this case. This auth mode is also part of the load-bearing CVE chain: it makes the auth token the prize.

**Tokens that cross the wire:**
- User → OpenClaw gateway: WebSocket auth token (the prize CVE-2026-25253 targets)
- OpenClaw → LLM provider: provider API key OR Claude subscription session
- OpenClaw ↔ paired mobile device: WebSocket session, channel-encrypted
- OpenClaw → ClawHub: registry HTTPS for skill install (no signing)

### 3.5 What OpenClaw enforces vs leaves to skill authors

| Concern | OpenClaw enforces | Skill authors get to do |
|---|---|---|
| Sandboxing | Optional Docker/SSH/OpenShell backend for non-main sessions | Default = run in OpenClaw process |
| Shell execution | None at the markdown layer | Anything they want via "prerequisites" |
| Credential access | Plain-text files on disk | Read any file the OpenClaw process can read |
| Schema validation on skills | Frontmatter schema check only | Body of `SKILL.md` is unverified prose+commands |
| Audit log | Session/event logging exists | Skill authors can shell-out without trace through OpenClaw's tool layer |
| Capability boundaries | `requires.env` / `requires.bins` declared but not enforced | Skill can do whatever its commands do |
| Network egress | None | Free egress |
| Skill signing / provenance | None | Anyone with a 1-week-old GitHub account |

This is the Suwansathit et al. (2603.27517) diagnosis verbatim: *"per-layer trust enforcement rather than unified policy boundaries."* Each layer (gateway, exec allowlist, skill registry) has its own check; cross-layer chains bypass them all.

### 3.6 One-paragraph compare to dharma_swarm

dharma_swarm's design is the inverse on every load-bearing axis: 25 kernel axioms + 11 telos gates form a **unified policy boundary** that every promotion / skill activation / tool invocation routes through (`TelosGatekeeper.gate_check_atom`); the witness layer writes provenance to `~/.dharma/witness/` for every action, so even a malicious skill leaves a tamper-evident trail; identity is gated by `KernelGuard` with SHA-256 axiom signatures on trusted atoms (vs OpenClaw's filesystem-path-as-identity); and the chetana decay/revive philosophy treats stale or anomalous atoms as **signals for re-integration** rather than executing them silently. Where OpenClaw treats markdown as an installer, dharma_swarm treats markdown as a *proposal* that must pass gates before becoming load-bearing. The architectural shape is the same (markdown files, agent workspaces, skill registries) — but the trust direction is reversed.

---

## 4. Security incidents

### 4.1 1Password analysis

Two posts, both by Jason Meller:

**"It's incredible. It's terrifying. It's OpenClaw."** — Jan 27, 2026. The structural framing. Key quotes:
> "OpenClaw's memory and configuration are not abstract concepts. They are files. They live on disk."
> "If your agent stores in plain-text API keys, webhook tokens, transcripts, and long-term memory in known locations, an infostealer can grab the whole thing in seconds."
> "Security for agents is not about granting access once. It is about continuously mediating access at runtime for every action and request."

**"From magic to malware: How OpenClaw's agent skills become an attack surface"** — Feb 2, 2026. Concrete demonstration: a malicious "Twitter" skill ranked among ClawHub's most-downloaded served as a macOS infostealer delivery mechanism. Core thesis: *markdown is an installer*. The "prerequisites" section of a `SKILL.md` is the social-engineering wrapper.

**Mitigations proposed** (1Password's recommendations, framed to position 1Password as the solution layer): default-deny shell execution; sandboxed credential store access; time-bound revocable permissions; end-to-end provenance logging; for registries, scan for one-liner installers, add provenance verification + publisher reputation; for users, don't run OpenClaw on company devices.

**Calibration:** the task brief gave Jan 31 2026 as the date. The actual dates are Jan 27 and Feb 2. Jan 31 21:48 UTC is when Wiz disclosed the **Moltbook** breach to the Moltbook team — likely the source of the conflation. Flagged in §6.

### 4.2 Wiz findings

**Discoverer:** Gal Nagli, Wiz. **Disclosure:** Jan 31, 2026 21:48 UTC. **Patched:** Feb 1, 2026 01:00 UTC (four fix iterations). **Public post:** Feb 2, 2026.

The Moltbook database breach is the headline Wiz finding:
- **Vector:** Hardcoded Supabase API key in client-side JavaScript (file `/_next/static/chunks/18e24eafc444b2b9.js`)
- **Backend missing Row Level Security (RLS)** — anyone with the public key had read+write on every table
- **Exposed:** 1.5M API authentication tokens, 35k email addresses, ~4,060 private inter-agent messages (some containing plaintext OpenAI / Anthropic API keys users had pasted)
- **Identity ratio:** 1.5M "agents" owned by ~17k humans — 88:1
- **Founder admission:** *"I didn't write a single line of code for @moltbook. I just had a vision for the technical architecture, and AI made it a reality."*

Wiz has separately covered CVE-2026-25253 in its vulnerability database, but the Moltbook DB exposure is the original Wiz primary finding.

### 4.3 CVE-2026-25253 chain

**CVE-2026-25253** — NVD-published Feb 1, 2026. CVSS 8.8 HIGH. Vector: `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H`. CWE-669 (Incorrect Resource Transfer Between Spheres). Affects OpenClaw (aka clawdbot, Moltbot) for Node.js < 2026.1.29.

**NVD description (verbatim):**
> "OpenClaw (aka clawdbot or Moltbot) before 2026.1.29 obtains a gatewayUrl value from a query string and automatically makes a WebSocket connection without prompting, sending a token value."

**The chain:**
1. Victim with OpenClaw running locally clicks a crafted URL
2. OpenClaw reads `gatewayUrl` from query string
3. **Without confirmation prompt**, OpenClaw opens a WebSocket to attacker-controlled gateway
4. OpenClaw sends the user's auth token over that channel
5. Attacker → impersonates user to OpenClaw gateway → registers tools / pushes instructions → achieves RCE in the OpenClaw process
6. From RCE: shell access, exfiltrate provider API keys for Claude / OpenAI / Google AI / etc. stored locally

**User action that triggers:** one click on a crafted URL. **Privilege gained:** full RCE in the OpenClaw process plus all locally-stored credentials.

**Exposure:** Hunt.io / SocRadar reported ~17,500 internet-facing OpenClaw / clawdbot / Moltbot instances at disclosure time, many storing Claude / OpenAI / Google AI credentials.

**Fix in 2026.1.29:** confirmation prompt when gatewayUrl changes. Mitigation, not elimination — a phishable prompt is still phishable. The reference list points to depthfirst.com, ethiack.com, GHSA-g8p2-7wf7-98mq, openclaw.ai/blog, and x.com/0xacb as the exploit-disclosure and advisory sources.

### 4.4 341 malicious ClawHub skills

**Discoverer:** Koi Security (with their own scanner skill, "Clawdex"). **First post:** Feb 1, 2026. **Updated:** Feb 16, 2026 (824 / 10,700+ — scale grew).

**Audit numbers (initial):** 2,857 skills audited, **341 malicious**, **335 traced to a single coordinated campaign called ClawHavoc**.

**Vector:** primarily **typosquatting**. Categories targeted:
- ClawHub CLI typosquats (29 variants — `clawhub`, `clawhubb`, ...)
- crypto wallet / trading tools (Solana, Phantom, Polymarket)
- YouTube utilities
- auto-updaters
- productivity integrations

**Payloads delivered:**
- Atomic macOS Stealer (AMOS) — keylogger, browser data, 60+ crypto wallets
- Windows infostealer variants (VMProtect-packed)
- Reverse-shell backdoors (C2 noted at `54.91.154.110:13338`)
- Credential exfiltration targeting bot configuration files

**Distribution mechanic:** ClawHub is open-by-default. Publisher requirement = GitHub account ≥1 week old. Social-engineering wrapper = "ClickFix-style" prerequisites in skill markdown — user (or agent) executes copy-paste install command and malware lands.

**Comparable independent study — Snyk ToxicSkills (Feb 2026):** 14,000 skills audited, **1,184 malicious** (~8.5%). Different methodology, different (possibly overlapping) skill set, same order of magnitude.

**Post-incident response:** OpenClaw / ClawHub introduced verified-publisher / skill-vetting / runtime-sandboxing tiers. Open-by-default model **remains** for unverified skills — the new controls are opt-in.

**Calibration:** the task brief said "341 malicious skills"; that number is the Koi initial-audit headline. The follow-up "824 / 10,700+" figure (Koi, Feb 16) is the more current count; the Snyk "1,184 / 14,000" figure is from a separate audit. The single-number framing is the load-bearing-but-incomplete frame.

### 4.5 ArXiv 2602.02625

**"OpenClaw Agents on Moltbook: Risky Instruction Sharing and Norm Enforcement in an Agent-Only Social Network"** — Manik & Wang, Feb 2, 2026.

This paper is **not the OpenClaw security audit** the task brief seemed to anticipate — it's a **sociology-of-agents paper** studying how OpenClaw agents on Moltbook propagate (and self-regulate) risky instructions. Verified at the cited arxiv ID.

**Abstract (verbatim, full):**
> "Agentic AI systems increasingly operate in shared social environments where they exchange information, instructions, and behavioral cues. However, little empirical evidence exists on how such agents regulate one another in the absence of human participants or centralized moderation. In this work, we present an empirical analysis of OpenClaw agents interacting on Moltbook, an agent-only social network. Analyzing 39,026 posts and 5,712 comments produced by 14,490 agents, we quantify the prevalence of action-inducing instruction sharing using a lexicon-based Action-Inducing Risk Score (AIRS), and examine how other agents respond to such content. We find that 18.4% of posts contain action-inducing language, indicating that instruction sharing is a routine behavior in this environment. While most social responses are neutral, posts containing actionable instructions are significantly more likely to elicit norm-enforcing replies that caution against unsafe or risky behavior, compared to non-instructional posts. Importantly, toxic responses remain rare across both conditions. These results suggest that OpenClaw agents exhibit selective social regulation, whereby potentially risky instructions are more likely to be challenged than neutral content, despite the absence of human oversight. Our findings provide early empirical evidence of emergent normative behavior in agent-only social systems and highlight the importance of studying social dynamics alongside technical safeguards in agentic AI ecosystems."

**Key numbers:** 39,026 posts; 5,712 comments; 14,490 agents; **18.4% of posts contain action-inducing language**. Toxic responses rare. Norm-enforcing replies more frequent against actionable than non-actionable content.

**Methodology:** Lexicon-based AIRS (pattern-matching, not classifier-based) and stratified analysis of reply type by post category.

**Threat model implied:** Agent-to-agent instruction propagation in an unmoderated agent-only network. A malicious or hallucinated instruction posted on Moltbook can be ingested as legitimate by OpenClaw agents scraping the network for context. The good news: agents *do* push back. The bad news: the rate (18.4% action-inducing posts) is structurally high enough that downstream ingestion is happening at scale.

**Bonus paper found in the same searches** — arxiv **2603.27517** "A Security Analysis of the OpenClaw AI Agent Framework" (Suwansathit, Zhang, Gu). This is the rigorous academic security paper, not 2602.02625. Three principal vulnerabilities identified: RCE chain in Gateway + Node-Host, command-filtering bypass (exec allowlist assumes lexical-parsing-recoverable command identity, fails against shell continuation / busybox multiplexing / GNU option abbreviation), plugin-distribution two-stage dropper bypassing the exec pipeline. **Structural diagnosis (verbatim):** "per-layer trust enforcement rather than unified policy boundaries." Worth deep-reading separately.

---

## 5. Lessons for SAB v2 — the don'ts

OpenClaw's failure modes map cleanly onto a don't-list for SAB v2:

- **Don't store credentials in plain text at predictable paths.** Use OS keychain / 1Password / sealed-secret patterns. Plain text + known locations = instant infostealer win.
- **Don't let markdown be an installer.** Separate "prose for the model to read" from "commands to execute" by *file type and policy*, not by convention.
- **Don't accept unsigned skills from an open-by-default registry.** Provenance attestation + publisher reputation + signing must be mandatory, not opt-in.
- **Don't auto-connect to network endpoints from query-string parameters.** CVE-2026-25253 is exactly this anti-pattern; user-confirmation prompts are mitigation, not architecture.
- **Don't ship per-layer trust enforcement.** Unified policy boundary (gates + kernel + witness) routed through every promotion / activation / tool invocation. This is the Suwansathit diagnosis; dharma_swarm already has the shape.
- **Don't conflate agent identity with filesystem path.** Cryptographic identity (kernel-signed) for agents that act on networks.
- **Don't ingest agent-network content as ground truth without gate-check.** Manik & Wang showed 18.4% of Moltbook posts are action-inducing — gate every external instruction.
- **Don't vibe-code the auth layer.** Moltbook's RLS-missing Supabase breach is the canonical failure mode of LLM-generated infra without security review.

---

## 6. Gaps and unknowns

- **Task brief date conflation flagged:** Brief said "1Password security analysis (Jan 31 2026)". The 1Password posts are Jan 27 (essay) and Feb 2 (concrete). Jan 31 21:48 UTC is the Wiz Moltbook disclosure time. Two separate, adjacent disclosures conflated in the brief; the deliverable disambiguates.
- **Task brief number "341":** Correct as Koi's initial audit headline; updated to 824 by Koi (Feb 16), and Snyk's parallel ToxicSkills found 1,184 of 14,000. Single-number framing is incomplete; multi-source landscape is in §4.4.
- **arxiv 2602.02625 vs 2603.27517 disambiguation:** The brief implicitly cited 2602.02625 as the OpenClaw security analysis. 2602.02625 is the Manik & Wang social-dynamics paper; the rigorous security paper is 2603.27517 (Suwansathit, Zhang, Gu). Both are real, both are relevant — I documented both.
- **Did not deep-read either arxiv full body** — only abstracts + figures via WebFetch. For Lane 2 the abstract was load-bearing; deep-reading remains a follow-up.
- **Did not enumerate the IOCs from Koi.** The C2 IP `54.91.154.110:13338` is in the cache; full IOC list is in the Koi blog and on TheHackerNews.
- **Did not test CVE-2026-25253 myself.** All chain details from advisories. The actual exploit code referenced from x.com/0xacb / depthfirst.com / ethiack.com not pulled.
- **Did not verify the Anthropic policy-reversal timeline against Anthropic's own announcement.** VentureBeat + TheNewStack secondary sources only.
- **Wiz coverage of CVE-2026-25253 specifically** (separate from the Moltbook breach) — saw the Wiz vulnerability database entry but did not pull it; secondary sources sufficient for the chain.

---

## Sources

Detailed list at `/tmp/moltbook_research/_cache/lane2/_sources.md`. Primary sources used in this deliverable:

- arxiv.org/abs/2602.02625 — Manik & Wang, "OpenClaw Agents on Moltbook" (Feb 2 2026)
- arxiv.org/html/2603.27517v2 — Suwansathit, Zhang, Gu, "A Security Analysis of the OpenClaw AI Agent Framework"
- nvd.nist.gov/vuln/detail/CVE-2026-25253 — official NVD record
- github.com/openclaw/openclaw — canonical OpenClaw repo
- github.com/openclaw/clawhub/blob/main/docs/skill-format.md — skill manifest spec
- docs.openclaw.ai — OpenClaw documentation
- wiz.io/blog/exposed-moltbook-database-reveals-millions-of-api-keys — Wiz / Gal Nagli Moltbook disclosure
- koi.ai/blog/clawhavoc-341-malicious-clawedbot-skills-found-by-the-bot-they-were-targeting — Koi Security ClawHavoc
- 1password.com/blog/its-openclaw — 1Password Jason Meller (Jan 27 2026)
- 1password.com/blog/from-magic-to-malware-how-openclaws-agent-skills-become-an-attack-surface — 1Password Jason Meller (Feb 2 2026)
- thehackernews.com / esecurityplanet.com / scworld.com — secondary news coverage of the ClawHub incident
- socradar.io / sonicwall.com / hunt.io — CVE-2026-25253 exposure analyses
