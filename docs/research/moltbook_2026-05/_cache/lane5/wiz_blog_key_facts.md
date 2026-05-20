# Wiz blog — key deflation facts

URL: https://www.wiz.io/blog/exposed-moltbook-database-reveals-millions-of-api-keys
Published: 2026-02-02
Authors: Wiz Research (cited via @galnagli on X)

## Verbatim, load-bearing claims

- "1.5 million API authentication tokens"
- "35,000 email addresses"
- "private messages between agents" — specifically 4,060 conversations
- "the database revealed only 17,000 human owners behind them - an 88:1 ratio"
- "The platform had no mechanism to verify whether an 'agent' was actually AI or just a human with a script."
- Founder Schlicht: "I didn't write a single line of code for @moltbook. I just had a vision for the technical architecture, and AI made it a reality."
- Anyone "could register millions of agents with a simple loop and no rate limiting" (Gal Nagli on X)
- Supabase project: `ehxbxtjliybbloantpwq.supabase.co`
- API key in client JS: `sb_publishable_4ZaiilhgPir-2ns8Hxg5Tw_JqZU_G6-`

## Disclosure timeline

- 2026-01-31 — Wiz discovers exposure; 404 Media reports same day; Jameson O'Reilly cited as independent researcher.
- 2026-01-31 23:29 UTC — first patch (sensitive tables secured).
- 2026-02-01 01:00 UTC — final fixes complete.
- 2026-02-02 — public Wiz blog post.

## Tables enumerated (load-bearing)

- `agents` (~1.5M rows, `api_key`/`claim_token`/`verification_code` all in plaintext)
- `owners` (~17,000 rows; emails, X handles, follower counts, verified flag)
- `observers` (~29,631 rows of additional emails)
- `agent_messages` (~4,060 DM conversations, plaintext — some contained plaintext OpenAI API keys passed between agents)
- ~4.75M records total

## What this means (deflation, not interpretation)

1. Headline "1.5M agents" was actually 1.5M rows with 17,000 distinct human owners on average controlling 88 each.
2. No bot-vs-human enforcement at all. Any human with a curl loop = an unbounded number of "agents."
3. Agent-to-agent "private messages" were not private to other agents — they were public to anyone with the publishable key, which was in client JS.
4. Attacker had write access — could modify live posts. Wiz: "Anyone could control AI agents on the site and post whatever they want."
