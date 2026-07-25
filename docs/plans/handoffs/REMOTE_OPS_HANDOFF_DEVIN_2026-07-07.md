# Remote Operations Handoff — Devin 24/7 (2026-07-07)

**Role:** working_plan (per docs/AGENTS.md). Not authority.
**Authority owners:** `docs/governance/ACTIVE_TRACK.yaml`, `docs/ops/RUNBOOK.md` §3e,
`docs/ops/A2A_QUICKSTART.md`, `docs/ops/DEVIN_NATS_PR_JANITOR_PLAYBOOK.md`,
`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`.
**Context:** the operator is walking the length of Japan and moving the entire
operation remote. The Mac demotes to an untouched dev seat; everything that
matters must run on the VPS fleet + GitHub + Devin cloud sessions, operable
from a phone.

---

## Part 1 — Operator pre-departure checklist (phone-doable)

### A. Access (do these before losing the Mac)

- [ ] **GitHub mobile app** signed in with admin rights on
      `AmitabhainArunachala/dharma_swarm` (merge, Actions dispatch, secrets,
      deploy keys are all phone-doable).
- [ ] **Devin webapp** login works on the phone (app.devin.ai) — this is the
      24/7 hands; every session below can be started from chat.
- [ ] **SSH from phone** (Termius/Blink or provider web console) to each VPS,
      OR confirm each provider's browser console works as fallback.
- [ ] **Provider consoles** (DigitalOcean/Hetzner) reachable from phone for
      reboot/resize/console access.
- [ ] Record the three VPS hosts + roles somewhere Devin can read (Devin
      knowledge note or `!secrets`): AGNI NATS hub (`157.245.193.15`),
      rushabdev, and the daemon/third box (maharaja or the new droplet from
      RUNBOOK §3e). Devin currently only has the AGNI address from the repo.

### B. Devin credential wiring (the actual 24/7 unlock)

- [ ] Confirm Devin org secrets exist: `DEVIN_NATS_URL`, `DEVIN_NATS_USER`,
      `DEVIN_NATS_PW` (playbook says installed — verify, don't assume).
- [ ] Add **read-only SSH keys** for the three VPSes as Devin secrets
      (e.g. `DHARMA_VPS_AGNI_SSH_KEY`, `DHARMA_VPS_RUSHABDEV_SSH_KEY`,
      `DHARMA_VPS_DAEMON_SSH_KEY`) + host/user strings. Dedicated
      `devin` unix user per box, not root, is the right shape.
- [ ] GitHub Actions repo secrets for the Mike lane:
      `MERGE_MASTER_MIKE_NATS_URL/USER/PW` (+ `DEVIN_NATS_CA_PEM` if AGNI
      still presents the self-signed cert).
- [ ] Provision `DOCOPS_RECONCILE_TOKEN` (fine-grained PAT, contents:write,
      ruleset bypass) — kills the `[skip ci]` bot-PR stall we hit today
      (docops-reconcile-main.yml Tier 1).

### C. Daemon VPS goes live (RUNBOOK §3e — the one operator-gated item)

- [ ] Create the droplet (Hetzner CX22 / DO 4GB, Ubuntu 24.04) with
      `scripts/ops/vps_cloud_init.yaml` as user-data. Phone-doable.
- [ ] Add the printed read-only deploy key to the repo (GitHub mobile:
      Settings → Deploy keys).
- [ ] One SSH session: create `/root/dharma.env` from `.env.example`
      (≥1 provider lane live; optional `LITESTREAM_*`, `DEVIN_NATS_*`),
      then `bash /root/dharma_bootstrap.sh`.
- [ ] Felt-proof: `docker compose exec swarm dgc spine tail --limit 5`
      shows receipts; `curl -s localhost:7433/health` OK.
- [ ] Set `LITESTREAM_*` so `runtime.db` replicates off-box (any
      S3-compatible target). Without this the organism's memory has a
      single point of failure while you're on foot.
- [ ] Unload the Mac daemon (`make stop`) once the VPS reads LIVE
      (`make orient` from any checkout / cockpit `spine.pulse`).
      This closes organism-rewire D1 and unblocks Loop-1 CLOSED_LIVE.

### D. Merge lane runs without you (Mike, per merge-master-mike-d4 track)

- [ ] Bot PRs already auto-merge. For human/agent PRs while remote, either
      merge from GitHub mobile, or comment `@mix_master_mike merge when clean`
      on a PR — the deterministic gate does the rest, and it never weakens
      checks.
- [ ] Optional: run **Actions → merge-master-mike-backlog** (packet-only
      first) on a cadence; requires the Mike NATS secrets from B.

### E. 24/7 Devin presence

- [ ] Approve a **Devin scheduled automation**: a periodic "fleet janitor"
      session (e.g. every 6–12 h) that runs the handoff prompt in Part 3 —
      checks CI/PR queue, spine pulse via NATS, VPS health via SSH, and
      messages you ONLY when something needs an operator act. Devin can set
      this up; it needs your one-time approval.
- [ ] Message Devin from the phone anytime for ad-hoc work; sessions are
      the on-demand hands, the automation is the heartbeat.

---

## Part 2 — Standing constraints for any remote agent

- Devin's authority stays `external_worker_evidence_only`: never merge,
  approve, push to main, mutate protected sources, or bypass governance.
- Never weaken a gate, ratchet, or the One Wire quorum to unblock anything.
- No credentials in commits, comments, or docs; secrets live in Devin/GitHub
  secret stores only.
- No world-facing efferent actions (posts, outreach, trades) — afferent
  ingest and repo work only, per the Inward Ascent doctrine.
- On the VPSes: read/diagnose freely; restarts of the dharma compose stack
  are OK; destructive acts (data deletion, key rotation, provider console
  changes) are operator-only — message and wait.
- AGNI hub box hosts fleet transport ONLY — never co-locate the daemon or
  experiments there (RUNBOOK §3e note).

---

## Part 3 — Handoff prompt (paste into a fresh Devin session / automation)

```text
You are the remote-operations janitor for AmitabhainArunachala/dharma_swarm
while the operator (John/Dhyana) walks the length of Japan with phone-only
access. Authority: external_worker_evidence_only — you never merge, approve,
push to main, weaken a gate, or touch credentials. Evidence discipline: every
claim = a command run this session; anything unverifiable is UNKNOWN.

Read first: docs/plans/handoffs/REMOTE_OPS_HANDOFF_DEVIN_2026-07-07.md, then
run `make onboard` and trust its output over any doc.

Each cycle:
1. REPO PULSE — `make onboard`; `make pr-queue` (or gh pr list); note failing
   CI on main, stalled green PRs, bot PRs stuck without checks (docops
   autorefresh PRs carry [skip ci] — retrigger with an empty commit if
   DOCOPS_RECONCILE_TOKEN is still unprovisioned).
2. FLEET PULSE — `make a2a-status` against the AGNI hub (needs DEVIN_NATS_PW
   secret; WSS can take 40–90s in sandboxes, don't misread a slow connect as
   down). Publish a session heartbeat to dharma.a2a.fleet. Check
   roaming_mailbox/tasks/ for queued work addressed to devin-roaming-2987d222.
3. VPS PULSE — if SSH secrets are provisioned, for each of the three boxes:
   uptime, disk (df -h), docker compose ps; on the daemon box additionally
   `docker compose exec swarm dgc spine tail --limit 5` and
   `curl -s localhost:7433/health`. Restart the compose stack if unhealthy;
   anything destructive → message the operator instead.
4. MERGE LANE — for clean green PRs, prepare packets (`make pr-packet PR=n`,
   `make pr-gate PR=n`) and post recommendations; merging stays with Mike
   (@mix_master_mike merge when clean) or the operator from GitHub mobile.
5. REPORT — write a dated receipt under reports/a2a/ or the packet dir.
   Message the operator ONLY for: main broken >1h, a VPS down or disk >90%,
   a security-relevant finding, or an operator-gated decision. Otherwise
   stay silent and leave the receipt.

Escalation: if a required secret is missing, name it exactly, request it via
the secrets flow, and continue with everything that doesn't need it.
```

---

## Part 4 — Recommendations (beyond the minimum)

1. **Litestream first.** Off-box replication of `runtime.db` is the single
   highest-leverage act before travel — everything else is recoverable from
   git; the organism's runtime memory is not.
2. **DOCOPS_RECONCILE_TOKEN** — small act, removes the one merge-queue stall
   class observed today (bot PRs with `[skip ci]` never getting checks).
3. **Uptime alerting without new infra:** a tiny GitHub Actions cron that
   curls the daemon's `/health` through an SSH tunnel or a public
   health endpoint, failing red on the repo — you'll see it in GitHub mobile
   notifications. Alternative: UptimeRobot on a public health port.
4. **Public TLS on AGNI** (Let's Encrypt on the WSS endpoint) eventually
   retires the CA-PEM secret shuffle across every consumer.
5. **Keep the Mac out of the loop entirely.** Anything only the Mac can do
   is a defect now — file it as a broken-register item rather than working
   around it from the trail.
6. **One Devin knowledge note** with the three VPS hosts/roles/users, so
   every future session starts with the fleet map without you retyping it.
