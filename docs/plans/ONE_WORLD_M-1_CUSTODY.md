# ONE WORLD — M−1 Custody Manifest (Estate Salvage, Witness Role)

- **Date:** 2026-08-30
- **Doc role (per docs/AGENTS.md):** `witness` — falsifiability artifact with captured evidence. Subordinates to `docs/plans/ONE_WORLD_2026-08-30.md` (the unification plan this custody manifest serves); makes no repo-level authority claims.
- **Adjudicator:** M−1 estate witness (read-only)
- **Scope:** `origin/rsi-lab/canonical` (d221961c), `origin/estate/foundry-rsi-continuous-snapshot` (ca17cbfab), and their custody relationship to `origin/main` (a0a88841).
- **Method:** read-only `git` inspection + local receipt readback. No commits, no pushes, no branch creation, no edits to any file other than this document. Nothing was fetched; nothing was ssh'd. The remote host meghadharma was not contacted.

## 0. Corrections to the brief (skeptic's footnote)

Two "known facts" were re-measured and found inaccurate in detail (not in substance):

1. **Test-file count.** The snapshot adds **26 test files**, but the split is **23 `tests/test_foundry_*.py` + 3 `tests/forge_lab_v1/test_candidate_*.py`** — not "25 `test_foundry_*` + `test_nats_transport`". `tests/test_nats_transport.py` is **modified**, not added (it already existed at b148f55e).
2. **`foundry/` is not snapshot-only.** `dharma_swarm/foundry/` exists on **`origin/main`** (21 files, merged as #1389 `16b8e3f3c` "Sublimation Foundry"). It is **absent** from `origin/rsi-lab/canonical` (0 files). The snapshot carries a **divergent extension** of main's foundry (24 files), not the only copy. This changes the receipt-provenance answer materially (§3).

Evidence commands: `git diff b148f55e ca17cbfab --diff-filter=A --name-only`, `git ls-tree -r --name-only <ref> -- dharma_swarm/foundry`.

---

## 1. Adjudication of the 34 unique commits (`origin/main..origin/rsi-lab/canonical`)

Command: `git log origin/main..origin/rsi-lab/canonical --format='%h %ad %s' --date=short` (and `--shortstat`).

**Global finding that shapes every verdict:** the 34 commits touch 136 unique paths, and **all 136 still differ from `origin/main`'s tip** (`comm -23` of touched-files vs `git diff --name-only origin/main origin/rsi-lab/canonical` is empty). Nothing in this lineage has already landed on main in identical form, so **no commit is content-superseded by main**. Verdicts below are about merge-worthiness, not duplication.

| Cluster | Commits | Verdict | Evidence |
|---|---|---|---|
| **A. A2A onboarding** (2026-07-07 → 07-11) | `95fb807fa`, `5b18c95a2` | **merge-worthy** | 334 + 67 lines; registration JSON + presence announce only; no code risk. |
| **B. forge-lab v0.1 spec & Packet A substrate** (2026-07-11) | `9186bbe25` → `d45152189` → `e22b58232` | **merge-worthy** (`9186bbe25` is a `wip:` commit whose design is refined by the next two — keep as history, do not cherry-pick alone) | spec +848/−259; control surface 27 files +1714. Foundation everything later stands on. |
| **C. forge fitness adapter** (2026-07-13) | `d96bf6c69` | **merge-worthy — load-bearing** | Sole carrier of `dharma_swarm/forge_v1/forge_v2/forge_fitness.py` (247 lines), verified absent from `origin/main` (`git ls-tree origin/main -- dharma_swarm/forge_v1/forge_v2` lacks it). |
| **D. model-route attestation** (2026-07-15) | `7cbb3e169` | **merge-worthy** | 7 files +425; touches the predicted conflict set (`forge_v1/providers.py`) — resolution needed but content is wanted. |
| **E. providers async cleanup** (2026-07-16) | `0e74145c0` | **merge-worthy** | +11/−26, impact-checked; `git merge-tree` shows `dharma_swarm/providers.py` and `base_provider.py` auto-merge. |
| **F. operator history projection** (2026-07-16) | `cbc404587` → `3498a03ab` | **merge-worthy** | +2063 feature, then +1583/−1501 decomposition; the receipt in §3 pins 13 `operator_history_*` files as release-critical. |
| **G. exact cross-host release sync** (2026-07-16) | `766a064be` → `c19ebbca7` → `f7a5c91ee` → `eb07c90e0` → `8306325b4` → `e3ddd0492` → `77de78e7e` | **merge-worthy — the release machinery** | This cluster built the sync system that produced the only locally-verified release receipt (§3). `eb07c90e0` closes the gates (+2714/−1986). |
| **H. main-merge glue + docops refresh** (2026-07-16) | `e9de1c727`, `a1612fc7d` | **obsolete as standalone items** | `e9de1c727` is a merge of an old main into the branch — it arrives automatically with any tip merge; never cherry-pick it. `a1612fc7d` refreshes `docs/docops/AUTO_INVENTORY.md`, a generated file that is stale by construction and must simply be regenerated post-merge. Neither warrants independent action. |
| **I. substrate ports & hardening** (2026-07-21 → 07-24) | `15bf374ec`, `bfb783e0c`, `d6174e38e`, `9a9fc8d02`, `309650d56` | **merge-worthy** | n30 megha-WIP ports (soft token cap, `require_valid_seed`), SWE-bench Docker tier, kimi empty-patch guard, newrun controls, evidence routes. `15bf374ec` is itself a port of unowned megha work — it has since been through PR review on this branch, which is exactly the laundering path such work needs. |
| **J. bounded autonomous RSI ops** (2026-08-25) | `840c12387` (#1435) | **merge-worthy** | 41 files, +7196; the unattended-operations core. |
| **K. hermetic guards — receipt-pinned point** (2026-08-26 → 08-27) | `1353d6ef4` (#1441), `b148f55e0` (#1442) | **merge-worthy — defines the verified release** | `b148f55e0` carries `forge_fitness.py`'s hermetic verifier context and is the exact commit the local release receipt read back (§3). |
| **L. daily automation & custody chain** (2026-08-27 → 08-28) | `73c810ef2` (#1454) → `bdf0750d5` (#1456) → `742a2da4b` (#1461) → `43edb4c2d` (#1462) → `7d1ac099c` (#1476) | **merge-worthy — and the reason the snapshot's dirty state is stale** | +8479, +140, +26, +2555, +4064 respectively. These 5 PRs rewrote the unattended machinery **after** the snapshot's base (b148f55e); see §2(d). |
| **M. physical-state preflight docs** (2026-08-28) | `c8babcf29` (#1478) | **merge-worthy** | docs-only, +21/−11. |
| **N. health ↔ service execution binding** (2026-08-29) | `d221961c2` (#1479) | **merge-worthy** | tip commit, 4 files +363; binds health reporting to actual service execution — closes the "reported alive but dead" failure mode. |

**Tally:** 32 merge-worthy, 2 obsolete-as-standalone (cluster H), 0 superseded-by-main. The correct unit of merger is the **branch tip `d221961c2`**, not 32 cherry-picks — the lineage is linear, PR-reviewed (#-numbered), and internally coherent.

---

## 2. Snapshot diff: `b148f55e → ca17cbfab`

Command: `git diff b148f55e ca17cbfab --stat` → **133 files, +33,329/−1,134** (115 added, 18 modified). The snapshot commit (`author estate-snapshot <estate@meghadharma>`, dated 2026-08-29) has a single parent, `b148f55e` — it is a flat preservation commit of a dirty worktree, **not** reviewed history. It is unreviewed and unowned by construction; the classifications below are what it earns on inspection.

### (a) The RSI→Foundry lane — KEEP (this is the M3 weld material)

Net-new, no equivalent on any other ref:

- **Lane core:** `forge_lab/candidate_transport.py` (978), `forge_lab/candidate_envelope.py` (509), `forge_lab/promotion_controller.py` (809), `forge_lab/taskpack.py` (786), `forge_lab/safety_control.py` (445), `forge_lab/alert_control.py` (85), `forge_lab/unattended_{budget,child,lease,receipts,reconcile}.py` (469/386/442/200/65).
- **A2A contracts:** `a2a/candidate_evaluator_deployment.py`, `candidate_lease.py`, `candidate_lease_receipt.py`, `candidate_topology_receipt.py`, `candidate_transport_contract.py` (190/133/246/224/380).
- **NATS provisioning:** `scripts/forge_lab/nats-foundry-rsi-{provision,render-config,topology}-v1`, `candidate-foundry-rsi-{consume,publish}-v1`, `candidate-foundry-rsi-envelope-v1.json.in`, `candidate-foundry-rsi-evaluator-identity-v1`, `rsi-service-install-v1`, `rsi-alert{,-v1}`, `rsi-legacy-cutover-v1`, `legacy_shims_v1/`, systemd units, logrotate.
- **Ops doc:** `docs/ops/FOUNDRY_RSI_CONTINUOUS_PIPELINE.md` (233 lines) — a disciplined contract: signed genesis envelopes, three distinct NKey users, no role with live-promotion authority, seed-handling rules. This is the work of someone who understood the threat model; it deserves review, not reverence — e.g. the e2e "proof" below is a *shadow* proof, and live promotion was never exercised.
- **Foundry daemon surface:** `scripts/foundry/{deploy_transaction,install_service,verify_deployment,foundry_status_job,foundry_alert,foundry_pilot,foundry_resume,migrate_legacy_state}.py`, systemd/logrotate templates.

### (b) Tests — KEEP

26 added: 23 `tests/test_foundry_*.py` (incl. `test_foundry_rsi_pipeline.py`, the 675-line end-to-end shadow proof: ed25519-signed envelope → JetStream transport → durable evaluation → terminal disposition, all in-process) + 3 `tests/forge_lab_v1/test_candidate_{envelope,promotion,transport}.py` (302/681/1068 lines). Plus modified `tests/test_nats_transport.py` (206 lines delta). Caveat: none of these have run in CI on any ref; "keep" means "keep for the weld review," not "trusted green."

### (c) Junk / scratch / single-campaign state — COMPOST (preserved on the estate ref, do not merge to main)

- `reports/agentops/work_packets/foundry-rsi-continuous-WP-O21.json` (278 lines) — the one campaign's authorization packet (allowed_files, forbidden_files, base_ref). Evidentiary value on the estate branch; dead weight on main.
- `docs/foundry/submissions/2026-08-19_openevolve_483/` — one-off external submission scratch (`PR_DESCRIPTION.md` + a `.py.txt` attachment). Not main material.
- `scripts/forge_lab/legacy_shims_v1/` (5 tiny shims) and `scripts/forge_lab/rsi-legacy-cutover-v1` — transitional cutover tooling; keep only if the weld actually performs that cutover, otherwise compost with them.

### (d) The 18 modified files — mostly STALE parallel work — preserve-only

Cross-check: `git diff b148f55e ca17cbfab --diff-filter=M --name-only` ∩ `git diff --name-only b148f55e d221961c` = **11 of 18 modified files were also rewritten by canonical's later PRs (cluster L)** — including `unattended_explore.py` (snapshot delta 1,450 lines from a pre-#1454 base; canonical-tip delta 1,811 lines) and `provider_selftest.py` (+1,005 in snapshot, +1,126 different lines at tip). The snapshot's versions **cannot** contain #1454/#1461/#1462/#1476 work (its base predates them), so for these 11 the **canonical tip wins; the snapshot versions are preserved-only**.

The remaining 7 modified files (`a2a/nats_transport_support.py`, `forge_lab/candidate_store.py`, `grade_explore.py`, `source_guard.py`, `state_io.py`, `sync_control.py`, `tests/test_nats_transport.py`) are untouched by later canonical commits and would apply onto `d221961c` cleanly in principle — but they are still unreviewed; route them through the weld review, not a bulk merge.

### (e) Ambiguous — flagged with file:line

1. `dharma_swarm/foundry/receipts.py:32` — snapshot and main both declare `SCHEMA_VERSION = "foundry_improvement.v1"`, but the snapshot's writer emits **extended fields** (`isolation_proofs`, `observations`, `evaluator_image_digest`, …; diff main→snapshot is additive). Same version string, different payload shape → the 39 remote receipts may not round-trip through main's reader. Version-string collision is a defect in whichever side ships second.
2. `dharma_swarm/foundry/daemon.py:1` — **three divergent foundry lineages exist**: main #1389 (`16b8e3f3c`), cursor-branch #1437 (`588690ed3`, *not* on main; `git branch -r --contains 588690ed3` → only `origin/cursor/foundry-run-real`, `origin/estate/cursor-foundry-run-real`), and the snapshot (+7,549/−108 vs #1389; +4,014/−262 vs #1437). Which is authoritative is an M3 decision this manifest deliberately does not make.
3. `dharma_swarm/forge_lab/unattended_explore.py:1` — two large, mutually unaware rewrites (snapshot vs canonical tip). No mechanical reconciliation is safe; requires an owner to read both.
4. `tests/forge_lab_v1/test_provider_selftest.py:1` — snapshot rewrites 709 lines of a file canonical also rewrote (438-line delta at tip). Whose expectations are authoritative is unresolved.
5. `scripts/forge_lab/rsi-provider-refresh:1` and `scripts/forge_lab/systemd/rsi-lab-explore.service:1` — ops config modified in the snapshot and also by cluster L; snapshot versions are stale but may carry host-local knowledge meghadharma never upstreamed.

---

## 3. Receipt provenance

**Which modules could write Foundry receipts, and where do they exist?**

| Module | `origin/main` | `origin/rsi-lab/canonical` | snapshot `ca17cbfab` |
|---|---|---|---|
| `foundry/receipts.py` | yes (#1389, blob `66c41edfa`) | **absent** | yes, extended (blob `51568b998`) |
| `foundry/targets.py` | yes | **absent** | yes, extended |
| `foundry/runner_isolation.py` | yes | **absent** | yes, extended (+388 vs main) |
| `foundry/kill_metrics.py` | yes | **absent** | yes, extended |
| `foundry/daemon.py` | yes | **absent** | yes, 1,427 lines, divergent |

Both versions state: *"Runtime receipts live under `~/.dharma/foundry/receipts/` and never enter git"* (`receipts.py:10` on each). The meghadharma worktree ran `b148f55e` + the dirty state the snapshot preserves, so the 39 Foundry receipts were **most plausibly produced by the `ca17cbfab` tree's `foundry/daemon.py` → `receipts.py` writer** — not by main's #1389 code (never deployed there per any local evidence) and categorically not by `rsi-lab/canonical` (no foundry package at all).

**Verifiable locally:**
- The writer modules, schema, digest scheme (`canonical_digest` from `foundry/evaluator.py`), and the `~/.dharma/foundry/receipts/` convention — as static code in the snapshot tree.
- That **no** `~/.dharma/foundry/` exists on this machine (`ls ~/.dharma/foundry` → absent): no Foundry receipt has ever been written locally. Consistent with "receipts live on meghadharma."
- The separate, genuine local receipt `~/.dharma/rsi-lab/receipts/20260826T151803Z__codex-20260827-rsi-sync-b148f55e__apply__0f6ee23f.json`: schema `rsi_lab.sync_receipt.v1`, `readback_identity.commit = b148f55e00f668fa84774f299610eaae4d8283e4`, `repo_clean: true`, per-file SHA-256 readback of 49 critical files, guard ok, `provider_calls: false`. This is a **real synchronized release**, and it pins `b148f55e` — nothing newer.

**Not verifiable locally (stated plainly):**
- The 39 Foundry receipts themselves: existence, count, digests, chain continuity, terminal dispositions. Zero of them are on this machine or in git.
- The daemon state, kill-metric counters, and whether the runtime code at the moment each receipt was written matched `ca17cbfab` exactly (the snapshot is a single 2026-08-29 capture; receipts may predate the final dirty state).
- Whether any Foundry "evaluation" behind those receipts touched a live model or was a shadow/in-process run. The only e2e proof in the snapshot (`tests/test_foundry_rsi_pipeline.py`) is explicitly a **shadow** proof.

**Custody verdict on the 39 receipts: real-but-remote.** They are claims, not evidence, until meghadharma's `~/.dharma/foundry/receipts/` is itself preserved on an estate ref. Recommend an M0.5 action: snapshot that directory (hashes + files) before any host reimaging.

---

## 4. Merge recommendation

Conflict prediction (read-only `git merge-tree --write-tree --name-only`, no refs written):

- **`origin/main` ← `origin/rsi-lab/canonical`:** 4 conflicted files —
  `dharma_swarm/forge_v1/canonical.py`, `dharma_swarm/forge_v1/forge_v2/runner_slots.py`, `dharma_swarm/forge_v1/providers.py`, `docs/docops/assertions.yaml`.
  (11 paths were touched on both sides since merge-base `145e0b7b`, but `base_provider.py`, `providers.py`, governance docs, and both test files auto-merge.) **Small, mechanical surface.**
- **`origin/main` ← `ca17cbfab` (direct):** **34 conflicted paths**, including ~15 `CONFLICT (add/add)` across `dharma_swarm/foundry/*` (main's #1389 vs snapshot's extension), 3 `docs/foundry/OPERATOR_*`/`RUNNING_NONSTOP` docs, `scripts/foundry/{foundry_daemon,run_campaign}.py`, 10 `tests/test_foundry_*.py`, plus the same 4 canonical-side conflicts. **Do not do this merge.**

**Recommended order:**

1. **Merge `origin/rsi-lab/canonical` (`d221961c2`) into `main` first.** Resolve the 4 conflicts in favor of canonical's forge_v1 attestation logic (main's side is the older, unattested routing; verify with the cluster-D/E owners). Regenerate `docs/docops/` after. This brings in all 32 merge-worthy commits including `forge_fitness.py` and the cluster-L custody chain — and it makes `b148f55e` an ancestor of main, anchoring the verified release in trunk history.
2. **Then weld the snapshot by path, not by merge.** From `ca17cbfab`, checkout/cherry-pick only:
   - the net-new lane files of §2(a) and tests of §2(b) (zero path collisions with main — verified: none of these appear in the add/add set);
   - the 7 non-stale modified files of §2(d), each as its own reviewed PR.
3. **Leave preserved-only (estate ref, never main):** the 11 stale modified files, the foundry package's 15 colliding files (pending the M3 three-lineage decision of §3/§2(e)(2)), the compost of §2(c). The snapshot commit `ca17cbfab` already preserves them immutably; that is its job.
4. **After the weld lands:** cut a fresh cross-host release from the merged trunk with a new `rsi_lab.sync_receipt.v1` receipt before any campaign runs.

---

## 5. CUSTODY DECLARATION

**Hashes placed under custody (immutable, pushed, witnessed 2026-08-30):**

- `a0a88841f0afecc960740e15d2b3ece46d014869` — `origin/main`, canon trunk.
- `d221961c24232d7d05dbff1d971e223da3967f9c` — `origin/rsi-lab/canonical`, canonical RSI lineage tip (34 ahead / 255 behind main).
- `b148f55e00f668fa84774f299610eaae4d8283e4` — the receipt-pinned verified release (ancestor of the above).
- `ca17cbfabffc2997e875505991060b267d46522f` — `origin/estate/foundry-rsi-continuous-snapshot`, single-parent preservation commit of the meghadharma worktree `/root/foundry-rsi-continuous-20260827`.
- Local receipt: `~/.dharma/rsi-lab/receipts/20260826T151803Z__codex-20260827-rsi-sync-b148f55e__apply__0f6ee23f.json` (schema `rsi_lab.sync_receipt.v1`, readback commit `b148f55e`, `repo_clean: true`, 49-file SHA-256 readback — verified present and self-consistent on this machine).

**Judged real:** the 34-commit canonical lineage (PR-reviewed, hermetic-tested, receipt-anchored at `b148f55e`); the local sync receipt; the snapshot as a faithful byte-capture of the named worktree; the RSI→Foundry lane as substantial, threat-model-aware engineering that has never been reviewed, CI-run, or promoted.

**Judged junk / compost:** the WP-O21 work packet and the openevolve_483 submission scratch (single-campaign residue); the legacy cutover shims unless the weld uses them; the docops inventory refresh `a1612fc7d` (regenerable); the merge-glue commit `e9de1c727` (history, not content).

**Judged real-but-unverifiable-here:** the 39 Foundry receipts and daemon state on meghadharma — claims until that host's `~/.dharma/foundry/` is itself preserved.

**Judged stale:** 11 of the snapshot's 18 modified files, superseded by canonical PRs #1454–#1476.

**The one release hash from which future campaigns should run:**

> **`b148f55e00f668fa84774f299610eaae4d8283e4`**

It is the newest commit with a locally verified, cross-host-hermetic, file-level-readback release receipt. `d221961c2` is the correct *merge source* for code, but no release receipt exists for it or anything newer; the next campaign must first cut a fresh receipt from the post-merge trunk, and until that receipt exists, `b148f55e` is the floor.

*— M−1 estate witness. Nothing was merged, moved, or destroyed in the making of this manifest.*
