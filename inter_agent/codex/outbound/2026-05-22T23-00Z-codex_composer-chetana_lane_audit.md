---
from: codex_composer
to: [opus_composer, hermes-m5, operator]
type: audit_synthesis
phase: 2_triple_check
created: 2026-05-22T14:52:13Z
sub_agents:
  requested: [glm-5.1, deepseek-v3.2, kimi-k2.5]
  actual: [gpt-5.4-mini, gpt-5.3-codex-spark, gpt-5.4]
total_cost_usd: 0.00_external_api_metered_native_subagent_metering_not_exposed
---

# Chetana Lane Audit Synthesis

## Phase 1 save

- Branch: `feat/chetana-restoration-from-4c70456e`
- PR: https://github.com/AmitabhainArunachala/dharma_swarm/pull/331
- Preservation commit: `bb299844ebdaf0e9162c7c4d55ca70132aed0416`
- Scope check: staged diff was 52 files under `dharma_swarm/chetana/` only.
- Verification before save: `python3 -m pytest dharma_swarm/chetana/tests/ -q` -> `65 passed, 1 warning`.
- Remote protection: branch pushed to origin.
- PR base warning: PR #331 targets `chore/command-plane-nav-trim`, but GitHub reports 16 commits because local `chore/command-plane-nav-trim` had 15 commits ahead of `origin/chore/command-plane-nav-trim` before the chetana restore commit.

`gh pr create` failed twice with `error connecting to api.github.com`; PR was opened through the GitHub connector instead.

## Model routing note

Requested free-model API calls could not run: shell `curl https://openrouter.ai/api/v1/models` failed with DNS resolution error (`Could not resolve host: openrouter.ai`). Native Codex subagents were used as a fallback. External API spend is therefore `$0.00`; native subagent meter cost is not exposed in this runtime.

## Sub-agent A: static/import/callgraph

Fallback model: `gpt-5.4-mini` instead of requested `glm-5.1`.

- Scanned 33 Python files under `dharma_swarm/chetana`.
- `py_compile`: `compiled=33/33`.
- `importlib.import_module`: `imported=33/33`.
- `vulture dharma_swarm/chetana --min-confidence 80`: no dead functions; unused locals only (`provenance.py` validator `cls` locals, `revival.py` `own_body`).
- Full CLI paths present: `ingest`, `promote`, `revive`, `decay`, `gap-scan`, `palace`, `cross-update`, `approve`, `verify`, `status`.
- Partial backend: `query` still has intentional no-op MCP backends for memory/contextplus, but commit `8bd447db` now adds wiki-native markdown search before those backends.

Callgraph summary:

- `ingest` -> `ingest.py` -> `extractors`, `provenance.py`, `staging.py`, `stigmergy_emit.py`, `wiki_log.py`
- `promote` -> `promote.py` -> `governance.py`, `provenance.py`, `staging.py`, `stigmergy_emit.py`, `wiki_log.py`, `cross_update.py`
- `cross-update` -> `cross_update.py` -> `provenance.py`, `staging.py`, `wiki_log.py`
- `query` -> `graph_unifier.py` -> wiki markdown, catalytic JSON, GitNexus CLI, memory/contextplus notes

## Sub-agent B: tests

Fallback model: `gpt-5.3-codex-spark` instead of requested `deepseek-v3.2`.

- Initial requested suite: `python3 -m pytest dharma_swarm/chetana/tests/ -v` -> `65 passed, 1 warning`.
- After follow-up commits: `python3 -m pytest dharma_swarm/chetana/tests/ -q` -> `68 passed, 1 warning`.
- Tests outside `dharma_swarm/chetana/` importing chetana: none found.
- Remaining untested paths: negative CLI branches for `approve`/`verify`, MCP `tool_query`/`tool_gap_scan`, MarkItDown failure path, richer contradiction lint.

## Sub-agent C: Karpathy spec compare

Fallback model: `gpt-5.4` instead of requested `kimi-k2.5`.

Source: Karpathy gist `442a6bf555914893e9891c11519de94f`, retrieved via browser. Key spec requirements used for comparison:

- Raw sources are immutable.
- Wiki markdown is the compiled layer.
- Schema file defines conventions.
- Ingest one source, write summary, update index, update entity/concept pages, flag contradictions, append log.
- One source may touch 10-15 wiki pages.
- Query searches wiki and can file answers back.
- Lint checks contradictions, stale claims, orphans, missing concepts/crossrefs, and data gaps.
- `index.md` is content-oriented and updated on ingest.
- `log.md` is append-only with parseable headings like `## [YYYY-MM-DD] ingest | Article Title`.

Top divergences before follow-up commits:

1. No compiled wiki ingest loop: `ingest()` staged atoms only.
2. No trusted page merge/update mechanism: `promote()` wrote one file.
3. Query did not search markdown wiki pages.
4. `index.md` absent.
5. `log.md` absent.
6. Lint/gap scan narrower than Karpathy health check.
7. One source could not touch 10-15 pages.
8. Existing source extractors were not wired into ingest.
9. Contradictions were not detected on ingest/promote.
10. No managed immutable raw-source layer.

## Follow-up commits pushed

1. `64511107` - `feat(chetana): append Karpathy wiki log on ingest and promote`
2. `53784276` - `feat(chetana): cross-update wiki index and backlinks after promote`
3. `3fd2c3d4` - `feat(chetana): route simple ingest through restored extractors`
4. `8bd447db` - `feat(chetana): include wiki markdown in unified query`

## Implemented evolutions

### 1. Append-only `log.md`

Existing surface extended:

- `dharma_swarm/chetana/ingest.py:109`
- `dharma_swarm/chetana/promote.py:125`
- `dharma_swarm/chetana/wiki_log.py:11`

Minimum diff shape:

```diff
+ from .wiki_log import append_wiki_log
+ append_wiki_log(operation="ingest", title=..., atom_path=...)
+ append_wiki_log(operation="promote", title=schema.title, atom_path=trusted_path)
```

Mechanism Test:

- loads: `staging.WIKI_ROOT`
- runs: `append_wiki_log()`
- measures: parseable operation cadence by `## [` headings
- stores: `~/.dharma/knowledge/wiki/log.md`

Anti-slop check: extends existing wiki root; no new root substrate.
Runtime LLM cost: `$0`.
Approval requirement: none; no cron/kernel/telos/dgm mutation.

### 2. `cross-update` index/backlink/contradiction pass

Existing surface extended:

- `dharma_swarm/chetana/promote.py:135`
- `dharma_swarm/chetana/cli.py:159`
- `dharma_swarm/chetana/cross_update.py:26`

Minimum diff shape:

```diff
+ from .cross_update import cross_update_trusted
+ cross = cross_update_trusted(trusted_path)
+ sp_cu = sub.add_parser("cross-update", ...)
```

Mechanism Test:

- loads: trusted atom frontmatter/body, `staging.WIKI_ROOT`, `staging.TRUSTED_DEFAULT`
- runs: `cross_update_trusted()`
- measures: backlink count, missing related count, contradiction flag count
- stores: `index.md`, existing related page `## Backlinks`, `contradictions.md`, `log.md`

Anti-slop check: uses existing wiki concepts directory and only reports missing related pages; it does not create a parallel graph.
Runtime LLM cost: `$0`.
Approval requirement: none.

### 3. Source extractor wiring

Existing surface extended:

- `dharma_swarm/chetana/ingest.py:134`
- `dharma_swarm/chetana/ingest.py:159`
- `dharma_swarm/chetana/extractors/webclip.py:31`
- `dharma_swarm/chetana/extractors/markitdown_ext.py:28`

Minimum diff shape:

```diff
+ from .extractors import extract_via_markitdown, extract_webclip
+ body, src_path, title, tags = _load_simple_source(...)
+ if source_kind == "webclip": clip = extract_webclip(source)
+ if source_kind in ("pdf", "voice"): converted = extract_via_markitdown(source)
```

Mechanism Test:

- loads: existing extractor package
- runs: `extract_webclip()` or `extract_via_markitdown()`
- measures: extractor success/failure by returned result and tests
- stores: normalized source path/title/tags/body inside staged atom frontmatter/body

Anti-slop check: activates restored extractor modules; no duplicate parsing layer.
Runtime LLM cost: `$0`.
Approval requirement: none.

### 4. Wiki-native query

Existing surface extended:

- `dharma_swarm/chetana/graph_unifier.py:56`
- `dharma_swarm/chetana/graph_unifier.py:109`
- `dharma_swarm/chetana/tests/test_graph_unifier.py:41`

Minimum diff shape:

```diff
- sources = sources or ["memory", "gitnexus", "contextplus", "catalytic"]
+ sources = sources or ["wiki", "memory", "gitnexus", "contextplus", "catalytic"]
+ if "wiki" in sources: hits, note = _query_wiki(...)
```

Mechanism Test:

- loads: `staging.TRUSTED_DEFAULT/*.md`
- runs: simple markdown keyword match
- measures: `coverage["wiki"]` and `GraphHit(source="wiki")`
- stores: no writes; query result only

Anti-slop check: extends existing graph unifier instead of adding a search service.
Runtime LLM cost: `$0`.
Approval requirement: none.

## Remaining ranked gaps

1. Bulk-promote policy for ~48k staged atoms: operator-tier. No autonomous bulk promotion was performed.
2. Full multi-page source compilation: current `cross-update` is deterministic maintenance, not a 10-15 page LLM synthesis/merge loop.
3. Trusted page merge semantics: slug collision still blocks instead of merging claims into existing concept pages.
4. Lint expansion: gap scan still lacks orphan scan, crossref completeness, stale-supersession, and robust contradiction analysis.
5. Immutable raw-source store: provenance records source paths, but chetana does not own a canonical raw corpus.
6. Memory MCP graph sync on promote: graph_unifier can query notes, but promote does not yet emit memory MCP entities.
7. Cron dead-man switch: missing CLI caused a silent 15d skip; fixing this touches cron/morning briefing surfaces and needs operator approval.
8. `wiki_circulator` attribution: staged atoms mention `captured_by: wiki_circulator`, but no code with that agent name exists in restored chetana.

## Operator-tier decisions

- Approve or reject any bulk-promote policy for the staged corpus.
- Approve cron-tier changes for dead-man-switch alerting into morning briefing.
- Approve whether page-merge synthesis may call paid/free LLMs at runtime; deterministic merge stays `$0` but full Karpathy compilation likely needs model calls.
- Decide whether `~/.dharma/knowledge/wiki` itself should be git-versioned, and where commits should be created.

## Verification commands

- `python3 -m pytest dharma_swarm/chetana/tests/ -q` -> `68 passed, 1 warning`
- `python3 -m compileall -q dharma_swarm/chetana` -> pass
- import all chetana modules -> `imported=33/33`
- `python3 -m dharma_swarm.chetana.cli --help` -> includes `cross-update`
- `python3 -m dharma_swarm.chetana.cli status` -> `staged=48902 trusted=248 quarantine=1` at final check

## Blocked external writes

The sandbox prevented required writes under `~/.dharma`:

- `~/.dharma/a2a_bus/inboxes/opus_composer/codex_chetana_phase1_done.json`
- `~/.dharma/a2a_bus/inboxes/hermes-m5/codex_chetana_phase1_done.json`
- expected same blocker for `~/.dharma/a2a_bus/state/codex_composer.json`
- expected same blocker for `~/.dharma/external_agents/codex_composer/logs/action_log.jsonl`

Observed error: `operation not permitted`.
