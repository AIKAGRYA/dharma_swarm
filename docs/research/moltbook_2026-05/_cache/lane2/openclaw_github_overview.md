# github.com/openclaw/openclaw — repo overview

**Source:** https://github.com/openclaw/openclaw
**License:** MIT
**Activity (snapshot):** 373k stars, 77.5k forks, 51,129 commits, 3.6k open issues/PRs

## What OpenClaw is
"A personal AI assistant you run on your own devices. It answers you on the channels you already use."
Local-first gateway. Multi-channel inbox: WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Microsoft Teams, Matrix, Feishu, LINE, Mattermost, and more. Voice on macOS/iOS/Android. Live Canvas (agent-driven visual workspace via A2UI).

## Provenance / naming history
Originally **Clawdbot** (Nov 2025) → renamed **Moltbot** → renamed **OpenClaw**. Author: Peter Steinberger (Austrian).

## Architecture components

### Transport & gateway
- Local-first control plane managing sessions, channels, tools, events
- Supports local + remote deployment (SSH, Docker)
- WebSocket-based node pairing for iOS/Android devices

### Agent + skills
- Multi-agent routing with isolated workspaces per agent
- Workspace skills at `~/.openclaw/workspace/skills/`
- Injected prompt files: `AGENTS.md`, `SOUL.md`, `TOOLS.md`
- Sandbox support for non-main sessions (Docker / SSH / OpenShell backends)

### Tools
- First-class: browser, canvas, nodes, cron jobs, sessions management
- Integrations: Discord/Slack actions, webhook automation, Gmail Pub/Sub

### Persistence
- Memory in plain Markdown files at known locations
- No vector DB by default — agent curates what's "important enough to remember"
- Session state, auth profiles, model registry, chat history persisted per-agent under `~/.openclaw/agents/<agentId>`

## Routing of model calls
LLM calls happen **directly from the local OpenClaw process** to provider APIs (Anthropic, OpenAI, Google, Ollama, OpenRouter). API keys stored locally. There is also a Claude-CLI auth mode where OpenClaw reuses the user's Claude subscription session — this is the path that triggered the Anthropic policy reversal in April/May 2026.
