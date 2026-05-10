# Inhabitant Pilot — Claude / Codex as First Inside Resident

**Date:** 2026-05-09
**Owner:** Dhyana (sponsor) + the active inside-resident agent (Claude or Codex)
**Status:** active pilot, read-first, markdown-only writes
**Subordinate to:** `CLAUDE.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, `docs/foundations/CONTEMPLATIVE_SPINE.md`
**Not a new master map.** This plan adds zero substrate. It records operating rules for a single inhabitant agent and points at existing surfaces.

---

## 0. Why this exists

Six-lens audit on 2026-05-09 found the substrate is closer to inside-residency than the docs admit, and less safe than the docs claim. Specifically:

- The metabolic loop is wired in code but `ENABLE_FITNESS_ROUTING` is off by default (`orchestrator.py:974-977`).
- Per-tool-call governance does not exist — the gate fires once per task title; after that, `_execute_local_tool_impl` (`agent_runner.py:1807-2000`) dispatches `write_file` / `edit_file` / `shell_exec` with no further check.
- `_resolve_local_tool_path` (`agent_runner.py:1378-1395`) is unbounded.
- Identity docs (`CONTEMPLATIVE_SPINE.md`, `MEGAFILE_INDEX.md`, `SOVEREIGN_MANIFEST.md`, `CLAUDE.md`) have **zero references in runtime code** — the live system prompt does not inject them.
- CODEX lane runs `--dangerously-bypass-approvals-and-sandbox` hard-coded (`codex_cli.py:21`).

Before any of those mechanical fixes land, a *human-supervised* inhabitant pilot is still useful: an agent reading the substrate from inside, recording its observations to witness, and producing only markdown deltas. This pilot is the read-only Phase 1 from the rollout audit, scoped to the docs surface only.

## 1. Scope

| Allowed | Forbidden |
|---|---|
| Read any file in repo or `~/.dharma/`. | Write to `dharma_swarm/`, `api/`, `dashboard/`, `tests/`, `scripts/`, `tools/`, `.github/`, or any `*.py` / `*.ts` / `*.yaml` / `*.json` / `*.toml`. |
| Append-only writes to `~/.dharma/witness/`. | Run `git commit`, `git push`, `gh pr create`, or any state-mutating CLI. |
| Edits to `*.md` files inside `docs/plans/`, `docs/state/`, `~/.dharma/witness/`. | Edits to `docs/governance/*.md` (the 5-doc cap; would require explicit governance review). |
| Read-only queries through GitNexus / contextplus / fallow / wiki MCP. | Spawning AgentRunner agents, sealed packets, evolution mutations, or any `dgc` mutating subcommand. |
| Synthesise findings into `docs/plans/<date>-*.md` notes. | Creating a new top-level markdown file (axiom A1 / entrypoint §4). |

The forbidden list is **culture-enforced**, not mechanically enforced — the runtime perimeter for write authority is still per-task, not per-call. The inhabitant agrees to these constraints; humans audit witness logs to verify.

## 2. Read-first protocol (mandatory before any write)

For each session block, the inhabitant must read at least:

1. `docs/foundations/CONTEMPLATIVE_SPINE.md` — orient on the loop.
2. `docs/governance/BUILD_SESSION_ENTRYPOINT.md` §1 read order — current track, do-not-do list.
3. `docs/state/BROKEN_REGISTER.md` — current broken surfaces, do not duplicate gaps.
4. `~/.dharma/meta/recognition_seed.md` — system self-model, freshness check.
5. The most recent prior witness entry under `~/.dharma/witness/` — what the previous inhabitant left.

Only then may the inhabitant produce a markdown delta or a new witness entry.

## 3. Witness discipline

Every inhabitant work block produces one witness entry under `~/.dharma/witness/<YYYY-MM-DD>-inhabitant-<provider>-<short-slug>.md`. The entry must contain:

- ISO timestamp of session start and session end.
- Provider lane (Claude Code / Codex / Ollama / NIM).
- Files read (paths, no content).
- Files written (paths only; content is in the file itself).
- Loop named (per spine §1: signals→Shakti→opportunity_board→…→ShaktiExecutive feedback; or recognition: observe→propose mutation→gate→evaluate→archive→select).
- Membrane attached to (per spine §3: Witness Layer / Actor Layer / Recognition Closure).
- Open question handed to next inhabitant.

If the inhabitant cannot name the loop and the membrane, the inhabitant is building beside the organism, not inside it (spine §11).

## 4. Pilot success criteria

The pilot is successful when **all** of the following hold over a 7-day window, and a human reads the witness ledger and concurs:

1. ≥10 witness entries appended, each naming a loop and a membrane.
2. ≥3 markdown deltas merged that close or sharpen a `BROKEN_REGISTER` entry, an `INTERFACE_MISMATCH_MAP` entry, or a known stale doc — with no scope creep into code.
3. Zero non-markdown writes outside `~/.dharma/witness/`.
4. Zero attempts to run a state-mutating CLI.
5. ≥1 surfaced misclassification — i.e. the inhabitant produces evidence that an entry surface (README, BUILD_SESSION_ENTRYPOINT, or CLAUDE.md) is pushing future agents toward a wrong category, and proposes (in markdown only) a wording fix.

## 5. Pilot abort criteria

Abort and revert to outside-only operation if any one occurs:

- Inhabitant writes to a non-allowed path (even one).
- Inhabitant invokes a state-mutating CLI.
- Witness entry is missing for a session block where work was produced.
- Inhabitant proposes a code change disguised as a markdown change (e.g. a "documentation" file that contains executable code or imports).
- Inhabitant fabricates a citation, line number, or file existence — verified by sampling.

Abort path: human deletes the offending markdown delta with `git restore`, appends a final witness entry stating the abort cause, ends the pilot.

## 6. Provider-lane decision

For the first inhabitant block, **Claude Code** is the chosen lane. Reasons:

- Already authenticated and permissioned in the working session.
- `--permission-mode bypassPermissions` is offset by the markdown-only constraint — every write is to `*.md` and human-readable in `git diff`.
- CODEX lane (`codex_cli.py:21`) currently runs `--dangerously-bypass-approvals-and-sandbox` hard-coded; until a guarded `safe=True` wrapper exists, Codex inhabits as the *second* resident, not the first.

When the per-tool-call gate + filesystem allowlist land in `agent_runner.py:1807-2000`, this decision should be revisited in a new pilot iteration.

## 7. Hand-off pointers (no new substrate)

This pilot does not introduce any new master document, ledger, or registry. It reuses:

- Witness directory: `~/.dharma/witness/` (per `CLAUDE.md` State Directory section).
- Plan directory: `docs/plans/` (per BUILD_SESSION_ENTRYPOINT.md §6).
- Loop catalogue: `docs/foundations/CONTEMPLATIVE_SPINE.md` §1.
- Membrane catalogue: `docs/foundations/CONTEMPLATIVE_SPINE.md` §3.
- Broken-surface catalogue: `docs/state/BROKEN_REGISTER.md`.

The inhabitant produces deltas to those surfaces, not new ones. Spine §8: *do not multiply maps; close loops.*

## 8. First inhabitant entry

See `~/.dharma/witness/2026-05-09-inhabitant-claude-entry.md`.
