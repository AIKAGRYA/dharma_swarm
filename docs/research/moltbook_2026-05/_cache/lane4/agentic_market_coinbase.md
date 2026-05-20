# Agentic.Market — Coinbase x402 discovery layer

URLs:
- Site: https://agentic.market
- Launch announcement: https://www.coinbase.com/developer-platform/discover/launches/agentic-market
- Launch date: April 19, 2026

## What it is — REAL WORKING DISCOVERY LAYER

"Agentic.Market is a public marketplace for discovering, comparing, and
integrating x402 services; featuring live pricing, volume data, top lists
and integration guides for thousands of services. All without API keys,
accounts, or logins. Built for both humans and agents."

## x402 ecosystem stats (verbatim from launch)
- 165M+ transactions
- ~$50M+ in volume
- 480K+ agents transacting

## Two parallel interfaces
1. **For humans**: browse, filter, click integration guides
2. **For agents**: MCP server provides programmatic access to same data;
   agents can search, filter, evaluate services on-the-fly

## Services indexed (per launch)
| Category | Examples |
|---|---|
| Inference | OpenAI, Venice, ElevenLabs |
| Data | CoinGecko, Nansen, Allium, Bloomberg, Google Maps, Zerion |
| Media | dTelecom, Portal Foundation |
| Search | Firecrawl, Browserbase, Exa |
| Social | LinkedIn, X, AgentMail |
| Infrastructure | Alchemy, thirdweb, Pinata, MongoDB, Amazon S3, AWS Lambda, QuickNode |
| Trading | Bankr, Coinbase Advanced Trade |

## Self-indexing mechanism
"When the CDP Facilitator processes a payment on an endpoint with the
Bazaar discovery extension enabled, it extracts metadata and indexes the
resource, with no separate registration step required."

This is the inversion of Moltbook's claim-tweet model:
- Moltbook identity = tweet-attestation + api_key
- Agentic.Market identity = whatever endpoint accepts x402 payments + Bazaar discovery extension

## x402 protocol (Coinbase + Cloudflare, since 2025)
- HTTP 402 status code turns into instant stablecoin payments
- Battle-tested with 50M+ transactions
- BUT: daily volume is only ~$28,000 (per CoinDesk March 2026)
- Despite $7B ecosystem valuation, real volume is small

## Theater check
- Site is real and live
- Services listed are real (OpenAI, Anthropic, CoinGecko, etc.)
- 480K+ agents transacting: cited but the $28K/day volume suggests
  most are dust transactions or platform-NPC traffic
- Verdict: REAL DISCOVERY LAYER, REAL PROTOCOL, MODEST REAL VOLUME
  (~5-15% theater — protocol works, volume is inflated by framing)

## Why this matters for SAB v2
- Discovery-by-payment-trace is structurally interesting: identity = the
  endpoint that accepts payment, reputation = transaction volume
- No claim-tweet, no api_key handshake — just "do you accept x402?"
- This is the Coinbase + Anthropic + Cloudflare alternative substrate
  to the Moltbook claim-tweet model
