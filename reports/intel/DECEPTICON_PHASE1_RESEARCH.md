# Decepticon Phase 1 Research Intake

Date: 2026-04-28
Lane: external-security-intel
Subject: PurpleAILAB/Decepticon autonomous red-team framework
Local review clone: `/tmp/decepticon-review`
Reviewed commit: `76a40a231d9999182c61eab51709135c86652500` (`v1.0.11`)

## Executive Verdict

Decepticon should be treated as a high-risk offensive-security system, not as a normal developer tool or passive scanner.

The project is useful to Dharma Swarm as an architecture reference for engagement discipline, operator control, evidence trails, and isolated task execution. It should not be installed on the host desktop, wired into live Dharma runtime, or given access to Dharma worktrees, host credentials, Docker socket power, LAN/VPN routes, or live cloud/API credentials.

Recommended Dharma posture:

1. Study and selectively port safe patterns.
2. Do not import or run its offensive agents, exploit prompts, C2 stack, or post-exploitation flows.
3. If execution is ever needed, use a disposable VM with no access to host secrets, live worktrees, LAN/VPN, or production targets.
4. Feed only architecture lessons and guardrails into Dharma memory until an explicit isolated-lab runbook exists.

## Sources Reviewed

- GitHub repository: `https://github.com/PurpleAILAB/Decepticon`
- Documentation: `https://docs.decepticon.red/`
- Architecture docs: `https://docs.decepticon.red/en/architecture/infrastructure`
- C2 docs: `https://docs.decepticon.red/en/features/c2-integration`
- Docker Engine security docs: `https://docs.docker.com/engine/security/`
- Docker Desktop security announcements: `https://docs.docker.com/security/security-announcements/`
- Sliver advisory context: `https://nvd.nist.gov/vuln/detail/CVE-2025-27090`
- Local inspected files:
  - `README.md`
  - `SECURITY.md`
  - `docker-compose.yml`
  - `.env.example`
  - `scripts/install.sh`
  - `.github/workflows/ci.yml`
  - `.github/workflows/codeql.yml`
  - `.github/dependabot.yml`
  - `clients/launcher/cmd/start.go`
  - `clients/launcher/internal/compose/compose.go`
  - `clients/launcher/internal/updater/updater.go`
  - `decepticon/backends/docker_sandbox.py`
  - `decepticon/core/schemas.py`
  - `decepticon/core/engagement_loop.py`
  - `decepticon/agents/prompts/recon.md`
  - `decepticon/agents/prompts/exploit.md`
  - `decepticon/agents/prompts/postexploit.md`

No installer was run. No Decepticon container was started. No C2 component was executed.

## Settled Observations

### 1. It is a real offensive stack

Decepticon advertises and implements an autonomous red-team workflow with reconnaissance, exploitation, post-exploitation, Sliver C2, Kali tooling, tmux-backed shell sessions, a web UI, a CLI, LiteLLM, PostgreSQL, and Neo4j.

This is not in the same risk class as a static scanner, benchmark harness, or prompt library.

### 2. The best Dharma-relevant pattern is engagement discipline

Decepticon's strongest transferable idea is its pre-execution engagement package:

- Rules of Engagement
- Concept of Operations
- Deconfliction Plan
- OPPLAN
- scoped objectives
- evidence trails
- operator visibility

This maps cleanly to Dharma's existing preference for explicit operator ground truth, read-before-write, and structured runtime rows.

### 3. The container architecture is thoughtful but not sufficient as a host boundary

The project separates management and operational services across Docker networks and uses an engagement-scoped workspace bind mount. That is directionally good.

However, the current `docker-compose.yml` mounts `/var/run/docker.sock` into the `langgraph` container. Docker's own security docs warn that control of the Docker daemon is effectively trusted-host power because containers can be created with host filesystem mounts. This makes the control plane a host-risk boundary, not just an application boundary.

### 4. Documentation and compose currently diverge on network isolation

The docs and README describe isolated networks with no management/operations cross-access and mention internal network boundaries. The locally reviewed `docker-compose.yml` defines normal bridge networks and does not mark `decepticon-net` or `sandbox-net` as `internal: true`.

That does not prove the project is unsafe, but it means Dharma should not rely on documentation-level isolation claims without direct compose/image verification.

### 5. Credential exposure is a first-class risk

The reviewed compose file mounts `${HOME}/.claude/.credentials.json` into the LiteLLM container as read-only. The `.env.example` also encourages Anthropic/OpenAI/Google API keys and default service passwords.

Dharma must not run this with real operator credentials or production API keys until a hardened secret-handling plan exists.

### 6. Sliver/C2 makes the blast radius qualitatively different

The default environment sets `COMPOSE_PROFILES=c2-sliver`. The C2 docs describe implant generation/deployment and covert channels.

Sliver had CVE-2025-27090 affecting versions before 1.5.43. The Decepticon image installs Sliver from Kali packages; the exact package version must be verified in an isolated image scan before any execution.

### 7. RoE enforcement appears mostly prompt-level

The code has RoE schemas and prompt instructions, and it injects scope summaries into execution prompts. That is useful discipline.

I did not find a deterministic egress policy that prevents an agent from scanning or connecting to out-of-scope destinations at the network layer. For Dharma purposes, prompt-level RoE is not enough for any autonomous offensive execution.

### 8. Project maturity improved, but safety is still contextual

The project has recent release hardening, CI, CodeQL, tests, signed GitHub release metadata, and a security policy. The installer has improved compared with a raw moving-branch `curl | bash` flow because the reviewed `scripts/install.sh` resolves a release and pins config downloads to that release tag.

That improves supply-chain hygiene. It does not make autonomous C2/exploit tooling safe on a normal workstation.

## Dharma Adoption Candidates

Safe to study and port:

- Engagement package templates: RoE, ConOps, Deconfliction, OPPLAN.
- One-objective/fresh-context loop to avoid context drift.
- Operator interview discipline: one ambiguity at a time, explicit authorization and scope.
- Evidence/timeline discipline for every action.
- Engagement-scoped workspace bind model.
- Interactive shell session abstraction, but only for benign tooling lanes.
- Defense-feedback framing, without exploit execution.

Do not port:

- C2 setup, Sliver workflow, implants, post-exploitation playbooks.
- Offensive prompts that instruct exploitation, credential dumping, lateral movement, or stealth.
- Docker socket mount pattern.
- Host credential mounts.
- Auto-update behavior without explicit operator confirmation.
- Any default that starts vulnerable targets or C2 infrastructure on a normal desktop.

## Proposed Dharma Guardrails Before Any Lab Run

Minimum required before running Decepticon anywhere:

1. Disposable VM only.
2. No shared clipboard or host folder mounts except an empty throwaway workspace.
3. No host `~/.claude`, SSH keys, cloud creds, `.env`, or Dharma worktrees.
4. Docker Desktop updated and hardened.
5. C2 profile disabled for first smoke test.
6. Auto-update disabled.
7. No LAN/VPN route from the VM.
8. Outbound network restricted except image pull and model endpoint if required.
9. Model keys scoped to a throwaway low-budget account.
10. Target limited to bundled vulnerable demo containers or an explicitly authorized lab.
11. Capture compose config, image digests, SBOM/vulnerability scan, and Sliver version before execution.
12. Write an operator kill-switch and cleanup procedure before any agent action.

## Machine-Readable Facts Exported

The distilled insights from this report are exported in:

`reports/intel/decepticon_phase1_memory_records.jsonl`

They are shaped as Dharma `MemoryRecord` payloads and were ingested through the canonical `SovereignMemoryPlaneAdapter` into a repo-local runtime DB:

`reports/intel/decepticon_phase1_intel.runtime.db`

That DB is intentionally local/ignored (`*.db`) and does not touch live `~/.dharma`.

## Recommendation

Use Decepticon as external field intelligence, not as an installed dependency.

The next safe Dharma action is to create a small follow-up issue or task:

`Port safe red-team engagement discipline into Dharma operator-ground-truth and Guardian guardrails`

Acceptance should be limited to templates, policies, and tests. No C2, no exploit agent, no live execution.
