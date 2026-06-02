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

## Gates

- `darshan.external_reader_go_receipts` decision `block`; coherence `declared_only`; gaps `darshan_external_reader_event_missing`.
- `operator_os.governed_work_admission` decision `allow`; coherence `bound`; gaps `none`.

## Memory Kernel

- Status: `large_projection_needs_index`
- Staged: `5000`
- Trusted: `1332`
- Quarantine: `5000`
- Truncated scan: `True`

## Daily Cycle

- observe local evidence and receipts
- update canvas and attention queue
- plan with governed_work_admission
- execute only reviewed internal work
- verify with tests or receipt checks
- write daily digest and next packet

## Next Actions

- Record one accepted, privacy-redacted external-reader Go receipt before external growth/comms autonomy.
- Attach current TaskBoard rows to the Operator OS canvas.
- Attach A2A queue rows and closure receipts to the Operator OS canvas.
- Build a read-through MemoryKernel index over Chetana/wiki with source and promotion receipts.

## Evidence

- `/Users/dhyana/.dharma/artifacts/venture_cell/DARSHAN/2026-05-26/the-thing-they-are-competing-for-is-not-just-your-attention`
- `/Users/dhyana/.dharma/knowledge/staging`
- `/Users/dhyana/.dharma/knowledge/wiki/concepts`
- `/Users/dhyana/.dharma/knowledge/quarantine`
- `dharma_swarm/venture_cell/operator_os/projection.py`
