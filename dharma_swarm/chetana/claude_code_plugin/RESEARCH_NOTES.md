# Research notes — session-capture continuous-evolution patterns (2026-04-27)

Background research conducted before integrating chetana into Claude Code.
Captured here so the pattern lineage is auditable and so future maintainers
know why each design choice was made.

## What's already there (Dhyana's machine, Apr 2026)

- **9,556 session JSONL files** at `~/.claude/projects/<sanitized-cwd>/<uuid>.jsonl`
  — the per-session transcript Claude Code writes natively. 124 in the
  primary `-Users-dhyana` project alone. This is the existing capture corpus
  that nothing was reading systematically.
- **Six plugins enabled** (`superpowers`, `everything-claude-code`,
  `frontend-design`, `claude-mem`, `maestro`, `obey`). Each ships its own
  hooks + skills. None close the loop into a typed knowledge system.
- **17 hooks already wired** in `~/.claude/settings.json` across
  `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`.
  chetana adds plugin-scoped hooks rather than touching this file directly.

## Plugin canonical structure (verified across claude-mem, obey, superpowers, maestro)

```
~/.claude/plugins/marketplaces/<source>/
├── .claude-plugin/
│   └── marketplace.json     # marketplace manifest
└── <plugin-name>/
    ├── .claude-plugin/
    │   └── plugin.json      # plugin manifest, references hooks/skills/commands
    ├── hooks/
    │   └── hooks.json       # registers events
    ├── scripts/             # actual hook implementations
    ├── skills/
    │   └── <skill>/SKILL.md
    ├── commands/
    │   └── <name>.md        # slash commands
    └── README.md
```

Hook registration via `plugin.json`:
```json
{
  "name": "chetana",
  "version": "0.3.0",
  "hooks": "./hooks/hooks.json",
  "skills": "./skills/",
  "commands": "./commands/"
}
```

## Available hook events (verified against the live schema 2026-04-27)

```
PreToolUse | PostToolUse | PostToolUseFailure | PostToolBatch
Notification | UserPromptSubmit | UserPromptExpansion
SessionStart | SessionEnd | Stop | StopFailure
SubagentStart | SubagentStop
PreCompact | PostCompact
PermissionRequest | PermissionDenied
Setup | TeammateIdle | TaskCreated | TaskCompleted
Elicitation | ElicitationResult | ConfigChange
WorktreeCreate | WorktreeRemove
InstructionsLoaded | CwdChanged | FileChanged
```

chetana uses: `SessionStart`, `Stop`, `SessionEnd`, `PreCompact`, `SubagentStop`.

## Hook command shape

```json
{
  "type": "command",
  "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/session_start.sh",
  "timeout": 8,
  "async": false
}
```

`${CLAUDE_PLUGIN_ROOT}` resolves to the plugin root at runtime. Hook stdin
receives a JSON payload with session context. Hook stdout (when JSON with
`systemMessage` key) gets injected into the session's context.

## Marketplace source types (canonical)

For local development, the schema accepts:
- `"directory"` — path containing `.claude-plugin/marketplace.json`
- `"file"` — direct path to a marketplace.json
- `"github"` — owner/repo
- `"git"` — full URL
- `"npm"` — package name
- `"hostPattern"` / `"pathPattern"` — regex allowlists

NOT accepted: `"local"` (common mistake; chetana initially used it; corrected).

## What "continuous evolution" looks like in the wild (2026 state of art)

| System | Capture | Process | Reuse | Notes |
|---|---|---|---|---|
| **Karpathy LLM Wiki** (gist) | one source at a time | LLM writes summary + index pages + chronological log | injected via `CLAUDE.md`-equivalent | Three-layer architecture: immutable raw / generated wiki / schema doc. The pattern chetana operationalizes. |
| **claude-mem** (thedotmack) | every CC session | tree-sitter + agent-sdk compression of JSONL | injected at SessionStart | Active locally. Uses tree-sitter for code-aware compression. Has 12+ hooks. |
| **Basic Memory MCP** | manual + agent | markdown notes + SQLite index | MCP search tool | Reference impl for "AI memory as local markdown." |
| **Mantra** (desktop) | every CC/Cursor/Gemini/Codex session | session replay UI | scrub timeline | Audit/debug branch, not memory branch. |
| **Daniel Miessler PAI** | manual + agents | TELOS layer + capability registry | injected into agent context | Personal AI infrastructure with TELOS — close to dharma_swarm in spirit. |
| **Garry Tan GBrain** | manual + auto | thousands of files + cron consolidation | citation-repaired | Production agent memory backbone. |
| **Bryce Robbie Lazy Obsidian** | web clipper + MarkItDown | Obsidian Skills + Graphify + qmd | PARA folders | Field synthesis stack; complementary to LLM Wiki. |

## Three missing layers (confirmed gaps in published patterns)

1. **Provenance schema enforced at write time** — no published system requires
   every promoted claim to carry source, capture chain, gate decision,
   axiom signature, review status. Bryce's lazy method, Karpathy's wiki, and
   Basic Memory all leave this implicit.
2. **Contradiction handling** — published systems silently overwrite older
   claims. chetana's `revival_chain` makes the audit trail explicit.
3. **Decay as re-integration trigger** — every system has accretion; none
   has a structural "stale → revive" loop. chetana's revival module is
   net-new in this regard.

## chetana's contribution beyond the published state-of-the-art

1. **`provenance.py`** — strict pydantic schema requires source / capture
   chain / gate result / axiom signature on every promoted atom. No public
   system enforces this contract.
2. **`governance.py`** — every promote routes through `dharma_swarm.telos_gates.TelosGatekeeper`
   (11 gates) and `dharma_swarm.dharma_kernel.KernelGuard` (25 axioms). The
   substring-match limitation is acknowledged; chetana doesn't add a
   competing semantic layer (waits for the separate Phase 6b campaign).
3. **`revival.py`** — stale atoms get re-integrated, not exiled. Append-only
   `revival_chain` in provenance records every revival event.
4. **Lenient legacy parse** — chetana reads pre-existing Karpathy-style
   atoms without requiring schema migration. 121/144 of the live wiki parses
   cleanly under lenient mode; 23 truly-non-conforming atoms are flagged.
5. **Five-layer PKM** — atoms / graph / PARA view / memory palace / governance
   overlay. No public system unifies all five.

## Design choices documented for future maintainers

- **Bash-only hook scripts** (not Python). Reason: zero external deps, runs
  on any macOS/Linux without venv issues. Same choice obey made.
- **Plugin discovers Python interpreter** rather than hard-coding a path.
  Survives the dev-worktree → canonical-install transition without rewiring.
- **Hooks NEVER block the session.** Every script has bounded timeout,
  silent degradation on failure, log-only error reporting. Failure mode is
  "no chetana for this session," never "session can't start."
- **Stop hook is async.** 30s budget for ingesting a session that may have
  hundreds of turns. async=true means Claude Code returns control to the
  user immediately; the ingest finishes in background.
- **PreCompact writes a checkpoint** so even mid-session compactions leave
  recovery points. Compactions are common (auto + manual); without this hook,
  compacted context vanishes from chetana's view.
- **SubagentStop is opt-outable** via `CHETANA_CAPTURE_SUBAGENTS=0`. Default
  is to capture. Subagent transcripts are smaller and higher-signal than
  main-session transcripts; usually worth keeping.

## What's NOT done in v0.3 (deferred to v0.4+)

- **Auto-promote pipeline** — every session ingest goes to `staging/`; nothing
  enters trusted wiki without manual `/chetana-promote` or `/chetana-revive --apply`.
  v0.4 could add a confidence-threshold auto-promote with witness logging.
- **Cron decay/revive** — currently only fires on SessionStart (too narrow).
  v0.4: launchd 04:30 daily job that runs `chetana revive --all` and
  `chetana decay --json` against the trusted wiki.
- **MCP server registration in Claude Code** — `mcp_server.py` is built but
  not auto-mounted. Requires adding to `~/.claude/.mcp.json` with the
  `chetana@local-chetana` plugin namespace.
- **Subagent JSONL ingest** — currently we just log subagent stops. The
  actual transcript files in `/tmp/claude-*/.../tasks/<aid>.output` could be
  ingested as their own atoms.
- **Semantic gate upgrade** — chetana waits for the separate Phase 6b
  campaign to land before swapping substring matching for LLM-evaluated
  rubrics. When that lands, chetana benefits without changes.
