# External Research Sources

Date researched: 2026-05-21

This packet uses current external sources to calibrate Dharma Swarm against the frontier. Vendor docs are used for product capabilities; research papers and security docs are used for architecture and risk.

## Primary And Near-Primary Sources

- OpenAI Agents SDK docs: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK sandbox/harness announcement: https://openai.com/index/the-next-evolution-of-the-agents-sdk/
- Anthropic multi-agent research system: https://www.anthropic.com/engineering/multi-agent-research-system
- Claude Code hooks docs: https://code.claude.com/docs/en/agent-sdk/hooks
- Claude Code subagents and persistent memory docs: https://code.claude.com/docs/en/sub-agents
- GitHub Copilot cloud agent docs: https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent
- GitHub Copilot cloud agent environment docs: https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/customize-the-agent-environment
- Cursor cloud agents and computer-use writeup: https://cursor.com/blog/agent-computer-use
- Augment Context Engine MCP docs: https://docs.augmentcode.com/context-services/mcp/overview
- Qodo Context Engine usage docs: https://docs.qodo.ai/qodo-aware/usage/usage-guide
- Sourcegraph Cody Enterprise docs: https://sourcegraph.com/docs/cody/clients/enable-cody-enterprise
- Sourcegraph Cody context chat docs: https://sourcegraph.com/docs/cody/capabilities/chat
- Greptile overview docs: https://www.greptile.com/docs/introduction
- Letta docs index and memory-first agent surface: https://docs.letta.com/
- LangGraph persistence docs: https://docs.langchain.com/oss/python/langgraph/persistence
- AutoGen memory docs: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/memory.html
- CrewAI memory docs: https://docs.crewai.com/en/concepts/memory
- MCP security best practices: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- OWASP MCP Tool Poisoning: https://owasp.org/www-community/attacks/MCP_Tool_Poisoning
- OWASP Top 10 for Agentic Applications PDF: https://genai.owasp.org/download/52117/?tmstv=1765059207
- Microsoft STATE-Bench: https://opensource.microsoft.com/blog/2026/05/19/introducing-state-bench-a-benchmark-for-ai-agent-memory/
- PEPA persistent autonomy paper: https://arxiv.org/abs/2603.00117
- Agent Sandbox docs: https://agent-sandbox.sigs.k8s.io/docs/
- Codified Context paper: https://arxiv.org/abs/2602.20478
- ContextCov paper: https://arxiv.org/abs/2603.00822

## Research Takeaways

- Best systems separate agent intelligence from execution environment. They give agents sandboxes, logs, resumability, branch isolation, and artifacts.
- The frontier is converging on codified context: persistent instruction files, role-specific agents, context manifests, on-demand knowledge docs, and tool-routing policies.
- The context layer is becoming a competitive surface. Augment, Qodo, Sourcegraph, Greptile, GitHub, Cursor, Claude Code, and OpenAI all treat codebase context as a product primitive.
- Memory is no longer just retrieval. STATE-Bench asks whether memory improves task reliability, efficiency, and user experience; Dharma Swarm should copy that stance.
- Security has moved from "do not leak prompts" to identity, privilege, tool poisoning, memory poisoning, cascading failures, and non-human identity lifecycle.
