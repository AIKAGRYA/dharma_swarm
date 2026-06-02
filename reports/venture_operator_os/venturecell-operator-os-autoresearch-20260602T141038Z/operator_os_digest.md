# VentureCell Operator OS Digest: DARSHAN

- Status: `blocked_on_external_reader_gate`
- Autonomy: `L0_read_only_plan`
- Artifact: `darshan-7302ff3a3a75`

## Departments

- `strategy` Strategy: bound; surface `decision_delta.json + governed_work_admission`; authority `review_required`.
- `product` Product Canvas: bound; surface `article.md + attention_ledger.json`; authority `draft_only`.
- `engineering` Engineering: partial; surface `TaskBoard + A2A filesystem receipts`; authority `reviewed_internal`.
- `growth` Growth: blocked_on_external_reader_gate; surface `Darshan external-reader Go receipt gate`; authority `human_approved_only`.
- `communications` Communications: blocked_on_external_reader_gate; surface `attention_ledger.json + external_reader_events`; authority `human_approved_only`.
- `operations` Operations: partial; surface `daily_operating_brief + ds-goal receipts`; authority `reviewed_internal`.
- `library` Library: bound; surface `source_pack.json + claim_ledger.json + reports`; authority `read_only`.
- `memory` Memory Kernel: read_only_projection; surface `Chetana staging/wiki/provenance`; authority `read_only_until_promoted`.
- `governance` Governance: bound; surface `governed_work_admission + gate ledgers`; authority `default_deny`.

## Canvas

- `artifact` Public artifact draft: `available`.
- `library` Source pack: `available`.
- `claims` Claim ledger: `available`.
- `attention` Attention ledger: `available`.
- `gates` Gate decisions: `available`.
- `decisions` Decision delta: `available`.
- `operator_handoff` External operator handoff: `available`.
- `operator_handoff` 30-day operating calendar: `requested`.
- `operator_handoff` artifact bundle checklist: `requested`.
- `operator_handoff` weekly operating review template: `requested`.
- `operator_handoff` 50-person first-reader outreach list: `requested`.
- `operator_handoff` ops board statuses from idea to corrected/published: `requested`.
- `operator_handoff` runbook for operating Darshan Season 0: `requested`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `task_board` eval_probe_task: `pending`.
- `a2a_queue` Fleet Health Collaboration — COLLECTOR role. Step 1: Collect current fleet metrics from ~/.dharma/a2a_bus/state/ for all: `completed_verified`.
- `a2a_queue` Fleet Health Collaboration — ANALYST role. Step 1: Wait for hermes-m5 metrics artifact at ~/.dharma/a2a_bus/conjunction/: `completed_verified`.
- `a2a_queue` Fleet Health Collaboration — ADVERSARIAL REVIEWER role. Step 1: Read codex_composer analysis at ~/.dharma/a2a_bus/conjun: `blocked_verified`.
- `a2a_queue` Fleet Health Collaboration — INFRA AUDIT role (dharma_swarm internals ONLY). Step 1: Audit A2A bus infrastructure: verif: `blocked_verified`.
- `a2a_queue` forge_council: (1) countersign v0.1.0 verifier_artifact (decorrelated); (2) build v0.1.1 transfer-gate in shadow per doc: `open_unclaimed`; blocked `a2a_task_not_terminal`.

## Gates

- `darshan.external_reader_go_receipts` decision `block`; coherence `declared_only`; gaps `darshan_external_reader_event_missing`.
- `operator_os.governed_work_admission` decision `allow`; coherence `bound`; gaps `none`.

## Memory Kernel

- Status: `read_through_index_available`
- Staged: `5000`
- Trusted: `1336`
- Quarantine: `5000`
- Truncated scan: `True`
- Index: `available_truncated` with `80` entries

## Memory Index

- `trusted` entries shown: `3`
  - Source turn: `/Users/dhyana/.dharma/knowledge/wiki/concepts/3---turn-121.md`
  - Source turn: `/Users/dhyana/.dharma/knowledge/wiki/concepts/3---turn-122.md`
  - Source turn: `/Users/dhyana/.dharma/knowledge/wiki/concepts/3---turn-123.md`
- `staged` entries shown: `3`
  - Operating Altitude Install — 2026-04-28 Session Milestone: `/Users/dhyana/.dharma/knowledge/staging/2026-04-28/914140f9-a31c-4cc7-927c-543f1861ff16.md`
  - Operating Altitude Install — 2026-04-28 Session Milestone: `/Users/dhyana/.dharma/knowledge/staging/2026-04-28/altitude-install-milestone.md`
  - Source turn: `/Users/dhyana/.dharma/knowledge/staging/2026-05-04/3af8f1c2-61ba-4afa-b8e2-23838c6d2468.md`
- `quarantine` entries shown: `3`
  - Telos Gates: `/Users/dhyana/.dharma/knowledge/quarantine/2026-04-28/c538a37e-6e89-42b1-be1a-473ec4ebe7da.md`
  - Source turn: `/Users/dhyana/.dharma/knowledge/quarantine/2026-05-23/057690cc-de18-4b84-b617-20441cb1a1e9.md`
  - Source turn: `/Users/dhyana/.dharma/knowledge/quarantine/2026-05-23/0e743772-dc67-4957-91c7-d07c1d72d511.md`

## Daily Cycle

- observe local evidence and receipts
- update canvas and attention queue
- plan with governed_work_admission
- execute only reviewed internal work
- verify with tests or receipt checks
- write daily digest and next packet

## Next Actions

- Record one accepted, privacy-redacted external-reader Go receipt before external growth/comms autonomy.
- Build a read-through MemoryKernel index over Chetana/wiki with source and promotion receipts.

## Evidence

- `/Users/dhyana/.dharma/artifacts/venture_cell/DARSHAN/2026-05-26/the-thing-they-are-competing-for-is-not-just-your-attention`
- `/Users/dhyana/.dharma/knowledge/staging`
- `/Users/dhyana/.dharma/knowledge/wiki/concepts`
- `/Users/dhyana/.dharma/knowledge/quarantine`
- `dharma_swarm/venture_cell/operator_os/projection.py`
