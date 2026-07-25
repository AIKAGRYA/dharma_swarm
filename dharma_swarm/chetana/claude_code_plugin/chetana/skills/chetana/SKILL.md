---
name: chetana
description: Use when the user wants to capture a session, ingest external content as atoms, promote staged atoms, scan for stale atoms, propose revivals, surface knowledge gaps, or render the memory palace. Triggers: "chetana", "ingest this", "promote that atom", "what's stale", "revive my wiki", "find gaps", "memory palace", "what did I say last session".
---

# chetana — connective tissue for the grand memory system

You have access to **chetana** (Sanskrit: चेतना, "consciousness") — a Python package that connects Dhyana's five distributed knowledge substrates into one operational PKM. It is installed as a plugin and accessible via:

- **CLI**: `python -m dharma_swarm.chetana.cli <subcommand>`
- **Hooks**: `SessionStart`, `Stop`, `SessionEnd`, `PreCompact`, `SubagentStop` fire automatically every session
- **Slash commands**: `/chetana-status`, `/chetana-revive`, `/chetana-gap-scan`, `/chetana-ingest`, `/chetana-palace`, `/chetana-promote`

## Resolving the chetana python (do this once per session)

Try in order, use the first that succeeds at `<python> -c "import dharma_swarm.chetana"`:
1. the dev worktree venv if present (e.g. `~/dharma_chetana/.venv/bin/python`)
2. the current repo's `.venv/bin/python`
3. bare `python3` with the repo on `PYTHONPATH`

If none import chetana, STOP and tell the user exactly that, pointing at: `cd ~/dharma_chetana && pip install -e ".[mcp,dev]"`. Never silently fall back to running nothing, and never guess a machine-specific path as fact — the dev worktree only exists on the Mac.

## When to invoke chetana

| User signal | Move |
|---|---|
| "what's stale?" / "what needs re-verification?" | `chetana decay` |
| "revive my wiki" / "re-integrate stale atoms" | `chetana revive --all` (proposal); add `--apply` only on explicit user confirmation |
| "what gaps are in the wiki?" / "what should I research?" | `chetana gap-scan` |
| "ingest this PDF / clip / note" | `chetana ingest <source> --kind <pdf\|webclip\|note>` |
| "show me the memory palace" / "where do my atoms live?" | `chetana palace` |
| "promote this staged atom" / "approve atom X" | `chetana promote <staged_path>` |
| "what did I capture last session?" | read `~/.dharma/sessions/captures/daily/<today>/` |
| "show me chetana state" | `chetana status` |

## The grand-memory architecture

Five layers, each with a chetana surface:

| Layer | What | chetana surface |
|---|---|---|
| L0 atoms | frontmattered markdown | `ingest` writes staged; `promote` writes trusted |
| L1 graph | bidirectional links over memory MCP + gitnexus + contextplus + catalytic | `query` |
| L2 PARA | dynamic projections by Projects/Areas/Resources/Archives | `palace --para` |
| L3 palace | 10 Pillars rooms, JSON Canvas | `palace` |
| L4 governance | TelosGatekeeper + KernelGuard + provenance schema | every `promote` and `revive --apply` routes through it |

## Continuous evolution cycle (already wired — don't re-trigger manually)

1. **Every SessionStart**: hook surfaces stale atoms + top wiki gaps + recent captures into the systemMessage.
2. **Every Stop**: hook ingests the just-finished JSONL into staged atoms in `~/.dharma/knowledge/staging/<date>/`. Nothing auto-promotes — review before trusting.
3. **Every PreCompact**: hook drops a checkpoint to `~/.dharma/sessions/captures/in_flight/`.
4. **Every SubagentStop**: hook records subagent stops to a daily manifest.

If a hook seems not to have fired, check `~/.dharma/sessions/captures/chetana_hook.log` before re-running anything by hand.

## Stale → revive, not exile

When an atom passes `stale_after`, the **default move is REVIVE, not quarantine**. Revival = read the atom, scan corpus for new neighbors / backlinks / questions now answered, propose patches, re-sign axiom signature, append a `revival_chain` entry to provenance. Quarantine is opt-in last resort (`chetana decay --quarantine`).

## Reporting back to the user

After any chetana operation, report in this shape — never just "done":

```
chetana <subcommand>: <ok | blocked | failed>
wrote/changed: <paths, or "nothing (proposal only)">
gate: <ALLOW | WARN (still staged) | BLOCK → quarantined> (write ops only)
next: <the single follow-up that makes sense, e.g. "review 3 staged atoms before promoting">
```

Example: `chetana ingest: ok · wrote ~/.dharma/knowledge/staging/2026-07-05/a1b2.md (staged, NOT trusted) · next: /chetana-promote after review`.

## Reference paths (state lives under ~/.dharma — same on every machine)

- Staging area: `~/.dharma/knowledge/staging/<date>/`
- Trusted atoms: `~/.dharma/knowledge/wiki/concepts/`
- Quarantine: `~/.dharma/knowledge/quarantine/`
- Session captures: `~/.dharma/sessions/captures/daily/<date>/`
- Hook log: `~/.dharma/sessions/captures/chetana_hook.log`
- Source of truth for the code: `dharma_swarm/chetana/` in whichever checkout is live (the Mac dev worktree is `~/dharma_chetana`, branch `feat/chetana-grand-memory` — verify it exists before citing it)

## When NOT to invoke chetana

- Ad-hoc Python scripting not tied to memory ops — chetana is not a general utility.
- Touching the dharma_swarm runtime (daemon, gates) — separate surface.
- Chat history of the *current* session — chetana captures on Stop, not in-flight.
- Never `promote` or `revive --apply` without explicit user say-so — staged→trusted is a trust boundary, and the gates exist because it's crossed deliberately.
- Never edit trusted atoms or their provenance by hand — all writes route through the CLI so gate checks and signatures stay valid.
