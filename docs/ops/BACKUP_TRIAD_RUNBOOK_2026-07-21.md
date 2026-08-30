# Backup Triad Runbook — 2026-07-21

Lane C prep. Docs-only: no values, credential NAMES and placeholders only. Machine-local artifacts (ready plist, Mac litestream config, per-host drill scripts) live in the operator packet `~/handoffs/2026-07-21_backup_triad/` on the Mac.

## Why this exists (verified 2026-07-21, read-only)

The estate's three truth-store hosts each had a backup that could not survive its own disk:

| Host | Store | Today's "backup" | Flaw |
|------|-------|------------------|------|
| meghadharma | `dharma_swarm_dharma-state` volume → `/data/state/runtime.db` | `dharma-litestream` container → `LITESTREAM_REPLICA_URL=file:///backups/runtime-db` | Replica on the SAME `/dev/vda1` as the data; S3 env names present but empty |
| meghadharma | `dharma_command_state` volume | `dharma-command-backup.timer` every 15 min → `/opt/dharma-command-node/backups/state-*.tar.gz`, keeps 48 (~12h) | Same disk, ~12h retention, different volume than runtime.db |
| Mac (M5) | `~/.dharma/state/runtime.db` (479MB live), `~/.dharma/ontology.db` (102MB) | Time Machine | FAILING: Error 18, destination 'Extreme SSD' unmounted; litestream not installed |
| rushabdev | `/home/openclaw/dhyana_mirror` (35G, incl. PSMV) | none off-box | Mirror pull to Mac `~/vps_mirrors/` started 2026-07-21 (in progress) |

Additional fragility found on megha: the running `dharma-litestream` container carries a `/root/backups/litestream:/backups:rw` bind that is NOT in the on-disk compose file (checkout clean at `88458e06f`). A plain `docker compose --profile vps up -d litestream` recreate drops the bind and the `file://` replica silently lands in the container overlay — lost on next recreate. The off-host flip removes this class of failure; a local file replica, if kept, must be persisted via `docker-compose.override.yml`.

## The triad

### Leg 1 — megha litestream → off-host object store

Interface already exists end-to-end: compose passes `LITESTREAM_REPLICA_URL` / `LITESTREAM_ACCESS_KEY_ID` / `LITESTREAM_SECRET_ACCESS_KEY` from `/root/dharma_swarm/.env` into the container; `scripts/ops/litestream.yml` replicates `/data/state/runtime.db` (sync 60s / snapshot 6h / retention 168h). No object-store credentials exist anywhere in the estate key store yet (names audited 2026-07-21) — operator must create a bucket + key pair.

Flip (3 lines in megha's `.env`, values never committed):

```
LITESTREAM_REPLICA_URL=s3://<bucket>/megha-runtime-db
# S3-compatible endpoints embed the host: s3://<bucket>.sgp1.digitaloceanspaces.com/megha-runtime-db
LITESTREAM_ACCESS_KEY_ID=<value>
LITESTREAM_SECRET_ACCESS_KEY=<value>
```

Deploy: `cd /root/dharma_swarm && docker compose --profile vps up -d litestream`.
Verify: `docker logs --since 5m dharma-litestream` (replica type=s3, no auth errors), then `docker exec dharma-litestream litestream snapshots -config /etc/litestream.yml /data/state/runtime.db`.
Rollback: restore `.env` backup + same `up -d` (file-replica rollback additionally requires the override-file bind — see packet).

Optional hardening (proposable as a follow-up PR): second replica entry `url: file:///backups/runtime-db` in `scripts/ops/litestream.yml` for an on-box copy alongside off-host.

### Leg 2 — Mac litestream fallback (until Time Machine is repaired)

`brew install litestream`; config at `~/.dharma/litestream-mac.yml` (NOT inside the repo checkout — background automation switches branches in `~/dharma_swarm`, so launchd must never point at a repo path; the existing `scripts/com.dhyana.litestream.plist` has exactly that flaw). LaunchAgent `com.dharma.litestream-mac` replicates `runtime.db` + `ontology.db` to `~/Backups/litestream/` immediately and to `s3://<bucket>/mac-*-db` once the same credential pair lands via `dkeys add`. The agent sources `~/.dharma/agent_keys.env` at start — no secrets in the plist. Ready-to-copy plist + config: packet files `com.dharma.litestream-mac.plist`, `litestream-mac.yml`.

Precondition check: both DBs must be in WAL mode (`sqlite3 -readonly <db> "PRAGMA journal_mode;"`); flipping a non-WAL live DB is operator-gated.

Time Machine itself: physical operator action — remount 'Extreme SSD' or choose a new destination (packet `tm_repair.md`).

### Leg 3 — cross-host mirrors + restore drills

- `rushabdev:/home/openclaw/dhyana_mirror` → Mac `~/vps_mirrors/rushabdev_dhyana_mirror/` and megha backups/rsi-lab → `~/vps_mirrors/meghadharma_20260721/` (pulls running since 2026-07-21). Do not delete the rushabdev mirror before PSMV is off and checksummed.
- Drills (packet `restore_drill.md`, run after each leg deploys, then monthly): megha litestream restore to `/tmp` + `PRAGMA integrity_check` (python3 stdlib — no sqlite3 CLI on megha), megha tar-lane list check, Mac litestream restore of both DBs, off-box restore of the megha bucket FROM the Mac (the real point), and PSMV mirror rsync-dry-run + random-file checksum. PASS criteria are written per drill. A backup that has never been restored is a hypothesis.

## Order of operations

1. Operator: create bucket + key pair; `dkeys add` the two `LITESTREAM_*` names on the Mac.
2. Leg 1 flip on megha; verify; run megha drill (on-box and from the Mac).
3. Leg 2 deploy on Mac; verify; run Mac drill.
4. Leg 3: confirm mirror pulls complete; run mirror spot-check; schedule monthly drills.
5. Operator: TM repair (physical).

## Receipts (2026-07-21, read-only over ssh)

- `docker inspect dharma-litestream`: litestream/litestream:0.3.13, started 2026-07-21T12:18:26Z, env `LITESTREAM_REPLICA_URL=file:///backups/runtime-db`, S3 keys empty, binds incl. `/root/backups/litestream:/backups:rw` (not in compose).
- Replica live: `/root/backups/litestream/runtime-db/generations/3c929681a4938c91/{snapshots,wal}`, 34M.
- `systemctl list-timers`: `dharma-command-backup.timer` next-elapse 15-min cadence; service tars `dharma_command_state` via alpine, retention 48 files.
- `/dev/vda1` 116G, 42% used — data and both "backups" co-resident.
- megha checkout `88458e06f` = origin/main tip, `git status` clean.
- Mac: `litestream` absent, 'Extreme SSD' unmounted, `runtime.db` 479MB (live), `ontology.db` 102MB.
