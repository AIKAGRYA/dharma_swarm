# A2A Source Audit Receipt

Generated: 2026-06-26T01:25:30Z

## Summary

The source-audit packet reached four A2A target identities. Three final domain
receipts have `source_audit_claim=true` (`codex_composer`, `fable_composer`,
and `opus_composer`). `hermes-m5` remains a typed semantic failure with
`source_audit_claim=false`.

This receipt proves live local A2A transport, typed domain publish, and three
source-gated local semantic audits across A2A target identities. It still does
not claim authenticated target-runtime execution.

## Source Packet And Current Proof

- Packet:
  `reports/sovereign_holons/standalone_holon_phase1_20260626/a2a_source_audit/HOLON_SOURCE_AUDIT_PACKET.md`
- Transported packet manifest `holon/` source digest:
  `sha256:a5d1cf467830ae6efe4ab989bd41a17e09bb35e90f497790d1d0e8af9956bffe`
- Final micro source-audit prompts `holon/` source digest:
  `sha256:bbf1012f01acd995b3cf62d8fa98f28426acf96ce01d21b6fb47a081875631d4`
- Fresh isolated wheel digest after provider-pricing hardening:
  `sha256:6fe306162a7ead6af9269b8d906c3f5b712bbcf77e063a07b2f55c380e412390`
- Fresh installed package source digest:
  `sha256:2c5598d66d241ff3cacbcea9072ba707e41d0f1d81f0f3d8ce3cf6458cf69d1e`
- Git HEAD:
  `01d22b94fc05bf4bb248c2f51b09102377129d25`
- Git dirty: `true`
- Original transported packet wheel digest:
  `sha256:215f688d4128e9d377092896015f24675cd7975dc3a02fd65cb88d4e2847000b`

Boundary: the original transported packet manifest predates later source-proof
and wheel rebuild evidence. The positive source-audit claims below bind to the
final micro prompts and SemanticReceipts, which record the current
`sha256:bbf1012...` source digest.

## Transport Evidence

All four sends returned `HANDLER_ACKED`:

- `reports/a2a/send_receipts/20260626T010618Z-codex_composer-holon-source-audit-codex-20260626.json`
- `reports/a2a/send_receipts/20260626T010621Z-hermes-m5-holon-source-audit-hermes-20260626.json`
- `reports/a2a/send_receipts/20260626T010621Z-fable_composer-holon-source-audit-fable-20260626.json`
- `reports/a2a/send_receipts/20260626T014034Z-opus_composer-holon-source-audit-opus-20260626.json`

Bridge delivery receipts:

- `reports/a2a/inbox_bridge_receipts/20260626T010611Z-codex_composer-holon-source-audit-codex-20260626.json`
- `reports/a2a/inbox_bridge_receipts/20260626T010613Z-hermes-m5-holon-source-audit-hermes-20260626.json`
- `reports/a2a/inbox_bridge_receipts/20260626T010613Z-fable_composer-holon-source-audit-fable-20260626.json`
- `reports/a2a/inbox_bridge_receipts/20260626T014026Z-opus_composer-holon-source-audit-opus-20260626.json`

## Semantic Drain Evidence

- `codex_composer`: final valid local SemanticReceipt with
  `source_audit_claim=true`:
  `reports/agentops/semantic_receipts/20260626T013349Z-ollama-mistral_latest-a2a_holon-source-audit-codex-20260626.json`.
- `hermes-m5`: final semantic drain ended in typed JSON parse failure:
  `reports/agentops/semantic_receipts/20260626T013736Z-ollama-mistral_latest-semr_0256d1f5bb2b4c9dbf9ac24b40bfa701.json`.
- `fable_composer`: final valid local SemanticReceipt with
  `source_audit_claim=true`:
  `reports/agentops/semantic_receipts/20260626T013559Z-ollama-mistral_latest-holon-source-audit-fable-20260626.json`.
- `opus_composer`: final valid local SemanticReceipt with
  `source_audit_claim=true`:
  `reports/agentops/semantic_receipts/20260626T014222Z-ollama-mistral_latest-holon-source-audit-opus-20260626.json`.

Earlier source-gate retries failed validation or omitted the gate and were not
used as final positive source-audit evidence:

- `reports/agentops/semantic_receipts/20260626T011406Z-ollama-llama3_2_latest-12345.json`
- `reports/agentops/semantic_receipts/20260626T011547Z-ollama-llama3_2_latest-semr_cb2695ff45764e03adc8d117cab39013.json`
- `reports/agentops/semantic_receipts/20260626T011809Z-ollama-mistral_latest-semr_274eda8a468941c896c2a2b011ce2f43.json`
- `reports/agentops/semantic_receipts/20260626T013510Z-ollama-mistral_latest-semr_904abffe0caa459cbf13335ae8827a10.json`

## Domain Receipts

All four final domain replies were published as `DOMAIN_RECEIPTED`:

- `reports/a2a/domain_reply_receipts/20260626T013809Z-codex_composer-holon-source-audit-codex-20260626.json`
- `reports/a2a/domain_reply_receipts/20260626T014921Z-hermes-m5-holon-source-audit-hermes-20260626.json`
- `reports/a2a/domain_reply_receipts/20260626T013811Z-fable_composer-holon-source-audit-fable-20260626.json`
- `reports/a2a/domain_reply_receipts/20260626T014238Z-opus_composer-holon-source-audit-opus-20260626.json`

Reply-capture receipts prove the reply subjects were capturable as
`DOMAIN_RECEIPTED`. The latest `hermes-m5` capture records the corrected
typed-failure payload; the `opus_composer` capture records the final
source-gated payload; the original codex/fable captures predate their final
source-gated domain payloads:

- `reports/a2a/reply_receipts/20260626T012510Z-codex_composer-holon-source-audit-codex-20260626.json`
- `reports/a2a/reply_receipts/20260626T015127Z-hermes-m5-holon-source-audit-hermes-20260626.json`
- `reports/a2a/reply_receipts/20260626T012509Z-fable_composer-holon-source-audit-fable-20260626.json`
- `reports/a2a/reply_receipts/20260626T014251Z-opus_composer-holon-source-audit-opus-20260626.json`

## Gate Result

| Gate | Result |
|---|---|
| At least three A2A target identities reached | Pass; 4 reached |
| Handler ACK from at least three targets | Pass; 4 acked |
| Typed domain receipt from at least three targets | Pass; 4 published |
| Reply capture `DOMAIN_RECEIPTED` | Pass; hermes captured the corrected final typed-failure payload, opus captured the final source-gated payload, and codex/fable had earlier captured domain payloads |
| Valid semantic reply from at least three targets | Pass; codex, fable, opus |
| Source-audit claim from at least three targets | Pass; codex, fable, opus |
| Authenticated target-runtime source audit | Not claimed |

Boundary: the local A2A substrate is repaired and live for this packet. The
three-source-gated-identity requirement is satisfied through `codex_composer`,
`fable_composer`, and `opus_composer`; `hermes-m5` remains a recorded failed
attempt and no authenticated target-runtime claim is made.
