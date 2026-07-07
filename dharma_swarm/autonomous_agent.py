"""Autonomous agents with multi-step reasoning and tool use.

This is what makes dharma_swarm agents REAL agents — not single-turn LLM calls.
Each agent runs a ReAct loop: reason about task -> use tools -> observe results
-> reason again -> repeat until done. Wrapped with dharma_swarm persistence
(memory, identity, communication, stigmergy).

The pattern is identical to what LangGraph, CrewAI, and Claude Code use internally:
    while not done:
        response = llm(messages, tools)
        if response.wants_tools:
            results = execute(response.tool_calls)
            messages.append(results)
        else:
            done = True

Requires: anthropic>=0.70.0 for Anthropic models, openai>=1.0.0 for OpenRouter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from dharma_swarm.agent_memory import AgentMemoryBank
from dharma_swarm.model_hierarchy import default_model as canonical_default_model
from dharma_swarm.models import LLMResponse, Message, MessagePriority, ProviderType
from dharma_swarm.runtime_provider import (
    create_runtime_provider,
    preferred_runtime_provider_configs,
)

logger = logging.getLogger(__name__)
_DEFAULT_AGENT_MODEL = canonical_default_model(ProviderType.ANTHROPIC)


# ---------------------------------------------------------------------------
# Dangerous command patterns blocked in bash tool
# ---------------------------------------------------------------------------
_DANGEROUS_PATTERNS = (
    "rm -rf", "rm -r /", "rmdir /", "drop table", "delete from",
    "sudo", "chmod 777", "kill -9", "pkill -9", "launchctl unload",
    "> /dev/", "dd if=", "mkfs", "format c:",
)


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic Messages API format)
# ---------------------------------------------------------------------------
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent dirs if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "bash",
        "description": "Execute a bash command. Use for git, python, tests, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "timeout": {"type": "integer", "description": "Timeout seconds", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "search_files",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob (e.g. '**/*.py')"},
                "directory": {"type": "string", "description": "Directory to search"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "search_content",
        "description": "Search file contents for a regex pattern (ripgrep).",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern"},
                "directory": {"type": "string", "description": "Directory to search"},
                "file_glob": {"type": "string", "description": "File filter glob"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "message_agent",
        "description": "Send a message to another agent via the message bus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient agent name"},
                "subject": {"type": "string", "description": "Message subject"},
                "body": {"type": "string", "description": "Message body"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "default": "normal",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "remember",
        "description": "Save something to your persistent memory for future sessions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Topic/label for this memory"},
                "value": {"type": "string", "description": "Information to remember"},
                "importance": {"type": "number", "description": "0.0-1.0", "default": 0.5},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall",
        "description": "Search your persistent memory for relevant information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "stigmergy_mark",
        "description": "Leave an environmental signal for other agents to discover.",
        "input_schema": {
            "type": "object",
            "properties": {
                "observation": {"type": "string", "description": "What you observed (max 200 chars)"},
                "file_path": {"type": "string", "description": "Related file path", "default": ""},
                "salience": {"type": "number", "description": "0.0-1.0 importance", "default": 0.5},
            },
            "required": ["observation"],
        },
    },
    {
        "name": "stigmergy_read",
        "description": "Read recent environmental signals left by other agents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max marks to return", "default": 10},
            },
        },
    },
    # ── Web search tools ────────────────────────────────────────────────────
    {
        "name": "web_search",
        "description": (
            "Search the live web for current information. "
            "Tries Perplexity → Exa → Brave → Jina → DuckDuckGo in order. "
            "Use for: current events, research papers, competitor intel, market news, "
            "anything that needs real-time or external information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results (1-10)", "default": 5},
                "backend": {
                    "type": "string",
                    "description": "Force a specific backend: perplexity, exa, brave, jina, arxiv, finnhub",
                    "enum": ["perplexity", "exa", "brave", "jina", "arxiv", "finnhub"],
                },
                "domain": {
                    "type": "string",
                    "description": "Domain hint: 'research' routes to arXiv, 'finance' routes to Finnhub",
                    "enum": ["research", "finance", "general"],
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch clean text content from any URL using Jina Reader. "
            "Returns markdown-formatted page content stripped of ads and navigation. "
            "Use for: reading full papers, documentation, news articles, competitor pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch (must start with https://)"},
            },
            "required": ["url"],
        },
    },
    # ── Ginko trading bridge tools ─────────────────────────────────────────
    {
        "name": "ginko_signals",
        "description": (
            "Get current market signals and regime from the Ginko trading system. "
            "Returns regime (bull/bear/neutral), signal values, and Brier scores. "
            "Use for: market intelligence, trading decisions, macro regime analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading symbol (BTC, ETH, SPY, etc.)", "default": "BTC"},
                "lookback_days": {"type": "integer", "description": "Days of data to analyze", "default": 7},
            },
        },
    },
    {
        "name": "ginko_regime",
        "description": "Get the current market regime from Ginko (bull/bear/neutral/unknown). Quick single-value answer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading symbol", "default": "BTC"},
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Result of an autonomous agent execution."""

    summary: str
    turns: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls_made: int = 0
    duration_s: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out


# ---------------------------------------------------------------------------
# Agent identity
# ---------------------------------------------------------------------------


@dataclass
class AgentIdentity:
    """Who an agent IS. Persists across sessions."""

    name: str
    role: str
    system_prompt: str
    model: str = _DEFAULT_AGENT_MODEL
    provider: str = "anthropic"
    max_turns: int = 25
    allowed_tools: list[str] = field(default_factory=lambda: [
        "read_file", "write_file", "bash", "search_files", "search_content",
        "remember", "recall", "stigmergy_mark", "stigmergy_read", "web_search", "fetch_url",
        "ginko_signals", "ginko_regime",
    ])
    working_directory: str = field(default_factory=lambda: str(Path.home()))


def _identity_from_registered_holon(
    agent_name: str,
    *,
    agents_root: Path | None = None,
) -> AgentIdentity | None:
    """Build an AgentIdentity from a registered holon's own prompt and model."""
    from dharma_swarm.holon_bridge import load_holon

    try:
        holon = load_holon(agent_name, agents_root=agents_root)
    except FileNotFoundError:
        return None

    provider = holon.provider_type
    role = str(holon.identity.get("role") or "registered_holon")
    working_directory = str(
        holon.identity.get("storage_root")
        or holon.identity.get("working_directory")
        or Path.home()
    )
    return AgentIdentity(
        name=holon.name,
        role=role,
        system_prompt=holon.system_prompt,
        model=holon.model,
        provider=provider,
        allowed_tools=[],
        working_directory=working_directory,
    )


def _providers_registered_on_router(
    router: Any,
    candidate_order: list[ProviderType],
) -> list[ProviderType]:
    """Keep cheap-first order; drop types the router did not instantiate."""
    out: list[ProviderType] = []
    for provider in candidate_order:
        try:
            router.get_provider(provider)
        except KeyError:
            continue
        out.append(provider)
    return out


def _llm_response_to_react_shape(response: LLMResponse) -> dict[str, Any]:
    """Normalize an LLMResponse into the dict _reason_and_act expects."""
    text_parts = [response.content] if response.content else []
    tool_uses: list[dict[str, Any]] = []
    for tc in response.tool_calls or []:
        parsed_input = tc.get("input")
        if parsed_input is None and "arguments" in tc:
            try:
                parsed_input = json.loads(tc["arguments"])
            except Exception:
                parsed_input = tc.get("arguments")
        tool_uses.append({
            "id": tc.get("id"),
            "name": tc.get("name"),
            "input": parsed_input,
        })
    raw_content: list[dict[str, Any]] = []
    if response.content:
        raw_content.append({"type": "text", "text": response.content})
    for tu in tool_uses:
        raw_content.append({
            "type": "tool_use",
            "id": tu["id"],
            "name": tu["name"],
            "input": tu["input"],
        })
    usage = response.usage or {}
    return {
        "text": text_parts,
        "tool_uses": tool_uses,
        "raw_content": raw_content or (response.content or ""),
        "stop_reason": response.stop_reason,
        "tokens_in": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "tokens_out": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
    }


# ---------------------------------------------------------------------------
# The autonomous agent
# ---------------------------------------------------------------------------


class AutonomousAgent:
    """A real autonomous agent with multi-step reasoning and tool use.

    This is what separates dharma_swarm from a chatbot framework:
    - ReAct loop: reason -> act -> observe -> repeat until done
    - Tool use: read/write files, run commands, search code, message agents
    - Persistence: remembers across sessions via AgentMemoryBank
    - Communication: messages other agents, reads/writes stigmergy marks

    When ``model_router`` is set, the ``openrouter`` lane uses
    ``ModelRouter.complete_for_task`` for providers the router actually
    registers (routing memory, breakers, telemetry). The ``codex`` lane
    always calls ``create_runtime_provider`` with
    ``working_dir=identity.working_directory`` because shared routers from
    ``create_default_router()`` are not built per-agent cwd — routing Codex
    through them would regress CLI working directory. Without an injected
    router, ``openrouter`` uses the cheap-first runtime chain as before.
    ``anthropic`` uses the canonical runtime provider factory so it stays
    under the same provider-routing and connection policy as the rest of the
    swarm.

    Usage::

        agent = AutonomousAgent(AgentIdentity(
            name="researcher", role="researcher",
            system_prompt="You are a research agent...",
        ))
        result = await agent.wake("Find the 3 weakest claims in the R_V paper")
        # Agent autonomously: reads files, searches code, analyzes, writes notes
        # Next day:
        result = await agent.wake("What did you find yesterday?")
        # Agent recalls from persistent memory
    """

    def __init__(self, identity: AgentIdentity, *, model_router: Any | None = None) -> None:
        self.identity = identity
        self.memory = AgentMemoryBank(identity.name)
        self._model_router = model_router
        self._openai_client: Any = None
        self._message_bus: Any = None
        self._stigmergy: Any = None
        # Ids of inbox messages fetched into the current wake's prompt but not
        # yet acknowledged; marked read only after the wake completes (see
        # _check_inbox / _ack_inbox).
        self._inbox_pending_ack: list[str] = []

    # -- Public API ----------------------------------------------------------

    async def wake(self, task: str) -> AgentResult:
        """Wake the agent to execute a task autonomously.

        Full lifecycle:
            load memory -> check inbox -> reason+act loop -> save memory -> report
        """
        start = time.monotonic()

        # 1. Load persistent memory
        await self.memory.load()
        memory_context = await self.memory.get_working_context()

        # 2. Check inbox for messages from other agents
        inbox = await self._check_inbox()

        # 3. Build system prompt: identity + memory + inbox
        system = self._build_system_prompt(memory_context, inbox)

        # 4. THE AGENTIC LOOP
        result = await self._reason_and_act(system, task)
        result.duration_s = time.monotonic() - start

        # 5. Save what was accomplished
        summary = result.summary[:500] if result.summary else "Task completed"
        await self.memory.remember(
            f"task:{task[:80]}", summary, importance=0.7,
        )
        await self.memory.save()

        # 6. Write run report
        await self._save_run_report(task, result)

        # 7. Wake completed: acknowledge the inbox messages delivered into this
        #    wake's prompt. Reached only if steps 4-6 did not raise, so a failed
        #    wake leaves the messages unread for the next cycle to retry.
        await self._ack_inbox()

        logger.info(
            "[%s] wake done: %d turns, %d tokens, %d tools, %.1fs",
            self.identity.name, result.turns, result.total_tokens,
            result.tool_calls_made, result.duration_s,
        )
        return result

    # -- The ReAct loop (core) -----------------------------------------------

    async def _reason_and_act(self, system: str, task: str) -> AgentResult:
        """The ReAct loop. Calls LLM -> executes tools -> feeds results -> repeats."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        tool_defs = self._get_tool_definitions()

        tokens_in = 0
        tokens_out = 0
        tool_calls_made = 0
        errors: list[str] = []
        final_text = ""

        for turn in range(self.identity.max_turns):
            try:
                resp = await self._call_llm(system, messages, tool_defs)
            except Exception as e:
                errors.append(f"LLM error turn {turn}: {e}")
                break

            tokens_in += resp.get("tokens_in", 0)
            tokens_out += resp.get("tokens_out", 0)

            text_parts: list[str] = resp.get("text", [])
            tool_uses: list[dict] = resp.get("tool_uses", [])
            raw_content = resp.get("raw_content")
            stop_reason = resp.get("stop_reason", "end_turn")

            # Append assistant message to conversation
            messages.append({"role": "assistant", "content": raw_content})

            if text_parts:
                final_text = "\n".join(text_parts)

            # Agent decided it's done
            if stop_reason == "end_turn" or not tool_uses:
                return AgentResult(
                    summary=final_text,
                    turns=turn + 1,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    tool_calls_made=tool_calls_made,
                    errors=errors,
                )

            # Execute tools, feed results back
            tool_results: list[dict[str, Any]] = []
            for tu in tool_uses:
                tool_calls_made += 1
                try:
                    result = await self._execute_tool(tu["name"], tu["input"])
                except Exception as e:
                    result = f"Error: {e}"
                    errors.append(f"Tool {tu['name']}: {e}")

                result_str = str(result)
                if len(result_str) > 15000:
                    result_str = result_str[:15000] + "\n... [truncated]"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})

        # Hit max turns
        return AgentResult(
            summary=final_text or f"Reached max turns ({self.identity.max_turns})",
            turns=self.identity.max_turns,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tool_calls_made=tool_calls_made,
            errors=errors + [f"Hit max turns ({self.identity.max_turns})"],
        )

    # -- LLM providers -------------------------------------------------------

    async def _call_llm(
        self, system: str, messages: list[dict], tools: list[dict],
    ) -> dict[str, Any]:
        """Call LLM. Returns normalized dict: text, tool_uses, raw_content, stop_reason, tokens."""
        if self.identity.provider in ("anthropic", "ANTHROPIC"):
            return await self._call_anthropic(system, messages, tools)
        if self.identity.provider in ("openrouter", "OPENROUTER"):
            return await self._call_openrouter(system, messages, tools)
        if self.identity.provider in (
            "claude_code",
            "CLAUDE_CODE",
            "anthropic_max",
            "ANTHROPIC_MAX",
        ):
            return await self._call_claude_code(system, messages, tools)
        if self.identity.provider in ("codex", "CODEX"):
            return await self._call_codex(system, messages, tools)
        raise ValueError(f"Unsupported provider: {self.identity.provider}")

    def _build_autonomous_route_request(
        self,
        *,
        has_tools: bool,
        available_provider_types: list[ProviderType],
    ) -> Any:
        from dharma_swarm.provider_policy import ProviderRouteRequest

        uncertainty = 0.42 if has_tools else 0.22
        risk = 0.32 if has_tools else 0.14
        ctx: dict[str, Any] = {
            "language_code": "en",
            "complexity_tier": "HIGH" if has_tools else "MEDIUM",
            "context_tier": "LONG",
            "requires_tooling": has_tools,
            "session_id": f"autonomous:{self.identity.name}",
            "agent_name": self.identity.name,
            "agent_role": self.identity.role,
            "preferred_model": self.identity.model,
            "task_brief": "autonomous_react_loop",
            "preserve_requested_model": len(available_provider_types) == 1,
            "available_provider_types": [p.value for p in available_provider_types],
        }
        return ProviderRouteRequest(
            action_name="autonomous_react",
            risk_score=min(1.0, risk),
            uncertainty=min(1.0, uncertainty),
            novelty=0.15,
            urgency=0.35,
            expected_impact=0.38,
            estimated_latency_ms=2400 if has_tools else 1000,
            estimated_tokens=1600 if has_tools else 900,
            preferred_low_cost=True,
            requires_frontier_precision=False,
            privileged_action=False,
            requires_human_consent=False,
            context=ctx,
        )

    @staticmethod
    def _openapi_tools_payload(tools: list[dict]) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    async def _call_anthropic(
        self, system: str, messages: list[dict], tools: list[dict],
    ) -> dict[str, Any]:
        from dharma_swarm.models import LLMRequest

        # The same Claude model serves via the metered Anthropic API OR — keyless —
        # via the claude_code Max-plan lane (live only when headless `claude -p`
        # smokes green). Order ANTHROPIC first, then fall back to the KEYLESS claude_code
        # lane, so this never dies with "configure ANTHROPIC_API_KEY" when dispatch
        # is actually available with zero keys.
        configs = preferred_runtime_provider_configs(
            provider_order=(ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE),
            model_overrides={
                ProviderType.ANTHROPIC: self.identity.model,
                ProviderType.CLAUDE_CODE: self.identity.model,
            },
        )
        if not configs:
            raise RuntimeError(
                "No Claude provider available. claude_code is KEYLESS only when "
                "headless `claude -p` dispatch smokes green — check "
                "key_oracle.dispatchable_now(); set "
                "ANTHROPIC_API_KEY only for the metered API path."
            )

        routed_order = (
            _providers_registered_on_router(
                self._model_router, [c.provider for c in configs]
            )
            if self._model_router is not None
            else []
        )
        if self._model_router is not None and routed_order:
            llm_req = LLMRequest(
                model=self.identity.model,
                system=system,
                messages=messages,
                max_tokens=4096,
                temperature=0.0,
                tools=tools,
            )
            route_req = self._build_autonomous_route_request(
                has_tools=bool(tools),
                available_provider_types=routed_order,
            )
            _, response = await self._model_router.complete_for_task(
                route_req,
                llm_req,
                available_provider_types=routed_order,
            )
            return _llm_response_to_react_shape(response)

        last_exc: Exception | None = None
        for config in configs:
            provider = create_runtime_provider(config)
            try:
                response = await provider.complete(
                    LLMRequest(
                        model=config.default_model or self.identity.model,
                        system=system,
                        messages=messages,
                        max_tokens=4096,
                        temperature=0.0,
                        tools=tools,
                    )
                )
                return _llm_response_to_react_shape(response)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[%s] provider %s failed for anthropic lane: %s",
                    self.identity.name,
                    config.provider.value,
                    exc,
                )
            finally:
                close = getattr(provider, "close", None)
                if callable(close):
                    await close()

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Anthropic provider chain exhausted without an explicit error")

    async def _call_openrouter(
        self, system: str, messages: list[dict], tools: list[dict],
    ) -> dict[str, Any]:
        from dharma_swarm.models import LLMRequest

        configs = preferred_runtime_provider_configs(
            model_overrides={
                ProviderType.OPENROUTER_FREE: self.identity.model,
                ProviderType.OPENROUTER: self.identity.model,
            }
        )
        if not configs:
            raise RuntimeError(
                "No preferred providers available; configure Ollama, NVIDIA NIM, or OpenRouter"
            )

        routed_order = (
            _providers_registered_on_router(
                self._model_router, [c.provider for c in configs]
            )
            if self._model_router is not None
            else []
        )
        if self._model_router is not None and routed_order:
            payload = AutonomousAgent._openapi_tools_payload(tools)
            lm_args: dict[str, Any] = {
                "model": self.identity.model,
                "system": system,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.0,
            }
            if payload is not None:
                lm_args["tools"] = payload
            llm_req = LLMRequest(**lm_args)
            route_req = self._build_autonomous_route_request(
                has_tools=bool(payload),
                available_provider_types=routed_order,
            )
            _, response = await self._model_router.complete_for_task(
                route_req,
                llm_req,
                available_provider_types=routed_order,
            )
            return _llm_response_to_react_shape(response)

        last_exc: Exception | None = None
        for config in configs:
            provider = create_runtime_provider(config)
            try:
                payload = AutonomousAgent._openapi_tools_payload(tools)
                request_kwargs = {
                    "model": config.default_model or self.identity.model,
                    "system": system,
                    "messages": messages,
                    "max_tokens": 4096,
                    "temperature": 0.0,
                }
                if payload is not None:
                    request_kwargs["tools"] = payload
                response = await provider.complete(LLMRequest(**request_kwargs))

                return _llm_response_to_react_shape(response)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[%s] provider %s failed for runtime-open stack: %s",
                    self.identity.name,
                    config.provider.value,
                    exc,
                )
            finally:
                close = getattr(provider, "close", None)
                if callable(close):
                    await close()

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Preferred provider chain exhausted without an explicit error")

    async def _call_codex(
        self, system: str, messages: list[dict], tools: list[dict],
    ) -> dict[str, Any]:
        del tools

        from dharma_swarm.models import LLMRequest

        configs = preferred_runtime_provider_configs(
            provider_order=(ProviderType.CODEX,),
            model_overrides={ProviderType.CODEX: self.identity.model},
            working_dir=self.identity.working_directory,
        )
        if not configs:
            raise RuntimeError("Codex provider unavailable; install the codex CLI")

        last_exc: Exception | None = None
        for config in configs:
            provider = create_runtime_provider(config)
            try:
                response = await provider.complete(
                    LLMRequest(
                        model=config.default_model or self.identity.model,
                        system=system,
                        messages=messages,
                        max_tokens=4096,
                        temperature=0.0,
                    )
                )
                return _llm_response_to_react_shape(response)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[%s] provider %s failed for codex lane: %s",
                    self.identity.name,
                    config.provider.value,
                    exc,
                )
            finally:
                close = getattr(provider, "close", None)
                if callable(close):
                    await close()

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Codex provider chain exhausted without an explicit error")

    async def _call_claude_code(
        self, system: str, messages: list[dict], tools: list[dict],
    ) -> dict[str, Any]:
        from dharma_swarm.models import LLMRequest

        configs = preferred_runtime_provider_configs(
            provider_order=(ProviderType.CLAUDE_CODE,),
            model_overrides={ProviderType.CLAUDE_CODE: self.identity.model},
            working_dir=self.identity.working_directory,
        )
        if not configs:
            raise RuntimeError("Claude Code provider unavailable; install the claude CLI")

        last_exc: Exception | None = None
        for config in configs:
            provider = create_runtime_provider(config)
            try:
                response = await provider.complete(
                    LLMRequest(
                        model=config.default_model or self.identity.model,
                        system=system,
                        messages=messages,
                        max_tokens=4096,
                        temperature=0.0,
                        tools=tools,
                    )
                )
                return _llm_response_to_react_shape(response)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[%s] provider %s failed for claude-code lane: %s",
                    self.identity.name,
                    config.provider.value,
                    exc,
                )
            finally:
                close = getattr(provider, "close", None)
                if callable(close):
                    await close()

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Claude Code provider chain exhausted without an explicit error")

    @staticmethod
    def _to_openai_message(msg: dict) -> dict:
        """Convert Anthropic-style message to OpenAI format."""
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            return {"role": role, "content": content}

        if isinstance(content, list) and content:
            first = content[0]

            # Tool results -> OpenAI tool messages
            if isinstance(first, dict) and first.get("type") == "tool_result":
                # OpenAI wants one message per tool result
                # Return just the first; caller handles multiple
                return {
                    "role": "tool",
                    "tool_call_id": first["tool_use_id"],
                    "content": first.get("content", ""),
                }

            # Assistant with content blocks
            if role == "assistant":
                text = ""
                tool_calls = []
                for block in content:
                    if hasattr(block, "type"):
                        # Anthropic SDK objects
                        if block.type == "text":
                            text += block.text
                        elif block.type == "tool_use":
                            tool_calls.append({
                                "id": block.id, "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input),
                                },
                            })
                    elif isinstance(block, dict):
                        if block.get("type") == "text":
                            text += block.get("text", "")
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block["id"], "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block["input"]),
                                },
                            })
                result: dict[str, Any] = {"role": "assistant", "content": text or None}
                if tool_calls:
                    result["tool_calls"] = tool_calls
                return result

        return {"role": role, "content": str(content)}

    # -- Tool execution ------------------------------------------------------

    async def _execute_tool(self, name: str, inputs: dict) -> str:
        """Execute a tool call. Returns result string."""
        if name not in self.identity.allowed_tools:
            return f"Error: tool '{name}' not allowed for agent '{self.identity.name}'"

        # S3 telos gate — check side-effect tools before execution
        _SIDE_EFFECT_TOOLS = {"bash", "write_file", "search_content", "message_agent"}
        if name in _SIDE_EFFECT_TOOLS:
            try:
                from dharma_swarm.telos_gates import check_action
                from dharma_swarm.models import GateDecision
                action_desc = f"autonomous_agent.{name}: {str(inputs)[:200]}"
                gate = check_action(action=action_desc, content=str(inputs))
                if gate.decision == GateDecision.BLOCK:
                    return f"GATE BLOCKED: {gate.reason}"
            except Exception as exc:
                # Fail CLOSED (operator directive 2026-07-07): a crashed gate
                # must not silently authorize a side-effect tool.
                logger.error(
                    "telos gate unavailable for %s; refusing side-effect tool: %s",
                    name, exc)
                return (f"GATE UNAVAILABLE: refusing side-effect tool '{name}' — "
                        f"telos gate raised {exc.__class__.__name__}: {exc}")

        handler = {
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
            "bash": self._tool_bash,
            "search_files": self._tool_search_files,
            "search_content": self._tool_search_content,
            "message_agent": self._tool_message_agent,
            "remember": self._tool_remember,
            "recall": self._tool_recall,
            "stigmergy_mark": self._tool_stigmergy_mark,
            "stigmergy_read": self._tool_stigmergy_read,
            "web_search": self._tool_web_search,
            "fetch_url": self._tool_fetch_url,
            "ginko_signals": self._tool_ginko_signals,
            "ginko_regime": self._tool_ginko_regime,
        }.get(name)

        if handler is None:
            return f"Unknown tool: {name}"
        return await handler(inputs)

    async def _tool_read_file(self, inputs: dict) -> str:
        path = inputs.get("path", "")
        try:
            text = Path(path).read_text(errors="replace")
            if len(text) > 50000:
                return text[:50000] + f"\n... [truncated, {len(text)} total chars]"
            return text
        except Exception as e:
            return f"Error reading {path}: {e}"

    async def _tool_write_file(self, inputs: dict) -> str:
        path = inputs.get("path", "")
        content = inputs.get("content", "")
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Wrote {len(content)} chars to {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    async def _tool_bash(self, inputs: dict) -> str:
        command = inputs.get("command", "")
        timeout = inputs.get("timeout", 30)

        cmd_lower = command.lower()
        for pattern in _DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                return f"BLOCKED: dangerous pattern '{pattern}'"

        try:
            import shlex
            proc = await asyncio.create_subprocess_exec(
                *shlex.split(command),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.identity.working_directory,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            parts = []
            if stdout:
                parts.append(stdout.decode(errors="replace"))
            if stderr:
                parts.append("STDERR:\n" + stderr.decode(errors="replace"))
            if proc.returncode != 0:
                parts.append(f"[exit code: {proc.returncode}]")
            return "\n".join(parts) or "(no output)"
        except asyncio.TimeoutError:
            return f"Timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_search_files(self, inputs: dict) -> str:
        pattern = inputs.get("pattern", "")
        directory = inputs.get("directory", self.identity.working_directory)
        try:
            matches = sorted(Path(directory).glob(pattern))[:50]
            if not matches:
                return f"No files matching '{pattern}' in {directory}"
            return "\n".join(str(m) for m in matches)
        except Exception as e:
            return f"Error: {e}"

    async def _tool_search_content(self, inputs: dict) -> str:
        pattern = inputs.get("pattern", "")
        directory = inputs.get("directory", self.identity.working_directory)
        file_glob = inputs.get("file_glob", "")

        cmd_args = ["rg", "--max-count", "5", "--max-filesize", "1M", "-n"]
        if file_glob:
            cmd_args.extend(["--glob", file_glob])
        cmd_args.extend([pattern, directory])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            result = stdout.decode(errors="replace")
            if len(result) > 10000:
                result = result[:10000] + "\n... [truncated]"
            return result or f"No matches for '{pattern}'"
        except asyncio.TimeoutError:
            return "Search timed out"
        except Exception as e:
            return f"Error: {e}"

    async def _tool_message_agent(self, inputs: dict) -> str:
        to = inputs.get("to", "")
        subject = inputs.get("subject", "")
        body = inputs.get("body", "")
        priority_str = inputs.get("priority", "normal")

        try:
            bus = await self._get_message_bus()
            if bus:
                priority = MessagePriority(priority_str)
                msg = Message(
                    from_agent=self.identity.name,
                    to_agent=to,
                    subject=subject,
                    body=body,
                    priority=priority,
                )
                await bus.send(msg)
                return f"Message sent to {to}: {subject}"
        except Exception as e:
            logger.warning("MessageBus send failed: %s", e)

        # Fallback: shared notes
        notes_dir = Path.home() / ".dharma" / "shared"
        notes_dir.mkdir(parents=True, exist_ok=True)
        note_file = notes_dir / f"{self.identity.name}_to_{to}.md"
        with open(note_file, "a") as f:
            f.write(f"\n## {subject}\n{body}\n")
        return f"Message saved to {note_file} (bus unavailable)"

    async def _tool_remember(self, inputs: dict) -> str:
        key = inputs.get("key", "")
        value = inputs.get("value", "")
        importance = inputs.get("importance", 0.5)
        await self.memory.remember(key, value, importance=importance)
        return f"Remembered: {key}"

    async def _tool_recall(self, inputs: dict) -> str:
        query = inputs.get("query", "")
        results = await self.memory.search(query)
        if not results:
            return f"No memories matching '{query}'"
        return "\n---\n".join(
            f"[{e.importance:.1f}] {e.key}: {e.value}" for e in results
        )

    async def _tool_stigmergy_mark(self, inputs: dict) -> str:
        observation = inputs.get("observation", "")[:200]
        file_path = inputs.get("file_path", "autonomous_agent")
        salience = inputs.get("salience", 0.5)

        try:
            store = await self._get_stigmergy()
            if store:
                from dharma_swarm.stigmergy import StigmergicMark
                mark = StigmergicMark(
                    agent=self.identity.name,
                    file_path=file_path,
                    action="scan",
                    observation=observation,
                    salience=salience,
                )
                await store.leave_mark(mark)
                return f"Stigmergy mark left: {observation[:60]}"
        except Exception as e:
            logger.warning("Stigmergy mark failed: %s", e)
        return "Stigmergy store unavailable"

    async def _tool_stigmergy_read(self, inputs: dict) -> str:
        limit = inputs.get("limit", 10)
        try:
            store = await self._get_stigmergy()
            if store:
                marks = await store.read_marks(limit=limit)
                if not marks:
                    return "No recent stigmergy marks"
                return "\n".join(
                    f"[{m.agent}] [{m.file_path}] {m.observation}" for m in marks
                )
        except Exception as e:
            logger.warning("Stigmergy read failed: %s", e)
        return "Stigmergy store unavailable"

    # -- Web search tools ----------------------------------------------------

    async def _tool_web_search(self, inputs: dict) -> str:
        from dharma_swarm.web_search import search_web
        query = inputs.get("query", "")
        if not query:
            return "Error: 'query' is required"
        max_results = min(int(inputs.get("max_results", 5)), 10)
        backend = inputs.get("backend") or None
        domain = inputs.get("domain") or None
        try:
            result = await search_web(
                query,
                max_results=max_results,
                backend=backend,
                domain=domain,
                format_output=True,
            )
            return str(result) if result else f"No results found for: {query}"
        except Exception as e:
            return f"Search error: {e}"

    async def _tool_fetch_url(self, inputs: dict) -> str:
        from dharma_swarm.web_search import fetch_url
        url = inputs.get("url", "")
        if not url:
            return "Error: 'url' is required"
        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"
        try:
            return await fetch_url(url)
        except Exception as e:
            return f"Fetch error: {e}"

    # -- Ginko trading bridge tools ------------------------------------------

    async def _tool_ginko_signals(self, inputs: dict) -> str:
        from dharma_swarm.ginko_bridge import ginko_get_signals, format_signals
        symbol = inputs.get("symbol", "BTC")
        lookback_days = int(inputs.get("lookback_days", 7))
        try:
            signals = await ginko_get_signals(symbol=symbol, lookback_days=lookback_days)
            return format_signals(signals)
        except Exception as e:
            return f"Ginko signals error: {e}"

    async def _tool_ginko_regime(self, inputs: dict) -> str:
        from dharma_swarm.ginko_bridge import ginko_get_regime
        symbol = inputs.get("symbol", "BTC")
        try:
            regime = await ginko_get_regime(symbol=symbol)
            return f"Current Ginko regime for {symbol}: {regime}"
        except Exception as e:
            return f"Ginko regime error: {e}"

    # -- System prompt -------------------------------------------------------

    def _build_system_prompt(self, memory_context: str, inbox: list[str]) -> str:
        parts = [self.identity.system_prompt]
        parts.append(
            f"\n\n## Your Identity\n- Name: {self.identity.name}\n- Role: {self.identity.role}"
        )

        if memory_context and memory_context.strip():
            parts.append(f"\n\n## Your Memory (from previous sessions)\n{memory_context}")

        if inbox:
            parts.append("\n\n## Inbox (messages from other agents)\n" + "\n".join(inbox))

        parts.append(
            "\n\n## Guidelines\n"
            "- You are an autonomous agent. Complete the task using your tools.\n"
            "- Be thorough but efficient. Use tools to verify, don't guess.\n"
            "- Save important findings to memory (remember tool) for future sessions.\n"
            "- If you discover something others should know, use stigmergy_mark.\n"
            "- When done, summarize what you accomplished and key findings."
        )
        return "\n".join(parts)

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        return [t for t in TOOL_DEFINITIONS if t["name"] in self.identity.allowed_tools]

    # -- Infrastructure wiring -----------------------------------------------

    async def _check_inbox(self) -> list[str]:
        # A fresh wake starts with no deferred acknowledgements.
        self._inbox_pending_ack = []
        try:
            bus = await self._get_message_bus()
            if bus:
                messages = await bus.receive(self.identity.name, limit=5)
                inbox = [
                    f"From {m.from_agent}: {m.subject} — {m.body[:200]}"
                    for m in messages
                ]
                # Defer acknowledgement: each fetched message is delivered into
                # the system-prompt inbox, but we mark it read only after the
                # wake's reason+act loop completes successfully (_ack_inbox).
                # Marking read here would permanently hide up to 5 messages if
                # the wake later fails (provider/tool/memory error) before it
                # could act on them; leaving them unread lets the next cycle
                # retry. Mirrors the consumer pattern in
                # contracts/runtime_adapters.py.
                self._inbox_pending_ack = [m.id for m in messages]
                return inbox
        except Exception:
            logger.debug("Message bus read failed", exc_info=True)
        return []

    async def _ack_inbox(self) -> None:
        """Mark this wake's fetched inbox messages read.

        Called only on the wake success path so a failed wake leaves the
        messages unread for a later retry. No-op when nothing was fetched or
        no message bus was available.
        """
        if not self._inbox_pending_ack:
            return
        bus = self._message_bus
        if bus is None:
            self._inbox_pending_ack = []
            return
        failed_acks: list[str] = []
        for msg_id in self._inbox_pending_ack:
            try:
                await bus.mark_read(msg_id)
            except Exception:
                failed_acks.append(msg_id)
                logger.warning("Message bus mark_read failed for %s; retained for retry", msg_id, exc_info=True)
        # Failed acks stay pending so the next wake retries them instead of
        # silently losing the acknowledgement (hygiene AS-09).
        self._inbox_pending_ack = failed_acks

    async def _get_message_bus(self) -> Any:
        if self._message_bus is None:
            try:
                from dharma_swarm.message_bus import MessageBus
                db_path = Path.home() / ".dharma" / "db" / "messages.db"
                self._message_bus = MessageBus(db_path)
                await self._message_bus.init_db()
            except Exception:
                logger.debug("Message bus init failed", exc_info=True)
        return self._message_bus

    async def _get_stigmergy(self) -> Any:
        if self._stigmergy is None:
            try:
                from dharma_swarm.stigmergy import StigmergyStore
                self._stigmergy = StigmergyStore()
            except Exception:
                logger.debug("Stigmergy store init failed", exc_info=True)
        return self._stigmergy

    async def _save_run_report(self, task: str, result: AgentResult) -> None:
        report_dir = Path.home() / ".dharma" / "agent_runs"
        report_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "agent": self.identity.name,
            "role": self.identity.role,
            "task": task[:500],
            "summary": result.summary[:1000],
            "turns": result.turns,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "tool_calls": result.tool_calls_made,
            "duration_s": round(result.duration_s, 1),
            "errors": result.errors,
            "timestamp": time.time(),
        }
        report_file = report_dir / f"{self.identity.name}_latest.json"
        report_file.write_text(json.dumps(report, indent=2))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class AgentOrchestrator:
    """Manages a fleet of autonomous agents.

    Stateless coordinator — agents own their state.
    The orchestrator decides who wakes up when and with what task.
    """

    def __init__(self, *, model_router: Any | None = None) -> None:
        self.agents: dict[str, AutonomousAgent] = {}
        self._run_log: list[dict[str, Any]] = []
        self._model_router = model_router

    def register(self, identity: AgentIdentity) -> AutonomousAgent:
        agent = AutonomousAgent(identity, model_router=self._model_router)
        self.agents[identity.name] = agent
        return agent

    async def dispatch(self, agent_name: str, task: str) -> AgentResult:
        """Wake a specific agent with a task."""
        if agent_name not in self.agents:
            raise ValueError(
                f"Unknown agent: {agent_name}. "
                f"Registered: {list(self.agents.keys())}"
            )
        agent = self.agents[agent_name]
        result = await agent.wake(task)
        self._run_log.append({
            "agent": agent_name, "task": task[:100],
            "turns": result.turns, "tokens": result.total_tokens,
            "timestamp": time.time(),
        })
        return result

    async def broadcast(
        self, task: str, agents: list[str] | None = None,
    ) -> dict[str, AgentResult]:
        """Send a task to multiple agents concurrently."""
        targets = agents or list(self.agents.keys())
        coros = [self.dispatch(n, task) for n in targets if n in self.agents]
        results = await asyncio.gather(*coros, return_exceptions=True)
        return {
            name: (r if isinstance(r, AgentResult) else AgentResult(
                summary=str(r), errors=[str(r)],
            ))
            for name, r in zip(targets, results)
        }


# ---------------------------------------------------------------------------
# Preset agent identities
# ---------------------------------------------------------------------------

PRESET_AGENTS: dict[str, AgentIdentity] = {
    "researcher": AgentIdentity(
        name="researcher",
        role="researcher",
        system_prompt=(
            "You are a research agent specializing in mechanistic interpretability, "
            "consciousness studies, and scientific rigor. You read papers, analyze data, "
            "verify claims, and produce research insights. You work in the dharma_swarm "
            "ecosystem alongside other agents."
        ),
        model=_DEFAULT_AGENT_MODEL,
        allowed_tools=[
            "read_file", "search_files", "search_content", "bash",
            "remember", "recall", "stigmergy_mark", "stigmergy_read", "web_search", "fetch_url",
            "ginko_signals", "ginko_regime",
        ],
        working_directory=str(Path.home() / "mech-interp-latent-lab-phase1"),
    ),
    "coder": AgentIdentity(
        name="coder",
        role="coder",
        system_prompt=(
            "You are a coding agent that writes, tests, and maintains Python code. "
            "You follow existing patterns, run tests after changes, and keep code clean. "
            "You work in the dharma_swarm ecosystem."
        ),
        model=_DEFAULT_AGENT_MODEL,
        allowed_tools=[
            "read_file", "write_file", "bash", "search_files", "search_content",
            "remember", "recall", "stigmergy_mark", "stigmergy_read", "web_search", "fetch_url",
            "ginko_signals", "ginko_regime",
        ],
        working_directory=str(Path.home() / "dharma_swarm"),
    ),
    "scout": AgentIdentity(
        name="scout",
        role="scout",
        system_prompt=(
            "You are a scout agent for the Jagat Kalyan project. You search for funding "
            "opportunities, potential partners, carbon market news, and strategic intelligence. "
            "You save findings to structured files and flag urgent items."
        ),
        model=_DEFAULT_AGENT_MODEL,
        allowed_tools=[
            "read_file", "write_file", "bash", "search_files", "search_content",
            "remember", "recall", "stigmergy_mark", "stigmergy_read", "web_search", "fetch_url",
            "ginko_signals", "ginko_regime",
        ],
        working_directory=str(Path.home() / "jagat_kalyan"),
    ),
    "reviewer": AgentIdentity(
        name="reviewer",
        role="reviewer",
        system_prompt=(
            "You are a review agent that audits code, papers, and claims for quality "
            "and correctness. You find bugs, weak arguments, and potential improvements. "
            "Constructively critical, always specific."
        ),
        model=_DEFAULT_AGENT_MODEL,
        allowed_tools=[
            "read_file", "search_files", "search_content", "bash",
            "remember", "recall", "stigmergy_mark", "stigmergy_read", "web_search", "fetch_url",
            "ginko_signals", "ginko_regime",
        ],
        working_directory=str(Path.home()),
    ),
    "witness": AgentIdentity(
        name="witness",
        role="witness",
        system_prompt=(
            "You are a witness agent in contemplative observation mode. You read the "
            "system's outputs, stigmergy marks, and shared notes, then synthesize "
            "what you observe without forcing interpretation. You notice patterns, "
            "connections, and what wants to emerge. Bhed Gnan — knowing through "
            "separation of the knower from the known."
        ),
        model=_DEFAULT_AGENT_MODEL,
        allowed_tools=[
            "read_file", "search_files", "search_content",
            "remember", "recall", "stigmergy_mark", "stigmergy_read", "web_search", "fetch_url",
            "ginko_signals", "ginko_regime",
        ],
        working_directory=str(Path.home()),
    ),
}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def cli_wake(agent_name: str, task: str, model: str | None = None) -> None:
    """CLI entry point: wake an agent with a task.

    Accepted legacy behavior: constructs ``AutonomousAgent`` **without**
    ``model_router``, so completions use direct runtime / SDK paths only (no
    shared routing memory). Use ``PersistentAgent`` / conductors or pass
    ``model_router=create_default_router()`` here if CLI should join the
    router substrate.
    """
    if agent_name in PRESET_AGENTS:
        identity = PRESET_AGENTS[agent_name]
    else:
        identity = _identity_from_registered_holon(agent_name)
        if identity is None:
            identity = AgentIdentity(
                name=agent_name, role="general",
                system_prompt=f"You are {agent_name}, an autonomous agent in dharma_swarm.",
            )

    if model:
        # Copy before overriding: presets are shared module state, and mutating
        # them leaks the override into every later wake in the same process.
        identity = replace(identity, model=model)

    agent = AutonomousAgent(identity)
    print(f"Waking {agent_name}...")
    result = await agent.wake(task)

    print(f"\n{'=' * 60}")
    print(
        f"Agent: {agent_name} | Turns: {result.turns} | "
        f"Tokens: {result.total_tokens} | Tools: {result.tool_calls_made}"
    )
    print(f"Duration: {result.duration_s:.1f}s")
    if result.errors:
        print(f"Errors: {result.errors}")
    print(f"{'=' * 60}")
    print(result.summary)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python autonomous_agent.py <agent_name> <task>")
        print(f"Preset agents: {', '.join(PRESET_AGENTS.keys())}")
        sys.exit(1)

    asyncio.run(cli_wake(sys.argv[1], " ".join(sys.argv[2:])))
