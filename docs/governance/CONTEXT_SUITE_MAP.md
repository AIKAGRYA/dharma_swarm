# Context Suite Map — who reads what, when

**Role:** reference (per `docs/AGENTS.md` document types). This file owns no repo-level fact;
it maps which instruction files shape an agent's context and which mechanism catches each
file's rot. Subordinate to `docs/governance/CANONICAL_DOC_STACK.md` (doc ownership) and
`CLAUDE.md` (behavior).
**Measured:** 2026-07-10 (token figures are chars/4 at that date; re-measure with the
command in the footer — the figures here are dated observations, not live claims).

## Session-start injection (what an agent sees before its first tool call)

| Surface | Injected for | Mechanism |
|---|---|---|
| `CLAUDE.md` | every Claude Code session (local + cloud) | harness auto-injects into system prompt |
| `.claude/settings.json` → `.claude/hooks/session-start.sh` | cloud sessions only (`CLAUDE_CODE_REMOTE=true`) | SessionStart hook; installs `.[dev]` deps, adds no prose context |
| `/AGENTS.md` (repo root) | agents/tools that honor the root convention | tracked minimal entrypoint; defers to `CLAUDE.md` and points edit work to packet preflight |
| `DEVIN.md` | Devin sessions | Devin convention; defers to CLAUDE.md on conflicts (its own header) |

Everything else below is read **on demand**, not injected.

## On-demand context files

| File | Reader / trigger | ~tokens (2026-07-10) | Rot catcher |
|---|---|---|---|
| `CLAUDE.md` | all agents, always | 14.2k before / see PR for after | docops path_guards (link targets), `render_active_track_includes.py --check` (managed block), `tests/test_context_suite.py` (stamp + leak-copy assertions) |
| `docs/AGENTS.md` | agents doing prose-layer work (docs/, reports/, specs/, foundations/, root .md) | 0.9k | docops path_guards + canonical_guard |
| `docs/governance/BUILD_SESSION_ENTRYPOINT.md` | build sessions, after `make onboard` | short stable contract | path_guards + `tests/test_context_suite.py` |
| `docs/governance/CANONICAL_DOC_STACK.md` | agents deciding where a truth lives | 3.6k | docops canonical_guard registry |
| `docs/MEGAFILE_INDEX.md` | before trusting any large map | 4.7k | registered in canonical_guard |
| `docs/architecture/NAVIGATION.md` | module lookup | 8.8k | self-flagged staleness banner; live counts via `python3 scripts/repo_xray.py` |
| `README.md` (agent sections) | humans + first-contact agents | 1.3k | docops change_review |
| `DEVIN.md` | Devin sessions | ~4k | vibe_code_scan.sh hygiene sweep |

## Skill / role registries (loaded per-role, never all at once)

| Registry | Consumer | Parser / contract | ~tokens total |
|---|---|---|---|
| `dharma_swarm/skills/*.skill.md` (8) | swarm subagents | `dharma_swarm/skills.py:192` `SkillRegistry`, yaml-lite frontmatter | 6.2k |
| `.agents/skills/*/SKILL.md` (5) | external coding agents (Devin etc.) | standard name/description frontmatter | 6.5k |
| `.warp/skills/*/SKILL.md` (4) | Warp/Oz operator | each declares a hard authority boundary | 6.1k |
| `dharma_swarm/chetana/claude_code_plugin/` (10 .md) | chetana memory plugin users | plugin skill + slash commands + hooks | 6.6k |

## Live-state surfaces (never answer from prose copies)

Declared portfolio/track intent is owned by `docs/governance/ACTIVE_TRACK.yaml`
and evaluated by `python3 scripts/governance/check_track_status.py`.
`make onboard` may display a compact session-status projection; it is not a
runtime or liveness oracle. The managed `ACTIVE_TRACK:START/END`
blocks in `CLAUDE.md` and `docs/governance/SOVEREIGN_MANIFEST.md` are stamped projections of the YAML
(compact digest since 2026-07-10) — they carry ownership boundaries and pointers, not
live status, and `render_active_track_includes.py --check` (CI: `active-track.yml`,
plus `make docops-integrity`) fails when they drift from the YAML.
`BUILD_SESSION_ENTRYPOINT.md` deliberately embeds no portfolio copy; it owns only
the stable boundary between session status, edit admission, closeout, CI, and
persistent-agent registration.

## Re-measure

```bash
# token estimate for any file: chars/4
python3 -c "import sys;t=open(sys.argv[1]).read();print(len(t)//4)" CLAUDE.md
# staleness of the managed blocks
python3 scripts/governance/render_active_track_includes.py --check
# content contract of the suite
python3 -m pytest tests/test_context_suite.py -q
```
