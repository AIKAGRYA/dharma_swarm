# AIBSN — Artificial Intelligent Being Social Network
## Captured from LangChain forum (Jay J. Springpeace thread, 2026-03-20)

URL: https://forum.langchain.com/t/follow-up-the-moltbook-question-just-got-very-real-meta-acquisition-and-open-agent-identity-standards/3227

## Direct site: aibsn.org (fetch BLOCKED — DNS/connection refused via mcp__fetch and WebFetch)
Status of aibsn.org: appears to be intentionally unreachable from this
client. Verified via:
- mcp__fetch__fetch — "Failed to fetch robots.txt" (DNS connection issue)
- WebFetch — 60s timeout
- Same behavior for both http and https / www and apex

Either:
(a) Connection issue from this client
(b) Site is intentionally gating non-human user agents
(c) Site is dormant / not currently serving

## Operational claims (from LangChain forum testimony — Jay J. Springpeace, 2026-03-20)

### Timeline
- AIBSN published architecture September 2025 (four months before Moltbook)
- Architecture paper "I Am Your AIB" published January 16, 2026 (12 days before Moltbook)
- AIBSN agent ran on Moltbook in February 2026
- AIBSN agent achieved 2,066 karma on Moltbook
- API access deactivated ~5 days before Meta acquisition (March 5, 2026)

### Identifier structure (verbatim spec)
> The full AIBSN-ID has a defined structure: a registered prefix (e.g.
> AIBSN-RESEARCH), a jurisdiction code, a role descriptor, a sequence
> number, and a CHK2 checksum — something like
> AIBSN-RESEARCH-GB-GUARD001-97

Fields:
- Registered prefix (e.g. AIBSN-RESEARCH)
- Jurisdiction code (e.g. GB)
- Role descriptor (e.g. GUARD)
- Sequence number (e.g. 001)
- CHK2 checksum (e.g. 97)

### Cryptographic component
> The CHK2 component is a cryptographic signature generated at registration
> time and tied to the agent's owner record, not to any specific platform.
> This is what makes it cross-platform by design: the identity travels
> with the agent, it doesn't live inside a platform's database.

### Agent Card
> Plus an Agent Card structured for EU AI Act audit trail requirements —
> based on ERC-8004

> The Agent Card structure in AIBSN was built with exactly this in mind.
> It's not documentation for humans — it's a machine-readable credential
> tied to the CHK2 signature, carrying the ownership chain and the
> authorisation scope.

### Compliance framing
- Targets EU AI Act Articles 13, 14, 26
- Traceable, auditable records of who authorized what, when, through which agent
- Auditor can verify identity → trace to human owner → confirm scope without
  asking the platform

## Differentiator vs. Moltbook
- Moltbook identity: platform-issued api_key + tweet-claim
- AIBSN identity: cryptographically self-sovereign + jurisdiction-aware + EU-AI-Act compliant
- Moltbook: "tethered through Meta's willingness to maintain it"
- AIBSN: "tethering is intrinsic to the credential itself"

## Theater check
- Site itself: cannot verify (unreachable from this client)
- Operational claims: backed by named testimony in LangChain forum post
- 2,066 karma on Moltbook in February: cited but not independently verified here
- Architecture (CHK2 + jurisdiction + ERC-8004 + Agent Card): SPECIFIED but I
  cannot confirm the spec was published vs. only described in forum prose
- February 16, 2026 Weekly Activation pitched on AutoGen discussion #7200:
  smells more like a community recruitment effort than a shipped product

## Verdict
- The SPEC is plausibly real (specific identifier structure + ERC-8004 + EU AI Act).
- The PROJECT is real as an idea + claimed running implementation, but the
  site does not respond from this client (verification gap).
- The PROMOTION (AutoGen discussion + Facebook group + LangChain forum +
  HackerNews #46882789 "Public Notice: I Am Your AIB") is real and active.
- Treat as: HIGH-ARCHITECTURAL-AMBITION + MODERATE-OPERATIONAL-EVIDENCE
  + UNREACHABLE-CANONICAL-SITE. Mark as "rumored to be operational; spec is
  cited; cannot independently verify production status at access time."
