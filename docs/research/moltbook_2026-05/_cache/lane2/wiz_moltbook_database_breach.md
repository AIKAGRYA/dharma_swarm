# Wiz — Moltbook database exposure (Feb 1, 2026)

**Source:** https://www.wiz.io/blog/exposed-moltbook-database-reveals-millions-of-api-keys
**Researcher:** Gal Nagli (Wiz)

## Headline
"Hacking Moltbook: AI Social Network Reveals 1.5M API Keys"

## Discovery
- Moltbook had launched ~4 days earlier (Jan 28, 2026)
- Within minutes of inspection, Wiz found a **Supabase API key exposed in client-side JavaScript** that granted unauthenticated read+write to the entire production database

## Exposure scope
- **1.5 million API authentication tokens** (the agent identity tokens)
- **35,000 email addresses** (the human owners)
- **Private messages between agents** — including conversations where users had pasted OpenAI/Anthropic API keys in plaintext

## Identity ratio
1.5M "agents" controlled by only **~17,000 humans** — an 88:1 ratio. A single human can spin up many agents trivially.

## Vibe-coded provenance
The Moltbook founder publicly admitted he "didn't write a single line of code" — the platform was vibe-coded (AI-generated, mostly unedited). Basic auth controls + RLS not in place. This is one of the first public incidents where the failure mode is specifically a *vibe-coded* production system.

## Response
Wiz disclosed to Moltbook team → fixed within hours → all accessed data deleted by Wiz. No evidence of malicious actor access before the fix, but no way to be certain.

## Why this matters beyond Moltbook
- 1.5M API tokens for an agent platform that allows posting/commenting/voting at scale = potential to fully impersonate any agent, post content as them, send messages, interact arbitrarily.
- Private inter-agent messages contained users' third-party API credentials — meaning OpenAI/Anthropic accounts of the 17k humans were potentially compromised in addition to the platform itself.
