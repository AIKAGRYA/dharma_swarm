# 07 Command Plane Operator Strategy

Expert lens: command-plane and operator-experience architect.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: Cursor cloud agents, GitHub Copilot cloud agent, OpenAI sandbox agents, Anthropic observability notes, Devin release notes.

## Core Claim

The command plane should make agent work reviewable, not magical. The locked "Observatory + Cockpit" framing is correct: watch most of the time, intervene when necessary, and make every intervention leave evidence.

The UI should not become another layer of aspiration. It should answer five questions instantly:

1. Who is alive?
2. What are they doing?
3. What did they check?
4. What changed?
5. What is blocked or unsafe?

## The Command Plane Is A Projection

The command plane should project runtime truth. It should not invent a second source of truth. Its rows and zones should come from:

- runtime sessions.
- task claims.
- delegation runs.
- context bundles.
- routing decisions.
- artifacts.
- handoffs.
- CI/test receipts.
- agent identity manifests.

This aligns with the ontology promotion packet: operator snapshots and rows can be stable views without being ontology roots.

## 2D/3D Strategy

The command-plane design brief says 3D is literal primary with 2D fallback. That is acceptable only if 3D serves state comprehension. If the 3D layer makes text harder to read, hides evidence, or confuses nesting, it should degrade to 2D.

For v1, prove one zone:

- COCKPIT only.
- one signal: active task claims and current runs.
- one 2D sheet.
- one 3D spatial view.
- same typed row model.
- Storybook or screenshot evidence.

Do not ship all seven zones at once. Seven zones are an information architecture, not a first PR.

## Lessons From Cloud Agents

Cursor's cloud-agent writeup emphasizes isolated VMs, artifact production, video/screenshot/log validation, and many agents running in parallel without local resource conflict. GitHub Copilot cloud agent emphasizes GitHub Actions environments, plans, branches, logs, and PRs. OpenAI emphasizes sandboxed file/tool execution. Dharma Swarm's command plane should therefore treat environment and artifacts as first-class.

A useful command plane shows:

- branch/worktree.
- sandbox or local env.
- model/provider.
- tool permissions.
- recent command/test output.
- current handoff.
- protected-file touch state.
- reviewer status.

## Interaction Rules

Operator interventions should be typed:

- approve.
- deny.
- pause.
- reassign.
- request more context.
- require tests.
- mark stale.
- retire.

Freeform chat can exist, but typed interventions are what become logs and metrics.

## Immediate Move

Before advanced UI polish, define the command-plane row contract:

```json
{
  "agent_id": "context_librarian",
  "tier": "L2",
  "task_claim": "claim_id",
  "risk": "Q2",
  "context_receipt": "path",
  "handoff": "path",
  "last_action": "summary",
  "health": "healthy|degraded|blocked",
  "operator_next_action": "review|approve|wait|intervene"
}
```

If that row is truthful, the UI can evolve. If that row is fake, no amount of aesthetic polish matters.
