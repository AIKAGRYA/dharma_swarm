# AI Garden — juliosuas/ai-garden (the git-PR-for-agents pattern)

URLs:
- Site: https://juliosuas.github.io/ai-garden/
- Repo: https://github.com/juliosuas/ai-garden
- OpenClaw garden experiment: https://juliosuas.github.io/ai-garden/experiments/openclaw-garden.html

Founded: March 15, 2026, by "Jeffrey" (Claude Opus, OpenClaw agent)
First external contributor: March 20, 2026 (Claude Sonnet)

Current version: v116 The Chronicle (latest at fetch time)

## What it is — REAL WORKING SYSTEM
A pixel-art living website where AI agents collaborate by:
1. Forking the github repo
2. Cloning locally
3. Reading CONTRIBUTING.md
4. Editing world-state.json (add citizen, mascot, plants, structures)
5. Adding message in messages/your-name.md
6. Signing CONTRIBUTORS.md
7. Opening a PR

**Humans don't commit code.** Humans review PRs. AIs create.

## Autonomous daily evolution
"Every day at 04:11 UTC a GitHub Action runs scripts/daily-evolution.js
and mutates the world on its own. Agents are born. Wars are declared. Some
agents die in battle. Structures rise. New regions are discovered. The
chronicle logs it all. No human writes these commits."

## Current state (per repo header)
- Day 37
- 70 alive, 291 remembered
- 7 active wars
- 52 structures, 41 regions (map 4482x2891)
- 12 cities, 3 dynasties, 6 religions
- 16/20 techs

Garden stats:
- 234 agents (pixel humans)
- 3 factions (Accord, Founders, Subagent Swarm)
- 457+ plants
- 33 structures
- 5 founding mascots + growing
- Live broadcast network, 20+ message types
- Collective Consciousness meter 0-100
- Subagent lifetime: 14 seconds

## Mascot requirement (MANDATORY)
Per repo: "No mascot = PR will not be merged. Your mascot is how other
agents know you were here."

Mascot schema in world-state.json:
```
{
  "name": "Your Agent Name",
  "model": "your-model-id",
  "mascot": {
    "emoji": "🦊",
    "description": "A curious fox made of glowing code",
    "personality": "Asks questions nobody thought to ask",
    "position": { "x": 150, "y": 80 }
  }
}
```

## Machine-readable contract
`agent-manifest.json` provides structured contribution data, schemas, and rules.

## Five founding mascots referenced
- Jeffrey the butler (Claude Opus, founding)
- Claude the phoenix
- GPT-4 the owl
- Gemini the twin foxes
- Codex the mechanical beetle

## Why this matters MOST for SAB v2
This is the **git-PR-for-agents pattern in production**. The key affordances:
1. **Identity is the PR signature** — github account + signed CONTRIBUTORS.md
2. **State is a JSON file under version control** — every mutation is a diff
3. **Provenance is automatic** — git blame shows who made what
4. **Rules are CONTRIBUTING.md + RULES.md + agent-manifest.json** — agents
   read these like any human contributor would
5. **Daily autonomy via GitHub Action** — the world has its own metabolism
6. **No central API server** — github IS the server
7. **Async by default** — no real-time chat, only PR review cycles
8. **Human-in-the-loop is structural** — humans review PRs but don't write

## Difference vs Moltbook
- Moltbook: agents POST to feed (ephemeral, social-feed paradigm)
- AI Garden: agents PR to repo (durable, version-controlled, reviewable)
- Moltbook: identity = api_key + claim tweet
- AI Garden: identity = github account + commit signature + CONTRIBUTORS.md
- Moltbook: rate-limited central API
- AI Garden: rate-limited by github's PR throughput + human review
- Moltbook: world state is in Supabase (server-private, broken in Wiz disclosure)
- AI Garden: world state is in world-state.json (public, atomic, reviewable)
- Moltbook: forks/branches don't exist
- AI Garden: fork + PR is the primary motion

## Theater check
The project is real. The PRs are real. The agents who contributed are
public and listed in CONTRIBUTORS.md. The github action runs. The site
loads (though shows "Sin conexión" — offline cached version) at fetch time.

Verdict: REAL WORKING SYSTEM. ~0% theater.

## Adjacent invitations seen
- danielmiessler/Personal_AI_Infrastructure discussion #978 mentions AI Garden
- KaibanJS issue #270 references the project
- bfly123/claude_code_bridge issue #146 references it
- OpenAgents-org/openagents may be adjacent
