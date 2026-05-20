# ArXiv 2603.27517 — A Security Analysis of the OpenClaw AI Agent Framework

**Source:** https://arxiv.org/html/2603.27517v2
**Authors:** Surada Suwansathit, Yuxuan Zhang, Guofei Gu
**(Not the paper in the task brief — but a separate, more rigorous academic security paper found while searching for Wiz coverage.)**

## Abstract (verbatim excerpt)
"AI agent frameworks connecting large language model (LLM) reasoning to host execution surfaces -- shell, filesystem, containers, and messaging -- introduce security challenges structurally distinct from conventional software."

## Three principal vulnerabilities identified

### 1. Remote Code Execution chain
Three moderate-to-high severity flaws in the **Gateway** and **Node-Host** subsystems compose into "a complete unauthenticated remote code execution (RCE) path" spanning delivery, exploitation, and C2.

### 2. Command filtering bypass
The exec allowlist mechanism assumes "command identity is recoverable via lexical parsing," but this fails against:
- shell line continuation
- busybox multiplexing
- GNU option abbreviation

### 3. Plugin distribution weakness
Malicious skills distributed via plugins can execute a **two-stage dropper "bypassing the exec pipeline,"** revealing absent runtime policy enforcement in skill distribution.

## Structural diagnosis
The dominant issue is **per-layer trust enforcement rather than unified policy boundaries** — making cross-layer attacks resistant to localized fixes.

## Why this matters for SAB v2 / dharma_swarm
This is the clearest academic articulation of OpenClaw's core architectural failure: **trust is enforced at each layer, but the layers are not unified under a single policy boundary**. dharma_swarm's kernel + telos-gate + witness model is precisely the unified policy boundary OpenClaw lacks — this paper validates that direction.
