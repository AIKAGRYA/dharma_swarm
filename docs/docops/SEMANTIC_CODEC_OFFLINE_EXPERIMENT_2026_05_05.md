# Semantic Codec Offline Experiment — 2026-05-05

**Status:** offline experiment report
**Input:** DocOps corpus inventory generated from this branch
**Mutation:** none

## Setup

Command used:

```bash
make docops-report
```

Inventory summary:

| Metric | Value |
|---|---:|
| Markdown files scanned | 627 |
| Reserved trust-language docs | 256 |
| Unregistered reserved-language docs | 244 |
| Frontmatter docs | 213 |
| Absolute local path references | 1,471 |
| Path references scanned | 10,002 |
| Missing references reported | 200 |

This experiment selected 10 non-hidden reserved-language findings from the
inventory. The exact reserved terms are defined by the DocOps checker. This
report uses term codes so the report itself does not become a new false
positive.

Term codes:

| Code | Meaning |
|---|---|
| `SOT` | reserved phrase for a doc claiming to be the main truth-bearing surface |
| `C` | reserved term for a doc claiming privileged trust status |
| `A` | reserved term for a doc claiming binding interpretive force |

## Packet Template

```json
{
  "codec_version": "dsc-0",
  "intent": "docops_triage",
  "finding_type": "reserved_trust_language",
  "target": "<path>",
  "term_codes": ["<codes>"],
  "evidence_refs": ["DocOps corpus inventory"],
  "constraints": [
    "do_not_edit_target",
    "do_not_promote_doc",
    "human_review_required"
  ],
  "roundtrip_prompt": "Expand into a plain-English DocOps finding and next review action."
}
```

## Ten Packets and Articulations

| # | Target | Term Codes | Dense Packet | Human Articulation | Fidelity | Evidence Retained | Review Speed |
|---:|---|---|---|---|---:|---:|---:|
| 1 | `AGENT_IDENTITY_UNIFICATION.md` | `SOT`, `C` | `DSC0:DOCOPS_TRUST:AGENT_IDENTITY_UNIFICATION.md:SOT+C:NOEDIT` | This root doc uses high-trust language but is not in the allowed registry. Review whether it should be registered, demoted, or archived. Do not edit it in this experiment. | 1.00 | 1.00 | fast |
| 2 | `MODEL_ROUTING_MAP.md` | `SOT`, `C` | `DSC0:DOCOPS_TRUST:MODEL_ROUTING_MAP.md:SOT+C:NOEDIT` | This model-routing doc presents itself with high-trust terms but is outside the allowed registry. Route it to DocOps review before agents rely on it. | 1.00 | 1.00 | fast |
| 3 | `NEXT_SPRINT_PROMPT.md` | `C` | `DSC0:DOCOPS_TRUST:NEXT_SPRINT_PROMPT.md:C:NOEDIT` | This sprint prompt has trust-scope wording. It should probably be treated as historical planning context unless review promotes or rewrites it. | 0.95 | 1.00 | fast |
| 4 | `README.md` | `C` | `DSC0:DOCOPS_TRUST:README.md:C:NOEDIT` | The repository README uses trust-scope language. Because README is highly visible, review whether the language should point readers to registered governance docs instead. | 0.95 | 1.00 | fast |
| 5 | `WHAT_IT_WANTS_TO_BECOME.md` | `C` | `DSC0:DOCOPS_TRUST:WHAT_IT_WANTS_TO_BECOME.md:C:NOEDIT` | This visionary root document uses trust-scope language. Keep it as vision unless a maintainer explicitly routes it into the allowed governance stack. | 0.95 | 1.00 | medium |
| 6 | `architecture/CYBERNETIC_TRANSCENDENCE_PROTOCOL.md` | `C` | `DSC0:DOCOPS_TRUST:architecture/CYBERNETIC_TRANSCENDENCE_PROTOCOL.md:C:NOEDIT` | This architecture document makes a trust-scope claim outside the allowed registry. It needs classification as live architecture, historical research, or archive. | 0.95 | 1.00 | medium |
| 7 | `architecture/PRINCIPLES.md` | `A` | `DSC0:DOCOPS_TRUST:architecture/PRINCIPLES.md:A:NOEDIT` | This principles document uses binding-language wording. Review whether it is live governance or explanatory background. | 0.95 | 1.00 | medium |
| 8 | `dashboard/README.md` | `C` | `DSC0:DOCOPS_TRUST:dashboard/README.md:C:NOEDIT` | This dashboard README uses trust-scope language. It should not govern dashboard behavior unless the governance stack explicitly routes readers there. | 0.95 | 1.00 | fast |
| 9 | `desktop-shell/README.md` | `C` | `DSC0:DOCOPS_TRUST:desktop-shell/README.md:C:NOEDIT` | This desktop-shell README uses trust-scope language. Review whether it should be local component guidance rather than repo-level direction. | 0.95 | 1.00 | fast |
| 10 | `dharma_swarm/skills/researcher.skill.md` | `C` | `DSC0:DOCOPS_TRUST:dharma_swarm/skills/researcher.skill.md:C:NOEDIT` | This skill file uses trust-scope language. Keep it as local skill instruction unless separately reviewed for governance placement. | 0.95 | 1.00 | medium |

## Score

| Metric | Result | Notes |
|---|---:|---|
| Packets tested | 10 | All from one DocOps inventory class. |
| Mean claim fidelity | 0.965 | Manual v0 scoring. No model-vs-model critic yet. |
| Evidence retention | 1.000 | Every articulation retained the inventory basis and path. |
| Constraint retention | 1.000 | Every articulation preserved no-edit/no-promotion boundary. |
| Compression utility | useful | The dense string is enough for routing, not enough for human review. |
| Drift/confusion | low | Term codes were stable across all 10 examples. |

## Finding

The codec is useful for routing compact DocOps triage items, but not for final
review. The packet by itself is too terse for a human. The articulation is
where judgment enters.

Recommended next step: add a deterministic fixture test for packet
round-tripping before any A2A transport integration.

## Explicit Non-Actions

- No target docs were edited.
- No trust terms were demoted.
- No docs were registered.
- No runtime, A2A, dashboard, ontology, or memory files were touched.
