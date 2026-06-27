# A2A Score Denominator

Generated for active track `a2a-cloud-agent-bridge-2026-06`.

This document declares the measured A2A population. It is not a liveness claim.
Live contact still requires fresh NATS/A2A receipts.

| agent_uid | kind | denominator_status |
| --- | --- | --- |
| codex_composer | local_agent | counted |
| claude-code | local_agent | counted |
| hermes-m5 | local_agent | counted |
| perplexity-computer | cloud_agent | counted |

Summary:

- local_agent_denominator: 3
- cloud_agent_denominator: 1
- total_agent_denominator: 4

`perplexity-computer` is now counted as present in the denominator. Its
live-contact status remains ready/down according to receipts, never absent by
definition.
