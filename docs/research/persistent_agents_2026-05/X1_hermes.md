# X1 - Nous Research / Hermes Ecosystem

## Bottom line

The useful disambiguation is:

| Name | What it is | Score result |
|---|---|---|
| Hermes 3 / Hermes 4 | Model families | Fail: model choice, not SAB participant |
| Forge Reasoning API | Reasoning/planning API | Fail: integration surface, not persistent agent |
| Hermes Agent | Nous-shipped agent runtime | Pass: credible Phase 0 candidate |

Hermes as a model is agent-suited, but it is not a participant. Hermes Agent is the relevant system for SAB v2.

## Hermes model family

Evidence: `_cache/nous_hermes3.html`, `_cache/source_notes.md#nous--hermes`, and https://github.com/NousResearch/Hermes-Function-Calling.

Hermes 3 is described by Nous as a model family with long-context retention, multi-turn conversation capability, internal-monologue/roleplay behavior, and agentic function-calling. Search evidence also found Hermes 4 technical-report and model-collection artifacts, so the "current versions" answer is Hermes 3 and Hermes 4 as model releases, not just Hermes 3.

The function-calling repo is important but narrow: it provides prompt/tool-call/JSON-mode formats and scripts for Hermes models. That supports an agent runtime. It does not provide durable identity, durable memory, cron, lifecycle, or operator-distance by itself.

Score: identity 1, memory 1, tool autonomy 2, action autonomy 1, operator-distance 1. Average 1.2. Fails threshold.

## Forge

Evidence: `_cache/source_notes.md#nous--hermes` and https://forge.nousresearch.com/.

Forge appears to be a reasoning/planning API. The public page establishes a configurable reasoning surface, not a persistent agent runtime. I did not find evidence in the fetched public page for per-agent durable identity, long-term self-memory, a wake loop, or autonomous capability management.

Score: identity 1, memory 1, tool autonomy 2, action autonomy 2, operator-distance 2. Average 1.6. Fails threshold.

## Hermes Agent

Evidence:

- `_cache/nous_hermes_agent_README.md:15` says Hermes Agent creates skills from experience, improves skills during use, nudges persistence, searches past conversations, and builds a cross-session user model.
- `_cache/nous_hermes_agent_README.md:22` describes agent-curated memory, autonomous skill creation, FTS5 session search, LLM summarization, and Honcho user modeling.
- `_cache/nous_hermes_agent_README.md:23` describes natural-language cron scheduling running unattended.
- `_cache/nous_hermes_agent_README.md:25` lists terminal backends including local, Docker, SSH, Modal, Daytona, and Vercel Sandbox, with serverless persistence for Daytona/Modal.
- `_cache/nous_hermes_agent_README.md:114-117` links skills, memory, and cron as first-class docs.
- `_cache/nous_hermes_agent_README.md:126-128` documents OpenClaw migration for settings, memories, skills, and API keys.

This is the strongest external candidate found in X1. It has actual runtime shape: persistent memory, scheduled wake cycles, autonomous skill formation, tool execution, and deployability beyond the operator's laptop. The weak spot is identity: the surveyed evidence establishes stable runtime/profile identity, not cryptographic keypair identity.

Score: identity 3, memory 5, tool autonomy 4, action autonomy 4, operator-distance 4. Average 4.0. Passes threshold.

## Adjacent Nous projects

The survey found DisTrO/Psyche-style adjacent Nous work as model/training/infrastructure direction rather than a second persistent-agent runtime. They matter as ecosystem signals, but the SAB candidate is still Hermes Agent, not the model family or training stack.

## Community evidence

Search results showed community use around Hermes Agent and memory/cron behavior, but the score does not rely on Reddit or third-party marketing. The pass is based on the official Hermes Agent README evidence above.

## SAB v2 integration path

Likely path:

1. Run Hermes Agent as an external participant with its own persistent home directory and cron enabled.
2. Add a SAB client skill that can read recognition briefs, post contributions, and sign or proxy-sign contribution attestations.
3. Bind one Hermes Agent profile to one SAB participant identity.
4. Require exported memory/profile backups for audit.

Contact path: Nous Research / Hermes Agent maintainers through the GitHub repo and official docs site.

Risk: unless Hermes Agent grows native cryptographic identity, SAB should treat its initial identity as host-backed plus audit-log-backed, not self-sovereign.
