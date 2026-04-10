---
title: Context+ Terminal Diagnostics
path: docs/plans/2026-04-10-contextplus-terminal-diagnostics.md
slug: contextplus-terminal-diagnostics
doc_type: diagnostic
status: active
summary: Separates Context+ repo usage from MCP transport and local Ollama sandbox failures observed during terminal cleanup.
source:
  provenance: repo_local
  kind: operational_diagnostic
  origin_signals:
  - terminal cleanup tranche
  - Context+ MCP transport failures
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- software_architecture
- verification
- operator_runtime
connected_relevant_files:
- /Users/dhyana/contextplus/src/index.ts
- /Users/dhyana/contextplus/src/core/embeddings.ts
- /Users/dhyana/.codex/config.toml
- docs/governance/TERMINAL_OPERATING_MODEL.md
stigmergy:
  meaning: This note prevents future agents from treating Context+ failures as Dharma terminal architecture failures.
  state: active
  semantic_weight: 0.79
  trace_role: operational_diagnostic
curation:
  last_frontmatter_refresh: '2026-04-10T00:00:00+08:00'
  curated_by_model: Codex (GPT-5)
  schema_version: pkm-phd-stigmergy-v1
---
# Context+ Terminal Diagnostics

## Current Finding

Context+ has two separate failure modes in this environment:

- the live Codex MCP wrapper reports `Transport closed`
- semantic tools that need Ollama embeddings cannot connect to `127.0.0.1:11434` from the sandboxed Node MCP process

These are operational problems, not evidence that the Dharma terminal architecture is wrong.

## Evidence

- direct SDK calls against the Context+ server can list tools and run structural tools
- direct structural tools such as context tree, file skeleton, and blast-radius calls work outside the wedged live MCP wrapper
- Ollama itself is running locally, but Node fetch from the MCP runtime gets a local-socket `EPERM`
- the live Codex session still reports `Transport closed` for `contextplus/get_context_tree`

## Local Fixes Already Applied Outside This Repo

- `/Users/dhyana/contextplus/src/index.ts` no longer depends on a remote instruction fetch for the instructions resource
- `/Users/dhyana/contextplus/src/index.ts` delays shutdown briefly after stdin EOF/close to avoid immediate transport teardown
- `/Users/dhyana/contextplus/src/core/embeddings.ts` now reports sandbox-blocked localhost/Ollama failures explicitly
- `/Users/dhyana/.codex/config.toml` has Context+ embedding tracker disabled to avoid watcher exhaustion

## Recommended Next Step

Restart the Codex session after rebuilding Context+ so the MCP wrapper starts from a clean transport. Then retest in this order:

1. `listTools`
2. `get_context_tree`
3. `get_file_skeleton`
4. `get_blast_radius`
5. `semantic_navigate`

If the first four pass and semantic tools still fail, the remaining blocker is local Ollama socket access from the MCP sandbox. That should be handled as an MCP runtime permission problem, not by changing Dharma terminal code.

## Terminal Work Rule

Do not block terminal cleanup on Context+ semantic tools when structural Context+ access is unavailable through the live wrapper. Use repo-native inspection and record the Context+ limitation explicitly.
