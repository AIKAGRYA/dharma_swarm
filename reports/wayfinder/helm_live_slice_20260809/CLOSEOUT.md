# Helm Live Slice 1 recovery closeout

Status: **CODE_COMPLETE / LIVE_PROOF_BLOCKED**
Observed: 2026-08-12T16:47:27Z

The interrupted Aug-9 multi-agent build has been preserved, semantically recovered onto current main, hardened under adversarial review, and prepared for draft-PR delivery. The implementation is complete. It is not live-verified, deployed, merged, or 7/7 OnCall.

## Truth at handoff

- Before the first authoritative response, and whenever disconnected or reconnecting, the display is `UNKNOWN ?/7`.
- An authoritative projection with no accepted evidence is `LIVE_DEGRADED 0/7`; all seven seat verdicts are `UNKNOWN` with `missing_evidence`.
- A current read-only probe admitted no safe Claude Opus 4.8 or OpenRouter Kimi K3 primary-chat lane.
- Claude Code reported `Credit balance is too low`. The interrupted Aug-9 Kimi attempt recorded HTTP 403 usage-limit responses.
- Five other fixed seats lack a current exact registered and verified route. Codex is deliberately excluded because its adapter exposes `shell`.
- The bounded two-route live journey was not started, and no successful provider completion was observed during recovery.

The overall delivery status is therefore `LIVE_PROOF_BLOCKED`, while the authoritative empty-evidence projection is `LIVE_DEGRADED 0/7`. These are different axes: delivery proof status versus runtime projection state. No evaluator or route alias was weakened to manufacture a greener state.

## What is complete

- Python owns the fixed seven-seat evidence types, the sole positive evaluator constructor, strict codec, 24-hour TTL, replay defense, and runtime-epoch binding.
- The bridge owns whole-input intent classification, exact raw prompt transport, the no-tools membrane, evidence collection, projection emission, and explicit command outcomes.
- Claude dispatches exactly one byte-preserved user prompt under sealed plan/no-tools settings. OpenRouter omits tools, forces `tool_choice=none`, binds served identity to `response.model`, and rejects tool use, embedded errors, malformed or multiple choices, and unsafe finish reasons before emitting success.
- TypeScript is render-only for RouteVerification, resets on reconnect, fences retired bridge output, and keeps the fixed `N/7` band visible at 80x24 and wider layouts.
- Unsupported commands and failed or cancelled operations never acquire a completion check. Provider narration has no command or state-promotion authority.

The small language-design result is concrete: positive epistemic modality is enforced as a constructor restriction. `RouteVerdict.ON_CALL` cannot enter through deserialization, caller claims, provider success, or terminal state; only the evaluator can construct it after all proof obligations hold.

## Verification

| Gate | Result |
|---|---|
| Governed clean-tree preflight | Passed: syntax, F821, 15,203 collected, onboarding, 67 sentinels, hygiene |
| Governed packet closeout | Passed: exact 51-path scope, all three gates, and isolated TTL mutation control |
| Packet Python regression | 190 passed after the CI-policy follow-up |
| Scoped Ruff and diff check | Passed |
| Full Bun terminal suite | Typecheck passed; 683 passed, 0 failed, 4,070 expectations |
| Terminal Guardian | Passed: 168 focused tests plus bridge syntax and real 80x24 tmux smoke |
| Decorrelated adversarial recheck | Passed after three final edge fixes |
| Semgrep / Gitleaks | 0 findings; 4,361 commits and 378.79 MB scanned with no leaks |
| Contracts / NATS / uplift | 22 passed; 115 passed; all uplift guards passed |
| DocOps pull-request mode | Passed; generated counts are advisory and owned by the post-merge reconciler |
| Claim/evidence | Passed in the track's current advisory enforcement mode |
| PR touched-file hygiene ratchet | Passed locally after replacing a swallowed cancellation error with a sanitized, test-covered failure |
| Rule 10 module budget | Passed locally: `terminal_bridge.py` is 2,770 lines against the immutable 2,792-line ceiling |
| Broad `test-fast` | 6,826 passed before `-x` stopped on one timing-sensitive audit exceeding its 10-second suite timeout |
| Isolated timed-out audit | Passed in 47.98 seconds |

The governed TTL mutation control is stdlib-only: it changes the fixed maximum from 24 to 48 hours and must make a 25-hour evidence fixture promote incorrectly; the control succeeds only when the verifier process exits with the expected failure signal.

The referenced packet closeout receipt is `/private/tmp/dharma-helm-live-slice-agentops-v4b-20260813/reports/agentops/helm-worldclass-terminal-WP-HELMSLICE1-RFC1-RFC2/20260812T162345494902Z/report.json` (SHA-256 `75f6fb6cb3c5edbb4451e0ac0541fe1d7c55703dfd139fa28260cb0aa28bf0e4`). It binds the initial 51-path delivery. The first PR CI pass then found two policy regressions not included in the original packet gates: a swallowed adapter-cancellation exception and the bridge module ceiling. The follow-up records cancellation failure without exception detail, doubles the adversarial cancellation cases, and moves existing command/prompt admission helpers into the packet-owned session-runtime module. The packet regression, Ruff, diff check, hygiene delta ratchet, and Rule 10 budget all pass locally after that repair. The first outer-wrapper continuation stopped after an earlier packet PASS because `semgrep` was not on `PATH`; rerunning with the pinned 1.168.0 executable reached strict local DocOps. That strict target reported only generated-count drift. The pull-request workflow intentionally runs DocOps with `--counts-advisory`, which passed; the post-merge reconciler owns updates to those generated count files.

## Recovery provenance

- Interrupted source: `codex/helm-live-slice-20260809` at `bb2c5174` with 37 dirty/untracked paths.
- Preservation snapshot: `recovery/helm-live-slice-20260809-wip-20260812` at `3560ab3f`.
- Recovery branch: `agent/helm-live-slice-recovery-v4-20260812`, parent `43e93f6de` (current-main parent `12212397b`).
- Work packet: `helm-worldclass-terminal-WP-HELMSLICE1-RFC1-RFC2`, digest `cdaf62ab32e1c9a0dd9458270a96ed2e09cf1547a6d2eee289bba40ea08ccb28`.

The preservation snapshot is archaeology, not a merge source. This delivery reapplies and hardens the intended slice against current main.

## Authority and rollback

The packet permits commit and requires human approval before merge. This closeout does not authorize merge or deployment. Rollback is the packet-scoped initial delivery plus its CI-policy follow-up; there is no migration or durable positive truth store, and reconnect resets the projection to `UNKNOWN`.
