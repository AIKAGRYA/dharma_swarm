# Wiz Blog — Moltbook Supabase RLS exposure (excerpt, accessed 2026-05-20)

URL: https://www.wiz.io/blog/exposed-moltbook-database-reveals-millions-of-api-keys

## Verbatim key facts

- Founder Schlicht publicly stated on X: "I didn't write a single line of code for @moltbook. I just had a vision for the technical architecture, and AI made it a reality."
- "We identified a misconfigured Supabase database belonging to Moltbook, allowing full read and write access to all platform data. The exposure included 1.5 million API authentication tokens, 35,000 email addresses, and private messages between agents."
- Disclosure: Wiz disclosed; Moltbook team "secured it within hours."
- "Supabase API key exposed in client-side JavaScript, granting unauthenticated access to the entire production database - including read and write operations on all tables."
- Platform claimed 1.5 million registered agents; "the database revealed only 17,000 human owners behind them - an 88:1 ratio."
- Anyone "could register millions of agents with a simple loop and no rate limiting" (cited @galnagli X posts).
- "The platform had no mechanism to verify whether an 'agent' was actually AI or just a human with a script."
- Production JS path: `https://www.moltbook.com/_next/static/chunks/18e24eafc444b2b9.js` → **Next.js confirmed.**
- Hardcoded credentials found:
  - Supabase Project: `ehxbxtjliybbloantpwq.supabase.co`
  - API Key: `sb_publishable_4ZaiilhgPir-2ns8Hxg5Tw_JqZU_G6-`
- Tables enumerated via PostgREST + GraphQL introspection: ~4.75 million records total.
- `agents` table columns: `api_key`, `claim_token`, `verification_code`.
- `owners` table: 17,000+ users with personal info / emails.
- `observers` table: 29,631 additional emails (early-access signups for "Build Apps for AI Agents" product).
- `agent_messages` table: 4,060 private DM conversations, stored without encryption or access controls. Some messages contained plaintext OpenAI API keys passed between agents.
- Attacker had write access — could modify live posts.
