# Packet 10: DocOps, Hygiene, And Repo Governance

Packet ID: `ctx.docops-hygiene-repo-governance`

Use when touching doc ownership, generated inventories, anti-slop rules,
hygiene baselines, PR quality gates, pre-commit, stale-doc cleanup, or repo-wide
governance checks.

Do not use for organ-specific runtime behavior unless the change is only about
documentation ownership or hygiene.

## Authority Model

- Doc ownership: `docs/governance/CANONICAL_DOC_STACK.md`,
  `docs/docops/assertions.yaml`, `docs/docops/AUTO_INVENTORY.md`
- Hygiene owner: `docs/governance/hygiene/**`, hygiene scripts and baselines
- PR/CI owner: `.github/workflows/**`, `docs/governance/PR_QUALITY_GATES.md`,
  `.pre-commit-config.yaml`
- Proof owner: docops integrity, hygiene checks, pre-commit outputs, CI logs

Core invariant: docs decay. Before citing or editing, check the declared owner,
freshness, generated-file status, and live repo reality.

## Mission

Keep the repo navigable and honest without adding doc maze. Governance work
should reduce ambiguity, protect agents from stale claims, and make generated
or canonical ownership explicit.

## First Reads

L0 Safety:

- `make onboard`
- `docs/governance/ANTI_SLOP_RULES.md`

L1 Route:

- `docs/governance/CANONICAL_DOC_STACK.md`
- `docs/docops/assertions.yaml`
- `docs/governance/VIBE_CODE_HYGIENE.md`
- `docs/governance/PR_QUALITY_GATES.md`

L2 Owners:

- `scripts/governance/**`
- `scripts/uplift_guards/**`
- `.pre-commit-config.yaml`
- `docs/docops/**`
- `docs/governance/hygiene/**`

L3 Evidence:

- `reports/governance/anti_ai_slop_*`
- `reports/docops/**`
- latest `docs/governance/hygiene/baselines/*.txt`
- pre-commit output

L4 Search:

- `rg -n "generated|do not hand-edit|canonical|anti-slop|hygiene|pre-commit|docops" docs scripts .github tests`

L5 Seat:

- No named seat by default. Use a reviewer or witness only for independent
  verification of governance claims.

## Live Probes

```bash
make onboard
make hygiene-check
make docops-integrity
git diff --check
```

Before PR:

```bash
make agent-build-closeout
```

If generated active-track includes changed:

```bash
python3 scripts/governance/render_active_track_includes.py --check
```

## Retrieval Contract

- Query: "canonical doc stack generated file owner"
  Source family: canonical doc stack, assertions, generated headers.
- Query: "AI agent governance hygiene advisory measured observed"
  Source family: hygiene docs, baselines, scan reports.
- Query: "precommit stale doc active track generated includes"
  Source family: pre-commit config, governance scripts, active-track renderer.

## Operating Loop

1. Determine whether the target doc is canonical, generated, archived, stale, or
   ordinary prose.
2. Read the owner map before editing.
3. Avoid editing generated blocks by hand.
4. Run the narrow docops/hygiene check.
5. If checks fail from unrelated repo-wide debt, separate your changes from
   pre-existing failures.
6. Handoff with exact failures and whether they are related.

## Guardrails

- Do not rewrite large doc trees unless explicitly scoped.
- Do not edit generated blocks manually.
- Do not delete stale docs just because they are stale.
- Do not convert advisory hygiene patterns into blocking gates without lifecycle
  promotion.
- Do not hide pre-existing hook failures.
- Do not stage unrelated dirty files.

## Context Budget

- Tiny: `make onboard`, anti-slop rules, this packet.
- Standard: tiny plus canonical doc stack, assertions, target doc, relevant
  script/test.
- Deep: standard plus hygiene baseline, scan report, pre-commit logs, CI logs.

## Done Criteria

Complete means:

- owner and generated status are known;
- edits are scoped;
- docops/hygiene checks are run or blockers are explicit;
- unrelated dirty work is untouched;
- final handoff lists changed docs and verification.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.docops-hygiene-repo-governance.
Docs decay, so check owner, freshness, and generated status before editing. Do not
hand-edit generated blocks or stage unrelated work. Run hygiene/docops checks or
state exact blockers. Keep advisory hygiene patterns advisory unless lifecycle
promotion explicitly says otherwise. Handoff with changed docs, checks, and any
pre-existing unrelated failures.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.docops-hygiene-repo-governance",
  "docs_touched": [],
  "owner_map": [],
  "generated_blocks_touched": false,
  "commands_run": [],
  "related_failures": [],
  "unrelated_preexisting_failures": [],
  "staged_files": [],
  "next_docops_action": ""
}
```
