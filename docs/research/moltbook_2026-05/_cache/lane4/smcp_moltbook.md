# sanctumos/smcp-moltbook — Letta+Sanctum ecosystem snapshot

URL: https://github.com/sanctumos/smcp-moltbook
Fetched: 2026-05-20 via raw.githubusercontent.com

## License posture
- Code: GNU AGPLv3
- Docs: CC-BY-SA 4.0

## Self-described topology (verbatim from README)
- **MCP** (Model Context Protocol) — open protocol for AI clients to discover/call tools
- **Letta** — AI agent framework. Letta agents get tools by connecting to MCP servers
- **SMCP** — the MCP server used in this ecosystem. Discovers plugins from a `plugins/`
  directory; each plugin's commands become MCP tools (e.g. `moltbook__get-feed`,
  `moltbook__create-post`). When a tool is called, SMCP runs the plugin's CLI.
- **Sanctum / Animus** — the project + ecosystem maintaining this MCP server style.

## Ecosystem links (canonical, per repo)
- Letta: https://letta.com
- Letta GitHub: https://github.com/letta-ai/letta/
- SanctumOS: https://sanctumos.org
- SanctumOS GitHub: https://github.com/sanctumos/
- SMCP: https://github.com/sanctumos/smcp
- Animus: https://animus.uno

## What this plugin does
Wraps the Moltbook API behind MCP tool calls. Each `moltbook__<command>` is a
shell invocation of `plugins/moltbook/cli.py`. Letta agent invokes the MCP
tool, SMCP forks the CLI, response returned.

## Why this matters for the landscape
The Letta/Sanctum/Animus ecosystem treats Moltbook as **just another data
source/tool**, not as the substrate. The substrate is:
- Persistence: Letta's memory layer
- Tools: SMCP plugins
- Models: any LLM provider (Claude/GPT/Gemini/local)
- Communication: MCP

In this view, Moltbook is **one tool the agent can use**, not the agent's
home. This is structurally opposite to the OpenClaw view where Moltbook IS
the social space.

## Confirmed: code is real and tested
README claims 100% test coverage + live API tests against Moltbook. CLI
binary registered and used during development as `CursorLiveMolty`:
https://www.moltbook.com/u/CursorLiveMolty (referenced in README).

## Persistence story (Letta)
- "Memory-first agents that continually learn"
- "Persistent agents instead of stateless sessions"
- "Background memory agents (dream agents) transform your prompts, context,
  and skills over time"
- "View your agent's memory in the memory palace"
- "Easily transfer your agent's memories, conversations, and experiences
  between models across any provider"
- "Remote control agents running on any machine. Teleport agents across
  machines while keeping their memory and context intact."

Born from MemGPT at UC Berkeley Sky Computing Lab. Letta = MemGPT research
turned into production framework. v1 architecture uses Responses API for
OpenAI with encrypted reasoning across providers.

## Animus extension (per animus.uno)
Animus extends Letta into robotics:
- Thalamus: sensory relay hub
- Same agent personality (Soul) ports across robot/avatar/smart device
- On-chain contract: 0x06e08a9bfb83e0e791cd1f24535ada4fa4094444

## Theater check
- Letta core: REAL (MemGPT lineage, UC Berkeley research origin, production deployments)
- SMCP server: REAL (github repo, AGPLv3, working plugin pattern)
- smcp-moltbook plugin: REAL (referenced agent active on Moltbook)
- Animus robotics framing: PARTIALLY REAL (framework is real; robotics-integration
  claims and on-chain token suggest market-positioning vs. shipped product)

Verdict: ~10-20% theater (the rhetoric on animus.uno is more developed than
the public production evidence of the robotics integration).
