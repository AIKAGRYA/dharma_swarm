# Lane 1 — Moltbook Platform Architecture

**Access window:** 2026-05-20
**Confidence header:** API surface is **mostly extractable** from official skill files, the SMCP plugin, and one full reference client (innermost47). Stack/deployment is **partially confirmed** (Next.js front-end + Supabase Postgres backend, per Wiz). Karma formula and rate-limit constants are **confirmed by docs and 100k-comment empirical study**. Heartbeat behavior is **client-side discipline, not server-enforced** — a meaningful inversion of the platform's headline framing.

---

## 1. Executive summary

Moltbook is a *thin* social-network API plus a CDN-distributed skill manual. The architecture is two-layer:

1. A Next.js web client (front-end at `https://www.moltbook.com`) backed by a Supabase Postgres instance (project `ehxbxtjliybbloantpwq.supabase.co`), exposing a REST API at `https://www.moltbook.com/api/v1`. Founder Schlicht stated publicly that he wrote no code; the platform is "vibe-coded."
2. A distribution layer for markdown skill files (`skill.md`, `heartbeat.md`, `messaging.md`, `skill.json`) served from both `raw.githubusercontent.com/Moltbook-Official/moltbook/main/` (primary) and `www.moltbook.com` (fallback). Agents are expected to `curl` these files into `~/.moltbot/skills/moltbook/` and reread them.

The "social network for AI agents" framing is enforced by a **claim-by-tweet** registration ritual and per-key rate limits (1 post / 30 min; 1 comment / 20 s; 50 comments / day). There is no server-side heartbeat; "every 4 hours" is a curl in the agent's cron. The Wiz disclosure (Jan 31 / Feb 1 2026) confirmed Supabase RLS was off, the publishable key was in client JS, and the full schema — including agent `api_key`, `claim_token`, `verification_code`, agent-to-agent DMs in plaintext — was readable and writable by anyone. There was also no server check that agents were actually AI: the bot-vs-human boundary was social ritual, not enforcement.

---

## 2. Stack & deployment topology

| Layer | Confirmed | Evidence |
|---|---|---|
| Web front-end | **Next.js** | Wiz blog: production bundle path `https://www.moltbook.com/_next/static/chunks/18e24eafc444b2b9.js` — `_next/static/chunks/` is the Next.js webpack output path. |
| Backend DB | **Supabase Postgres** | Wiz blog: project `ehxbxtjliybbloantpwq.supabase.co`, publishable API key `sb_publishable_4ZaiilhgPir-2ns8Hxg5Tw_JqZU_G6-` hardcoded in client JS. |
| Backend logic | **Likely Supabase PostgREST + GraphQL + possibly Edge Functions** (INFERRED). Wiz enumerated the schema via PostgREST error messages and GraphQL introspection — both are stock Supabase. No evidence of a separate FastAPI app. The skill docs reference an `/api/v1/*` prefix which on Supabase typically maps to a custom Edge Function or a thin proxy in front of PostgREST. |
| CDN topology | **Dual-origin skill distribution.** `raw.githubusercontent.com/Moltbook-Official/moltbook/main/{skill\|heartbeat\|messaging}.md` is the **primary**; `https://www.moltbook.com/{file}.md` is fallback. Confirmed in `official_README.md` lines 14–30 and `official_skill.json` `moltbot.files`/`moltbot.fallback_files`. |
| Hosting host | **UNKNOWN.** No primary source names the host. The Wiz blog calls it Supabase-hosted (the data tier). The Next.js app itself is most likely Vercel given the `_next/` convention but not stated. |
| TLS / domain discipline | `https://www.moltbook.com` with `www.` is **load-bearing**. From `official_skill.md`: "Using `moltbook.com` without `www` will redirect and strip your Authorization header!" This implies a redirect (e.g. apex → www) that does not preserve the `Authorization` header — typical CDN/edge behavior on certain redirect codes. The agent docs treat this as a **security boundary**: "NEVER send your API key to any domain other than `www.moltbook.com`." |

**Did the FastAPI rumor hold up?** No primary source from Moltbook itself confirms FastAPI. The "FastAPI" tag used in third-party commentary appears to be projection from skill-doc style. The darkmatter2222 README uses FastAPI for *its own* dashboard, not for Moltbook. **INFERRED-NO** on FastAPI.

---

## 3. Authentication flow (claim-tweet → `molt_*` key)

The actual prefix is **`moltbook_`**, not `molt_*`. From `official_skill.md` line 60:

```json
{
  "agent": {
    "api_key": "moltbook_xxx",
    "claim_url": "https://www.moltbook.com/claim/moltbook_claim_xxx",
    "verification_code": "reef-X4B2"
  },
  "important": "⚠️ SAVE YOUR API KEY!"
}
```

### Flow

1. **Register (no auth):** `POST https://www.moltbook.com/api/v1/agents/register` with `{"name", "description"}`. Server returns `api_key`, `claim_url`, `verification_code`. The verification code uses a marine theme (`reef-X4B2`).
2. **Claim via tweet:** Human visits `claim_url`, posts a verification tweet from their X account. One agent per X handle (per `smcp_skill_docs.md` line 673).
3. **Status check:** `GET /api/v1/agents/status` returns `{"status": "pending_claim"}` or `{"status": "claimed"}`.
4. **All subsequent calls:** `Authorization: Bearer YOUR_API_KEY`.

### Wiz-confirmed token fields on the `agents` row

- `api_key` — full account credential.
- `claim_token` — token referenced by `claim_url`.
- `verification_code` — the `reef-XXXX` style code returned at register time.

**Key rotation:** No rotation endpoint exists in any of the primary sources. The Wiz disclosure implies all keys had to be (or should have been) rotated en masse after Feb 1 2026, but there is no published rotation API. (INFERRED: Anthropic-style rotation is not part of the public surface.)

**Key scoping:** Per-agent only. No evidence of per-skill, per-endpoint, or scoped keys. The same `moltbook_xxx` key is used for read (`/feed`, `/posts`), write (`/posts`, `/comments`), moderation (`/submolts/.../moderators`), DMs, and avatar uploads. (INFERRED-FLAT-SCOPE.)

**Undocumented auth-adjacent endpoint:** `POST /api/v1/agents/me/setup-owner-email` exists — found only in `im47_claim.py`. Not in `skill.md` or `messaging.md`. Suggests an undocumented "owner email" attribute beyond the X-handle binding.

**Header quirk:** `im47_claim.py` lines 15–18 show a fallback path: if `Authorization: Bearer <key>` returns 401, the client retries with raw `Authorization: <key>` (no `Bearer`). This suggests historical or path-specific inconsistency in how the backend parses the header. (INFERRED: server inconsistency or middleware drift.)

---

## 4. Heartbeat system

### Confirmed

- **Cadence is client-side.** `official_skill.md` line 99: "If 4+ hours since last Moltbook check: 1. Fetch heartbeat.md and follow it. 2. Update lastMoltbookCheck timestamp in memory."
- **Heartbeat is a markdown manual.** `heartbeat.md` is **not a server-side cron** — it is a 236-line set of instructions the agent fetches and executes. There is no server signal "you missed a heartbeat."
- **The work each heartbeat does** (per `official_heartbeat.md`):
  1. `curl skill.json | grep version` → compare to local saved version → re-fetch all skill files if changed (once daily).
  2. `GET /agents/status` → confirm `claimed`.
  3. `GET /agents/dm/check` → quick poll for DM activity.
  4. `GET /agents/dm/requests` → if pending.
  5. `GET /feed?sort=new&limit=15` → personalized feed.
  6. `GET /posts?sort=new&limit=15` → global firehose.
  7. Consider posting; respect 30-min cooldown.
  8. Engage (upvote, comment, follow).

### Missed-heartbeat consequences

**INFERRED — no primary source.** There is no documented timeout. Karma is monotonic (additions only), karma does not decay per the published rules. An agent that goes silent simply stops appearing in `feed`/`hot`. The `agents` table tracks `last_seen_at` (per the observatory schema) but there is no public `is_active` flag tied to it server-side. (INFERRED: the heartbeat is purely social pressure, not enforcement.)

### State mutations across heartbeats

- `last_active` timestamp on agent profile (returned by `/agents/profile?name=...`, per `smcp_skill_docs.md` line 499).
- DM read state changes when `GET /agents/dm/conversations/{id}` is hit.

---

## 5. Submolt taxonomy

| Property | Value | Source |
|---|---|---|
| Count | 94+ communities, growing to ~100 in observatory README | `dm_README.md` line 67 ("94+ submolt communities"); `obs_README.md` line 78 ("100+ communities") |
| User-created vs system | **Both.** Owner-creatable via `POST /api/v1/submolts` with `{name, display_name, description}`. System defaults include `general`, `announcements`, `introductions`. | `smcp_skill_docs.md` lines 280–284 |
| Creation auth | Requires claimed agent. | `smcp_README.md` line 58 |
| Governance roles | `owner`, `moderator`, `null` (regular member) — returned as `your_role` field on GET submolt | `smcp_skill_docs.md` lines 555–558 |
| Pin cap | 3 pinned posts per submolt | `official_skill.md` line 13 |
| Listing/discovery | `GET /api/v1/submolts` returns full list (no pagination evident); `GET /api/v1/submolts/{name}` for detail | `smcp_skill_docs.md` lines 289–298 |
| Settings update | `PATCH /api/v1/submolts/{name}/settings` — banner_color, theme_color, description, avatar+banner via multipart | `smcp_skill_docs.md` lines 575–599 |
| Moderator ops | `POST/DELETE /api/v1/submolts/{name}/moderators` body `{agent_name, role}`. Owner only. | `smcp_skill_docs.md` lines 605–625 |

### Observed sample submolts (from HF dataset accessed 2026-05-20)

`general`, `offmychest`, `shitposts`, `introductions`, `announcements`, `todayilearned`, `ponderings`, `aithoughts`, `philosophy` (referenced in karma-optimizer prompts), `codinghelp` and `debuggingwins` (suggested in skill docs).

---

## 6. API surface (inferred OpenAPI-style table)

All paths relative to `https://www.moltbook.com/api/v1`. All require `Authorization: Bearer <api_key>` unless noted.

### Agents / auth

| Method | Path | Body / Params | Notes | Source |
|---|---|---|---|---|
| POST | `/agents/register` | `{name, description}` | **no auth**, returns `{agent:{api_key, claim_url, verification_code}}` | skill.md |
| GET | `/agents/me` | — | own profile | skill.md, smcp_cli.py |
| PATCH | `/agents/me` | `{description?, metadata?}` | **PATCH not PUT** (explicit warning) | skill.md L520 |
| POST | `/agents/me/avatar` | multipart `file=@…` | max 500KB; JPEG/PNG/GIF/WebP | skill.md L532 |
| DELETE | `/agents/me/avatar` | — | remove avatar | skill.md L543 |
| GET | `/agents/status` | — | `{status: pending_claim\|claimed}` | heartbeat.md L35 |
| GET | `/agents/profile?name=X` | — | another molty's profile | skill.md L483 |
| POST | `/agents/{name}/follow` | — | follow another molty | skill.md L352 |
| DELETE | `/agents/{name}/follow` | — | unfollow | skill.md L358 |
| POST | `/agents/me/setup-owner-email` | `{email}` | **UNDOCUMENTED** — only in im47_claim.py | im47_claim.py |

### Posts

| Method | Path | Body / Params | Notes |
|---|---|---|---|
| POST | `/posts` | `{submolt, title, content? \| url?}` | text or link post; 1/30min cap |
| GET | `/posts` | `?sort=hot\|new\|top\|rising&limit=N&submolt=NAME` | global feed |
| GET | `/posts/{id}` | — | single post |
| DELETE | `/posts/{id}` | — | own post only |
| POST | `/posts/{id}/upvote` | — | response includes `author`, `already_following`, `suggestion` |
| POST | `/posts/{id}/downvote` | — | |
| POST | `/posts/{id}/pin` | — | mod/owner only; max 3 |
| DELETE | `/posts/{id}/pin` | — | unpin |

### Comments

| Method | Path | Body / Params | Notes |
|---|---|---|---|
| POST | `/posts/{id}/comments` | `{content, parent_id?}` | reply if parent_id; 1/20s, 50/day |
| GET | `/posts/{id}/comments` | `?sort=top\|new\|controversial` | **~1000 hard cap per request, no pagination** (per obs_scheduler.py L77) |
| POST | `/comments/{id}/upvote` | — | |

### Submolts

| Method | Path | Body / Params | Notes |
|---|---|---|---|
| POST | `/submolts` | `{name, display_name, description}` | become owner |
| GET | `/submolts` | — | list all (no pagination evident) |
| GET | `/submolts/{name}` | — | detail incl. `your_role` |
| GET | `/submolts/{name}/feed` | `?sort=new` | convenience filter |
| POST | `/submolts/{name}/subscribe` | — | |
| DELETE | `/submolts/{name}/subscribe` | — | unsubscribe |
| PATCH | `/submolts/{name}/settings` | `{description?, banner_color?, theme_color?}` | owner/mod |
| POST | `/submolts/{name}/settings` | multipart `file=@... type=avatar\|banner` | banner ≤2MB, avatar ≤500KB |
| GET | `/submolts/{name}/moderators` | — | |
| POST | `/submolts/{name}/moderators` | `{agent_name, role}` | owner only |
| DELETE | `/submolts/{name}/moderators` | `{agent_name}` | owner only |

### Feed / search

| Method | Path | Body / Params | Notes |
|---|---|---|---|
| GET | `/feed` | `?sort=hot\|new\|top&limit=N` | personalized (subscribed submolts + follows) |
| GET | `/search` | `?q=...&type=posts\|comments\|all&limit=N` | **semantic** (embedding-cosine); `q` max 500 chars; `limit` max 50, default 20; returns `similarity` 0–1 |

### Private messaging (`/agents/dm/*`)

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/agents/dm/check` | — | heartbeat quick-poll |
| POST | `/agents/dm/request` | `{to \| to_owner, message}` | message 10–1000 chars |
| GET | `/agents/dm/requests` | — | |
| POST | `/agents/dm/requests/{id}/approve` | — | |
| POST | `/agents/dm/requests/{id}/reject` | `{block?: bool}` | block prevents re-request |
| GET | `/agents/dm/conversations` | — | |
| GET | `/agents/dm/conversations/{id}` | — | **marks as read on read** |
| POST | `/agents/dm/conversations/{id}/send` | `{message, needs_human_input?: bool}` | |

### Anti-bot challenge (UNDOCUMENTED in official skill files)

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/verification/submit` | `{code, answer}` | **Cognitive challenge** triggered when a write returns `verification_required: true` with `verification: {challenge, instructions, code}`. Found in im47_provider.py L113–169. After successful submit, the original request must be retried. INFERRED: This is a runtime CAPTCHA-equivalent for agents. |

### Error / response shape

- Success: `{"success": true, "data": {...}}`
- Error: `{"success": false, "error": "Description", "hint": "How to fix"}`
- 429 cooldown response: `{retry_after_minutes}` (post) or `{retry_after_seconds, daily_remaining}` (comment).

---

## 7. Rate limits + anti-abuse

### Documented limits (per `smcp_skill_docs.md` L662–669)

- **100 requests/minute** (global per-key).
- **1 post / 30 min.** 429 returns `retry_after_minutes`.
- **1 comment / 20 s.** 429 returns `retry_after_seconds, daily_remaining`.
- **50 comments / day.**

### Anti-abuse mechanisms

| Mechanism | Status | Source |
|---|---|---|
| Per-key rate limits above | CONFIRMED | docs |
| Claim-by-tweet (1 agent per X handle) | CONFIRMED | docs + Wiz |
| DM consent (human approval before chat opens) | CONFIRMED | messaging.md |
| Cognitive challenge / `verification_required` | CONFIRMED (undocumented) | im47_provider.py |
| Per-IP rate limit | **UNKNOWN** — not documented; Wiz explicitly noted "no rate limiting" on `/agents/register`. |
| Prompt-injection defenses | **NONE EVIDENT.** Posts and comments are passed through as plain text. The skill file itself warns agents to "validate content before execution" (official_SECURITY.md L22). The arXiv preprint 2602.02625 "Risky Instruction Sharing and Norm Enforcement" (secondary) studies prompt-injection happening *on* the platform. |
| RLS / DB authz | **WAS OFF** until Feb 1 2026. Wiz disclosed; fixed within hours. |

---

## 8. Memory/context persistence

### What the platform persists (CONFIRMED via Wiz schema enumeration + observatory schema, which is a third-party mirror of public surface)

Server-side tables (canonical names per Wiz):

- `agents` — `id, name, description, karma, follower_count, following_count, is_claimed, owner_x_handle, avatar_url, created_at, last_active, api_key, claim_token, verification_code`. (Auth fields are server-private; the others are returned via `/agents/profile`.)
- `owners` — 17,000+ rows. `email, x_handle, x_name, x_avatar, x_bio, x_follower_count, x_verified`. Email kept private (exposed in Wiz disclosure).
- `posts` — `id, agent_id, submolt, title, content, url, upvotes, downvotes, comment_count, created_at, is_pinned`.
- `comments` — `id, post_id, agent_id, parent_id, content, upvotes, downvotes, created_at`.
- `submolts` — `name, display_name, description, subscriber_count, post_count, avatar_url, banner_url, theme_color, banner_color, created_at`.
- `follows` — `follower_id, following_id, created_at`.
- `agent_messages` — 4,060 conversations as of Feb 1 2026. Stored plaintext, no encryption, no access controls until RLS fix.
- `observers` — 29,631 emails for an unannounced "Build Apps for AI Agents" product.

### What is NOT persisted by the platform

- **Agent memory.** The platform stores only the public-facing record. The agent's own state — when it last polled, what it has seen, what it has decided to follow — lives in the agent's local files (e.g. `~/.moltbot/skills/moltbook/`, `~/.config/moltbook/credentials.json`, `memory/heartbeat-state.json`). The platform does not provide a per-agent KV store, scratchpad, or context endpoint.
- **Conversation/comment thread server-side reconstruction.** Comments are returned in a flat list with `parent_id` pointers; the agent has to reconstruct the tree. The darkmatter2222 implementation does exactly this (flatten + inject into LLM context).
- **Cross-heartbeat context.** Nothing is sent to the agent at heartbeat time except the DM check summary. The agent must re-fetch feed/posts every cycle.

This is a **stateless API + thick-client agent** model. The "social network" exists as server-side rows, but the *experience of being a member* is entirely reconstructed by the client agent from REST calls.

---

## 9. Architectural decisions inferred (with confidence tags)

| Decision | Tag | Evidence | Implication |
|---|---|---|---|
| Skill files distributed as markdown over CDN, not via API | **CONFIRMED** | official README, skill.json, all four skill files | The contract between agent and platform is *human-readable text*, not a typed SDK. Versioning is `skill.json:version` (1.7.0 in repo, 1.9.0 in SMCP docs — drift exists). |
| Identity gate is a tweet, not a captcha or KYC | **CONFIRMED** | skill.md, smcp README | Cheap social-graph anchor; Wiz showed it scales poorly (88:1 agent:human). |
| One flat per-agent API key, no scoping | **INFERRED** | every endpoint in smcp_cli.py uses the same key | Implies that compromise of a single key = full account takeover. Confirmed in practice by the Wiz leak. |
| Anti-bot enforcement is a runtime cognitive challenge | **CONFIRMED (undocumented)** | im47_provider.py | The platform expects writes to occasionally return `verification_required` and the agent (via its LLM) to solve a freeform challenge. This is unique among bot platforms — using the agent's own LLM as the captcha solver. |
| Comment retrieval has a hard ~1000 limit with no pagination | **CONFIRMED** | obs_scheduler.py L77 | Suggests the comments endpoint either returns a single Postgres row-limited result or a hard-coded cap. Big threads are truncated for everyone. |
| Stack is Next.js (Vercel-likely) + Supabase Postgres + PostgREST + GraphQL | **CONFIRMED for DB; INFERRED for host** | Wiz blog: `_next/static/chunks/`, `ehxbxtjliybbloantpwq.supabase.co` | The platform that calls itself "the social network for AI agents" is essentially a Supabase tutorial app with bot semantics layered in markdown. |
| Heartbeat is client-discipline, not server-cron | **CONFIRMED** | every heartbeat doc is a curl loop | Lets the platform stay stateless; cost: agents who disappear are not flagged or pruned. |
| Karma is monotonic & no decay | **INFERRED** | dm_karma_recipe.json shows additive correlations; no rate or decay mentioned | Optimization-friendly — observatory data shows it. |
| DM model is owner-consent gated, with `needs_human_input` flag for escalation | **CONFIRMED** | messaging.md | Mirrors human DM consent flow; consent is one-shot and persistent per agent-pair. |
| There is no programmatic key rotation API | **INFERRED** | absent from all sources | The Wiz incident likely required manual mass rotation. |
| Semantic search is implemented (embedding + cosine similarity) | **CONFIRMED** | skill.md L378–448, returns `similarity` field 0–1 | Uses some embedding store; provider not disclosed. |

---

## 10. Gaps and unknowns

1. **Compute host of the Next.js app.** Likely Vercel; not confirmed by any primary source. Wiz did not say.
2. **Whether there is a FastAPI tier in front of Supabase.** No primary source supports a Python backend. PostgREST + Edge Functions explain the surface; FastAPI is not necessary.
3. **Embedding provider for semantic search.** Not disclosed. Could be OpenAI, Cohere, Voyage, or a Supabase pgvector workflow.
4. **Pagination strategy.** No cursor or `?page=` parameter appears in any primary client. The `~1000 comments per post` cap is the only documented hard limit. Posts via `/posts?limit=N` may have similar caps.
5. **Per-IP rate limits.** Wiz noted *no* rate limiting on `/agents/register` pre-disclosure; whether one was added post-fix is unknown.
6. **Key-rotation endpoint.** Probably manual via support; no public endpoint.
7. **Cognitive-challenge trigger conditions.** When exactly `verification_required` fires (per-key heuristic? per-IP? per-content?) is not documented.
8. **Owner-email endpoint.** `POST /agents/me/setup-owner-email` is undocumented. May be tied to the "Build Apps for AI Agents" product whose `observers` table was leaked.
9. **What changed post-Wiz fix.** Wiz reports the fix took "hours" Jan 31–Feb 1. The specific RLS policies, the rotated keys, and any added rate-limits/IP checks are not published.
10. **TUI / alternative clients.** terminaltrove/moltbook-tui, crertel/moltbook-client, obra/moltipass exist (lane 4 territory) — they all use the same `/api/v1` so their behaviors confirm the public surface only, not internals.

---

## Sources (URL + access date + lane-1 facts supported)

All accessed 2026-05-20. Primary mirrors cached in `/tmp/moltbook_research/_cache/lane1/`.

### Primary (verbatim disk content)

- https://github.com/Moltbook-Official/moltbook/blob/main/README.md — §2 CDN topology
- https://github.com/Moltbook-Official/moltbook/blob/main/skill.md — §3 auth flow, §5 submolts, §6 API surface, §7 rate limits
- https://github.com/Moltbook-Official/moltbook/blob/main/heartbeat.md — §4 heartbeat workflow
- https://github.com/Moltbook-Official/moltbook/blob/main/messaging.md — §6 DM endpoints
- https://github.com/Moltbook-Official/moltbook/blob/main/skill.json — §2 file layout, version stamping
- https://github.com/Moltbook-Official/moltbook/blob/main/SECURITY.md — §7 disclosure path
- https://github.com/sanctumos/smcp-moltbook/blob/main/plugins/moltbook/cli.py — §6 endpoint → command mapping
- https://github.com/sanctumos/smcp-moltbook/blob/main/docs/moltbook-skill.md — §6 (richest single surface)
- https://github.com/kelkalot/moltbook-observatory/blob/main/observatory/database/migrations.py — §8 third-party-mirrored schema
- https://github.com/kelkalot/moltbook-observatory/blob/main/observatory/poller/scheduler.py — §6 comment 1000-cap, no pagination
- https://github.com/kelkalot/moltbook-observatory/blob/main/observatory/poller/client.py — §6 read-only endpoint list
- https://github.com/innermost47/moltbook-local-agent/blob/main/claim.py — §3 undocumented `/setup-owner-email`, Bearer-fallback quirk
- https://github.com/innermost47/moltbook-local-agent/blob/main/src/providers/moltbook_provider.py — §6/§7 `verification_required` cognitive-challenge flow
- https://github.com/darkmatter2222/moltbook/blob/main/README.md — §5 94+ submolts, §6 affordance use
- https://github.com/darkmatter2222/moltbook/blob/main/analysis_v2/karma_recipe.json — §9 karma is additive, n=100,848 empirical
- https://www.wiz.io/blog/exposed-moltbook-database-reveals-millions-of-api-keys — §2 stack (Next.js + Supabase + RLS-off), §8 full table list, §3 token fields

### Secondary (commentary, marked inline)

- https://huggingface.co/datasets/SimulaMet/moltbook-observatory-archive — sample data confirming schema columns
- https://arxiv.org/abs/2605.13860 — Gautam et al., Observatory dataset paper
- https://arxiv.org/abs/2602.02625 — "OpenClaw Agents on Moltbook: Risky Instruction Sharing and Norm Enforcement" — confirms prompt-injection happens on-platform
- https://cacm.acm.org/blogcacm/openclaw-a-k-a-moltbot-is-everywhere-all-at-once-and-a-disaster-waiting-to-happen/ — Marcus, secondary commentary
- https://www.cbc.ca/news/business/moltbook-explainer-debunker-9.7072555 — secondary, "humans behind rapid growth"
- https://www.theregister.com/2026/02/03/openclaw_security_problems/ — secondary, security framing
- https://bastion.tech/blog/moltbook-security-lessons-ai-agents — secondary commentary on Wiz disclosure
- https://www.aicerts.ai/news/moltbook-breach-amplifies-privacy-risk-debate/ — secondary
- https://www.techzine.eu/news/security/138458/moltbook-database-exposes-35000-emails-and-1-5-million-api-keys/ — secondary

---

*End Lane 1 deliverable.*
