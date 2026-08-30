# VPS resource guard

This package bounds the fleet's known high-memory workloads and provides a
second, reactive host-pressure control. Its guarantees are deliberately scoped:

1. systemd `MemoryMax` is a hard cgroup allocation limit for each named system
   service, root user service, and exact running Docker scope. `MemoryHigh` is
   a reclaim/throttling threshold, not a kill threshold. `MemorySwapMax` bounds
   additional swap use by each protected container.
2. `vps-resource-guard` samples Linux `MemAvailable` every five seconds. At 85%
   global use it enters pressure mode, remains armed until use recovers to 78%,
   and labels 92% critical. It can restart at most one explicit allowlisted
   target per cycle, with a five-minute per-target cooldown.

The package cannot guarantee an instantaneous 85% ceiling for total host
memory: kernel memory, system services outside the named cgroups, and a burst
between samples remain outside that claim. It does provide hard limits for the
named workloads and a bounded-action policy on a five-second poll cadence.

## Shipped limits

| Host | Scope | Reclaim threshold | RAM maximum | Swap maximum |
| --- | --- | ---: | ---: | ---: |
| rushabdev | `ollama.service` | 640M | 800M | inherited |
| rushabdev | root `hermes-gateway.service` | 800M | 1200M | inherited |
| rushabdev | root `openclaw-gateway.service` | 512M | 768M | inherited |
| agni | `ollama.service` | 4G | 5G | inherited |
| agni | root `hermes-gateway.service` | 1500M | 2G | inherited |
| meghadharma | `dharma-command-backend` container scope | 2G | 2560M | 640M |
| meghadharma | `hermes` container scope | 1500M | 2G | 768M |
| meghadharma | `dharma-swarm` container scope | 768M | 1G | 256M |
| meghadharma | `dharma-command-edge` container scope | 384M | 512M | 192M |

These maxima were selected above the observed current and peak working sets in
the 2026-08-24 fleet audit. The installer rechecks current and peak RAM and swap
and refuses a hard limit without at least 128 MiB of headroom.

The reactive restart allowlist contains Ollama plus the named root Hermes and
OpenClaw user services on Rushabdev/Agni, and the four named containers on
Meghadharma. All candidates have equal priority, so the largest observed
working set is shed first. A candidate reporting less than 128 MiB
is skipped, preventing a restart of an idle target that cannot materially
relieve pressure. On Meghadharma equal-priority candidates are ordered by
largest observed memory use, with the stable target ID as the tie-breaker.

## Safety and evidence contract

The configuration grammar accepts exactly three actions: `systemd-restart`
for an explicit system `.service`, `systemd-user-restart` for an explicit root
user `.service`, and `docker-restart` for an explicit container name. There is
no shell action, arbitrary PID kill, `drop_caches`, Docker
prune, image deletion, volume action, or wildcard target. Unknown fields,
malformed TOML, an unexpected hostname, unavailable targets, and untrusted
cooldown state fail closed.

Pressure transitions, decisions/actions, errors, and a bounded five-minute
heartbeat append JSON receipts to
`/var/log/vps-resource-guard/receipts.jsonl`. It includes the global sample,
candidate observations, deterministic decision, and action result. The file
rotates at 5 MiB and retains one rotated generation, bounding both files to
at most roughly 10 MiB. Cooldowns and hysteresis survive daemon restarts in
`/var/lib/vps-resource-guard/state.json`. File contents and namespace changes
are fsynced before they are treated as durable, and a process-wide lock prevents
a manually launched second controller from racing the systemd instance.

The separate, non-enabled `vps-resource-guard-self-test.service` runs the
read-only `--self-test-targets` check during installation or on explicit
operator request. It verifies the exact expected hostname and queries every
configured target from the same private-network and inaccessible-home-directory
sandbox used by the daemon, without creating a boot-time readiness dependency.
On Docker hosts, both units pin
`DOCKER_HOST=unix:///run/docker.sock` and use an empty private runtime
directory as `DOCKER_CONFIG`.

## Validate and install

Run from the repository checkout with Python 3.11 or newer:

```bash
python3 scripts/ops/vps_resource_guard.py \
  --config deploy/vps-resource-guard/configs/rushabdev.toml \
  --validate-config
sudo deploy/vps-resource-guard/install.sh --host rushabdev --dry-run
sudo deploy/vps-resource-guard/install.sh --host rushabdev
```

Replace `rushabdev` with `agni` or `meghadharma` on those hosts. A live install:

- stages and validates every payload before replacing a managed file;
- verifies the selected policy's exact hostname and reads every target;
- saves preexisting file collisions and effective runtime limits under
  `/var/lib/vps-resource-guard/preinstall`;
- content-addresses any differing managed file before an in-place upgrade, so
  operator edits or the prior package bytes are retained inside that same
  restore generation;
- rolls back files, service state, and systemd properties, including container
  scope properties only for the exact captured container ID and systemd scope
  `InvocationID`;
- installs persistent system and root-user service drop-ins without restarting the
  guarded workloads, then applies the same properties live with
  `systemctl set-property --runtime`;
- enables the persistent journal bound, restarts journald, and vacuums old
  journal segments to 512 MiB; and
- runs the dedicated read-only in-sandbox target self-test, then restarts and
  verifies the guard; and
- on Meghadharma, enables the fixed-allowlist Docker scope reconciler timer.

An older Meghadharma release briefly managed a Compose override. This installer
detects that legacy preinstall record and refuses an in-place upgrade; run the
older package's uninstaller first so it can remove its own override, then install
this scope-only release. Docker HostConfig memory fields remain untouched. This
package never creates, edits, or removes a Compose file or writes Compose memory
fields. Container limits exist only as reversible runtime properties on the
exact systemd scope incarnation.

The journal vacuum is authorized cleanup and is the one non-transactional
effect: configuration can be rolled back, but deleted historical journal
segments cannot be recreated.

Inspect the deployed control and repeat the exact unit-context read-only probe:

```bash
systemctl status --no-pager vps-resource-guard.service
systemctl restart vps-resource-guard-self-test.service
systemctl show vps-resource-guard-self-test.service -p Result -p ExecMainStatus
journalctl -u vps-resource-guard-self-test.service -n 30 --no-pager
```

On Rushabdev or Agni, inspect named service caps with:

```bash
systemctl show ollama.service -p MemoryCurrent -p MemoryHigh -p MemoryMax
XDG_RUNTIME_DIR=/run/user/0 systemctl --user show hermes-gateway.service \
  -p MemoryCurrent -p MemoryHigh -p MemoryMax
```

On Meghadharma, resolve a container's exact systemd scope and inspect its live
limits with:

```bash
container_id="$(docker inspect --format '{{.Id}}' dharma-command-backend)"
systemctl show "docker-${container_id}.scope" \
  -p MemoryCurrent -p MemoryHigh -p MemoryMax \
  -p MemorySwapCurrent -p MemorySwapMax
```

The live scope properties disappear when Docker restarts or recreates a
container. Meghadharma therefore runs a fixed-allowlist reconciler every five
seconds. It resolves only the four names above to their exact active
`docker-<full-id>.scope`. Before the first mutation of each scope incarnation,
it durably records that scope's original limits keyed by both the full Docker ID
and systemd `InvocationID`; only then does it apply and verify `MemoryHigh`,
`MemoryMax`, and `MemorySwapMax`. Records for captured incarnations remain while
their exact scopes are active; records are pruned only after the recorded scope
is proven inactive. Interrupted-write temporary files are cleaned under the
same operation lock, so restart churn and failed writes do not create an
unbounded active evidence namespace.

Ordinary reconciliation does not restart containers. If the full Docker ID or
scope `InvocationID` changes across the narrow baseline/mutation boundary, the
result is identity-ambiguous. Before every property mutation the reconciler
fsyncs a quarantine record containing the trusted pre-mutation inverse. It may
then restart only the exact captured full Docker ID, resolves the resulting
exact live scope, explicitly restores the inverse properties, verifies both
identity and all three property readbacks, and only then clears the quarantine.
If any recovery step fails, later cycles refuse a new baseline and retry the
quarantined identity instead of canonizing uncertain values. Automatic
exact-ID restart retries are durably limited to once per allowlisted container
name per five minutes, while an operator-held restore transaction retains one
immediate attempt. The throttle is consulted only before that recovery restart;
ordinary policy mutation remains eligible on a new Docker ID or scope
`InvocationID`. Unrelated
allowlisted containers continue to reconcile and the cycle reports partial
failure. If the captured Docker ID is absent and its exact recorded scope is
proven inactive, the quarantine is retained as non-live evidence and no longer
blocks a newly created ID. A recovered scope is durably baselined before policy
can be applied again. This path does not select by a mutable name and does not
change Compose or Docker HostConfig. The reconciler cannot create containers,
prune data, or touch volumes. It refuses a cap without 128 MiB of current/peak
RAM and swap headroom.

## Uninstall

```bash
sudo deploy/vps-resource-guard/uninstall.sh --host rushabdev --dry-run
sudo deploy/vps-resource-guard/uninstall.sh
```

The live uninstaller derives the host policy from the root-owned saved record,
prevalidates the complete restore contract before stopping anything, and
restores every backed-up collision and validated preinstall systemd property.
Its baseline check is read-only: a pending mutation quarantine or interrupted
baseline temporary aborts before the uninstall transaction begins. Before
replacing any managed path, the uninstaller also content-addresses its current
bytes inside the generation, preventing post-install operator edits from being
silently discarded.
For a live container it requires and restores the baseline for the exact current
Docker ID plus scope `InvocationID`; it fails closed rather than reporting
success with an unrestored or stale scope. A stopped or absent container has no
live scope to restore. Scope baselines live inside the root-owned preinstall
generation, so a successful uninstall rotates the file/property inverse and
every scope inverse together with one same-filesystem rename into timestamped
evidence. The active baseline namespace is therefore empty for a later fresh
install, which must capture fresh administrator settings; a true in-place
reinstall continues to use the active generation. Per-incarnation scope
evidence, state, receipts, and that installation's restore evidence remain by
default; `--purge` explicitly deletes them. Empty coordination lock inodes may
remain so a concurrent or later operator can never acquire a different lock
namespace during cleanup.
Journal history removed during installation cannot be restored.
