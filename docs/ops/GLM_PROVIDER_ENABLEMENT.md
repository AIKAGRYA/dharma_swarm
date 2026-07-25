# Enabling GLM (and other external providers) on Claude Code on the web

**Status:** reference · **First written:** 2026-06-21 · **Scope:** ops / runtime

This note explains why GLM / Ollama / OpenRouter could not run in a Claude
Code **on the web** session, and the exact steps to enable them. It also
records the keyless lane that *does* work inside the default network policy.

## What was observed (2026-06-21, cloud_default environment)

A live probe of outbound egress from the remote container showed the network
policy blocks essentially every LLM route except Anthropic:

| Target | HTTP | Meaning |
|---|---|---|
| `ollama.com`, `registry.ollama.ai` | 403 | cannot install Ollama or pull models |
| `huggingface.co` | 403 | cannot pull GGUF weights |
| `openrouter.ai` (+ `/api/v1`) | 403 | OpenRouter (a common GLM host) blocked |
| `z.ai`, `open.bigmodel.cn` | 403 | Zhipu/GLM first-party APIs blocked |
| `api.openai.com`, `api.groq.com` | 403 | blocked |
| **`api.anthropic.com`** | **401** | **reachable** (needs auth only) |

`403` = blocked by policy; `401` = reachable, just unauthenticated. So GLM via
any cloud route, and Ollama via local pull, are both impossible under the
default policy — independent of any API key.

## To enable GLM specifically

GLM is a cloud model (Zhipu). The two supported routes:

1. **Via OpenRouter** (one key, many models incl. GLM):
   - Change the environment's **network policy** to allow egress to
     `openrouter.ai` (see the environment configuration docs:
     https://code.claude.com/docs/en/claude-code-on-the-web).
   - Add `OPENROUTER_API_KEY` as an environment **secret** (never paste a key
     into chat or commit it). The resolver reads it verbatim
     (`dharma_swarm/api_keys.py`, `OPENROUTER_API_KEY_ENV`).
   - Drive a GLM model explicitly, e.g.:
     ```bash
     python3 scripts/loop1_closure_run.py --tasks 1 --agents 1 \
       --provider openrouter --model z-ai/glm-4.6
     ```
     (Confirm the exact GLM model id against OpenRouter's model list.)

2. **Via Zhipu / z.ai first-party API**: allow `open.bigmodel.cn` (or
   `api.z.ai`) egress in the network policy and supply that provider's key.
   Note the runtime `ProviderType` enum has no first-party Zhipu lane today;
   OpenRouter is the supported path.

Network-policy and secret changes take effect on the **next session start**
(the container is ephemeral), not retroactively in the current session.

## The keyless lane that works inside the default policy

Because Anthropic egress is open, the `claude_code` provider lane — which
shells out to the local `claude -p` binary using the session's host-managed
auth — runs with **no API key**:

```bash
python3 scripts/loop1_closure_run.py --tasks 1 --agents 1 --provider claude_code
```

Two remote-environment fixes were required for this lane (both landed
2026-06-21): the headless env builders in `dharma_swarm/claude_cli.py` and
`dharma_swarm/providers.py` now drop `CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES`,
which the host injects and which forces `--include-partial-messages` —
invalid alongside the `--output-format text` headless args and fatal to every
nested subprocess agent.

### Known remaining gap (provider routing)

Passing `--provider claude_code` spawns agents on that provider, but the
TaskProvider router (`dharma_swarm/providers.py`) still selects its default
fallback chain (seed order from `model_hierarchy.py`) and ignores the agent's
provider, so a keyless run currently dead-letters with
`OPENROUTER_API_KEY not set` even though `EvidenceReceipt`s are minted through
the spine. Making the router honour `claude_code` as the in-policy keyless
fallback is the loop-closure track's named **Phase 1a — provider chain
hardening (fallback ordering)** item and should be done there, not improvised.
