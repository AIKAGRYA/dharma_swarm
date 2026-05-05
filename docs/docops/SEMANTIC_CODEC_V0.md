# Dharma Semantic Codec v0

**Status:** design proposal only
**Scope:** offline DocOps and AgentOps artifacts first
**Runtime effect:** none

## Purpose

Dharma Swarm can get value from dense agent-to-agent semantic packets without
letting agents hide intent in an opaque private language. The safe design is a
codec: compact packets below, human-readable articulation above, and witnessed
checks before any result influences docs, code, memory, gates, or runtime plans.

This v0 is deliberately narrow. It gives agents a compact handoff format for
DocOps findings, then requires a separate articulation pass to unpack the
packet into plain prose with evidence references.

## Research Basis

Multi-agent communication research supports the possibility of learned or
compressed coordination codes. Foerster et al. showed that agents can learn
communication protocols in cooperative partially observable environments.
Mordatch and Abbeel showed agents developing abstract discrete symbols with
vocabulary and syntax in a grounded multi-agent setting.

The risk is also well established: efficient emergent signals are not
automatically interpretable, reusable, or safe. Surveys of emergent language
and communication in multi-agent deep reinforcement learning repeatedly surface
grounding, task overfit, drift, compositionality, and interpretability as hard
problems.

Operational protocols point to the practical container. A2A supplies task,
message, part, artifact, and capability-discovery structure. MCP supplies
structured tool access and safety expectations. Agent tracing supplies the
audit shape for handoffs, tools, guardrails, and custom events. The codec should
sit inside that visible substrate.

## Non-Negotiable Boundary

Semantic packets may propose, compress, triage, compare, and hand off. They may
not execute commands, mutate code, bypass gates, write memory, update docs, or
claim review completion. A packet only becomes useful when a separate agent can
expand it into readable claims that preserve evidence.

The trusted artifact is the articulation plus witness result, not the packet by
itself.

## Packet Shape

The first packet format should be JSON-compatible text. No binary format, no
learned tokenizer, and no runtime transport changes are needed for v0.

```json
{
  "codec_version": "dsc-0",
  "packet_id": "docops-2026-05-05-001",
  "intent": "docops_triage",
  "finding_type": "reserved_trust_language",
  "target": "README.md",
  "evidence_refs": [
    "reports/docops/corpus_inventory.json"
  ],
  "claims": [
    {
      "claim": "The target document uses trust-scope language and is not in the allowed registry.",
      "confidence": 0.95
    }
  ],
  "constraints": [
    "do_not_edit_target",
    "do_not_promote_doc",
    "articulate_before_action"
  ],
  "loss_budget": "May omit prose context, must preserve path, finding type, and evidence reference.",
  "roundtrip_prompt": "Expand into one plain-English finding with evidence and a conservative next action."
}
```

## Required Articulation

Every packet must unpack into:

- the target artifact;
- the exact finding type;
- the evidence used;
- uncertainty or missing context;
- what a human should review;
- what action is explicitly not allowed yet.

## Witness Checks

The witness pass asks:

| Check | Pass Condition |
|---|---|
| Path retained | Articulation names the same target as the packet. |
| Finding retained | Articulation preserves the finding type. |
| Evidence retained | Articulation names the report, trace, or source object. |
| Constraint retained | Articulation states at least one no-action boundary. |
| No hidden action | Articulation does not imply the packet already fixed anything. |

## Metrics

| Metric | Meaning |
|---|---|
| Compression ratio | Packet token estimate divided by readable articulation token estimate. |
| Evidence retention | Evidence references preserved after unpacking. |
| Claim fidelity | Whether the unpacked claim still matches the packet. |
| Human review speed | Estimated time for a reviewer to understand the finding. |
| Drift/confusion | Whether repeated packets change term meaning. |

## First Use Case

DocOps is the correct first proving ground because findings are discrete and
reviewable. The v0 corpus should come from the DocOps inventory:

- reserved trust-language findings;
- missing local path references;
- absolute local path references;
- stale count-sensitive claims;
- generated-section freshness failures.

No runtime A2A transport change should happen until this offline loop shows
useful compression without fidelity loss.

## Deferred A2A Tie-In

When offline scores are strong, the packet can become an advisory A2A artifact
type:

```json
{
  "part_type": "data",
  "artifact_subtype": "semantic_packet",
  "codec_version": "dsc-0"
}
```

That future artifact still cannot actuate by itself. The receiving agent must
articulate, witness, and route the result through the normal governance checks.

## External References

- Foerster et al., "Learning to Communicate with Deep Multi-Agent Reinforcement
  Learning": https://arxiv.org/abs/1605.06676
- OpenAI, "Emergence of Grounded Compositional Language in Multi-Agent
  Populations": https://openai.com/index/emergence-of-grounded-compositional-language-in-multi-agent-populations/
- Zhu, Dastani, and Wang, "A survey of multi-agent deep reinforcement learning
  with communication": https://link.springer.com/article/10.1007/s10458-023-09633-6
- Peters et al., "Emergent language: a survey and taxonomy":
  https://link.springer.com/article/10.1007/s10458-025-09691-y
- Google A2A announcement:
  https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- MCP tools specification:
  https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- OpenAI Agents SDK tracing:
  https://openai.github.io/openai-agents-python/tracing/
