# Darshan Editorial Pipeline — the official process for every article

**Status:** DRAFT — takes force when the operator merges the PR carrying this
file. Until then, and independently of it, NO Darshan-branded content may be
drafted, adapted, or published by any agent. **Doc role:** operationalizes the
editorial law already declared in `docs/plans/DARSHAN_CHARTER_2026-07-12.md`
("enforced on every piece, no exceptions"); subordinate to that charter and to
the operator. **Enforcement:** `scripts/darshan/check_darshan_editorial.py`,
run by `tests/test_darshan_editorial_pipeline.py` inside the merge-required
pytest gate — an article whose process chain is incomplete cannot pass CI.

## Founding case — why this file exists

On 2026-08-19 three launch drafts were produced for Darshan by a single agent
pass whose topics were chosen unilaterally in the commissioning prompt. They
went through none of the charter's laws: no both-fires attack, no register
tags, no editor seat, no emissions. The operator rejected them on sight. The
drafts are dead; this pipeline is the corrective. The failure was not the
absence of law — the charter had it — but the absence of a mechanism that
makes an unlawful piece impossible to advance. This file is that mechanism.

## Roles

- **Editor-in-chief: the operator.** Every publication act (merge of an
  approved piece, platform posting) is theirs. The charter's boundary stands:
  third-party platform posting is operator-gated per platform.
- **Head-editor holon** (`darshan_fable`, seat per charter §Structure): may
  run every stage up to and including the editorial verdict, but its APPROVE
  is advisory until the operator ratifies a delegation grant naming which
  desks or piece classes it may approve alone. No such grant exists today.
- **Any agent** may PROPOSE a commission. No agent may self-commission:
  drafting before an approved commission is a pipeline violation, full stop.

## The pipeline — seven stages, each with a typed artifact

Every piece lives as one directory:
`reports/darshan/articles/<desk-slug>/<YYYY-MM-DD>-<slug>/`
(layout contract in `reports/darshan/articles/README.md`). The stages, in
order, each blocking the next:

1. **COMMISSION** — `commission.json`: desk (one of the charter's seven),
   thesis (one sentence), why-now, proposed_by, approved_by, date. A
   commission is live only when `approved_by` is the operator (or a
   holder of a ratified delegation grant). *Fixes the founding failure: topic
   selection is an approved act, never a prompt author's aside.*
2. **DOSSIER** — `dossier.md`: the research substrate. Every load-bearing
   claim listed in a claims table, register-tagged **FACT** (primary source
   fetched, cited), **HYPOTHESIS** (test named), or **WILD** (tagged
   speculation) — charter law 2. FACT rows carry their source; a FACT row
   without one is a pipeline violation.
3. **DRAFT** — `piece.md` with YAML front matter (`desk`, `commission`,
   `registers`) written in the charter's voice, produced through the VWRITE
   refinery shape (`docs/plans/2026-06-11-vwrite-v3-refinery-design.md`)
   where that substrate is built; by disciplined agent passes until then.
4. **BOTH FIRES** — charter law 1, as two artifacts by agents independent of
   the drafter: `fire_attack.md` (full attack on every load-bearing framing)
   and `fire_counter.md` (full counter-attack). Each ends with a verdict line
   `VERDICT: SURVIVED` or `VERDICT: KILLED`. Only the double-survivor
   advances. A kill ends the piece through stage K below.
5. **EDITORIAL VERDICT** — `approval.json`: `approved_by`, `date`, `notes`.
   While no delegation grant exists, `approved_by` must be the operator.
6. **EMISSIONS** — `emissions.json`: at least one typed downstream work item
   (research question, build candidate, measurement) the piece hands the
   swarm — charter law 6. A piece that spawns nothing is decoration and
   cannot complete. Anti-feed (law 7) is asserted here: no trackers, no
   engagement mechanics in the piece or its adaptations.
7. **PUBLICATION** — only after 1–6 are complete may a piece be rendered
   outward (site branch, Substack, X adaptations), and each platform posting
   is a separate operator act. The publisher must be loud (VWRITE death cause
   D1/D2): every publish emits a receipt or an alarm, never silence.

**K. KILL WITH SALVAGE** — a piece killed at any stage keeps its directory
with `killed.json` naming the stage, the reason, and — charter law 5 — what
in it was worth keeping. Killed pieces are exempt from stages after their
death but never deleted; misses are part of the record.

## The mechanical gate

`scripts/darshan/check_darshan_editorial.py` validates every piece directory:
required artifacts present for its state (complete or killed), desk valid,
registers well-formed with sourced FACTs, both fire verdicts present and
SURVIVED for any approved piece, approval present, emissions non-empty.
It runs inside the required pytest gate via
`tests/test_darshan_editorial_pipeline.py`, so an unlawful article fails the
same checks that block any broken code from merging. The site/Substack
publishers must refuse any piece the checker rejects.

## What the operator ratifies by merging this

That this pipeline governs all Darshan content from merge onward; that the
operator is editor-in-chief with per-piece approval until they explicitly
delegate; and that the three 2026-08-19 launch drafts are formally dead.
Changing any stage later is an ordinary PR to this file — which, being
Darshan surface, the operator merges.
