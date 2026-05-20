# GTIG report — UNC5673 / UNC6201 / Claude-Relay-Service / CLIProxyAPI

URL: https://cloud.google.com/blog/topics/threat-intelligence/ai-vulnerability-exploitation-initial-access
Publisher: Google Threat Intelligence Group (GTIG) / Mandiant
Date: May 2026 (per BleepingComputer + CNBC, ~2026-05-08 to 2026-05-11 release)

## Did the Moltbook ↔ GTIG link check out?

**Partly.** The GTIG report itself does **NOT mention Moltbook**. It does:

1. Confirm UNC5673 (PRC-nexus) using `Claude-Relay-Service` and `CLI-Proxy-API` to aggregate Claude/Gemini/OpenAI keys.
2. Confirm UNC6201 (also PRC-nexus) using a Python script to register+cancel premium LLM accounts via CAPTCHA bypass + SMS verification.
3. **Separately** discuss OpenClaw supply-chain compromise — "malicious packages masquerading as OpenClaw skills containing hidden routines designed to execute unauthorized code and commands on the host system."

So the Lane 5 task brief is correct that GTIG named these IOCs in May 2026, but the brief overstates the link: GTIG is about **LLM account-pool abuse + OpenClaw skill supply-chain**, not about Moltbook specifically.

## Verbatim quotes

UNC5673 (key passage):
> "We have observed similar activity from UNC5673, a PRC-nexus threat cluster that has notable overlaps with TEMP.Hex and that has targeted government sectors primarily in South and Southeast Asia. […] they employ 'Claude-Relay-Service' to aggregate multiple Gemini, Claude, and OpenAI accounts, enabling account pooling and cost-sharing. Similarly, they use 'CLI-Proxy-API,' a proxy server that provides compatible API interfaces for various models to support similar account pooling strategies."

UNC6201 (key passage):
> "In our analysis of PRC-nexus threat activity associated with UNC6201, we observed attempted use of a publicly available Python script hosted on GitHub that automates a workflow to register and immediately cancel premium LLM accounts. The tool allegedly supports the entire process from automatic account registration, CAPTCHA bypassing, and SMS verification to account status confirmation and cancellation."

OpenClaw skill supply chain:
> "Most notably, we observed the distribution of malicious packages masquerading as OpenClaw skills containing hidden routines designed to execute unauthorized code and commands on the host system."

Mitigation noted:
> "OpenClaw has partnered with VirusTotal to integrate automated security scanning directly into ClawHub, its public skill marketplace."

## Tools — full table

| Tool | Type | Actor | Purpose |
|---|---|---|---|
| Claude-Relay-Service | API aggregator | UNC5673 | Account pooling across Claude/Gemini/OpenAI |
| CLI-Proxy-API | API gateway | UNC5673, UNC6201 | OpenAI-compatible proxy for pooled accounts |
| CLIProxyAPI ManagementCenter | Infrastructure mgmt | various | Centralized C2 for distributed proxies |
| Python account-reg script (unnamed) | LLM provisioning | UNC6201 | Auto-register + cancel premium accounts |
| Malicious OpenClaw skills | Agent framework supply chain | TeamPCP / UNC6780 | Code execution + data exfil via skill install |
| Hexstrike | Multi-agent pen-test | suspected PRC | Auto vuln discovery |
| Strix | Multi-agent pen-test framework | various | Auto vuln ID |
| GeminiAutomationAgent (in PROMPTSPY) | Mobile malware | various | Autonomous Android UI nav |

## Lane 5 read

The GTIG report is **a strong, primary deflation source for the OpenClaw side** (Lane 2 territory) and a strong source for the **LLM-account-pool-abuse pattern** (which intersects with Moltbook's claim-by-tweet ritual: a UNC5673-style operator could trivially register thousands of Moltbook agents via aggregated/fresh LLM accounts).

It is **NOT** a Moltbook-specific report. Lane 5 should cite it as adjacent threat-landscape evidence, not as a primary Moltbook indictment.
