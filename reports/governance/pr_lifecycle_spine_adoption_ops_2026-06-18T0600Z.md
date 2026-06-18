## PR Lifecycle + Spine Adoption Ops — 2026-06-18T06:00Z [automated]

### Mission 1: Spine Adoption
- **adoption_pct: 93.8%** | Target: 95% | Gap: 1.2 pp
- 12 joined, 3 adapter-ready, 1 legacy, 0 missing, 0 quarantine (16 total surfaces)
- `adoption_pct` unchanged from committed (93.8% → 93.8%) — no metric commit triggered
- `source_status`: clean | `audit_sha`: `2368f26c0c60ed162454f7d14fab40694f2c7880`
- No surfaces changed status since previous run

#### Top Saturation Targets (adapter-ready → joined requires):
| Surface | Missing Pattern |
|---|---|
| `tool_registry_dispatch` | `try_begin_idempotent_side_effect` in `tool_registry.py` |
| `self_modification_loop` | `try_begin_idempotent_side_effect` in `diff_applier.py` |
| `mcp_tool_access` | `ExecutionIdentity`, `RuntimeStateStore`, `record_side_effect` in `mcp_server.py` / `dharma_context_mcp.py` |

`mcp_tool_access` is the highest-impact gap — 3 missing patterns, completely untracked for identity/ledger.

---

### Mission 2: PR Lifecycle

**Open PRs before this run: 21**
**Auto-closed this run: 0** (no CONFLICTING PRs older than 7 days)
**Open PRs after this run: 21**

#### CONFLICTING PRs (not yet eligible for auto-close, all < 7 days old):
| PR | Title | Age | Action |
|---|---|---|---|
| #614 | report(governance): PR lifecycle ... 2026-06-15T12:00Z | ~2.8d | Rebase or close as duplicate |
| #613 | report(governance): PR lifecycle ... 2026-06-15 06:00Z | ~3.0d | Rebase or close as duplicate |
| #602 | test(complexity): replay metamorphic relations | ~3.8d | Rebase needed |
| #592 | Bug Corral: signal-graded provenance manifest v2 | ~4.9d | Rebase needed |

#### Duplicate Auto-Grounding PR Streams (flagged — comments posted):

**Spine adoption metric refresh stream** — keep #627 (newest), close older:
- #622 — 2026-06-17T00:02Z — duplicate
- #621 — 2026-06-16T18:02Z — duplicate
- #615 — 2026-06-16T00:01Z — duplicate
- #612 — 2026-06-15T06:02Z — duplicate

**Governance ops report stream** — keep #628 (newest), close older:
- #626 — 2026-06-17T12:03Z — duplicate
- #624 — 2026-06-17T06:05Z — duplicate
- #618 — 2026-06-16T12:12Z — duplicate
- #614 — 2026-06-15T12:04Z — duplicate + CONFLICTING
- #613 — 2026-06-15T06:04Z — duplicate + CONFLICTING

#### Green-and-Ready (MERGEABLE) PRs: 17
#629, #628, #627, #626, #625, #624, #623, #622, #621, #620, #619, #618, #615, #612, #609, #607, #599

#### Recommended Operator Actions:
1. **Close duplicate spine metric PRs**: #622, #621, #615, #612 — superseded by #627
2. **Close duplicate governance report PRs**: #626, #624, #618, #614, #613 — superseded by #628
3. **Rebase or close**: #602, #592 — CONFLICTING, non-duplicate, approaching 7-day threshold
4. **Review for merge**: #625 (feat/orientation), #623 (Devin A2A), #620 (palantir-pilot), #619 (ci/governance), #609 (docs reconciliation), #607 (ci/tests), #599 (docs/state)

---

_Report role: `report` (dated descriptive output — not operational authority)_
_Generated: 2026-06-18T06:00:37Z by ops agent run `019ed950-a9bb-7a17-a222-1a368e81cb02`_
