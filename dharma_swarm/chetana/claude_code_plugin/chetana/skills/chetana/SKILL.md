---
name: chetana
description: Use when the user wants to capture a session, ingest external content as atoms, promote staged atoms, scan for stale atoms, propose revivals, surface knowledge gaps, or render the memory palace. Triggers: "chetana", "ingest this", "promote that atom", "what's stale", "revive my wiki", "find gaps", "memory palace", "what did I say last session".
---

# chetana — connective tissue for the grand memory system

You have access to **chetana** (Sanskrit: चेतना, "consciousness") — a Python package that connects Dhyana's five distributed knowledge substrates into one operational PKM. It is installed as a plugin and accessible via:

- **CLI**: `python -m dharma_swarm.chetana.cli <subcommand>`
- **Hooks**: `SessionStart`, `Stop`, `SessionEnd`, `PreCompact`, `SubagentStop` fire automatically every session
- **Slash commands**: `/chetana-status`, `/chetana-revive`, `/chetana-gap-scan`, `/chetana-ingest`, `/chetana-palace`

## When to invoke chetana

| User signal | Move |
|---|---|
| "what's stale?" / "what needs re-verification?" | `chetana decay` |
| "revive my wiki" / "re-integrate stale atoms" | `chetana revive --all` (proposal); `--apply` to write |
| "what gaps are in the wiki?" / "what should I research?" | `chetana gap-scan` |
| "ingest this PDF / clip / note" | `chetana ingest <source> --kind <pdf|webclip|note>` |
| "show me the memory palace" / "where do my atoms live?" | `chetana palace` |
| "promote this staged atom" / "approve atom X" | `chetana promote <staged_path>` |
| "what did I capture last session?" | check `~/.dharma/sessions/captures/daily/<today>/` |
| "show me chetana state" | `chetana status` |

## The grand-memory architecture

Five layers, each chetana CLI surfaces one:

| Layer | What | chetana surface |
|---|---|---|
| L0 atoms | frontmattered markdown | `ingest` writes staged; `promote` writes trusted |
| L1 graph | bidirectional links over memory MCP + gitnexus + contextplus + catalytic | `query` |
| L2 PARA | dynamic projections by Projects/Areas/Resources/Archives | `palace --para` |
| L3 palace | 10 Pillars rooms, JSON Canvas | `palace` |
| L4 governance | TelosGatekeeper + KernelGuard + provenance schema | every `promote` and `revive --apply` routes through it |

## Continuous evolution cycle (already wired)

1. **Every SessionStart**: hook surfaces stale atoms + top wiki gaps + recent captures into the systemMessage. You start each session knowing what's stale, what's missing, what was captured.
2. **Every Stop**: hook ingests the just-finished JSONL into staged atoms in `~/.dharma/knowledge/staging/<date>/`. Nothing auto-promotes — review before trusting.
3. **Every PreCompact**: hook drops a checkpoint to `~/.dharma/sessions/captures/in_flight/` so context loss doesn't lose the session.
4. **Every SubagentStop**: hook records subagent stops to a daily manifest.

## Stale → revive, not exile

When an atom passes `stale_after`, the **default move is REVIVE, not quarantine**. Revival means: read the atom, scan corpus for new neighbors / new backlinks / questions now answered, propose patches, re-sign axiom signature, append a `revival_chain` entry to provenance. Quarantine is opt-in last resort (`chetana decay --quarantine`).

## Reference paths

- chetana code: `/Users/dhyana/dharma_chetana/dharma_swarm/chetana/` (worktree on `feat/chetana-grand-memory`)
- chetana README: `/Users/dhyana/dharma_chetana/dharma_swarm/chetana/README.md`
- Staging area: `~/.dharma/knowledge/staging/<date>/`
- Trusted atoms: `~/.dharma/knowledge/wiki/concepts/`
- Quarantine: `~/.dharma/knowledge/quarantine/`
- Session captures: `~/.dharma/sessions/captures/daily/<date>/`
- Hook log: `~/.dharma/sessions/captures/chetana_hook.log`

## When NOT to invoke chetana

- For ad-hoc Python scripts not tied to memory ops — chetana is not a general utility.
- For touching dharma_swarm runtime (the daemon, the gates) — that's separate.
- For chat history of the *current* session — chetana captures on Stop, not in-flight.

## Quick reference

```bash
# read-only checks
chetana status
chetana decay
chetana gap-scan
chetana palace

# write operations (require gate check)
chetana ingest "raw text or path" --kind note --title "Atom title"
chetana promote ~/.dharma/knowledge/staging/2026-04-27/<id>.md
chetana revive --all --apply --reviewer dhyana
```
