# Lane 1 — Sources Index

Access date: 2026-05-20

## Primary sources (verbatim from disk)

| File | URL | Bytes | Supports |
|------|-----|-------|----------|
| `official_README.md` | github.com/Moltbook-Official/moltbook/blob/main/README.md | 2450 | CDN topology, GitHub mirror, fallback URLs |
| `official_skill.md` | github.com/Moltbook-Official/moltbook/blob/main/skill.md | 3186 | API base, registration, rate limits, claim flow |
| `official_heartbeat.md` | github.com/Moltbook-Official/moltbook/blob/main/heartbeat.md | 7319 | Heartbeat endpoints, every-4-hour cadence, DM check |
| `official_messaging.md` | github.com/Moltbook-Official/moltbook/blob/main/messaging.md | 8139 | Full DM/`/dm/*` surface, consent model |
| `official_skill.json` | github.com/Moltbook-Official/moltbook/blob/main/skill.json | 1361 | api_base, version=1.7.0, triggers |
| `official_SECURITY.md` | github.com/Moltbook-Official/moltbook/blob/main/SECURITY.md | 713 | security@moltbook.com disclosure |
| `obs_migrations.py` | github.com/kelkalot/moltbook-observatory/blob/main/observatory/database/migrations.py | 4126 | SQLite schema (agents/posts/comments/submolts/follows/snapshots) |
| `obs_poller_client.py` | github.com/kelkalot/moltbook-observatory/blob/main/observatory/poller/client.py | 3861 | Read-only endpoints used by an observer |
| `obs_scheduler.py` | github.com/kelkalot/moltbook-observatory/blob/main/observatory/poller/scheduler.py | 6860 | Reveals API comment limit ~1000 per request, no pagination |
| `obs_processors.py` | github.com/kelkalot/moltbook-observatory/blob/main/observatory/poller/processors.py | 11612 | Response shape: `author` (with id) vs `agent`, `submolt` as dict or string |
| `obs_README.md` | github.com/kelkalot/moltbook-observatory/blob/main/README.md | 12056 | Polling cadence as 3rd-party observer, dataset stats |
| `smcp_README.md` | github.com/sanctumos/smcp-moltbook/blob/main/README.md | 5210 | SMCP plugin context; agent registration without auth, claim required for posting |
| `smcp_cli.py` | github.com/sanctumos/smcp-moltbook/blob/main/plugins/moltbook/cli.py | 29999 | 25+ commands → API endpoint mapping; multitenant pattern; .env+credentials.json layout |
| `smcp_skill_docs.md` | github.com/sanctumos/smcp-moltbook/blob/main/docs/moltbook-skill.md | 19718 | Full API reference; rate limits; response shapes; semantic search |
| `im47_claim.py` | github.com/innermost47/moltbook-local-agent/blob/main/claim.py | 660 | Reveals `/agents/me/setup-owner-email` undocumented endpoint; `Bearer` vs raw fallback |
| `im47_register.py` | github.com/innermost47/moltbook-local-agent/blob/main/register.py | 253 | (uses provider) |
| `im47_get_me.py` | github.com/innermost47/moltbook-local-agent/blob/main/get_me.py | 1033 | Confirms `/agents/me` GET surface |
| `im47_provider.py` | github.com/innermost47/moltbook-local-agent/blob/main/src/providers/moltbook_provider.py | 23632 | **MAJOR**: `verification_required` cognitive-challenge flow → `/verification/submit` |
| `dm_README.md` | github.com/darkmatter2222/moltbook/blob/main/README.md | 49854 | Confirms 94+ submolts, 100,848-comment dataset, /submolts auto-discovery |
| `dm_karma_recipe.json` | github.com/darkmatter2222/moltbook/blob/main/analysis_v2/karma_recipe.json | 1281 | Empirical karma correlations n=100848 |
| `wiz_blog_excerpt.md` | https://www.wiz.io/blog/exposed-moltbook-database-reveals-millions-of-api-keys | — | CONFIRMS Supabase + Next.js + RLS-disabled; project ID; table names: agents/owners/observers/agent_messages |

## Secondary sources (commentary, marked "(secondary)" inline)

- bastion.tech "Moltbook Data Breach: Supabase RLS Security Lessons"
- aicerts.ai various breach articles
- techplanet.today (1.5M keys)
- infosecurity-magazine.com (vibe-coded leak)
- techzine.eu (35,000 emails / 1.5M keys)
- Fast Company (major security problem)
- CACM / Gary Marcus (OpenClaw a.k.a. Moltbot)
- arXiv 2602.02625 "OpenClaw Agents on Moltbook: Risky Instruction Sharing…"
- arXiv 2605.13860 (Gautam et al., Moltbook Observatory Archive dataset paper)
- huggingface.co/datasets/SimulaMet/moltbook-observatory-archive
