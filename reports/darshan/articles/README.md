# Darshan articles — pipeline-governed pieces

Every piece is one directory: `<desk-slug>/<YYYY-MM-DD>-<slug>/`.

Desk slugs: `bridge`, `instrument`, `witness-ledger`, `noosphere-weather`,
`field-notes`, `readings-in-fire`, `polity` — the charter's seven desks
(`docs/plans/DARSHAN_CHARTER_2026-07-12.md`).

A complete piece contains: `commission.json` (operator-approved topic),
`dossier.md` (register-tagged claims table; FACT rows carry sources),
`piece.md`, `fire_attack.md` + `fire_counter.md` (each ending
`VERDICT: SURVIVED` — only the double-survivor advances), `approval.json`,
and `emissions.json` (≥1 typed downstream work item). A killed piece keeps
its directory with `killed.json` carrying its salvage note.

Contract: `docs/plans/DARSHAN_EDITORIAL_PIPELINE_2026-08-19.md`. Enforced by
`scripts/darshan/check_darshan_editorial.py` inside required pytest
(`tests/test_darshan_editorial_pipeline.py`): an unlawful piece cannot merge.
