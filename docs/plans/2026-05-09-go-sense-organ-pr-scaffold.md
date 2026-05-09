# Go Sense-Organ PR Scaffold

Date: 2026-05-09
Status: scaffold only
Base rule: Go is a fast evidence, ingestion, transport, and observability layer. Python remains the telos, policy, gate, dispatch, ontology, and decision layer.

This plan records the 14 Go-track PRs so they do not disappear into chat context. Each PR has a matching AgentOps packet stub under `reports/agentops/work_packets/go-gXX-*.json`.

## Current Anchor

G0 is PR #176:

- Branch: `feat/go-evidence-sense-organ-v0-closure`
- PR: `https://github.com/AmitabhainArunachala/dharma_swarm/pull/176`
- Purpose: first Go sidecar, file-native evidence receipt, Python closure bridge
- Status at scaffold time: open, clean, CI green, awaiting explicit merge decision

## Design Boundary

Go may:

- collect high-volume signals
- normalize source payloads into receipts
- hash content and assign stable event IDs
- expose health and metrics
- spool evidence to disk
- run source-specific connectors
- serve read-only resources when explicitly scoped

Go may not:

- choose `NextDecision`
- write ontology/runtime databases
- dispatch agents
- approve gates
- mutate kernel/telos/evolution surfaces
- merge or push code
- become a second control plane

## Wild Pattern Mapping

| Wild pattern | Dharma Swarm use |
| --- | --- |
| OpenTelemetry Collector | Many source adapters normalize into one evidence stream |
| Prometheus exporters | Every Go organ exposes health, metrics, backlog, drops |
| Kubernetes operators | Watch actual state and propose reconciliation evidence |
| Temporal workers | Durable long-running ingestion jobs and retries, later |
| Terraform providers | Connector SDK: one external binary per source family |
| NATS or JetStream | Optional event fabric after file spool is proven |
| MCP servers | Read-only DS resources exposed to external agents |
| Local model daemons | Local/open model inventory and health probes |

## PR Chain

| PR | Packet | Branch | Owner lane | Depends on | Purpose |
| --- | --- | --- | --- | --- | --- |
| G0 | `go-g00-evidence-sense-organ-v0` | `feat/go-evidence-sense-organ-v0-closure` | Go seed | Tracks 1-3 merged | Merge #176 as the first bounded Go sidecar |
| G1 | `go-g01-language-boundary-policy` | `docs/go-language-boundary-policy` | Governance/docs | G0 | Record the language boundary and kill criteria |
| G2 | `go-g02-receipt-sdk` | `feat/go-receipt-sdk` | SDK | G1 | Shared Go receipt package and contract tests |
| G3 | `go-g03-adapter-contract-harness` | `feat/go-adapter-contract-harness` | SDK/tests | G2 | Adapter interface, golden fixtures, CI contract gates |
| G4 | `go-g04-github-repo-ingestor` | `feat/go-github-repo-ingestor` | Sources A | G3 | GitHub/repo event evidence adapter |
| G5 | `go-g05-ai-frontier-ingestor` | `feat/go-ai-frontier-ingestor` | Sources B | G3 | AI news, model release, paper, benchmark receipts |
| G6 | `go-g06-local-model-runtime-inventory` | `feat/go-local-model-runtime-inventory` | Sources C | G3 | Local/open model and runtime inventory receipts |
| G7 | `go-g07-health-metrics` | `feat/go-health-metrics` | Observability | G2 | Standard `/healthz`, `/readyz`, `/metrics` for Go organs |
| G8 | `go-g08-file-spool-backpressure` | `feat/go-file-spool-backpressure` | Transport | G2 | File spool, backpressure, idempotent replay |
| G9 | `go-g09-nats-event-fabric-experiment` | `exp/go-nats-event-fabric` | Transport | G8 | Optional NATS experiment, off by default |
| G10 | `go-g10-readonly-mcp-server` | `feat/go-readonly-mcp-server` | Product/API | G3 | Read-only MCP resources for receipts/projections |
| G11 | `go-g11-dharma-go-cli-bundle` | `feat/dharma-go-cli-bundle` | Packaging | G4,G5,G6,G7 | Single CLI bundle for Go sense organs |
| G12 | `go-g12-connector-sdk-examples` | `docs/go-connector-sdk-examples` | Product/docs | G10,G11 | Public connector examples and product docs |
| G13 | `go-g13-enterprise-deploy-profile` | `feat/go-enterprise-deploy-profile` | Deploy | G7,G8,G11 | launchd/systemd/container/Kubernetes deployment profile |

## Agent Plan

Use six agents, but keep one coordinator in charge of merge order.

| Agent | Role | Owns | Rule |
| --- | --- | --- | --- |
| Coordinator | merge conductor | G0, dependency graph, PR bodies | never writes implementation files |
| SDK agent | core Go package | G2, G3 | no source adapters before G3 lands |
| Source agent A | repo signals | G4 | no transport changes |
| Source agent B | frontier signals | G5, G6 | tests use fixtures, no network in CI |
| Observability/transport agent | metrics and spool | G7, G8, G9 | NATS stays experimental and off by default |
| Product agent | external surface | G10, G11, G12, G13 | read-only first, deploy profiles after CLI |

## Parallelization

Strict sequence:

1. Merge G0.
2. Land G1.
3. Land G2.
4. Land G3.

Safe parallel wave after G3:

- G4, G5, G6 can run in parallel if they do not touch the SDK.
- G7 and G8 can run in parallel after G2 if they only use stable receipt APIs.
- G9 waits for G8.
- G10 waits for G3.
- G11 waits for G4, G5, G6, and G7.
- G12 waits for G10 and G11.
- G13 waits for G7, G8, and G11.

## Branch Hygiene

For every packet:

```bash
git fetch origin
git worktree add -b <branch> /Users/dhyana/promotion_worktrees/<worktree> origin/main
```

Before opening a PR:

```bash
git status --short --branch
git diff --check
make go-ci
python3 scripts/docops/check_docops_integrity.py --changed-from origin/main
gh pr list --search "<packet id>"
```

PR bodies must include:

- packet id
- dependency statement
- allowed-file footprint
- Go/Python boundary statement
- test transcript
- Coherence Delta fields
- explicit note if DocOps count-only files changed

## Kill Criteria

Stop and return to operator if any packet:

- edits `dharma_swarm/ontology.py`
- edits `dharma_swarm/telic_seam.py`
- edits `dharma_swarm/evolution.py`
- edits `dharma_swarm/telos_gates.py`
- edits `dharma_swarm/dharma_kernel.py`
- writes runtime or ontology database state from Go
- exports a write-capable MCP tool
- adds NATS or another broker to the default runtime path
- makes network-dependent CI tests
- changes Python decision policy to trust Go verdicts directly

## Product Direction

The finished product shape is:

- Go daemon or CLI bundle collects signals.
- Each source emits receipts with content hash, event UID, source, observed time, and correlation id.
- Python ingests receipts through operator-core bridges.
- Closure tests prove success/failure evidence changes decisions.
- Users can add custom connectors without touching swarm policy code.
- Enterprises can deploy collectors near their code, models, logs, and documents while keeping Dharma Swarm's decision layer governed.
