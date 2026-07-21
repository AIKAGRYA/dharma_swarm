# Build Spec: REMOTE_HOLON_MESH_AND_SHARED_BOARD_V1 — v1.1 (hardened)

Version: v1.1, 2026-07-10 JST.
Supersedes: the v1.0 draft (2026-07-09) and the earlier short execution-contract pass of this file.
Review provenance: v1.0 was reviewed by a 6-lens adversarial workflow (54 findings: 15 adversarially
CONFIRMED, the rest verified directly against disk/receipts after the verify fleet was cut short).
Every behavioral change from v1.0 is grounded in an on-disk fact, not taste.

## 0. Executive Summary

Build a safe, receipt-backed remote holon operations mesh across the Mac (operator workstation),
agni, meghadharma, and rushabdev.

The goal is NOT to claim Sarathi is alive, NOT to create another orchestration layer, and NOT to
invent a second board. The goal is to harden and connect the existing substrate: safe key
distribution + agni NATS/A2A hub + VPS spoke hosts + the existing ECB board + cross-host receipts +
explicit liveness/freshness gates.

Success means, in claim-state language (§5):

1. secrets are `proven` present only where approved, with movement ledgers;
2. agni is the `proven` NATS hub (including negative-path auth proof);
3. meghadharma is `proven` as an authenticated spoke;
4. rushabdev is `proven`, `blocked`, or `descoped` — by explicit operator decision (D1), never by drift;
5. the existing ECB board is revived, repo-owned, and extended (ECB-004..012);
6. a remote mesh matrix exists and honestly reports pass/fail/blocked with descopes recorded;
7. Sarathi remains non-live (`alive_claim=false`, `wake_loop_active=false`) until receipts prove otherwise.

---

# 1. Current Changed Files and Commit Discipline

Curated files from the previous pass:

- `scripts/runtime/sync_agent_keys_to_vps.sh`
- `docs/governance/REMOTE_HOLON_MESH_AND_SHARED_BOARD_V1.md` (this file)

Commit rules:

- Explicit staging only. `git add .` is forbidden for this pass (repo is dirty).
- **Do NOT use `--no-verify`.** The repo's pre-commit guards (uplift guards, name-drift preflight)
  exist precisely to protect governed surfaces; a governance commit must pass them. If a guard
  fails, fix the cause or record the specific guard + reason in the commit body — never bypass
  silently. (v1.0 instructed `--no-verify` twice with no justification.)
- Disposition of the OTHER currently-dirty files must be decided in Phase 1, not left dirty:
  `reports/governance/nats_live_production_matrix/latest.json` + the untracked
  `nats-live-20260708T005030Z-*/` run dir (either commit as an intentional evidence refresh from
  the 07-08 local run, or revert), and `reports/governance/active_track_evidence.{json,md}` +
  `track_portfolio.json` (generated; commit only if regenerated deliberately).
- **Track ownership (D6):** `dharma_swarm/a2a/board/`, the remote-matrix runner/checker, and the
  new tests are NEW repo surfaces inside track-owned territory (`dharma_swarm/a2a/**` files are
  owned by the runtime-truth-nats and a2a-cloud-agent-bridge tracks). Before Phase 2 lands code,
  the operator must map these surfaces to an existing track or open a new track in
  `docs/governance/ACTIVE_TRACK.yaml` (operator canon — never hand-edited by agents).

```bash
cd /Users/dhyana/dharma_swarm
git add scripts/runtime/sync_agent_keys_to_vps.sh \
        docs/governance/REMOTE_HOLON_MESH_AND_SHARED_BOARD_V1.md
git diff --cached --check && git diff --cached --stat
git commit -m "governance: specify remote holon mesh build (v1.1 hardened)"
```

---

# 2. Known Verified State (as of 2026-07-09/10; re-verify anything older than 7 days before acting on it)

## 2.1 Local repo / Mac

- repo `/Users/dhyana/dharma_swarm`; runtime `/Users/dhyana/.dharma`; canonical key file
  `~/.dharma/agent_keys.env` (mode 0600, 42 names).
- Helper `scripts/runtime/sync_agent_keys_to_vps.sh`: `bash -n` clean; dry-run remote-read-only;
  apply requires `--operator-approved`; risky-host gate; values never printed; **backs up the
  remote file to `agent_keys.env.bak.<UTC-ts>` before overwrite** (this is the rollback path);
  writes redacted ledger `dharma.secret_sync_receipt.redacted.v1`.
- Mac NATS is loopback-only; local matrix pass 2026-07-08 (`local-live-jetstream`,
  `nats://127.0.0.1:4222`). A local JetStream proof is NOT a remote mesh proof.

## 2.2 agni (157.245.193.15)

- ssh OK (root@agni-openclaw). NATS `/usr/local/bin/nats-server -c /etc/nats-server.conf`,
  v2.10.9, PID 907 at verification time (parent 1, NOT confirmed systemd-managed —
  **re-derive the PID at run time; never reuse 907**).
- Config markers present: authorization, users, TLS, JetStream, store_dir.
- `meghadharma_hermes` NATS user: absent.
- Observed firewall posture (record honestly): 4222 allowed from rushabdev + two Mac-side IPs;
  **deny-anywhere rules exist AFTER the allow rules**; **8443 is PUBLIC (WSS)**; rushabdev also
  has a broad source-IP allow. The §4.1 target posture therefore DIVERGES from observed reality —
  closing or keeping 8443/broad-allow is operator decision **D2**, not something to silently
  "fix" or silently accept.

## 2.3 meghadharma (178.128.87.170)

- ssh OK. `~/.dharma/agent_keys.env`: absent. No NATS listener. Cannot reach agni:4222 (timeout).
- **The box is NOT key-free**: `/root/dharma_swarm/.env` (compose env) already holds live provider
  keys (Anthropic/OpenAI/OpenRouter/Kimi/NVIDIA/Groq/Cerebras + Litestream S3 + a Devin-era NATS
  credential). Two key stores on one box is a drift risk this spec manages explicitly (§6.0).
- **"UFW: OpenSSH-only" is not a sufficient security claim**: Docker's iptables chains bypass ufw.
  The real network edge is DOCKER-USER deny rules plus a compose loopback-bind patch that is
  currently an **UNCOMMITTED local change** — a clean rebuild from main REOPENS public 8080/7433.
- Safety state verified 07-09: SHADOW=1, AUTONOMY=1, SELF_IMPROVE=0, LIVE_MUTATION=0; code at
  origin/main tip, source bind-mounted read-only; exposure currently closed.
- **The organism (1GB docker volume: 18k receipts, 1.45M idea_links) has ZERO off-host backup**;
  litestream crash-looped 8,418× on three empty env vars. And the box's container healthcheck
  stayed GREEN through a 69-of-73-hour main-loop wedge — container-up is a lying liveness signal
  here. Both facts shape §13 and the card set (ECB-011/ECB-012).

## 2.4 rushabdev (167.172.95.184)

- ssh from Mac: `Permission denied (publickey)`. **This is a REVOCATION, not breakage**: the
  Mac's key was revoked (verified 2026-07-08; the reverse-tunnel plan moved to agni because of
  it). Restore-vs-keep-revoked is operator decision **D1**.
- **Data-preservation invariant**: `rushabdev:/home/openclaw/dhyana_mirror` (35G) holds the only
  known copy of the Persistent-Semantic-Memory-Vault + unique research repos. **No reimage,
  rebuild, reset, disk cleanup, or provider-console "repair" action that could touch the disk is
  permitted until PSMV is rsynced off and verified.** (§3.5)

## 2.5 Existing shared board

`~/.dharma/a2a_bus/boards/ecosystem_command_board_v0/` — BOARD_SPEC.md, board.json, ecb.py
(480 lines), events.jsonl, receipts/, digests/, proposals/, remote_runs/.

Verified state (from source, not memory):

- Board validates. Last event 2026-06-30T07:14:51Z (stale ~9 days by any definition).
- Canonical writer is **hermes-m5** (BOARD_SPEC.md policy; validator enforces it).
- Proposal allowlist (`ecb.py:275`) = `{agni, rushabdev, hermes-m5}` — meghadharma excluded.
- Mirror default (`ecb.py:334`) = `["agni", "rushabdev"]` — meghadharma excluded; and with
  rushabdev revoked, mirror runs now FAIL (`check=True` raises mid-loop).
- **Defect (confirmed by code read):** `mirror()` attaches a `result="pass"` board_mirror receipt
  BEFORE any copy occurs; a failed host therefore leaves a false pass receipt on the canonical
  board. Must be fixed in the repo port, not blindly "ported as-is".
- Subcommands: validate/show/claim/status/receipt/proposal/mirror — **no add-card command**.
- Path resolution is `__file__`-relative (`ROOT = Path(__file__).resolve().parent`) — tests
  against a ported copy would write into the repo or the live board unless a board-root override
  is added (§9.2).

## 2.6 Remote mesh matrix

Missing. `reports/governance/nats_remote_mesh_matrix/` does not exist. The existing local pattern
to mirror: `scripts/governance/run_nats_live_production_matrix.py` (runner) + separate
`check_nats_live_production_evidence.py` (checker, incl. tamper/freshness negative tests).

## 2.7 Sarathi

Already further along than v1.0 assumed — repo package `dharma_swarm/holon_system/sarathi/`
(`brief.py`, `gateway.py` [`dharma.sarathi.gateway.v1`], `pulse.py`, `roster.py`,
`tests/test_sarathi_apex.py`); runtime seat `~/.dharma/agents/sarathi/` (identity.json, outbox/,
gateway_receipts/, pulse_receipts/, READINESS_RECEIPT.md); proven-live-with-receipts (07-08):
wake pipe, inbox file-drop observation, holon_talk. Staged NOT armed: standing 900s wake-loop
plist + lease — **the operator's `launchctl load` is the approval act**; `wake_loop_active`
stays false until the overnight (G9) receipts are verified. Phase 9 EXTENDS these surfaces.

---

# 3. Non-Negotiable Constraints

## 3.1 Secrets

Never: print secret values; **print value lengths, prefixes, or hashes of values**; commit secret
values; paste them into prompts; copy OAuth/session stores without explicit request; copy keys to
meghadharma without `--operator-approved` AND the §6.0 preconditions.

**Never source a key file and never `eval` over key names/values — anywhere, on any host.**
Presence checks are grep-by-name or the helper's receipt fields, full stop. (v1.0's own
verification block sourced the merged file as root and ran `eval` over values — a confirmed
root code-execution channel via remote-preserved lines, plus a length leak.)

Secret classes covered by this spec's ledger discipline: provider API keys AND **NATS
credentials** (§7.3). Out of scope unless separately requested: `~/.codex/auth.json`, `~/.qwen`,
macOS Keychain, Claude Code/Max auth, model weights.

Claim language: say "API/env keys synced (names verified)". Never "all models moved", "all auth
moved", "all providers proven".

## 3.2 Runtime/source boundary

`dharma_swarm/` = source, tests, scripts, docs. `~/.dharma/` = runtime state, identities,
ledgers, inboxes, heartbeats, receipts. Real implementations never live only under `~/.dharma`;
runtime wrappers import repo-owned code (§9.2, incl. version receipting).

## 3.3 Sarathi truthfulness

Until proven: `alive_claim=false`, `wake_loop_active=false`. Never claim alive / remotely
autonomous / overnight-proven / phone-egress-proven without receipts. The arming of any standing
loop is an operator act (§3.6).

## 3.4 No parallel systems

Do not create a new: board, task store, router, orchestrator, A2A bus, receipt spine, NATS
abstraction, **or claim-state vocabulary**. Use the existing substrate. (This spec unifies the
two claim vocabularies that had already drifted — §5.)

## 3.5 Data-preservation invariant (new in v1.1)

Look before you delete, on every host. Specifically: rushabdev's `dhyana_mirror` (PSMV) must be
rsynced off and verified before ANY destructive/reprovisioning action on that host; meghadharma's
`dharma_swarm_dharma-state` volume is the organism's only life — no container/volume operations
that could destroy it until off-host replication (ECB-011) is live.

## 3.6 Maker ≠ approver (new in v1.1)

No agent installs or arms persistence (launchd/cron/systemd timers). Agents STAGE plists/units +
lease files; the operator's load/bootstrap command is the approval act. Consequence accepted
honestly: freshness gates that require standing heartbeats will report `stale` until the operator
arms emitters (D3) — that is the correct, expected reading, not a failure to hide.

---

# 4. Target Architecture

## 4.1 Host roles (target; where observed reality diverges, the divergence is named)

- **Mac** — source-of-truth dev/operator console. Owns repo, canonical key file, operator
  approvals. Must not become required for every runtime event long-term.
- **agni** — NATS/A2A hub. Owns NATS server, JetStream, hub credentials, hub firewall policy.
  Target inbound: SSH + NATS from approved spoke IPs only. **Observed divergence: 8443 public
  WSS + broad rushabdev allow → decision D2 (close vs. ratify into the target posture).**
  Must not become an untracked source-code home.
- **meghadharma** — spoke VPS / remote worker. Owns local runtime key file, outbound NATS to
  agni. Inbound: SSH only. Must not expose public agent services until proof gates pass —
  **and the current exposure closure must be made durable (compose patch committed) before keys
  land (§6.0)**.
- **rushabdev** — historical board participant; access REVOKED; role suspended pending D1
  (restore / keep-revoked-descoped). Carries the PSMV data-preservation invariant either way.
- **Sarathi** — apex continuity holon shell, non-live; may read board/heartbeats/matrix/state;
  may emit operator brief, risk digest, next-card recommendation; may not self-claim autonomy.

## 4.2 NATS topology

agni = canonical hub; meghadharma (and rushabdev if D1=restore) = outbound spokes; Mac = dev
node, loopback tests allowed. No VPS becomes a second hub in V1.

---

# 5. Claim-State Model (unified — replaces both prior vocabularies)

One vocabulary, six states:

- `declared` — plan text or operator intent only.
- `observed` — read-only command output or file inspection, with timestamp.
- `configured` — a change was applied; not yet independently verified.
- `proven` — objective receipt PLUS an independent verifier/checker result.
- `blocked` — an external dependency prevents progress (we want it, we can't).
- `descoped` — the operator decided not to pursue it (recorded decision reference required).

`failed` is not a state of the world; it is a matrix row/step result. A claim is written as
`subject = state (evidence-ref, timestamp)`, e.g.:

```
meghadharma_keys      = observed_absent (dry-run 2026-07-09) → configured → proven (receipt + name-check)
rushabdev_ssh         = blocked (revoked key, 2026-07-08) | descoped (D1 record)
agni_nats_hub         = observed (listener) → proven (remote publish/consume + auth-rejection rows)
remote_mesh           = missing → blocked | proven (matrix pass ≤ 24h old, checker-verified)
sarathi_liveness      = false until wake-loop armed by operator AND overnight receipts verified (G9)
```

Every `proven` claim carries a TTL: **any proof older than 7 days (matrix: 24 hours) must be
re-stated as `observed (stale, age=X)` in reports and Sarathi briefs** — the meghadharma
green-healthcheck-through-a-69h-wedge lesson generalizes: verified states decay.

No report may use stronger language than the state permits.

---

# 6. Secret Sync Build Requirements

## 6.0 Preconditions for ANY apply to meghadharma (new in v1.1 — all four required)

The helper's own contract says `--allow-risky-host` is for use "only after remediation". The
remediation is currently non-durable. Therefore, before `--operator-approved` may be combined
with `--allow-risky-host`:

- **(a) Durable exposure closure**: the compose loopback-bind patch is COMMITTED upstream and the
  running stack is built from that pinned commit (a clean rebuild must not reopen 8080/7433).
- **(b) DOCKER-USER deny rules verified present** on the box (fresh read, not memory).
- **(c) Fresh probe (< 24h)**: `ss -ltn` on meghadharma shows no non-loopback listener except SSH.
- **(d) Named consumer**: the sync is pointless without one — meghadharma's running container
  reads `/root/dharma_swarm/.env`, NOT `~/.dharma/agent_keys.env`. State in the ECB-004 card
  which process will consume the synced file (host-level spoke tooling: NATS spoke client, board
  mirror agent, heartbeat emitter — Phase 6+). Explicitly record that this sync does NOT fix the
  container's dead claude lane; that is a separate, container-env change requiring its own
  operator approval.

Record (a)-(c) results in the sync receipt's environment (a companion note
`~/.dharma/security/secret_sync_receipts/<ts>-meghadharma-preconditions.json` with the probe
summary and compose commit SHA). Two-key-store policy: `~/.dharma/agent_keys.env` is canonical
for host-level tooling; `/root/dharma_swarm/.env` remains container-scoped; never auto-merge the
two; note the coexistence in the receipt.

## 6.1 Helper behavior (contract = the implemented script; do not respecify divergently)

Required behavior (all already implemented — tests in §15.3 pin them): dry-run remote-read-only;
apply requires `--operator-approved`; values never printed; no full-file SHA printed; remote-only
vars preserved; local wins on overlap; remote mode 0600 (helper also requires LOCAL file 0600);
**remote backup `agent_keys.env.bak.<UTC-ts>` created before overwrite (the rollback path)**;
redacted ledger written on apply; risky hosts refused without `--allow-risky-host`.

Command shapes (dry-run any time; apply ONLY after D4 + §6.0):

```bash
cd /Users/dhyana/dharma_swarm
scripts/runtime/sync_agent_keys_to_vps.sh --host meghadharma --allow-risky-host --dry-run
# after operator approval (D4) AND §6.0(a-d):
scripts/runtime/sync_agent_keys_to_vps.sh --host meghadharma --allow-risky-host --operator-approved
```

Rollback: restore the timestamped remote `.bak` file over the merged file (document the exact
`ssh meghadharma 'cp -p <bak> <path>'` in the receipt note if ever exercised).

## 6.2 Secret movement ledger (adopt the IMPLEMENTED schema verbatim)

Receipts land under `~/.dharma/security/secret_sync_receipts/` (runtime, never git), schema
**`dharma.secret_sync_receipt.redacted.v1`** with fields exactly as implemented: `timestamp`,
`host`, `source`, `destination`, `names_count`, `remote_names_before_count`,
`remote_names_after_count`, `local_only_added`, `remote_only_preserved`, `overlap_names`,
`missing_after`, `mode`, `values_printed`, `operator_approved`, `overlap_policy`,
`verified_provider_names`. (v1.0 respecified a divergent `…receipt.v1` — that schema is dead;
the implementation wins.) No secret values, no value hashes.

## 6.3 Post-sync verification (rewritten — never source, never eval, no lengths)

Primary verification is the helper's own post-merge name check (hard-fails on missing names,
exit 7) plus the receipt's `verified_provider_names`. Optional independent re-check:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 meghadharma '
  test -f ~/.dharma/agent_keys.env &&
  stat -c "mode=%A owner=%U:%G size=%s" ~/.dharma/agent_keys.env
'
ssh -o BatchMode=yes -o ConnectTimeout=8 meghadharma '
  for k in OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY GOOGLE_AI_API_KEY GROQ_API_KEY \
           NVIDIA_API_KEY NGC_API_KEY OPENROUTER_API_KEY SAKANA_API_KEY; do
    if grep -qE "^[[:space:]]*(export[[:space:]]+)?${k}=.+" ~/.dharma/agent_keys.env; then
      echo "$k=PRESENT"
    else
      echo "$k=MISSING"
    fi
  done
'
```

Expected: `mode=-rw------- owner=root:root`. Note: `.+` proves a non-empty right-hand side only —
that is the intended scope of a names-only check.

---

# 7. agni NATS Hub Build Requirements

## 7.0 Runtime re-derivation rule (new in v1.1)

Never reuse recorded PIDs or IPs in commands. Before any agni/meghadharma action: re-derive the
NATS PID (`pgrep -f nats-server`), re-read `ufw status numbered`, and cross-check host IPs
against `~/.dharma/host_identity.json` (§12) AND a live lookup. DigitalOcean droplet IPs can
change on rebuild; a firewall rule for a stale IP is silent lockout.

## 7.1 Pre-change inspection (structure only — never print raw auth config lines)

```bash
ssh agni '
  echo "-- process --";  pgrep -af nats-server
  echo "-- config structure (marker names + counts only) --"
  for m in authorization users tls jetstream store_dir websocket listen port; do
    printf "%s=%s\n" "$m" "$(grep -ciE "$m" /etc/nats-server.conf)"
  done
  echo "-- firewall --"; ufw status numbered
'
```

(v1.0 grepped raw config lines with a blacklist sed — a fragile redactor that misses nkey/jwt/
include-file credentials. Print structure, never content.)

## 7.2 Supervisor/reload contract (pinned, not open questions)

Because NATS is PID-1-parented and not confirmed systemd-managed, write the contract BEFORE any
config mutation, containing at minimum these pinned mechanics:

- start mechanism: discover and record (systemd unit? rc.local? tmux? docker?) — command + evidence;
- config path: `/etc/nats-server.conf`; backup: `cp -p` to `/etc/nats-server.conf.bak.<UTC-ts>`;
- validation BEFORE any signal: `nats-server -c /etc/nats-server.conf -t` (test mode; hard gate);
- change application: **prefer `nats-server --signal reload=<live-pid>` (SIGHUP; `users` blocks
  are reloadable in 2.x) over restart**; restart requires a NEW operator approval;
- post-reload verification: listener up (`ss -ltn | grep 4222`), version/health probe, existing
  spokes still connected;
- rollback: restore `.bak` config + reload again; if reload fails, STOP — no kill/restart without
  fresh approval;
- operator warning text to show before any signal.

Location: `docs/ops/agni_nats_reload_contract.md` ONLY if it contains no runtime-only
specifics/secrets; otherwise `~/.dharma/ops/nats_reload_contract_agni_<YYYYMMDD>.md`. When in
doubt, runtime path.

## 7.3 Dedicated meghadharma user + credential lifecycle (fully specified)

Add NATS user `meghadharma_hermes`. Never reuse `agni_hermes`, `rushabdev_hermes`, `hermes`, or
the Devin-era NATS credential already present in meghadharma's compose env.

Credential lifecycle (plaintext is born on the spoke and never leaves it):

1. Generate ON meghadharma: `umask 077; mkdir -p /root/.dharma/nats; openssl rand -base64 32 > /root/.dharma/nats/meghadharma_hermes.cred` (mode 0600).
2. Derive the bcrypt hash ON meghadharma (`nats server passwd` if the nats CLI is present, else a
   documented python-bcrypt one-liner reading the file — never echoing it).
3. Transfer ONLY THE HASH to agni; place it in the `users` block of `/etc/nats-server.conf`.
4. Write a movement receipt to `~/.dharma/security/secret_sync_receipts/` (same redacted
   discipline: host pair, paths, mode, `values_printed:false`, operator_approved) — NATS creds
   are secrets and get the same ledger as API keys.
5. Rollback: remove the user block from agni config + reload; shred the cred file on meghadharma.

## 7.4 Firewall (rule ORDER is the whole game)

agni's existing ruleset has deny-anywhere rules AFTER its allow rules. A plain `ufw allow`
APPENDS — the new rule would sit after the deny rules and never match, while a `ufw status | grep`
"verification" happily greens the dead rule. Required procedure:

```bash
ssh agni 'ufw status numbered'                       # find index N of the FIRST deny rule for 4222
ssh agni 'ufw insert <N> allow from <MEGHADHARMA_IP> to any port 4222 proto tcp comment "NATS-MEGHADHARMA"'
ssh agni 'ufw status numbered'                       # confirm the allow now precedes the denies
```

`<MEGHADHARMA_IP>` is re-derived per §7.0 (host_identity + live check), not copy-pasted.
**Verification of this step is FUNCTIONAL, not textual**: the §7.5 probe from meghadharma must
succeed AND a probe from a non-allowed source must still fail. Rollback:
`ufw status numbered` → `ufw delete <N>` for the inserted rule (record before/after).

## 7.5 Connectivity probe (with fallback; nc may be absent)

```bash
ssh meghadharma '
  AGNI=157.245.193.15   # re-derive per §7.0
  if command -v nc >/dev/null 2>&1; then nc -vz -w 5 "$AGNI" 4222;
  else python3 -c "import socket,sys; s=socket.create_connection((\"'"$AGNI"'\",4222),5); print(\"tcp-ok\"); s.close()"; fi
'
```

This is port reachability only — not auth proof, not A2A proof.

## 7.6 Authentication proof — positive AND negative (new in v1.1)

"Authenticated spoke" requires all three, each receipted:

- `meghadharma_hermes` credential connects and can publish/consume on its allowed subjects;
- an ANONYMOUS connection attempt is REJECTED by agni;
- a WRONG-credential attempt is REJECTED.

Without the negative rows, "verified NATS hub" can be certified while auth is effectively open.
These become matrix rows (§10).

---

# 8. rushabdev — Operator Decision Gate (reframed; was "Recovery")

Ground truth: the Mac's key was REVOKED (2026-07-08), not lost. §8 is therefore a DECISION gate,
not a repair runbook. Present the operator with D1:

- **D1a — restore**: re-add the Mac public key via provider console/known-good path. Then verify
  (SSH, key file, NATS reachability to agni, board mirror, heartbeat) and proceed as a spoke.
- **D1b — keep revoked, descope**: record `rushabdev = descoped (D1b, <date>)`; remove rushabdev
  from the required-spoke set (§10) and the mirror set (§9.5); the mesh can then honestly reach
  `pass` without it, with the descope recorded in every report.
- **D1c — defer**: remains `blocked`; matrix status stays `blocked`; say so.

Hard guards regardless of choice:

- **No reimage/rebuild/reset/disk-destructive provider action until PSMV
  (`/home/openclaw/dhyana_mirror`) is rsynced off and verified** (§3.5).
- No workarounds via copied private keys or session stores.
- Restoring root SSH to a host previously flagged top-estate-risk is itself a security decision —
  D1a must be an explicit operator "yes", not a default.

If restored, verification (BatchMode ssh: hostname/id, key file stat, `ss -ltn` for NATS ports)
as in v1.0. If still blocked/descoped, record the exact state string and never include rushabdev
in "verified mesh" claims.

---

# 9. Board System Build Requirements

## 9.1 Existing board remains canonical

`~/.dharma/a2a_bus/boards/ecosystem_command_board_v0/`. Do not create ecosystem_command_board_v1,
sarathi_board, remote_mesh_board, kanban_v2, or any parallel task store.

## 9.2 Repo-owned board primitive (port WITH fixes — not "as-is")

Source package: `dharma_swarm/a2a/board/` (`__init__.py`, `ecb.py`) — after D6 track mapping.
Port from the runtime `ecb.py`, applying these REQUIRED changes:

1. **Board-root injection**: `ECB_BOARD_ROOT` env var / `--board-root` flag overrides the
   `__file__`-relative default. Tests run against tmp dirs; the live board is never touched by
   the test suite.
2. **Mirror fix (confirmed defect)**: write the `board_mirror` receipt AFTER the copy loop, with
   per-host `ok` results; replace `check=True`-raise-mid-loop with per-host try/except so one
   dead host cannot wedge the others or fabricate a pass; `result` = `pass` only if ALL
   configured hosts verified sha-equal, else `partial` with the failed hosts named.
3. **Policy as data**: move the proposal allowlist and mirror host set out of code into a
   `policy` block in `board.json` (`proposal_allowlist`, `mirror_hosts`, `canonical_writer`,
   `writer_delegates`). Adding meghadharma is then a receipted board EVENT (`policy_amended`),
   not a code fork.
4. **`add-card` subcommand**: event-backed card creation — event type `card_created`, initial
   status `ready`, full v0 field set, receipt written, board validated after.
5. **Version receipting**: every receipt written via the repo implementation carries
   `writer_code_sha` (best-effort `git rev-parse HEAD` of the repo at import time) — the runtime
   wrapper means repo commits silently change the canonical writer's behavior; receipts must
   record which code wrote them.

Runtime wrapper replaces the 480-line runtime copy (same path) and imports the repo module; a
test (§15.4) asserts the wrapper actually delegates (no second diverging implementation).

## 9.3 Card schema = the REAL v0 schema (v1.0 diverged while forbidding divergence)

Required fields (from `REQUIRED_CARD_FIELDS` + practice): `id`, `title`, `domain`, `priority`,
`status`, `owner`, `collaborators`, `objective`, `done_when`, `artifacts`, `receipts`,
`verifier`, `lease_until`, `updated_at` (+ `created_at`, `created_by` as in existing cards).
Status values (`VALID_STATUSES`): `inbox, ready, claimed, doing, review, blocked, done, stale,
rejected`. Event schema stays `dharma.ecosystem_command_board.event.v0`. (v1.0's
`proof_artifacts` rename and 7-status list are dead — they would have failed the live validator.)

New cards (all P0 unless noted):

- ECB-004 — Sync env/API keys to meghadharma safely (gated on D4 + §6.0; names the consumer)
- ECB-005 — rushabdev decision gate: restore / descope / defer (D1) + PSMV preservation guard
- ECB-006 — Add meghadharma as authenticated NATS spoke to agni (incl. §7.3 cred lifecycle)
- ECB-007 — Run remote A2A/NATS mesh proof (runner + independent checker)
- ECB-008 — All-host heartbeat freshness digest (**meghadharma liveness = main-loop pulse
  recency, NOT container/ssh-up** — the 69h-wedge lesson)
- ECB-009 — Wire agents to read board at wake and post claims/receipts
- ECB-010 — Sarathi remote check-in reads board and emits operator brief (extends existing
  `holon_system/sarathi/` surfaces)
- ECB-011 — meghadharma off-host replication: fix litestream (3 empty env vars) or declare state
  disposable by operator decision (P0 — currently the organism has zero backup)
- ECB-012 — agni firewall posture reconciliation (D2): 8443 public WSS + broad rushabdev allow —
  close or ratify, receipted

Verifier ≠ owner wherever practical.

## 9.4 Board freshness rules (computable version)

Definitions first: an **active host** = `host_identity.json` present with `agent_runtime: true`
AND an operator-armed heartbeat emitter registered for it (§3.6/D3). Then the board is `fresh`
iff: latest event age < 6h; every ACTIVE host heartbeat age < 10m; every `doing` card has an
unexpired lease; every `done` card has ≥1 receipt; every `blocked` card has blocker text; every
mirrored host's last mirror receipt sha-matches canonical.

Until any emitter is armed there are zero active hosts, so the heartbeat clause is vacuous —
therefore the freshness digest must ALSO report `armed_heartbeat_hosts=[]` explicitly, and the
board report reads `board_status=stale (no armed heartbeat emitters — expected until D3)`.
Honest staleness is the designed outcome pre-D3, not an error.

## 9.5 Board mirrors and writer governance

Mirror set comes from board policy (§9.2.3): initially `[agni, meghadharma]`; rushabdev rejoins
only under D1a. Mac remains the canonical local runtime path.

**Canonical-writer amendment (required before Phase 3 writes cards):** BOARD_SPEC.md names
hermes-m5 as sole canonical writer and the validator enforces it. The Mac-side builder must not
silently write as someone else. Either (a) route card creation through hermes-m5, or (b) amend
the policy explicitly: `policy_amended` event adding `writer_delegates: [fable_composer]`
(operator-acked in the event note), each delegate event recording its true actor. Option (b) is
recommended; the amendment itself is a receipted board event.

Spoke agents propose events (proposal allowlist now includes meghadharma via policy); they never
mutate canonical state directly.

---

# 10. Remote Mesh Matrix Requirements

Output: `reports/governance/nats_remote_mesh_matrix/<run_id>/evidence.json` + `latest.json`.
Two scripts, mirroring the local pattern (worker ≠ judge):

- `scripts/governance/run_nats_remote_mesh_matrix.py` — runner;
- `scripts/governance/check_nats_remote_mesh_evidence.py` — independent checker: schema, row
  completeness vs the REQUIRED set, freshness (`--max-age-hours`, default 24), tamper checks
  (mirror the local checker's negative tests).

Schema:

```json
{
  "schema": "dharma.nats_remote_mesh_matrix.v1",
  "run_id": "nats-remote-mesh-...",
  "generated_at": "ISO-8601",
  "status": "pass|fail|blocked",
  "hub": "agni",
  "spokes_required": ["meghadharma"],
  "spokes_descoped": [{"host": "rushabdev", "decision": "D1b", "recorded_at": "..."}],
  "required_rows": [], "rows": [], "missing_rows": [], "failed_rows": [], "blocked_rows": []
}
```

**`spokes_required` is declarative and operator-scoped** (D1): descoped hosts' rows are removed
from `required_rows` and listed under `spokes_descoped` with the decision reference — so the mesh
can honestly `pass` without rushabdev if and only if the operator descoped it. `blocked` remains
for wanted-but-unreachable dependencies. (v1.0 hardwired rushabdev rows, making `pass`
permanently unreachable under a legitimate operator choice.)

Required rows (for the required spoke set):

```
agni_nats_hub_topology
<spoke>_keyfile_present
<spoke>_nats_port_reachable
nats_auth_anonymous_rejected          # negative path — required for any "authenticated" claim
nats_auth_wrong_creds_rejected        # negative path
mac_to_agni_publish
agni_to_<spoke>_consume
<spoke>_to_agni_publish
duplicate_task_dedup_cross_host
handler_failure_redelivery_cross_host
dlq_cross_host
restart_reconnect_cross_host
board_event_publish
board_mirror_to_all_hosts
heartbeat_freshness_all_hosts         # one-shot heartbeats emitted DURING the run count here;
                                      # standing freshness is §9.4's separate gate
```

`status=pass` requires: `missing_rows=[] ∧ failed_rows=[] ∧ blocked_rows=[]` AND checker green.
Any required host blocked → `status=blocked`. Consumers (Sarathi, reports) MUST treat a matrix
older than 24h as stale evidence (§5 TTL) and report its age.

---

# 11. Sarathi Integration Requirements

Sarathi V1 = read-only remote operator brief, **built on the EXISTING surfaces**: repo package
`dharma_swarm/holon_system/sarathi/` (`brief.py` generates the brief; `gateway.py` defines
`dharma.sarathi.gateway.v1`; `pulse.py`, `roster.py`), runtime seat `~/.dharma/agents/sarathi/`
with existing `outbox/`. Extend `brief.py`/`gateway.py`; do not invent a parallel brief pipeline.

May read: ECB board, host identities, heartbeats, local+remote matrix `latest.json` (with age),
A2A inbox state, holon seat state, redacted secret-sync receipts. May emit: operator brief, risk
digest, next-card recommendation. May NOT emit alive/wake_loop_active/autonomous/overnight_proven/
phone_egress_proven=true unless separately proven (G9 path: operator arms the staged plist via
`launchctl load`; overnight receipts verified in a later, separate step).

Brief JSON (additions to the existing brief output; schema extends, does not replace):

```json
{
  "schema": "dharma.sarathi.operator_brief.v1",
  "alive_claim": false,
  "wake_loop_active": false,
  "board_status": "fresh|stale",
  "remote_mesh_status": "missing|blocked|fail|pass",
  "remote_mesh_age_hours": 0,
  "descoped_hosts": [],
  "hosts": {}, "current_cards": [], "next_exact_step": "..."
}
```

(`remote_mesh_status` enum now matches §10 exactly; v1.0 had two different enums in §11 vs
Phase 9.) A matrix `pass` older than 24h is reported as `pass (stale, age=Xh)` and downgrades any
"mesh proven" language.

---

# 12. Host Identity Requirement

Runtime-only `~/.dharma/host_identity.json` per host (never git-tracked), schema
`dharma.host_identity.v1` as in v1.0 (host_id, hostname, kind, role, public_ip, nats_role,
board_role, agent_runtime, last_verified) with two additions:

- `armed_heartbeat: true|false` — set only when the operator has armed an emitter (D3);
- **TTL rule**: any command that consumes `public_ip` (firewall, probes) must check
  `last_verified` ≤ 7 days AND cross-check against a live lookup (§7.0). Stale identity = re-verify
  first.

Host IDs: mac, agni, meghadharma, rushabdev. Do not collide with the existing
`~/.dharma/agents/sarathi/identity.json` (agent identity ≠ host identity; different files,
different schemas). Referenced by: heartbeats, board receipts, matrix rows, secret ledgers.

---

# 13. Heartbeat Requirement

Schema `dharma.heartbeat.v1` as in v1.0 (agent, host_id, timestamp, status, current_card,
last_receipt, nats_connected, board_sha256_seen) with one addition and one rule:

- Addition: `probe` object stating HOW status was derived, e.g.
  `{"kind": "pulse_recency", "pulse_age_seconds": 42}`.
- Rule: **self-reported or container-up/ssh-up liveness is not acceptable for meghadharma** — its
  healthcheck stayed green through a 69-hour main-loop wedge. The meghadharma heartbeat's
  `status` MUST derive from main-loop pulse recency (wedged main loop ⇒ `degraded` even if the
  container is green). ECB-008 owns implementing this probe.

Freshness: fresh if age < 10 minutes; stale otherwise. Emitters are STAGED by agents and ARMED
only by the operator (§3.6, D3). One-shot heartbeats emitted during a matrix run satisfy the
matrix row; they do not make the board `fresh`.

---

# 14. Implementation Phases (REORDERED — board before keys)

The board's own ratified doctrine (three-Hermes council) is "build the shared board first". v1.0
ran the key sync before the board existed, reducing ECB-004 to retroactive paperwork. The
operator-approval latency argument cuts the other way: ASK for D4 approval early (Phase 1), and
by the time it lands the board can receive the work as a real claimed card.

**Phase 1 — Commit curated work + request decisions.**
Commit the two curated files per §1 (guards ON, no `--no-verify`; disposition for the other dirty
files; D6 track mapping requested). Simultaneously put D1 (rushabdev), D2 (agni 8443), D3
(heartbeat arming), D4 (key sync) in front of the operator — see §17. Rollback: `git revert`.

**Phase 2 — Repo-owned ECB board primitive.**
Port + fix per §9.2 (board-root injection, mirror fix, policy-as-data, add-card, version
receipting, wrapper). Tests per §15.4 run against tmp board roots only. Rollback: revert the
commit; the runtime wrapper swap is reversible by restoring the archived runtime `ecb.py`
(archive it, don't delete).

**Phase 3 — Revive the ECB board.**
Amend writer policy per §9.5 (operator-acked `policy_amended` event). Create ECB-004..012 via
`add-card` with receipts (creation, validation, mirror attempt/result, freshness status). Mirror
set: agni + meghadharma (rushabdev per D1). Board report says `board_status=stale (no armed
heartbeat emitters — expected until D3)` until freshness criteria pass honestly. Rollback: cards
can be moved to `rejected` by event; events are append-only — a bad event is corrected by a
superseding event, never by editing history.

**Phase 4 — Key sync to meghadharma (ECB-004).**
Only after D4 approval AND §6.0(a-d). Dry-run → apply → §6.3 verification → receipt + precondition
note. Rollback: remote `.bak` restore (§6.1).

**Phase 5 — agni NATS reload contract (§7.2).** No config mutation before it exists. No restart.

**Phase 6 — Add meghadharma as authenticated NATS spoke (ECB-006).**
1. backup agni config (§7.2); 2. credential lifecycle §7.3 (generate on spoke, hash to hub,
movement receipt); 3. `ufw insert` per §7.4 (order-verified); 4. `nats-server -t` validate;
5. warn operator; 6. `--signal reload=<live-pid>`; 7. verify listener + existing spokes;
8. §7.5 probe (with fallback); 9. §7.6 auth proof positive AND negative. Do not call A2A linked
yet. Rollback: restore config backup + reload; `ufw delete` inserted rule; shred spoke cred.

**Phase 7 — rushabdev decision gate (ECB-005, D1).** Execute D1a/D1b/D1c per §8 with the PSMV
guard. Rollback for D1a: remove the re-added key (return to revoked state).

**Phase 8 — Remote mesh proof (ECB-007).**
Runner + independent checker per §10; `spokes_required` from D1. Evidence committed only if that
matches the repo's evidence-in-git practice for governance matrices (the local matrix's
latest.json is tracked; per-run receipt dirs under reports/a2a stay runtime-only).

**Phase 9 — Sarathi remote operator brief (ECB-010).**
Extend `holon_system/sarathi/brief.py` + gateway per §11; brief lands in the existing
`~/.dharma/agents/sarathi/outbox/`. `alive_claim` stays false; wake-loop arming remains the
operator's `launchctl load` of the already-staged plist, and `wake_loop_active` flips only after
the overnight receipts are verified in a separate later step (G9).

---

# 15. Test Plan (partitioned: CI-runnable vs live probes)

## 15.1 Static (CI)

```bash
bash -n scripts/runtime/sync_agent_keys_to_vps.sh
python -m py_compile dharma_swarm/a2a/board/ecb.py
git diff --check
```

## 15.2 Secret safety grep (CI; extended paths + patterns)

Scan ALL surfaces this build touches — including the ones it creates:

```bash
grep -RInE '(sk-|AKIA|AIza|xoxb-|ghp_|gho_|ghu_|ghs_|nvapi-|-----BEGIN|bcrypt\$|\$2[aby]\$|[A-Z0-9_]*API_KEY=[^[:space:]$]{8,})' \
  scripts/runtime scripts/governance docs/governance docs/ops \
  dharma_swarm/a2a/board tests reports/governance/nats_remote_mesh_matrix 2>/dev/null || true
```

Any hit is manually inspected. NATS credential material (bcrypt hashes included) never enters git.

## 15.3 Helper behavior (live-adjacent; needs a target host or a loopback ssh fixture)

Pin the implemented contract: dry-run writes nothing remotely; apply without `--operator-approved`
fails (exit 3); risky host without `--allow-risky-host` fails (exit 3); apply writes the redacted
ledger with schema §6.2; values never printed; remote-only names preserved; mode 0600;
**remote `.bak.<ts>` created before overwrite**.

## 15.4 Board tests (CI; tmp board root ONLY — never the live board)

- validates a COPY of the real ECB-001..003 board (back-compat: the port must not reject existing
  history);
- `add-card` creates a schema-valid card (all §9.3 fields; event + receipt written);
- receipt attach works; validation passes after each mutation;
- proposal from `meghadharma` accepted once policy includes it; rejected before (allowlist is
  policy-driven);
- mirror: per-host failure isolation (one dead host → `partial` result, other hosts still
  mirrored, NO pass receipt before copy, no exception wedge);
- freshness: stale board marked stale; done-without-receipt fails; expired-lease `doing` fails;
  zero-armed-heartbeats yields `stale` + explicit `armed_heartbeat_hosts=[]`;
- wrapper: runtime wrapper imports the repo module (no second implementation); receipts carry
  `writer_code_sha`.

## 15.5 Remote matrix (LIVE probes — not CI; each produces receipts, ordered)

`meghadharma blocked before firewall` → `reachable after firewall` (order-dependent, one-shot);
`rushabdev per D1`; anonymous + wrong-cred connects REJECTED; cross-host publish/consume rows
pass only on actual receipts; DLQ/retry rows never pass without proof; checker rejects a
tampered/stale evidence file (negative test, CI-runnable against a fixture).

---

# 16. Acceptance Criteria (each names its evidence artifact)

1. Curated files committed (guards passing) — evidence: commit SHA; or staged-only with reason
   recorded in the ECB card.
2. meghadharma key sync approved+verified (receipt path) or explicitly not approved (D4 record).
3. Redacted movement ledger exists for EVERY secret movement, NATS creds included — receipt paths.
4. agni reload contract exists before any config mutation — doc path.
5. `meghadharma_hermes` exists iff meghadharma is connected — agni config structure check + auth rows.
6. agni firewall allows meghadharma:4222 iff intended — intent = D2/D4 decision records; evidence
   = `ufw status numbered` before/after + functional probe receipts.
7. rushabdev is `proven`, `blocked`, or `descoped` — D1 record + verification receipts.
8. ECB board has a repo-owned implementation — package path + wrapper test green.
9. ECB-004..012 exist with full schema — board validate receipt.
10. Board freshness computed honestly (incl. `armed_heartbeat_hosts`) — digest artifact.
11. Remote mesh matrix exists with checker green, or explicitly blocked — latest.json + checker
    output (age ≤ 24h at report time).
12. Sarathi emits only a non-live brief — outbox artifact with `alive_claim:false`.
13. Final report per §18 — path.

---

# 17. Explicit Blockers and Operator Decisions

Blockers (work): agni reload contract missing; matrix runner+checker missing; board port + policy
amendment pending; ECB cards 004-012 not yet created; meghadharma compose loopback patch
UNCOMMITTED (gates Phase 4); litestream replication down (ECB-011).

**Operator decisions (nothing above `configured` happens without them):**

- **D1** rushabdev: restore / descope / defer (§8) — includes the root-SSH-risk acknowledgment.
- **D2** agni posture: close vs ratify public 8443 WSS + broad rushabdev allow (ECB-012).
- **D3** heartbeat arming: operator `launchctl load` / cron-enable of staged emitters (§3.6).
- **D4** key sync approval for meghadharma + named consumer (§6.0d).
- **D5** canonical-writer amendment ack: `writer_delegates` addition (§9.5).
- **D6** track ownership for the new repo surfaces in ACTIVE_TRACK.yaml (§1).

---

# 18. Final Report Format

1. Changed files; 2. Hosts touched; 3. Secrets movement summary (redacted; ledger paths);
4. NATS topology before/after (+ D2 state); 5. Board changes + freshness state (incl.
`armed_heartbeat_hosts`); 6. Remote mesh matrix result **with age and descoped hosts + decision
refs**; 7. Sarathi state; 8. Verification run (checker output); 9. Remaining blockers + open
decisions; 10. Next exact step.

Required truth statements while true: Sarathi is not alive. `wake_loop_active=false`. Remote mesh
is not proven unless the latest matrix passes AND is ≤ 24h old AND the checker is green. Board is
stale unless the freshness gate passes (expected until D3). rushabdev is blocked/descoped per D1,
never silently "back".

---

# 19. Recommended Immediate Next Step

1. Commit the two curated files (guards ON) and put D1-D6 in front of the operator in one
   message — decisions, not status.
2. Build the repo-owned board primitive + ECB-004..012 + freshness gate (Phases 2-3). This gives
   every later agent one canonical place to look before touching VPSes, NATS, keys, or Sarathi.
3. Only then, with D4 + §6.0 satisfied, run the meghadharma key sync as the execution of a
   claimed ECB-004 — receipts attached to the card that authorized it.

Do not jump to Sarathi. Sarathi's brief is only as honest as the truth surfaces underneath it.
