---
title: Karpathy Wiki, Obsidian MCP, RSI, and Revenue Engine Deep Dive
type: research_plan
status: high_priority_seed
priority: HIGH
created: 2026-07-05
related:
  - docs/plans/2026-07-05-karpathy-llm-wiki-system-integration.md
  - docs/research/naga-ir-language-womb-wiki.md
  - docs/loomwork/wiki_weaving_engine.md
  - docs/ops/MEMORY_COMMON.md
tags:
  - llm-wiki
  - obsidian
  - mcp
  - rsi
  - self-evolution
  - revenue
  - naga-ir
---

# Karpathy Wiki, Obsidian MCP, RSI, and Revenue Engine Deep Dive

## Verdict

The strongest path is not "AI notes." The strongest path is a verified context
engine that performs billable work and also feeds self-evolution.

Use the Karpathy LLM Wiki pattern as the compounding knowledge substrate,
Obsidian as the operator cockpit, Chetana as the promotion and metabolism
layer, Memory Common as the one-door retrieval surface, and NAGA as the
authority/effect checker. MCP is the tool bus, not the trust boundary.

The commercial wedge should be a paid service first:

```text
client corpus -> staged wiki -> cited evidence packet -> receipt -> client value
```

The RSI wedge should be a staged experiment loop first:

```text
mutation idea -> proposal atom -> sandbox experiment -> receipt
  -> fitness/dead-end/contradiction memory -> Memory Common -> next proposal
```

No direct trusted wiki writes. No direct autonomous Obsidian command execution.
No self-modification promotion without receipts, evals, rollback, and authority.

## Five-Agent Synthesis

| Lane | Main finding | Action |
| --- | --- | --- |
| Monetization | The paid value is verified context that finishes work, not generic memory. Outcome and usage pricing are already normalized in AI support and agent markets. | Start with paid pilots and evidence packets before generic SaaS. |
| RSI and self-evolution | The wiki is useful for RSI only as an evolutionary evidence system with experiments, dead ends, contradictions, and fitness receipts. | Build `RSI Memory Loop v0` as read-only/staging first. |
| Obsidian/MCP implementation | Use `cyanheads/obsidian-mcp-server` behind a Dharma policy gateway. Keep Local REST API's built-in MCP as upstream/admin only. | Ship read-only profile, then agent outbox writer profile. |
| Security and governance | MCP tools are model-controlled and vault content is untrusted input. Broker access with NAGA effects, path scopes, and receipts. | Default to read-only; writes require typed authority and rollback. |
| Product and operations | Keep one front door: the dashboard cockpit. Obsidian is workbench, not a new product UI. | Add Evidence Loom and RSI panels to `/dashboard/cockpit`. |

## Bleeding-Edge Use Cases

### 1. Receipt-Billed Expert Wiki

Buyer: AI governance teams, compliance teams, legal ops, grant/RFP teams,
vendor diligence teams, security-questionnaire teams, investigative research
teams.

Offer: "14-day Evidence Loom audit." The operator drops policies, PDFs, URLs,
meeting notes, Slack exports, tickets, filings, or research notes into a
controlled intake. Dharma compiles a living wiki, promotes only gate-passing
claims, and emits 3 to 5 cited evidence packets with correction ledger and
source map.

Initial price:

- `USD 3,000-15,000` pilot depending on corpus size and deadline.
- `USD 1,000-5,000/month` retained workspace.
- `USD 100-500` per verified memo or evidence packet after the pilot.

Why this can print: buyers already pay humans for slow, evidence-heavy work.
The system makes the recurring labor cheaper, faster, and auditable.

### 2. Outcome-Priced Support Knowledge Loop

Buyer: SMB SaaS teams, support agencies, internal IT/helpdesk teams, vertical
software companies with scattered documentation.

Offer: Ingest help docs, tickets, changelogs, Slack answers, and escalation
notes into a self-improving LLM Wiki. Agents answer user/internal questions,
write missing-doc candidates to outbox, and bill only when an outcome is
confirmed or a workflow completes.

Initial price:

- `USD 750-2,000` setup.
- `USD 500-2,000/month` minimum.
- `USD 0.75-2.00` per resolved outcome, depending on risk and integration.

Why this can print: every resolved ticket becomes future margin when it is
compiled into the wiki and gated back into retrieval.

### 3. NAGA MCP Trust Gateway

Buyer: agent builders, AI teams adopting MCP, regulated teams exposing private
tools or local knowledge to agents.

Offer: A local or hosted MCP broker that classifies each tool/resource by NAGA
effect, blocks unsafe writes, detects tool poisoning/prompt-injection-shaped
requests, pins tool descriptors, and records receipts for audit.

Initial price:

- Free local developer profile.
- `USD 99/developer/month`.
- `USD 999-5,000/team/month` with audit exports, policy packs, and red-team
  tests.

Why this can print: MCP adoption is increasing, but permissioning,
provenance, prompt-injection, and write-action trust remain open pain points.

### 4. Founder or Chief-of-Staff Vault Setup

Buyer: solo founders, consultants, funds, operators with expensive context
switching and high document volume.

Offer: A governed Obsidian/Dharma vault that turns calls, notes, client files,
and research into a maintained decision memory, weekly briefs, and action
packets.

Initial price:

- `USD 750-5,000` setup.
- `USD 99-499/month` upkeep.

This is the fastest cash wedge, but weaker defensibility unless verticalized.

### 5. Self-Evolving Agent Lab In A Box

Buyer: companies building agent systems with evals, memory, tool calls, and
unclear improvement loops.

Offer: A sandboxed self-evolution system where every proposed agent change has
a hypothesis, diff hash, eval manifest, cost, score, rollback, and NAGA
authority state.

Initial price:

- `USD 10,000-50,000` implementation.
- `USD 5,000-20,000/month` retained evolution operations.

This is high-ticket, but slower to sell than Evidence Loom because buyers need
more trust before letting agents near code evolution.

## Revenue Engine Architecture

```text
Raw client/source corpus
  -> Chetana ingest
  -> staged atoms and source receipts
  -> citation/provenance gate
  -> trusted wiki concepts or quarantined objections
  -> Evidence Loom brief/revelation packet
  -> client review and correction ledger
  -> Memory Common retrieval for future work
```

### The Product Surface

The dashboard remains the front door. Do not create a separate GUI.

Add cockpit panels for:

- Loom queue: staged, trusted, quarantined, stale, revived.
- Latest gated briefs and evidence packets.
- Citation coverage and uncited-claim rate.
- Client/source registry.
- Cost per packet.
- Corrections/retractions.
- Revenue pipeline: pilot leads, active pilots, retained work, outcome count.

Obsidian is the operator workbench for inspection and editing. It is not the
commercial app surface and not the autonomous source of truth.

### First Offer To Sell

Name: `Verified LLM Wiki Revenue/Audit Vault`.

Deliverables:

- One Obsidian vault profile with quarantined intake and curated read path.
- One Chetana ingest/promote path.
- One Evidence Loom source registry.
- Three cited evidence packets.
- One correction ledger.
- One dashboard status panel or static operator report.
- One closeout receipt with sources, gates, cost, and next monetizable loop.

Target first customers:

- AI governance/compliance startup.
- Security questionnaire or vendor diligence agency.
- Grant/RFP shop.
- Policy, climate, or supply-chain research team.
- Solo consultant already selling high-trust research.

Definition of first-dollar success:

- At least one paid pilot invoice.
- At least one packet accepted by a real buyer.
- One repeated workflow identified for productization.
- At least one correction/retraction path exercised.

## RSI and Self-Evolution Architecture

The wiki should not merely remember what happened. It should shape the next
mutation while preventing false fitness.

### Core Loop

```text
1. Proposal
   mutation hypothesis, target component, expected metric, risk, rollback

2. Staging
   proposal becomes a staged atom with NAGA authority state

3. Experiment
   sandbox/worktree run with fixed eval manifest and budget

4. Receipt
   diff hash, commands, pass/fail, cost, score, trace, rollback path

5. Memory
   derived fitness, dead-end, contradiction, and lesson atoms

6. Retrieval
   Memory Common returns relevant prior wins, failures, objections, and stale
   assumptions before the next proposal
```

### Required Evolution Objects

`SelfEvolutionRunPacket.v1`:

- objective
- component
- parent lineage
- proposed diff hash
- eval manifest hash
- budget and timeout
- model/provider profile
- risk class
- rollback plan

`EvolutionReceipt.v1`:

- task id
- branch/worktree
- commands
- exit codes
- tests
- costs
- logs/traces
- before/after scores
- rollback verification
- human/operator approval when required

`FitnessAuthorityPolicy.v1`:

- which metrics can count as fitness
- which metrics are advisory only
- required holdout evals
- anti-Goodhart checks
- stale-after for fitness claims
- challenge conditions

`DeadEndLedgerEntry.v1`:

- failed approach
- conditions under which it failed
- evidence
- reopen conditions
- TTL

`ContradictionEvent.v1`:

- claim A
- claim B or runtime observation
- source refs
- challenger
- severity
- block condition
- resolution receipt

### Promotion Rule

```text
Claim[Attested_by, agent] cannot become Claim[Verified_by, core]
without PromotionProof[eval_manifest, receipt, rollback, authority].
```

CI passing is not proof of product value. LLM council agreement is not proof of
truth. Dashboard rows are projections. Promotion requires typed evidence and no
unresolved blocking challenge.

### Anti-Goodhart Rules

- Fitness cannot be a single metric.
- Retrieval precision and semantic density are not utility by themselves.
- Every winner gets a stale-after date.
- Repeated winners require ablation against a held-out task set.
- Novelty budget is reserved so early winners do not entrench.
- Repeated failures become dead-end hints, not permanent bans.
- Unresolved contradiction count blocks promotion when over threshold.

## Obsidian and MCP Architecture

Recommended shape:

```text
Obsidian vault
  -> Obsidian Local REST API plugin >= 4.1.3, HTTPS loopback
  -> cyanheads/obsidian-mcp-server, pinned tested version
  -> Dharma Obsidian Gateway / policy broker
  -> Dharma Swarm agents
```

The Local REST API built-in MCP is powerful and should be treated as upstream
or admin-only. It exposes full vault CRUD, active-file operations, periodic
notes, tag listing, command listing, command execution, and opening files in
the UI. As of the GitHub release page checked on 2026-07-05, `4.1.3` is the
latest release and fixes an authenticated path traversal vulnerability in
`/vault/{path}` endpoints. That makes `>=4.1.3` a hard floor.

Use `cyanheads/obsidian-mcp-server` as the default upstream adapter because it
adds path-scoped reads/writes, global read-only mode, command tools disabled by
default, typed section patching, Omnisearch/BM25 mode, and MCP resources.
Pin a tested version in production. The observed current release was `v3.2.9`
on 2026-06-30.

### Profiles

`obsidian_ro_context`:

- Read-only.
- Exposes search/list/read/document-map only.
- No tag-wide resource to restricted agents.
- No write, delete, move, UI open, or command execution.

`obsidian_agent_outbox`:

- Reads curated safe context.
- Writes only to `agent_outbox/`, `scratch/`, and task folders.
- Section/frontmatter patch only.
- No overwrite of existing whole files except create-new inside outbox.

`obsidian_curator_admin`:

- Human/operator lane.
- Can promote proposed notes into canonical locations.
- Still avoids command execution unless a command id is separately approved.

### Vault Layout

```text
90_dharma_swarm/
  public/
  reference/
  tasks/
  agent_outbox/
    <agent-id>/
  scratch/
    <agent-id>/
  dashboards/
  web_clips/
    raw/
    curated/
  receipts/
```

Never expose to general agents:

```text
.obsidian/
_private/
_secrets/
journal/
people/
credentials/
attachments/private/
```

### NAGA Effect Mapping

| Operation | Effect | Default |
| --- | --- | --- |
| Search/list/read curated notes | `reads_memory` | Allow in read-only profile |
| Document-map read | `reads_memory.structure` | Allow before patch |
| Create outbox note | `stages_claim` | Allow only in outbox profile |
| Append/patch approved section | `stages_claim.patch` | Allow with receipt |
| Promote staged note | `promotes_claim` | Chetana/operator only |
| Delete/move/overwrite | `destructive_memory_write` | Deny by default |
| Execute Obsidian command | `acts_as_operator_ui` | Deny by default |
| External send/post/payment | `contacts_external` / `spends_money` | Explicit grant only |

### Write Receipt Minimum

```yaml
request_id:
actor_id:
task_id:
vault_id:
tool_id:
tool_descriptor_hash:
effect_type:
path:
path_allowlist_match:
target_heading_or_field:
before_hash:
proposed_diff:
secret_scan_result:
backup_id:
approval_id:
after_hash:
rollback_command:
timestamp:
```

No receipt, no write. No typed effect, no tool call. No authority inheritance
across agents.

## Security Gates

MCP tools are model-controlled. Vault content, web clips, notes, frontmatter,
search results, and tool descriptions are untrusted until policy accepts them.

Hard gates:

- Broker all Obsidian access through the Dharma gateway.
- Read-only default.
- Path allowlists for every read/write profile.
- Disable command execution.
- Hide delete/move/whole-file overwrite from ordinary agents.
- Pin tool descriptors and re-review on `tools/list_changed`.
- Keep Obsidian tokens out of repo files, vault notes, prompts, logs, and
  agent memory.
- Separate contexts: do not co-load Obsidian with email/browser/payment/shell
  tools unless a typed export grant exists.
- Scan web clips and notes for prompt-injection-shaped instructions before
  promotion.
- Store append-only receipts outside mutable target paths.
- Provide kill switches: global disable, write freeze, token revocation, and
  scheduler pause.

Red-team tests before write enablement:

- Poisoned note asks agent to export vault/API key.
- Tool descriptor includes hidden exfiltration instruction.
- Tool descriptor changes after approval.
- Agent attempts `.obsidian/**`, `.env`, SSH keys, or MCP config.
- Prompt tries to reach `command_execute` through benign wording.
- Concurrent agents patch the same note.
- Path traversal with `../`, encoded slash, symlink, or absolute path.
- Broad search attempts full-vault extraction.
- Kill switch activates mid-run and blocks later calls.

## First 14-Day Build Slice

Day 1-2: Freeze contracts.

- `RevelationPacket.v1`
- `ChetanaPromotionReceipt.v1`
- `EvolutionReceipt.v1`
- `FitnessAuthorityPolicy.v1`
- `OperatorBrief.v1`

Day 3-4: Build demo vault fixture and source registry.

- 30 seed atoms.
- 10 scout-derived atoms.
- Web Clipper raw/curated folders.
- Chetana round trip from markdown to staged atom to trusted atom.

Day 5-6: Build citation and gate harness.

- Every public claim has a citation.
- Deliberately bad packets are rejected.
- Correction/retraction record is exercised.

Day 7: Add dashboard cockpit panel.

- Loom queue.
- Latest brief.
- Memory status.
- Eval status.
- Cost and blockers.

Day 8-9: Produce three demo evidence packets.

- One AI governance packet.
- One support knowledge-loop packet.
- One supply-chain/compliance packet.

Day 10-11: Wire RSI dry-run packet.

- Candidate patch.
- Eval manifest.
- Cost and score.
- Receipt.
- No automatic promotion.

Day 12: Add policy tests.

- Private path read forbidden.
- Private sentinel search returns zero.
- Delete/move/command tools absent.
- Existing-note overwrite denied.
- Approved outbox section patch succeeds.
- Patch outside approved heading denied.
- Omnisearch down degrades to text search.

Day 13: Rehearse demos.

- Evidence Loom paid-pilot demo.
- Obsidian/MCP memory workbench.
- Self-evolution dry run.
- Dashboard truth panel.

Day 14: Package pilot sales kit.

- `ClientPilotSOW.v1`
- sample evidence packets
- demo vault fixture
- metrics baseline
- risk register
- one-page offer

## 30-Day Commercial Plan

Week 1:

- Finish the gated demo.
- Write the one-page offer.
- Identify 25 buyers with evidence-heavy workflows.
- Send direct outreach with a sample evidence packet.

Week 2:

- Close 1 paid pilot.
- Deliver three packets manually assisted by the system.
- Track time saved, correction rate, and buyer acceptance.

Week 3:

- Turn repeated workflow into a dashboard panel and Chetana recipe.
- Add outcome and cost reporting.
- Ask for retained monthly scope.

Week 4:

- Productize the repeating piece:
  `Evidence Loom`, `Support Knowledge Loop`, or `NAGA MCP Trust Gateway`.
- Keep custom work priced high.
- Only build generic SaaS after at least two pilots repeat the same workflow.

## Metrics

Commercial:

- Time to first usable packet.
- Citation accuracy.
- Uncited-claim rate.
- Correction rate.
- Human review minutes per packet.
- Cost per packet.
- Pilot close rate.
- Pilot-to-retainer conversion.
- Monthly retained revenue.

RSI:

- Receipt fill rate.
- Gate pass/block rate.
- Eval lift at matched cost.
- Change failure rate.
- Rollback success rate.
- Cost per evolution cycle.
- Stale winner count.
- Contradiction queue age.
- Dead-end reuse avoidance.
- Claim promoted without authority, target zero.

## Current Source Anchors

- Karpathy LLM Wiki gist:
  https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Trip2G LLM Wiki and MCP/federated memory comments:
  https://trip2g.com/en/user/llm_wiki
- MCP tools spec, 2025-06-18:
  https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- MCP resources spec, 2025-06-18:
  https://modelcontextprotocol.io/specification/2025-06-18/server/resources
- MCP security best practices:
  https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- OpenAI MCP server guide for ChatGPT Apps, deep research, and API:
  https://developers.openai.com/api/docs/mcp
- OpenAI Apps SDK monetization:
  https://developers.openai.com/apps-sdk/build/monetization
- cyanheads Obsidian MCP server:
  https://github.com/cyanheads/obsidian-mcp-server
- Obsidian Local REST API:
  https://github.com/coddingtonbear/obsidian-local-rest-api
- Obsidian Local REST API releases:
  https://github.com/coddingtonbear/obsidian-local-rest-api/releases
- Intercom outcome pricing signal:
  https://www.intercom.com/pricing
- Salesforce Agentforce pricing signal:
  https://www.salesforce.com/agentforce/pricing/
- Glean enterprise search ROI signal:
  https://www.glean.com/enterprise-search

## Non-Goals

- Do not promise autonomous money generation.
- Do not expose private vaults directly to agents.
- Do not enable Obsidian command execution for autonomous agents.
- Do not promote self-evolution results without eval and rollback receipts.
- Do not create another product UI outside the dashboard.
- Do not rely on ChatGPT marketplace monetization for first dollars; external
  checkout and direct pilots are the near-term path.
