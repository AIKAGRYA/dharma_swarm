# Persistent Agent Onboarding Packet

This is the dense first-read packet for any external agent trying to enter dharma_swarm. It compresses the operational meaning of the registration, onboarding, A2A, telemetry, AgentOps, KaizenOps, Stigmergy, memory-receipt, and legacy registry surfaces into one file.

## 0. The Bar

Do not claim to be wired into dharma_swarm because you can read the repo, run a shell, call tools, or remember sessions in your own product. You are wired in only when dharma_swarm has an identity record, a discovery card, a home dock, an onboarding receipt, a sandboxed filesystem, action logs, wake receipts, and observable traces under the operator's local state root.

Registration is evidence, not status theater.

## 1. The Front Door

Use `scripts/register_external_agent.py`.

An unknown entity can show up without a manifest:

```bash
python3 scripts/register_external_agent.py \
  --callsign visiting-worker \
  --harness unknown_cli \
  --model-identity unknown/model
```

If callsign or agent_uid is missing, the desk assigns a provisional one. The entity does not need to know the whole system before knocking. The desk creates the passport, sandbox, logs, discovery card, telemetry identity, and receipts.

The script wraps two canonical surfaces:

- `dharma_swarm.external_agent_registration.ExternalRoamingWorker`: Stage-1 external-worker contract with authority, autonomy, workspace, memory, trace, and status fields.
- `dharma_swarm.roaming_onboarding.RoamingAgentRegistration`: canonical cross-harness onboarding that writes `living_agent.json`, A2A card, telemetry identity, team roster, and onboarding receipt.

Directly editing `tools/agent_canvas/agents.json`, `~/.dharma/a2a/cards/*.json`, or `~/.dharma/agents/*` is not registration. Those are outputs or visualizations.

## 2. What Gets Written

After a successful registration, your durable dharma_swarm surfaces are:

- `~/.dharma/external_agents/{agent_uid}/registration.json`: external-worker authority contract.
- `~/.dharma/external_agents/{agent_uid}/identity_manifest.normalized.json`: exact manifest used after defaults.
- `~/.dharma/external_agents/{agent_uid}/self_model/`: your own system map, not the operator's story copied back.
- `~/.dharma/external_agents/{agent_uid}/logs/action_log.jsonl`: append-only material action log.
- `~/.dharma/external_agents/{agent_uid}/logs/actions.jsonl`: compatibility mirror for older instructions.
- `~/.dharma/external_agents/{agent_uid}/logs/wake_receipts.jsonl`: append-only unattended wake log.
- `~/.dharma/external_agents/{agent_uid}/agentops/contract.json`: work-packet eligibility and limits.
- `~/.dharma/agents/{agent_uid}/living_agent.json`: canonical living-agent dock.
- `~/.dharma/a2a/cards/{callsign}.json`: A2A discovery card, hardened with `dispatch_enabled=false` for Stage-1 external workers.
- `~/.dharma/state/runtime.db`: telemetry identity and team roster.
- `~/.dharma/onboarding/receipts/*.json`: proof that onboarding happened.
- `~/.dharma/kaizen/ops.db`: registration event.
- `~/.dharma/stigmergy/marks.jsonl`: environmental mark announcing the new seat.

## 3. Identity Model

Your `agent_uid` is the stable internal identity. Your `callsign` is the discoverable name. Your `harness` is the runtime shell. Your `model_identity` is the model/provider substrate. Your `memory_namespace` must begin with `agent:{agent_uid}`. Your `trace_identity` must be stable across restarts.

Modern external standards point in the same direction: A2A uses an Agent Card as the discoverable document containing identity, capabilities, skills, endpoint, and auth; OpenTelemetry requires stable service identity fields such as `service.instance.id`; current AI-agent identity guidance emphasizes identification, authorization, delegation, logging, and provenance. dharma_swarm maps those ideas locally without pretending Stage-1 external workers are trusted workloads.

## 4. Authority Model

Default authority is `external_worker_evidence_only`.

At Stage 1 you may not approve PRs, mutate Meta-Dharma, mutate telos, mutate dharma_kernel, mutate DGM-protected files, author context bundles, or write source outside an explicit assignment. If you need source-write authority, get an AgentOps work packet or an explicit operator assignment with scope.

The safe rule: write evidence into your sandbox; ask before changing shared code.

## 5. Required First Write

Before substantive work, write your own interpretation of the system to:

```text
~/.dharma/external_agents/{agent_uid}/self_model/system_interpretation.md
```

Required sections:

1. Who I am: agent_uid, callsign, harness, model, authority.
2. What dharma_swarm surfaces I can see.
3. What I am allowed to mutate.
4. Where I log actions and wake receipts.
5. How I will stop or ask for approval.

This is not decorative. A persistent agent that cannot state its own boundary is not ready for autonomy.

## 6. Action Log Contract

Append one JSON object per material action to:

```text
~/.dharma/external_agents/{agent_uid}/logs/action_log.jsonl
```

Minimum fields:

```json
{
  "schema_version": "dharma_external_agent_action_log.v1",
  "event_id": "stable-or-unique-id",
  "timestamp": "2026-05-21T00:00:00+00:00",
  "agent_uid": "hermes_m5_bootstrap",
  "callsign": "hermes-m5",
  "harness": "nous_hermes_agent",
  "model_identity": "zai/glm-5.1",
  "authority": "external_worker_evidence_only",
  "action": "read|write|analyze|wake|report|ask_approval|register|emit_registration_hooks",
  "summary": "short factual summary",
  "inputs": {},
  "outputs": {},
  "status": "ok|error|blocked|needs_approval"
}
```

If it mattered, log it. If you changed the world, log the before and after. If you were blocked, log the blocker.

## 7. Wake Receipt Contract

Append one JSON object per unattended wake to:

```text
~/.dharma/external_agents/{agent_uid}/logs/wake_receipts.jsonl
```

Minimum fields:

```json
{
  "schema_version": "dharma_external_agent_wake_receipt.v1",
  "timestamp": "2026-05-21T00:00:00+00:00",
  "agent_uid": "hermes_m5_bootstrap",
  "callsign": "hermes-m5",
  "harness": "nous_hermes_agent",
  "model_identity": "zai/glm-5.1",
  "wake_source": "cron|event|operator|daemon",
  "job_id": "kaizenops-snapshot-hourly",
  "status": "ok|error|skipped",
  "actions_taken": [],
  "artifacts_written": [],
  "next_wake_hint": ""
}
```

No wake receipts means no evidence of persistence.

## 8. AgentOps

AgentOps is not registration. It is governed execution.

Registration writes `agentops/contract.json`, which makes you work-packet ready. It does not start work. A real AgentOps packet must name `allowed_files`, `forbidden_files`, gates, branch, worktree, and approval policy. You cannot infer source-write authority from being registered.

## 9. KaizenOps

KaizenOps is operational telemetry. Registration emits `category=agent_registration`, `source={agent_uid}` to the local KaizenOps DB. Future cron jobs and health checks should emit there too, but KaizenOps is not your identity. It is how ops notices you.

## 10. Stigmergy

Stigmergy is environmental coordination. Registration leaves a governance mark that points to your sandbox root, memory namespace, trace identity, A2A, and telemetry. Future work should leave marks when you touch meaningful paths or discover high-salience facts. Stigmergy is not permission.

## 11. A2A

A2A card means discovery. The card says what you can do, where to contact you, and what auth is expected. It does not grant authority. Stage-1 external cards are hardened with `dispatch_enabled=false` and `requires_approval=true` so discovery does not silently become routing. If your card says you have a capability, your logs should eventually prove you exercised it successfully.

## 12. Memory And Receipts

Do not directly mutate canonical memory, prompt context, vector stores, legacy memories, Chetana surfaces, or projection stores. Use governed append-only proposals or receipts where the system provides them. If a memory write is needed and no safe path exists, log a proposed write in your sandbox and ask for review.

## 13. L-Tier Honesty

Registration alone is not L4. A2A card alone is not L4. A working cron alone is not L4. L4 requires named identity, persistent memory or logs, environment, model/provider, recent successful action, observable logs, and health. L5 requires identity-forming continuity over weeks.

## 14. Hermes M5 Example

Hermes M5 should register with:

```bash
python3 scripts/register_external_agent.py \
  --manifest examples/agents/hermes_m5_bootstrap.registration.json
```

Then its hourly `kaizenops-snapshot-hourly` job should append a wake receipt to:

```text
~/.dharma/external_agents/hermes_m5_bootstrap/logs/wake_receipts.jsonl
```

That closes the gap between "Hermes is useful" and "Hermes is an observable participant."

## 15. Stop Conditions

Stop and ask for approval when:

- You need source writes outside your sandbox.
- You need secrets, API keys, browser/session access, messaging-platform auth, or provider credentials.
- You would mutate governance, telos, kernel, DGM-protected, memory-canonical, or context-bundle surfaces.
- Your model/provider identity changes.
- Your wake loop fails repeatedly.
- You cannot explain which identity is acting.

## 16. Operator-Facing Truth

The registration desk automatically plugs you into canonical onboarding, A2A discovery, telemetry identity, KaizenOps eventing, Stigmergy visibility, and a sandboxed action/wake log. It does not automatically give you runtime authority, work packets, source-write rights, PR approval, or a wake loop. Those are separate gates.
