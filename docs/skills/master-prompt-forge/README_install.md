# Installing master-prompt-forge

**Doc role:** `reference` (per `docs/AGENTS.md` § Authority Model). This
package is portable tooling for external distribution — it carries no
operational authority over this repo, and none of its doctrine (hygiene
rules, prompt contract, quality gate) governs this repo's own agents or
docs. Once installed elsewhere, its instructions apply only within the
Skill/plugin scope the installing user grants it — the same as any other
Claude Skill.

This directory holds the tracked, maintained copy of the `master-prompt-forge`
Claude Skill. It lives here in git so it survives across checkouts; it is
*not* auto-loaded into any Claude Code session by virtue of living in this
repo (Claude Code Skills are discovered from `~/.claude/skills/` or a
project's `.claude/skills/`, both of which are local/gitignored — see the
"Skills & Agent Role Registries" section of the repo's `CLAUDE.md`). To
actually use it, install it into one of those locations.

## Claude Code — personal (all your projects)

```bash
mkdir -p ~/.claude/skills
cp -R docs/skills/master-prompt-forge ~/.claude/skills/master-prompt-forge
```

## Claude Code — project-local (this repo or another)

```bash
mkdir -p .claude/skills
cp -R docs/skills/master-prompt-forge .claude/skills/master-prompt-forge
```

## claude.ai — custom Skill upload

claude.ai's custom Skills UI takes a zip. Build one from this directory:

```bash
cd docs/skills
zip -r master-prompt-forge.zip master-prompt-forge
```

Upload `master-prompt-forge.zip` through the custom Skills interface.
Review the contents before installing anywhere — Skills can carry
instructions and executable code, so audit what you're granting. Everything
in `scripts/` here is read-only reporting; nothing writes or deletes.

## Codex

Codex reads layered `AGENTS.md` guidance (global `~/.codex/AGENTS.md` and
per-repo `AGENTS.md`) before doing work. Paste
`codex/AGENTS.fragment.md` into either so Codex applies the same
seed-to-master-prompt forging behavior and the same workspace-hygiene
doctrine without this skill needing to be re-invoked by name:

```bash
cat docs/skills/master-prompt-forge/codex/AGENTS.fragment.md >> ~/.codex/AGENTS.md
# or, for one repo only:
cat docs/skills/master-prompt-forge/codex/AGENTS.fragment.md >> AGENTS.md
```

## Using it

Once installed, invoke it in Claude Code / claude.ai with something like:

```
Use master-prompt-forge. Turn this rough seed into a master prompt for
Claude Code/Codex:
[paste your messy seed here]
```

or just:

```
Forge this into a master prompt:
[paste seed]
```
