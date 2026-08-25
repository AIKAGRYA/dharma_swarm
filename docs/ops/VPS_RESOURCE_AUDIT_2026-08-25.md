# VPS resource audit — 2026-08-24/25

> **Role:** dated operational report. It replaces no existing document, makes
> no repo-level authority claim, and is subordinate to the deployment package
> and the canonical governance stack.

## Scope and authority

This audit covered the three persistent SSH fleet targets in the operator
inventory: `rushabdev`, `agni`, and `meghadharma`. The retired/dynamic RunPod
entries and the unconfigured `vps3` placeholder were not treated as persistent
VPSes. `meghadharma_cloud` is an alias of `meghadharma`, not a fourth host.
The inventory and hostname command under "Reproduction and verification
commands" is the evidence boundary for that scope.

The authorized mutation scope was resource cleanup and bounded memory control.
No personal mirror data, Docker volume, live application database, SSH policy,
credential, or unrelated failed application unit was deleted or rewritten.

## Live findings

| Host | RAM / swap | Initial root disk | Material finding |
| --- | --- | ---: | --- |
| rushabdev | 4 GiB / 4 GiB | 100%, no usable free blocks | Daily raw SQLite copy filled `/`, left malformed multi-gigabyte partial backups, and never reached retention. |
| agni | 8 GiB / 5 GiB | 84% | Ollama was the dominant memory consumer; journals and old Docker artifacts consumed avoidable disk. |
| meghadharma | 8 GiB / 2 GiB | 77% | A 2026-08-20 global OOM killed a Python process at about 6.8 GiB anonymous RSS; 18.2 GB of images and 5.7 GB of build cache were reported reclaimable. |

These are historical outputs of the fleet snapshot, kernel OOM-history, and
Docker disk-accounting commands below, captured before cleanup. Rerunning them
shows the post-remediation state rather than rewriting the historical result.

At audit time, Rushabdev and Agni had no recent kernel OOM event. Ollama on
Rushabdev/Agni and the four named Meghadharma containers were unbounded; the
root-user Hermes services already had partial service-level limits that were
preserved. `systemd-oomd` was not installed.

## Cleanup performed

- Vacuumed archived journals, cleaned APT caches and age-eligible temporary
  files, and pruned stopped Docker containers plus unused old images/build
  cache. Active containers and every Docker volume were retained.
- Compressed the closed `syslog.1` on each host after proving it had no open
  file descriptor. No log content was discarded by that step.
- Rushabdev: removed only mechanically malformed/zero-byte backup artifacts and
  superseded verified backup generations; retained a verified SQLite keeper,
  the newest valid Hermes archive, and the verified repaired state database.
- Rushabdev: removed six unused, unopened Codex standalone releases while
  retaining the current release and its immediate predecessor. These releases
  are recoverable only by redownload.
- Rushabdev's 36.5 GB `/home/openclaw/dhyana_mirror` was not changed. Similar
  size is not evidence of duplicate identity, so it did not qualify for
  deletion.

Root filesystem use after cleanup was approximately 83% on Rushabdev, 82% on
Agni, and 71% on Meghadharma. The post-cleanup fleet snapshot and Docker volume
inventory commands below verify the retained state.

## Recurrence controls

`scripts/ops/rushabdev_sqlite_backup.sh` replaces the unsafe Rushabdev job. It
uses SQLite's online backup API, checks a free-space reserve before staging,
serializes runs with `flock`, verifies gzip and a bounded restored
`PRAGMA quick_check`, publishes atomically, and performs retention before new
allocation while preserving a verified keeper. A full live run produced final
archives for all three SQLite databases with no partials left behind. A second
independent restore of the largest archive returned `quick_check=ok` for
2,972,508,160 bytes. The deployed backup script matches the repository at
SHA-256 `6cb36d3ebe68cb6f1a4697bcaa27d25436235ad9f787c78becbdddbeafb2d9c9`.
DuckDB is explicitly skipped until a DuckDB-native consistent backup lane
exists.

Implementation evidence: `scripts/ops/rushabdev_sqlite_backup.sh:287`,
`:303`, `:372`, `:448`, `:470`, `:474`, `:492`, `:507`, `:533`, and `:553`;
tests live in `tests/test_rushabdev_sqlite_backup.py`. The full archive check is
also reproducible with the bounded backup commands below.

`deploy/vps-resource-guard/` installs three complementary controls:

1. hard cgroup maxima and reclaim thresholds on named high-memory services or
   exact running container scopes only, with additional per-container swap
   maxima on Meghadharma;
2. a host-bound daemon sampling `MemAvailable` every five seconds, entering
   pressure at 85%, recovering at 78%, and treating 92% as critical; and
3. bounded persistent journald storage (512 MiB, with 2 GiB kept free).

The daemon can restart only exact allowlisted system services, root-user
services, or Docker containers. It has no arbitrary command, PID kill,
`drop_caches`, prune, image, or volume action. It skips candidates below
128 MiB, chooses at most one deterministically, writes an intent receipt before
mutation, enforces per-target and global settling, and stores event receipts
plus five-minute heartbeats in a roughly 10 MiB two-file bound.

This does **not** claim an instantaneous hard 85% ceiling for the entire host.
Kernel allocations, uncapped essential services, and bursts between samples
remain outside any honest userspace guarantee. Enforcement is hard while the
limits are applied to the named, exact current workload cgroups. A Docker scope
replacement creates a bounded lifecycle gap until the five-second reconciler
observes it. Ambiguity-recovery restarts are limited to once per allowlisted
container name per 300 seconds, but this throttle is not a policy-mutation
gate: a new Docker ID or scope `InvocationID` remains eligible for its cap on
the next reconciliation. Reconciler/control-plane availability is not a
continuous hard guarantee. The host-wide threshold is a bounded reaction
policy.

Policy evidence: `deploy/vps-resource-guard/configs/rushabdev.toml:1`,
`deploy/vps-resource-guard/configs/agni.toml:1`,
`deploy/vps-resource-guard/configs/meghadharma.toml:1`, and
`scripts/ops/vps_resource_guard.py:331`, `:489`, `:867`, `:999`, `:1153`, and
`:1180`. The hard-limit values are owned by
`deploy/vps-resource-guard/systemd/target-limits/` and the Meghadharma fixed
allowlist in
`deploy/vps-resource-guard/scripts/reconcile-meghadharma-docker-limits.sh`.

## Live deployment proof

The final package was deployed from the same SHA-256-verified archive
(`64155b402f53d3a9d93384438228660e73eb82617acc21f6eadb783abd4bf8d1`)
to all three hosts. The installed controller on each host matches the repository
at SHA-256
`827c4095649f8a9247e47260baa9ed9c6b015e306fa11e5d7cf66734592bed52`.
Meghadharma's installed reconciler matches at SHA-256
`358ada89d2de755394f1dc8b10f34fd4f69f0823ace5f9b2554516a6eff991d0`.
On 2026-08-25 04:13 UTC:

| Host | Available RAM | Pressure PSI (10s) | Guard | Effective journal use | Root disk |
| --- | ---: | ---: | --- | ---: | ---: |
| rushabdev | 2,383 MiB | 0.00 | active, enabled | 504.2 MiB | 83% |
| agni | 4,212 MiB | 0.00 | active, enabled | 433.0 MiB | 82% |
| meghadharma | 5,287 MiB | 0.00 | active, enabled | 451.6 MiB | 71% |

Every dedicated in-sandbox target probe returned success. The effective
journald configuration loaded the fleet drop-in last, so its 512 MiB cap was
not shadowed by older host configuration. Rushabdev and Agni exposed the exact
service limits documented in the deployment package. Meghadharma exposed the
following live scope postconditions:

| Container | `MemoryHigh` | `MemoryMax` | `MemorySwapMax` |
| --- | ---: | ---: | ---: |
| `dharma-command-backend` | 2 GiB | 2560 MiB | 640 MiB |
| `hermes` | 1500 MiB | 2 GiB | 768 MiB |
| `dharma-swarm` | 768 MiB | 1 GiB | 256 MiB |
| `dharma-command-edge` | 384 MiB | 512 MiB | 192 MiB |

The final five-second Meghadharma reconciler was exercised through its hardest
bounded recovery path. A deliberate, well-formed mutation quarantine for
`dharma-command-edge` caused a restart by the previously verified full Docker
ID, not its mutable name. The full container ID stayed the same while the scope
`InvocationID` changed from `7888e005dbb246448c5227bdd11ef82f` to
`c64e343ce6044f398b410f2b32fb3e94`. The reconciler restored the captured
`infinity/infinity/infinity` inverse on the new exact scope, verified the
readback, pruned the inactive baseline, captured a fresh baseline, cleared the
quarantine, and durably armed one per-name recovery-restart cooldown. In that
same cycle it applied and verified the 384/512/192 MiB policy; the cycle ended
with `Result=success`, `ExecMainStatus=0`, `changed=1`, and `failures=0`. An
immediate second cycle retained the same full ID and `InvocationID`, reported
the scope already capped, and completed with `changed=0`, `failures=0`, proving
that it neither restarted again nor held policy behind the restart throttle.
Final baseline, quarantine, and active cooldown counts were four, zero, and
one. The cooldown is a bounded durable record from this proof and is removed
lazily before the next eligible recovery restart; ordinary reconciliation does
not consult it.

The legacy Compose-managing package was first removed with its own uninstaller;
that legacy removal alone deleted its saved Compose override. The final
scope-only package never creates, edits, or removes Compose or Docker HostConfig
memory settings. Its complete Meghadharma uninstall check and transaction were
then exercised: all four exact live scopes returned to
`infinity/infinity/infinity`, full container IDs were retained, and nine current
managed files plus the whole four-record preinstall generation moved together
to timestamped, root-owned, content-addressed evidence at
`/var/lib/vps-resource-guard/uninstall-evidence-20260824T173116Z-4129529`.
The active preinstall generation was absent afterward. A fresh install captured
four new infinity baselines and reapplied the verified caps; subsequent
in-place upgrades preserved superseded managed bytes in the active evidence
generation.

A separate no-action pressure fixture lowered only temporary threshold and
receipt paths. Each host selected the expected largest eligible target and
reported `dry-run-would-restart`: Hermes on Rushabdev, Ollama on Agni, and the
command backend on Meghadharma. No workload was restarted by this test.

## Residual findings

- Two Rushabdev script copies contain a plaintext bearer credential. Their
  values were not printed or copied into this report. The issuer must
  rotate/revoke the credential; mirror evidence was preserved pending that
  external action.
- Several application/governance units remain failed on the fleet. They were
  not reset merely to make status output green; each needs an owner-specific
  diagnosis unrelated to resource cleanup.
- Meghadharma swap remains substantially occupied despite ample
  `MemAvailable`. Forced swap cycling was not used because it creates an
  avoidable RAM spike and does not prove pressure.
- The Rushabdev backup output is currently `root:root 0700`, which makes its
  predictable publication names safe from untrusted writers. The script does
  not yet enforce that owner/mode invariant for a future custom output path.
  Capacity checks are conservative snapshots; concurrent unrelated disk use or
  database growth can still consume reserve after preflight, so every publish
  remains bounded and fail-closed rather than promising filesystem isolation.
- Docker 29.1.3 treats zero-valued live resource updates as "leave unchanged."
  A controlled compatibility probe therefore left a monotonic HostConfig cap
  on `dharma-command-backend` (2 GiB reservation, 2560 MiB RAM, 3200 MiB
  combined RAM+swap). It is within the installed scope policy and was retained
  as defense in depth. Clearing it would require a separately validated
  container recreation. The failed-attempt baseline was preserved at
  `/var/lib/vps-resource-guard/failed-install-evidence-20260824T153000Z`.
- `dharma-command-backend` is running with zero restarts and no OOM kill, but
  its existing HTTP healthcheck is failing while the application logs repeated
  NATS slow-consumer errors. That application-level fault was not hidden or
  restarted as part of memory remediation.

The secret-count-only, failed-unit, swap, Docker HostConfig, health, and bounded
log-query commands below are the evidence for these residuals; none prints the
credential value.

## Evidence gate for future deletion

Deletion eligibility is treated as a promotion type, not intuition:

```text
Candidate
  + exact path and owner
  + no open references
  + (mechanically corrupt OR reconstructible and superseded)
  + retained verified keeper when custody-bearing
  + pre/post filesystem receipt
  -> Deletable
```

Personal mirrors require the stronger two-pass cross-host manifest and explicit
approval gate. A matching apparent size cannot inhabit `Deletable`.

## Reproduction and verification commands

The narrow local release gate is:

```bash
PYTHON_BIN=/Users/dhyana/dharma_swarm/.venv/bin/python \
  deploy/vps-resource-guard/tests/test_installers.sh
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q \
  tests/test_vps_resource_guard.py tests/test_rushabdev_sqlite_backup.py
/Users/dhyana/dharma_swarm/.venv/bin/python -m ruff check \
  scripts/ops/vps_resource_guard.py tests/test_vps_resource_guard.py \
  tests/test_rushabdev_sqlite_backup.py
```

Fleet inventory and historical/current resource snapshots:

```bash
for host in rushabdev agni meghadharma; do
  ssh "$host" 'hostname; date -u; free -m; df -h /; \
    head -n 1 /proc/pressure/memory; journalctl --disk-usage'
done
ssh meghadharma 'journalctl -k --since "2026-08-20 00:00:00" \
  --until "2026-08-21 00:00:00" --no-pager | \
  grep -E "Out of memory|Killed process"'
for host in rushabdev agni meghadharma; do
  ssh "$host" 'docker system df 2>/dev/null || true; docker volume ls'
done
```

Each live host was checked with `systemctl show`, `free -m`, `df -h /`, the
first `/proc/pressure/memory` sample, `journalctl --disk-usage`, and SHA-256
readback of its installed files. The sandbox-equivalent target probe can be
repeated without restarting a workload:

```bash
systemctl start vps-resource-guard-self-test.service
systemctl show vps-resource-guard-self-test.service \
  -p Result -p ExecMainStatus
```

The final policy and the remaining application-level findings are inspectable
without printing process environments:

```bash
ssh rushabdev 'sha256sum /etc/vps-resource-guard/config.toml \
  /usr/local/lib/vps-resource-guard/vps_resource_guard.py \
  /root/rushabdev/ops/backup.sh; stat -c "%U:%G %a %n" \
  /root/rushabdev/backups/sqlite; systemctl --failed --no-pager; free -m'
ssh agni 'sha256sum /etc/vps-resource-guard/config.toml \
  /usr/local/lib/vps-resource-guard/vps_resource_guard.py; \
  systemctl --failed --no-pager; free -m'
ssh meghadharma 'docker inspect --format \
  "{{.Name}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} \
  restarts={{.RestartCount}} oom={{.State.OOMKilled}} \
  reservation={{.HostConfig.MemoryReservation}} memory={{.HostConfig.Memory}} \
  memory_swap={{.HostConfig.MemorySwap}}" dharma-command-backend hermes \
  dharma-swarm dharma-command-edge; free -m; systemctl --failed --no-pager'
ssh meghadharma 'docker logs --since 30m dharma-command-backend 2>&1 | \
  grep -E "slow consumer|health" | tail -n 30'
ssh rushabdev 'rg -l -i "authorization:[[:space:]]*bearer|bearer[_ -]?token" \
  /root/rushabdev /home/openclaw 2>/dev/null | wc -l'
```

The largest published backup can be independently restored and checked in its
own bounded filesystem namespace:

```bash
ssh rushabdev 'set -euo pipefail
backup_dir=/root/rushabdev/backups/sqlite
archive=$backup_dir/db_markets.db__256300041--20260824T173358Z--3487790.sqlite3.gz
reserve_bytes=1073741824
margin_bytes=1048576
gzip -t "$archive"
free_bytes=$(df --output=avail -B1 "$backup_dir" | awk "NR == 2 { print \$1 }")
(( free_bytes > reserve_bytes + margin_bytes ))
limit_bytes=$((free_bytes - reserve_bytes - margin_bytes))
limit_kib=$((limit_bytes / 1024))
(( limit_kib > 0 ))
verify_path=$(mktemp -p "$backup_dir" .verify-markets.XXXXXX.partial)
trap '\''[[ -z ${verify_path:-} ]] || rm -f -- "$verify_path"'\'' EXIT HUP INT TERM
(ulimit -f "$limit_kib"; gzip -dc -- "$archive" > "$verify_path")
(( $(stat -c %s "$verify_path") <= limit_bytes ))
sqlite3 -batch -readonly "$verify_path" "PRAGMA quick_check(1);"
rm -f -- "$verify_path"
verify_path=
find "$backup_dir" -maxdepth 1 -type f -name "*.partial" -print'
```

That exact archive name is an audit witness and may age out under the seven-day
retention policy. Afterward, use the newest verified `db_markets` archive with
the same reserve and decompression bound rather than weakening the procedure.
