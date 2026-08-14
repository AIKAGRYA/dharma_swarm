---
title: Fleet Logical Filesystem and Truth Architecture
date: 2026-08-14
status: PROPOSED REFERENCE
---

# Fleet Logical Filesystem and Truth Architecture

## Document role and authority boundary

**Document class:** `reference` and proposed target architecture. This document
owns no live state, grants no deployment authority, and is not an active-track
declaration. It replaces no existing owner. It consolidates an end-to-end answer
to one question: how the operator Mac and the three known VPS aliases can expose
the same logical files and the same state of truth without storing every byte on
every machine.

The owners remain:

- build intent: `docs/governance/ACTIVE_TRACK.yaml`;
- declared surfaces: `ACTIVE_SURFACE_MANIFEST.yaml`;
- live state: owner-specific probes and the live-state owner selected through
  the document hierarchy (`docs/AGENTS.md:13-27`);
- runtime rows, receipts, and idempotency: `dharma_swarm/runtime_state.py` and
  the spine modules (`docs/governance/SWARM_GENOME.md:59-81`);
- internal fleet delivery: `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`;
- document ownership: the hierarchy named by `docs/AGENTS.md:13-27`.

This file is subordinate to those owners. If a live probe, owner file, or
ratified decision contradicts this proposal, the owner wins and this reference
must be revised. That keeps this file within the narrower reference role
required by `docs/AGENTS.md:13-49`.

Words such as **must**, **required**, **forbidden**, and **acceptance** below
define the proposed design's safety boundary. They are not present-tense fleet
commands. They become binding only if an existing owner adopts the relevant
slice through its normal track/ADR/change process.

## Recommended answer

Do **not** build a four-way writable filesystem mirror.

Build one **logical namespace** whose objects are materialized selectively:

1. Git and immutable releases own code identity.
2. One writer per mutable state surface owns transactional truth.
3. A versioned, content-addressed object store preserves large immutable byte
   identity and durability; manifest publication decides fleet membership.
4. A small generation manifest maps logical paths to object digests.
5. NATS JetStream carries bounded commands, events, receipts, and object
   references; it does not carry the whole filesystem or become a second state
   database.
6. Each node keeps only its role-required pins plus a quota-limited disposable
   cache.
7. Secrets, virtual environments, logs, temporary files, model caches, live
   databases, WAL files, and worktrees remain node-local.

The fleet publishes one desired coordinate and each node reports its own
convergence against it:

```text
FleetCoordinate = {
  desired_release_manifest_sha256,
  source_commit,
  authority_registry_generation,
  surface_positions: {       # one entry per mutable owner surface
    <surface>: {
      authority_epoch,
      required_revision,     # owner-assigned durable mutation revision
      owner_schema_version
    }
  },
  manifest_root_sha256,      # immutable logical-path -> blob closure
}

NodeCoordinate = {
  node_uid,
  fleet_coordinate_digest,
  observed_surface_revisions,
  secret_bundle_generation,  # identity only; never secret material
  node_profile_version,
  pin_set_digest,
  selected_platform_runtime_sha256
}
```

The fleet coordinate is a target; node coordinates legitimately differ by
profile, secret bundle, pin set, and projection lag. A node is converged when
it matches the release, authority epochs, and manifest root, and each observed
surface revision meets the required revision or carries an allowed-staleness
state. This does **not** imply byte-identical disks, virtual environments,
caches, logs, or database files. Broker delivery positions remain transport
metadata and never substitute for an owner surface revision.

## 1. Problem statement

The phrase "same filesystem and same state of truth" hides several different
requirements:

- the same path should name the same published artifact;
- every node should run the same admitted desired release identity, selecting
  only its allowed platform runtime;
- every node should know which owner controls each mutable record;
- a small node should fetch a large artifact when needed without retaining the
  full archive;
- an offline node should remain useful without becoming a second writer;
- a failed primary should be recoverable without allowing two primaries;
- a cache, backup, receipt, or peer consensus should never acquire authority
  merely because it contains plausible or newer-looking data.

A symmetric home-directory mirror cannot satisfy those requirements. It copies
authority and garbage together: live SQLite/WAL, caches, worktrees, logs,
downloads, local secrets, and backups all become peers. A conflict file detects
split brain only after it has happened. A full mirror also scales storage cost
with the largest host rather than the smallest host.

The target is therefore **location-transparent reading with explicit writing
authority**, not distributed POSIX multi-writer semantics.

## 2. Evidence baseline and epistemic labels

Every baseline statement below separates evidence grade from runtime authority:

- **DECLARED:** stated by the named owner document; not necessarily deployed;
- **IMPLEMENTED:** present in executable/configuration code at the pinned
  commit; not necessarily invoked successfully in the live fleet;
- **OBSERVED:** raw command output preserved by a dated witness;
- **REPORTED:** present in dated documentation, not freshly reproduced;
- **INFERRED:** conclusion from static evidence, awaiting a runtime test;
- **PROPOSED:** target behavior in this reference, not current behavior.

Neither executable code nor a signed report acquires a mutation authority merely
from its evidence grade.

### 2.1 Static support at the inspected commit

The source citations below were inspected in a clean checkout at
`de52bef55adcbb9193c839288b7bb827eb1176b8`. Reproduce the historical source
with `git show de52bef55adcbb9193c839288b7bb827eb1176b8:<path>`; re-audit line
pointers after later commits.

| Claim | Evidence grade | Evidence and falsifier |
|---|---|---|
| Runtime truth is a WAL-backed SQLite store explicitly scoped to single-host orchestration. | DECLARED + IMPLEMENTED | `dharma_swarm/runtime_state.py:1-6,30,437-454,1209-1218`. Falsified by a newer runtime owner implementing and enforcing cross-host transactional semantics. |
| Filesystem and SQLite A2A surfaces are compatibility/audit mirrors, not live delivery, ordering, or retry authority. | DECLARED | `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:19-46,306-319`. |
| Exact immutable Git release admission already requires a clean full-SHA checkout and a release-local interpreter. | IMPLEMENTED | `scripts/runtime/dharma_swarm_release_runner.sh:3-5,40-73,91-139`; `dharma_swarm/runtime_admission.py:271-353`. |
| Artifact manifests already record SHA-256, lineage, promotion state, and provenance. | IMPLEMENTED | `dharma_swarm/artifact_manifest.py:23-28,44-89,117-176,205-234`. |
| Artifact storage is local and UUID-addressed rather than a bounded external content-addressed store. | IMPLEMENTED | `dharma_swarm/engine/artifacts.py:59-128`; the artifact root is local in `dharma_swarm/artifact_store.py:18-42`. |
| A Litestream configuration requests a 60-second async sync cadence, six-hour snapshots, and seven-day retention of `runtime.db`. | IMPLEMENTED CONFIG | `scripts/ops/litestream.yml:1-16`; optional compose wiring at `docker-compose.yml:135-153`. Enabling it, verifying an independent replica, and measuring recovery lag remain separate proofs. |
| The inspected tree reports multiple competing fleet identity/route projections and no ratified roster owner. | REPORTED | `docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md:242-255,331-337`. Ratification and a fresh roster would supersede this statement. |
| The July field registry reports Agni as the hub, Rushabdev as AGNI-connected, the **Codex seat** on Meghadharma as relay-only, and the Mac broker as unbridged/often offline. It does not establish Meghadharma's whole-host role. | REPORTED | `docs/ops/FLEET_FIELD_REGISTRY.yaml:1-45,103-122,161-177`; its `updated` and `refreshed_by` fields expose the dated provenance. |
| An August draft reports deployed `A2A_*` streams while the July transport doctrine reports different live/target stream names; the fresh service topology is unknown. | REPORTED | `docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md:94-103,177-188`; `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:98-116`. Neither report is a fresh August 14 service probe. |
| The documented compose launch path appears not to supply either Git metadata or container-source-manifest provenance even though live orchestration calls fail-closed admission. | INFERRED | `Dockerfile.swarm:18-20,39-40`; `docker-compose.yml:78-112`; `dharma_swarm/orchestrate_live.py:2519-2528`; container admission contract at `dharma_swarm/runtime_admission.py:191-268,375-425`. A successful fresh compose admission receipt would falsify the inference. |

### 2.2 Fresh capacity observation

The raw command, timestamp, hostnames, inode/memory/load output, per-SSH exit
codes, mirror sizes, and interpretation limits are preserved separately in
`docs/reports/FLEET_CAPACITY_WITNESS_2026-08-14.md:9-101`. Aliases in this table
are probe routes, not stable node UIDs.

| Node alias | Root blocks (KiB) | Used (KiB) | Available (KiB) | Use | Memory (bytes) | Modality |
|---|---:|---:|---:|---:|---:|---|
| `agni` | 120,791,536 | 99,881,228 | 20,893,924 | 83% | 8,326,946,816 | OBSERVED |
| `rushabdev` | 120,791,536 | 119,910,560 | 864,592 | 100% | 4,106,100,736 | OBSERVED |
| `meghadharma` | 120,791,536 | 79,321,124 | 41,454,028 | 66% | 4,106,100,736 | OBSERVED |
| operator Mac data volume | 1,948,404,040 | 1,476,058,288 | 444,921,100 | 77% | not probed here | OBSERVED |

These numbers are a dated witness, not a capacity owner. Re-run the command
before allocation or cleanup.

Rushabdev also held a 35,708,632 KiB directory at
`/home/openclaw/dhyana_mirror`, last modified 2026-07-21. The Mac copy measured
35,672,392 KiB; similar aggregate size does not prove file equality
(`docs/reports/FLEET_CAPACITY_WITNESS_2026-08-14.md:82-86`). No process named
`rsync`, `rclone`, or `syncthing` was returned at that instant.

Process absence is a point observation only. Systemd units, cron jobs, timers,
launchd jobs, and remote push jobs still require an explicit job census before
the directory can be considered retired.

### 2.3 Immediate conclusion from the baseline

This proposal applies the following safety posture to the observed capacities:

- Rushabdev must admit no new nonessential bytes until capacity is recovered.
- Agni is above the proposed 80% high-water mark.
- Meghadharma has the most sampled VPS disk headroom but also had elevated
  load; neither its role nor writer eligibility is established by a ratified
  owner (`docs/reports/FLEET_CAPACITY_WITNESS_2026-08-14.md:70-77,97-101`).
- This design treats Mac sleep, roaming, and operator shutdown as expected
  failure cases, so it does not nominate the Mac as an automatic primary.

The first implementation phase is therefore classification and capacity
recovery, not another sync daemon.

## 3. Terms and state classes

| Class | Meaning | Authority rule | May be evicted? | Replication method |
|---|---|---|---|---|
| **code release** | Immutable admitted source plus platform-specific runtime lock/attestation | Exact Git SHA or verified image/source-manifest digest | Old releases yes; current and previous no | Git fetch/build, immutable activation |
| **generation manifest** | Published mapping from logical paths to immutable object digests | One manifest publisher for the current epoch; conditional generation promotion | No for current/previous | Small signed/hash-verified object plus atomic pointer |
| **immutable object** | Large content whose identity is its digest | Digest proves bytes; active manifest membership comes from publication | Local copy yes; required remote copy no | S3-compatible object store; lazy fetch |
| **mutable database** | Transactional work, receipts, claims, identities, or facts | Exactly one writer per surface unless replaced by an explicitly designed database cluster | No | State API plus Litestream/PITR backup; never file sync |
| **event/command** | Ordered delivery input or receipt transport | Broker sequence and domain write boundary; transport acceptance is not domain truth | Per retention policy | Bounded JetStream |
| **projection** | Rebuildable view over an owner | Never an authority | Yes | Recompute or subscribe |
| **cache** | Local copy fetched for speed/offline reading | Never an authority | Yes, unless selected by the node's pin set in the active manifest | Lazy fetch plus LRU/size/inode GC |
| **node-local runtime** | PID files, sockets, temp output, logs, venv, package cache, model cache | Node only | Yes under service policy | None |
| **secret** | Credential or key material | External secret authority and per-node policy | Rotate/revoke, never replicate as normal data | Per-node encrypted delivery into memory/system credentials |
| **backup** | Recovery copy, not a live reader/writer | Restore procedure plus integrity proof | Per retention schedule | Independent account/provider/failure domain |

**Replica**, **projection**, **cache**, **backup**, and **receipt** are evidence
types. None can promote itself into an authority type.

## 4. Proposed safety invariants

1. **One writer per mutable surface.** A node may be a candidate, standby, or
   projection reader, but it cannot be a concurrent peer writer by filesystem
   synchronization.
2. **No live database-file synchronization.** SQLite databases, PostgreSQL data
   directories, WAL, `-wal`, and `-shm` never enter rsync, Syncthing, Git,
   FUSE/object mounts, NFS, or the blob cache. SQLite WAL requires local
   filesystem storage (`docs/ops/RUNBOOK.md:259-270`).
3. **Publish immutable data before publishing its manifest.** A reader sees the
   previous complete generation or the next complete generation, never a mix.
4. **Authority is explicit and epoch-bound.** Newer mtime, larger file, later
   model response, majority opinion, matching hash, or possession of a receipt
   is not write authority.
5. **An offline node is read-only for shared truth.** It may create a proposal
   in node-local space; reconnection must rebase and re-verify it.
6. **The current release, active manifest object, and node-profile pin-set
   closure are pinned.** GC may only evict unpinned cache and retired releases.
7. **A disk reserve beats cache demand.** Fetching stops before the filesystem
   threatens service health.
8. **Secrets never enter manifests, object caches, Git, logs, images, prompts,
   or general backups.** The repository already mandates no secrets in Git
   (`CLAUDE.md`, Hard rules).
9. **A backup is untrusted until restored.** Replication status alone does not
   prove recovery.
10. **Compatibility mirrors remain subordinate.** Their presence cannot prove
    live delivery, ordering, liveness, or completion
    (`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:306-319`).

## 5. Target topology

```text
                         CODE AUTHORITY
                 GitHub AIKAGRYA/dharma_swarm
                    exact SHA / image digest
                              |
                              v
                immutable per-platform releases
                              |
           +------------------+------------------+
           |                  |                  |
           v                  v                  v
       operator Mac         Agni VPS       Meghadharma VPS       Rushabdev VPS
       operator/client      NATS/gateway   state-svc candidate   thin worker
       cold verifier        bounded cache  DB owner + cache      minimal pins
           |                  |                  |                  |
           +------------------+------------------+------------------+
                              |
                    FLEET COORDINATE CHECK
             release + epoch/seq + manifest root
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
     external object storage            mutable-state authority
     SHA-256 objects + manifests        one local DB writer/API
     versioning + lifecycle             Litestream -> off-fleet
             ^                                 ^
             |                                 |
       refs/hashes only                 idempotent commands
             +-------------- NATS -------------+
```

This proposal intentionally separates four authorities:

- Git orders code.
- The state writer orders database mutations within an epoch.
- The manifest publisher orders published immutable generations.
- NATS exposes per-stream/per-consumer delivery positions, not one global order
  and not domain truth.

They share trace and generation identifiers, but none silently substitutes for
another.

## 6. Proposed node profiles and storage budgets

These are initial **PROPOSED** profiles, not claims about current runtime roles.
Ratification belongs in the future fleet-roster and node-profile owner.

| Probe route/candidate | Proposed role | Shared-writer eligibility | Required pins | Initial object-cache cap | Reserve rule |
|---|---|---|---|---:|---|
| operator Mac | operator client, release builder/verifier, large cold cache, restore-drill target | no automatic fleet writer | current/previous release; all manifest objects; operator-selected archives | 100 GiB | retain at least 100 GiB free; global watermarks still apply |
| Agni | NATS/gateway/transport hub; no bulk archive | NATS stream owner only; not default DB or manifest writer | service release; NATS configs; current service objects | 5 GiB | VPS reserve = max(20 GiB, 20% of root); stop all nonessential fetches at 80% use |
| Meghadharma | state-service placement candidate; warm artifact cache | one explicitly named state surface only after selection | service release; state schema; current manifest object plus profile pin-set closure | 12 GiB | same VPS reserve; preserve DB growth budget ahead of cache |
| Rushabdev | thin worker and optional manually promoted cold replacement after recovery | none until disk and role gates pass | worker release and task-specific objects only | 2 GiB after recovery; zero while below reserve | same VPS reserve; fail closed on new downloads until at least 20 GiB is free |

These labels are probe-route names. The roster must bind each to a stable
`node_uid`, observed hostname, provider instance identity/fingerprint, role,
and route set before enrollment.

Admission for one new fetch is always bounded by:

```text
max_admissible_fetch_bytes = max(0, min(
    profile.cache_cap - current_cache_bytes,
    filesystem_free
      - profile.required_reserve
      - reserved_db_log_scratch_growth
      - other_inflight_peak_reservations
  )
)
```

The cache also needs an inode cap. The starting limit should be the lower of
250,000 objects or 25% of total filesystem inodes, while retaining at least 10%
of total inodes free. Cache admission fails before crossing either limit.

Every concurrent download/build obtains a serialized reservation for compressed
bytes, the largest `.partial`, unpack/build peak, and expected DB/log growth
before it starts. Reservations count against both free-space reserve and cache
cap. `.partial` files expire after 24 hours unless an active reservation renews
them; quarantine has a 512 MiB/1,000-object cap and moves excess samples to the
off-host evidence store before local eviction.

Profile ratification computes the active pin-set bytes and object/inode counts.
If pinned content plus the largest in-flight/unpack peak and other whole-node
budgets do not fit, the node cannot enroll that profile; `pinned` is not an
exemption from capacity arithmetic.

### 6.1 Whole-node storage envelopes

An object-cache cap alone is insufficient: stream data, databases, logs,
release builds, and scratch space can still consume the disk. Enrollment must
satisfy this proposed planning inequality using fresh census data:

```text
unmanaged_used
+ releases_budget
+ service_state_budget
+ object_cache_budget
+ logs_budget
+ scratch_budget
+ required_reserve
<= filesystem_capacity
```

Initial ceiling values, all **PROPOSED**, are:

| Node | Releases | Service-owned state | Object cache | Logs | Scratch/restore | Required reserve |
|---|---:|---:|---:|---:|---:|---:|
| operator Mac | 10 GiB | 0 GiB fleet service state | 100 GiB | 5 GiB | 100 GiB | 100 GiB |
| Agni | 4 GiB | 8 GiB total JetStream file storage | 5 GiB | 2 GiB | 2 GiB | max(20 GiB, 20% root) |
| Meghadharma | 4 GiB | 12 GiB DB/WAL growth envelope | 12 GiB | 2 GiB | 4 GiB | max(20 GiB, 20% root) |
| Rushabdev | 4 GiB | 0 GiB fleet service state | 2 GiB after recovery | 1 GiB | 4 GiB | max(20 GiB, 20% root) |

These are admission ceilings, not reservations that excuse existing unknown
usage. If the inequality fails, the node cannot enroll that profile until data
is classified, moved, or capacity is added. Reaching a database envelope stops
new nonessential task admission and triggers capacity/migration work; it never
truncates or evicts database pages. Agni's JetStream ceiling is aggregate
on-disk bytes across all streams and replicas placed on that node, not a
per-stream allowance.

Using only the fresh free-space witness and reserve formula—not current cache,
in-flight reservations, or the still-missing usage census—the provisional
upper bounds are Mac 100 GiB, Agni 0, Meghadharma 12 GiB, and Rushabdev 0. Agni
and Rushabdev already violate the VPS reserve; the Mac is above the global 75%
prefetch stop. The stricter of a node override, reserve check, and global
watermark always wins. Meghadharma's 12 GiB value is a cache-only ceiling: its
proposed 22 GiB of non-cache budgets exceed its sampled free-after-reserve by
roughly 5.5 GiB unless the full census reclassifies existing used space. These
upper bounds do not enroll any node
(`docs/reports/FLEET_CAPACITY_WITNESS_2026-08-14.md:57-86`).

### 6.2 Watermarks

| State | Trigger | Required behavior |
|---|---|---|
| normal | below 75% and reserve satisfied | admit role-allowed cache fills |
| high | 75-80% or reserve margin shrinking | stop prefetch/optional fills; allow only reserved required-pin fetches; evict unpinned LRU to low watermark |
| hard | above 80% or reserve violated | reject nonessential downloads/builds; evict all unpinned cache; alert operator |
| emergency | above 90% | preserve current release, DB, active manifest object, profile pin-set closure, and minimum logs; disable optional workloads; require operator triage |

No cache eviction may touch:

- the active release;
- the immediately previous rollback release;
- the current generation manifest;
- objects in the current manifest that are required by the node pin set;
- live database/WAL files;
- current secret material;
- the newest successful restore witness.

## 7. Logical namespace

Use a platform-specific root with one identical relative contract:

```text
Linux:  DHARMA_FLEET_ROOT=/srv/dharma
macOS:  DHARMA_FLEET_ROOT=/Users/dhyana/.dharma/fleet

$DHARMA_FLEET_ROOT/
  releases/
    <release-manifest-digest>/<platform>/  # immutable admitted runtime
  current -> releases/<digest>/<platform>/ # atomic local activation
  previous -> releases/<digest>/<platform>/# rollback pin
  manifests/
    generations/<epoch>-<generation>.json
    current.json                     # verified local pointer projection
  object-cache/
    sha256/<first-two>/<digest>      # disposable local materialization
  projections/
    <surface>/                       # read-only/rebuildable views
  runtime/
    <node-id>/                       # logs, sockets, temp, local-only state
  quarantine/
    corrupt/                         # digest failures; never served
  receipts/
    convergence/                     # small verification receipts only
```

Secrets do not live under this tree. Linux services receive them through
`/run/credentials` or an equivalent tmpfs/systemd credential surface. macOS
services receive them from the Keychain or a memory-only materialization.

### 7.1 Logical URIs

Applications should store logical URIs rather than host paths:

```text
dharma://release/<manifest-digest>/<platform>/<relative-path>
dharma://manifest/<epoch>/<generation>
dharma://object/sha256/<digest>
dharma://projection/<surface>/<key>
dharma://runtime/<node-id>/<key>       # explicitly nonportable
```

The resolver checks the node profile, current generation, cache quota, and
digest before returning a local path.

Before enabling it, F0 inventories every code/config/service consumer of the
selected host paths and records `{consumer, access_mode, owner, logical_uri,
adapter, cutover_gate, rollback_path}`. A caller with unknown write behavior
blocks migration. Applications that require ordinary paths receive a narrow
materialization adapter or read-only bind path; the rollout does not rewrite a
whole home directory behind their backs.

### 7.2 Cross-platform path rules

The logical namespace must not inherit accidental macOS/Linux differences:

- logical paths use `/`, lowercase ASCII directory names, and normalized UTF-8
  metadata;
- reject absolute paths, `..`, NUL, empty segments, control characters, and
  path traversal after decoding;
- reject two logical paths that differ only by case;
- manifests never follow symlinks outside the admitted release or cache root;
- object keys are digest-derived, not user-provided filenames;
- executable bit, content type, and normalized mode are manifest fields rather
  than inferred from the receiving filesystem;
- rename, lock, and `fsync` guarantees are local-node guarantees only. There is
  no cross-node POSIX lock or atomic rename claim.

If a workload truly requires shared live POSIX semantics, it must use one
single-writer filesystem service over the private network and accept that
service as an availability dependency. It still may not host SQLite WAL or
database data directories. Object mounts, rclone mounts, and Syncthing are not
database-grade POSIX substitutes.

## 8. Code and release plane

### 8.1 Release identity

The source coordinate includes a full 40-character Git SHA from the owner
repository, `AIKAGRYA/dharma_swarm` (`docs/ops/RUNBOOK.md:146`). The deployable
coordinate is a signed release-manifest digest that binds:

```text
{source_commit, dependency_lock_sha256, source_manifest_sha256,
 platform -> {runnable_artifact_sha256, toolchain_digest,
              runtime_attestation_policy}}
```

The release body is I-JSON/JCS with schema
`dharma.fleet.release-manifest.v1`; its root and Ed25519 envelope use distinct
domain separators and the versioned trust-history rules from section 9.3.
Define its root as
`SHA256(UTF8("dharma.fleet.release-manifest.v1\0") || RFC8785(body))` and sign
the exact UTF-8 JCS bytes of
`{domain: "dharma.fleet.release-signature.v1", release_manifest_root,
trust_registry_generation}`. The manifest is immutable and may be referenced by
many deployments.

Activation is a separate signed, monotonic deployment record:

```text
DeploymentBody = {
  schema: "dharma.fleet.deployment.v1",
  deployment_generation,
  parent_deployment_root,
  desired_release_manifest_root,
  previous_release_manifest_root,
  authority_epoch,
  trust_registry_generation
}
```

Define `deployment_root` with domain
`dharma.fleet.deployment.v1\0` over the JCS body and sign the exact UTF-8 JCS
bytes of `{domain: "dharma.fleet.deployment-signature.v1", deployment_root,
deployment_generation, parent_deployment_root, authority_epoch,
trust_registry_generation}` under the deployment-publisher policy.

The state writer advances its active deployment root with expected-parent and
`generation == current + 1` checks through the two-phase publication/outbox
protocol defined in section 9.4. Nodes accept only the state-owned active
deployment record under a current authority epoch; replaying an old but valid
record cannot reactivate its release.

Every node activates the platform entry allowed for its profile. Source commit
and dependency lock converge fleet-wide; runnable bytes may legitimately differ
between macOS arm64 and Linux x86_64. A node never activates a branch checkout
or copied working tree as a release.

Existing enforcement already provides the core mechanism:

- require a full pinned SHA;
- require a clean Git root;
- reject ignored import bytecode;
- use a release-local copied interpreter;
- run admission before the live orchestrator
  (`scripts/runtime/dharma_swarm_release_runner.sh:40-139`);
- require `HEAD == origin/main` and optional pin equality
  (`dharma_swarm/runtime_admission.py:271-353`).

The fleet controller should generalize that boundary to all four nodes. Before
admission it verifies the remote URL resolves to `AIKAGRYA/dharma_swarm`, performs
a fresh fetch of the desired commit, verifies the signed release manifest and
its active signer, and binds the source SHA, lock, source manifest, platform,
toolchain, and runnable artifact digest. A locally stale `origin/main` ref is
not sufficient evidence.

There is currently a rollback-policy gap: admission requires
`HEAD == origin/main` (`dharma_swarm/runtime_admission.py:271-353`), so a
previous release becomes inadmissible as soon as the branch advances. Slice F2
must implement the deployment record above. Admission should require membership
in that state-owned set plus the existing clean-tree/source-manifest proofs; it
must not weaken those proofs or treat an arbitrary historical commit as
deployable.

### 8.2 Platform parity

macOS arm64 and Linux x86_64 do not need byte-identical virtual environments.
They need:

- the same source commit;
- the same dependency lock digest;
- the same critical-file/source-manifest digest;
- separately admitted platform runtimes;
- the same release manifest schema;
- a node-specific runtime attestation.

Virtual environments, wheels, compiled extensions, caches, and interpreters are
node-local build products. They are not mirrored.

### 8.3 Activation and retention

1. Fetch/build into `releases/<release-manifest-digest>/<platform>.partial`.
2. Verify source, lock, critical files, runtime, and smoke checks.
3. Rename to `releases/<release-manifest-digest>/<platform>` on the same
   filesystem.
4. Atomically repoint `current`; preserve the prior target as `previous`.
5. Emit a convergence receipt containing the full coordinate and verification
   results.
6. Garbage-collect every unpinned release after a minimum seven-day rollback
   grace period.

Keep exactly current plus previous by default. A release needed for forensic
retention belongs in object storage or a Git ref, not in every VPS release
directory.

### 8.4 Container admission gap

Do not declare container parity complete until the compose path supplies the
container-source manifest and digest required by runtime admission. The
current static seam is documented in section 2.1. The acceptable repairs are:

- bake `.dharma-runtime-source.sha256` beside the image source and set the
  expected digest; or
- run the image from an admitted immutable Git release with the required
  provenance.

Mounting a mutable host package directory into `/app` is not an immutable
release mechanism.

## 9. Immutable object and generation-manifest plane

### 9.1 Why a new adapter is required

The current artifact system is already checksummed and provenance-aware, but
its payload path is local and its artifact ID is random rather than
content-addressed (`dharma_swarm/artifact_manifest.py:44-65,117-176`;
`dharma_swarm/engine/artifacts.py:59-128`). Reuse the manifest fields and
runtime `ArtifactRecord`; add an external object URI and a content-addressed
adapter instead of inventing a parallel artifact ontology.

The existing sidecar writer uses a direct `write_text` path
(`dharma_swarm/artifact_manifest.py:178-190`). F3 must write local projections
through same-filesystem temporary files, flush file and parent directory as the
platform permits, verify, then atomically rename; a torn sidecar never becomes a
published manifest.

### 9.2 Object identity

```text
algorithm: sha256-v1
object_id: sha256:<64 lowercase hexadecimal characters>
remote_key: objects/sha256/<first-two>/<digest>
```

Every fetch verifies size and SHA-256 before activation. A mismatch is moved to
`quarantine/corrupt/`, emits a receipt, and is refetched from a clean remote
version. A corrupt remote object blocks the generation; it is never silently
accepted from a local cache.

A digest proves integrity, not confidentiality, authorization, publisher
identity, or freshness. The object backend must enforce TLS, encryption at
rest, bucket versioning, least-privilege prefix policy, and access logging.
V1 admits only data explicitly classified for that backend; it excludes secrets
and payloads requiring client-side confidentiality. A later encrypted-object
schema must separately define plaintext/ciphertext digests, envelope algorithm,
key version/rotation, locator privacy, and recovery through the secret plane
before admitting those classes. Object metadata must avoid original host paths
and secret-bearing filenames.

### 9.3 Manifest body, root, and signature envelope

V1 permits JSON regular-file entries only. The **body** excludes
`manifest_root` and `signatures`:

```json
{
  "schema": "dharma.fleet.generation.v1",
  "authority_epoch": 7,
  "generation": 184,
  "parent_manifest_root": "sha256:...",
  "release": {
    "release_manifest_root": "sha256:...",
    "platform": "linux-x86_64"
  },
  "publisher": {
    "surface": "fleet_manifest",
    "node_uid": "<roster-node-uid>",
    "lease_id_digest": "sha256:..."
  },
  "objects": [
    {
      "logical_path": "knowledge/current/index.json",
      "object_id": "sha256:...",
      "size_bytes": 12345,
      "content_type": "application/json",
      "mode": "0644",
      "pin_groups": ["all", "worker"],
      "retention_class": "current_plus_30d",
      "durability_class": "two_failure_domains_before_publish"
    }
  ],
  "created_at": "2026-08-14T00:00:00Z"
}
```

`<roster-node-uid>` is intentionally not an SSH alias. V1 rejects symlinks,
hardlinks, sparse-file semantics, devices, sockets, ACLs, xattrs, UID/GID
ownership, and directory objects; add them only through a versioned schema and
cross-platform fixtures.

Parse JSON with duplicate-key rejection, Unicode validation, and schema/type
limits. Apply logical-path normalization during schema validation, then preserve
all validated strings byte-semantically. Serialize the body with
[RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785). Define:

```text
manifest_root = "sha256:" + hex(
  SHA256(UTF8("dharma.fleet.generation.v1\0") || RFC8785(body))
)

signature_payload = RFC8785({
  "domain": "dharma.fleet.generation-signature.v1",
  "schema": body.schema,
  "manifest_root": manifest_root,
  "trust_registry_generation": 12,
  "authority_epoch": body.authority_epoch,
  "generation": body.generation,
  "parent_manifest_root": body.parent_manifest_root,
  "lease_id_digest": body.publisher.lease_id_digest
})
```

The stored envelope contains
`{body, manifest_root, trust_registry_generation, signatures}`. Each signature
uses Ed25519 raw 32-byte public keys and 64-byte signatures encoded as unpadded
base64url and includes `{key_id, algorithm: "Ed25519", signature}`. Sign the
exact bytes `UTF8(RFC8785(signature_payload))`. I-JSON/JCS numeric fields are
safe nonnegative integers no larger than `2^53 - 1`; digests, IDs, and values
requiring a larger range are strings.

Initial policy is at least one manifest-publisher key valid in the envelope's
versioned trust-registry generation and effective interval. Normal rotation
preserves retired public keys and historical validity metadata for retained
manifests. Compromise marks the key compromised from a bounded incident time,
quarantines affected reachable roots, and requires an explicit incident
promotion/re-sign procedure; it does not silently reinterpret history through
the current registry. Unknown, compromised-in-window, or policy-invalid keys
fail. The verifier recomputes the body root, checks the signature threshold,
verifies the lease binding/epoch, and then verifies every object. A signature
authenticates a publisher; it cannot mint authority.

### 9.4 Atomic publish and crash recovery

V1 deliberately keeps the active manifest pointer in the single-writer state
surface so object membership and its owner revision commit atomically. Object
storage holds immutable bodies/envelopes; `manifests/current.json` on nodes is a
projection.

1. Deterministically serialize and hash every payload locally.
2. Upload each object under a temporary upload ID to every failure domain
   required by its durability class.
3. Read back and verify byte length and SHA-256. Never use an S3 multipart ETag
   as a content digest.
4. Commit each immutable digest key without overwrite.
5. Build, hash, sign, and independently verify a manifest that closes over only
   objects whose required copies verify.
6. Store and read-back-verify the immutable envelope in every required domain.
7. Construct the exact JCS `operation_body` as `{method:
   "publish_generation", surface: "fleet_manifest", side_effect_key,
   expected_parent_root, authority_epoch, lease_id, envelope_object_id,
   manifest_root, generation}`. The `idempotency_key` and `operation_hash` are
   deliberately outside that body. Compute `operation_hash =
   SHA256("dharma:publish-generation:v1" || UTF8(JCS(operation_body)))`, then
   submit `{idempotency_key, operation_hash, operation_body}` to the state
   writer. Reusing an idempotency key with a different operation hash is
   rejected.
8. Implement a **new generic publication outbox and transaction-scoped receipt
   helper**. The current `RuntimeReceipt` writer commits separately, and the
   current `_db` outbox is episode-specific
   (`dharma_swarm/runtime_state.py:3187-3244,4153-4223,4483-4492`). In one
   database transaction the new helper fetches/read-back-verifies the envelope,
   recomputes its root/signature/lease/durability closure, requires
   `generation == current + 1` and the expected parent, rejects any referenced
   object carrying an active GC tombstone, claims `(idempotency_key,
   side_effect_key, operation_hash)`, and inserts a `PENDING` candidate plus its
   candidate revision and existing `RuntimeReceipt` envelope. It does **not**
   change `active_root`, advance the active owner revision, or enqueue an
   activation announcement.
9. An independent replica monitor restores or otherwise verifies a recovery
   point containing that exact candidate revision, then stores a signed
   durability witness with the operation hash, root, candidate revision, and
   recovery-point identity in both required off-host evidence domains.
10. A second state-writer CAS transaction verifies the two-copy witness, the
    still-current parent, generation, authority/lease, and absence of GC
    tombstones; changes the candidate to `RECOVERABLE`; advances `active_root`
    and the `fleet_manifest` owner revision; persists the activation receipt;
    and enqueues the fixed activation subject/payload/message ID. The generic
    outbox publisher sets `Nats-Msg-Id` to that durable message ID, publishes
    `{root, generation, epoch, owner_revision, trace_id}`, and marks the row
    delivered only after JetStream publish ACK. Consumers remain idempotent
    because loss of the ACK can cause a duplicate. Nodes verify the state-owned
    pointer and durability witness before activation.

A crash before step 8 leaves only unreferenced immutable objects for grace-period
GC. A crash after either transaction commits but before reply returns the
committed phase when the same idempotency key is retried. A crash before NATS
publish leaves a durable activation outbox row for replay. If the activation
transaction is lost with its asynchronous database replica, recovery reconstructs
and replays that exact CAS from the already durable candidate and two-copy
durability witness; it never infers activation from object timestamps.

Because SQLite/Litestream durability is asynchronous, an acknowledgement alone
does **not** give a candidate zero RPO. The first transaction returns
`{publication_receipt, durability: PENDING}`. Only steps 9-10 may expose
`durability: RECOVERABLE`, advance the active pointer and fleet desired
coordinate, announce activation, and let nodes activate the root. The request
origin may inspect a PENDING candidate, but it is not fleet-published truth.

After total DB-host loss, restore the newest recovery point, read its active root
and revision, and compare it with off-host durability witnesses and acknowledged
publication receipts. A receipt newer than the restored revision is a
lost-publication candidate: keep shared writes disabled, verify its immutable
envelope/object copies, and replay the exact operation through idempotency under
the new epoch. A valid two-copy RECOVERABLE witness is sufficient recovery input
to reconstruct its exact publication transaction; a PENDING receipt is only a
candidate. Unknown or conflicting candidates require operator resolution.
No node selects a root merely because a receipt or object has a later timestamp.

A restored database selects the active root from its reconciled publication row
and verifies object closure before writes reopen. There is no object-pointer
last-write-wins fallback. Replacing this owner with backend CAS requires a
separately proved migration, not a runtime switch.

### 9.5 Garbage collection

Remote object GC is a receipt-gated, authority-serialized mark-and-sweep:

- freeze a root-set revision containing the active/previous manifests, retained
  releases, holds, and manifests within retention;
- mark from that root set and tag unmarked objects as candidates with the mark
  revision; do not delete;
- run a second scan after at least 30 days. In one state-writer transaction,
  re-check each candidate against the newest root-set revision and insert a
  `DELETE_CLAIMED` tombstone containing a unique claim token and exact backend
  version IDs. This transaction serializes with publication, whose transaction
  rejects every referenced object with an active tombstone;
- after the tombstone commits, conditionally delete only those exact immutable
  backend version IDs, then record the root revisions, keys, sizes, claim token,
  and deletion results in the receipt. A failed deletion leaves the tombstone
  active and is safe to retry;
- configure lifecycle rules only for expired temporary/multipart uploads, never
  live or candidate object identities by age alone; candidate tags are metadata,
  not deletion authority;
- never clear a deletion claim merely to republish the digest. Reuse requires
  completed deletion, a fresh read-back-verified upload with new backend version
  IDs, and a state-writer transaction that replaces the completed tombstone with
  that availability record before a later publication can reference it;
- keep destructive sweeps operator-approved until repeated fault-injection
  tests justify a separately ratified automation policy.

Local cache metadata uses transactional states
`DOWNLOADING -> READY -> EVICTING`, byte/inode reservations, pin counts, and
short read leases. Fetch promotes on the same filesystem only after digest
verification and metadata commit recovery. GC selects an unpinned/no-reader
candidate under lock, marks `EVICTING`, rechecks under lock, unlinks, and commits
metadata; startup reconciles every intermediate state. If quarantine is full and
off-host evidence is unavailable, retain only digest/error receipt where policy
allows, stop new fetches, and preserve the disk reserve—remote evidence transfer
never overrides the hard node bound.

## 10. Mutable-state plane

### 10.1 Database census before convergence

The repository has more state surfaces than `runtime.db`. The legacy/Mac
Litestream configuration names five candidate databases:
`memory_plane.db`, `temporal_graph.db`, `ecosystem_index.db`, `runtime.db`, and
`ontology.db` (`scripts/litestream.yml:12-61`). That list is backup
configuration, not an authority registry.

Before migrating anything, create one database census with this shape:

```yaml
schema: dharma.fleet.database_registry.v1
databases:
  - surface: runtime
    path: ~/.dharma/state/runtime.db
    closure_layer_role: <exact-rule-2-role>
    lifecycle: active
    owner_module: dharma_swarm.runtime_state
    writer_node_uid: <roster-node-uid>
    probe_route_hint: meghadharma
    writer_mode: single
    epoch: 1
    revision_source: proposed_authority_meta_table
    direct_writer_callers: <generated-census>
    allowed_service_uid: <dedicated-os-user>
    remote_clients: <roster-role-selector>
    access: state_api
    api_schema_version: 1
    backup: litestream
    target_rpo_seconds: 60
    rto_minutes: 60
    failover: manual_fenced_restore
```

Do not invent a competing persistence taxonomy. `closure_layer_role` imports the
exact Rule 2 role vocabulary from `docs/governance/ANTI_SLOP_RULES.md:41-63`.
Record location/lifecycle separately as `active`, `node-local`, or `retired`,
and record writer, reader, backup, retention, and migration facts in their own
fields.

Unknown ownership blocks migration. Do not sync an unclassified
`~/.dharma` subtree.

The existing `RuntimeStateStore` does not claim one global fleet commit
revision in its core schema (`dharma_swarm/runtime_state.py:33-313`). Before
remote mutation, add a per-surface `authority_meta` row whose epoch and
monotonic revision are advanced in the same transaction as every governed
write. Do not substitute timestamps, receipt IDs, or NATS stream positions for
that database revision.

### 10.2 Initial mutable-state design

For the existing SQLite runtime:

- run one service beside the database on the selected state-primary node;
- keep `runtime.db`, `runtime.db-wal`, and `runtime.db-shm` on that node's local
  filesystem;
- expose typed state operations over an authenticated private API or the
  existing governed command path;
- require per-method role authorization, mTLS/node identity, API schema
  negotiation, request size/rate limits, bounded queues, overload backpressure,
  replay windows, and idempotency conflict detection;
- make remote operations idempotent at the state write boundary and reject one
  key reused with a different operation hash;
- return the committed epoch, revision, receipt ID, and trace ID;
- let other nodes maintain read-only projections or request fresh reads;
- replicate recovery state to an independent S3-compatible target with
  Litestream.

The API is not exclusive while local callers can still open the database.
Inventory every direct writer, migrate it behind the service boundary, run the
service as a dedicated OS user, and use directory/file ownership plus service
sandboxing to deny database writes from workers and operator processes. Cutover
requires a mechanically acknowledged write barrier from every old caller and a
direct-open bypass test.

Meghadharma is only a placement **candidate** because the capacity witness shows
the most sampled VPS disk headroom and also elevated load
(`docs/reports/FLEET_CAPACITY_WITNESS_2026-08-14.md:70-77`). Selection requires
a host-readiness matrix covering sustained load, CPU, filesystem type, latency
and fsync behavior, uptime, provider/failure domain, private connectivity,
firewall, service conflicts, supervision, backup egress, security posture, and
operator access, plus a role decision, clean restore drill, private API, and
old-writer fencing.

### 10.3 Why not remote-mount SQLite

SQLite WAL explicitly assumes local filesystem behavior. A remote NFS/FUSE
mount adds ambiguous locking and failure semantics while retaining a
single-writer bottleneck. The safe distribution boundary is a state API, not a
shared database path.

### 10.4 Litestream boundary

The existing VPS config requests a 60-second asynchronous sync cadence,
six-hour snapshots, and seven-day retention (`scripts/ops/litestream.yml:10-16`).
The cadence is a target, not a guaranteed 60-second RPO. Production use must
additionally prove:

- the target is in an independent provider/account or at least an independent
  failure domain, not another directory on the same root disk;
- encryption and least-privilege credentials;
- replica freshness monitoring;
- SQLite integrity after clean-host restore;
- point-in-time selection and documented rollback;
- retention beyond seven days if the recovery policy requires it.

Litestream recovery points use Litestream's own generation/snapshot/WAL or
timestamp selection, not application revision numbers. After restore, read the
transactional `authority_meta` row to learn the contained epoch/revision, then
compare it with acknowledged receipts and report the measured lag. Never infer
a database revision from `sync-interval` alone.

The upstream v0.3 reference defines `sync-interval` as frame-push frequency,
and its caveats describe the recent-write loss window of asynchronous
replication ([configuration](https://litestream.io/v0.3/reference/config/),
[data-loss caveat](https://litestream.io/v0.3/tips/)). Pin the deployed
Litestream version and revalidate these semantics before rollout.

The `cp runtime.db` fallback currently shown in
`docs/ops/RUNBOOK.md:290-304` is not sufficient evidence for a hot WAL-consistent
backup. That is an inference from the WAL mode and the absence of WAL/backup-API
steps; use Litestream, the SQLite backup API, or a stopped/checkpointed database
and prove the result with `PRAGMA integrity_check`.

### 10.5 When to move to PostgreSQL

Do not migrate merely to sound distributed. Move a state surface to PostgreSQL
when at least one of these becomes true:

- two or more hosts need direct concurrent transactions rather than a state
  API;
- the required write throughput exceeds measured SQLite capacity;
- automatic failover has a justified RPO/RTO and reliable fencing mechanism;
- operational tooling can support schema migration, base backup, WAL archive,
  monitoring, and restore drills.

Even then, use one writable primary, a separately placed standby, continuous
WAL archive, and stale-primary fencing. PostgreSQL data directories and WAL
remain outside the logical filesystem mirror.

## 11. NATS/event plane

NATS owns live transport, durable consumers, replay, acknowledgements, and
fanout within its declared stream/consumer boundaries; it does not own domain
completion (`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:19-46,171-212`).

### 11.1 Payload boundary

- commands and events carry IDs, small typed payloads, manifest roots, object
  references, sizes, and hashes;
- large transcripts/artifacts remain external objects; the NATS doctrine
  already permits references plus hashes
  (`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:297-304`);
- a consequential command is durably recorded/idempotency-claimed before its
  external side effect;
- publish acceptance, consumer delivery, handler ACK, and domain receipt remain
  distinct truth levels.

### 11.2 Retention and storage bounds

The target doctrine specifies max ages from seven to ninety days and
discard-old behavior (`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:80-96`),
but byte quotas must also be explicit for every deployed stream.

For each stream define:

```text
{max_age, max_bytes, max_msgs, max_msgs_per_subject,
 duplicate_window, discard_policy, replicas, storage_location}
```

Neither `max_age` nor `max_bytes` may be unlimited on any stream. Configure
JetStream account/server ceilings as well: total file and memory bytes, maximum
streams/consumers, and a requirement that new streams/Object Store buckets
declare byte limits. The sum of placed stream replicas must fit the Agni
whole-node envelope. R3 broker replication, if later enabled, multiplies broker
storage on each peer; it is availability, not archival backup. Small VPS nodes
should consume remotely or hold only bounded stream state, not a full blob/Object
Store replica.

### 11.3 Broker-loss behavior

NATS must not be the sole record of a completed domain effect. After a broker
loss:

- rebuild pending/complete projections from the state owner and domain
  receipts;
- re-enqueue only idempotent unfinished work;
- reject a replay whose idempotency key is already complete;
- preserve the distinction between a lost unaccepted command and a completed
  effect.

### 11.4 Private network and node identity

- expose the state API and broker client ports only on an authenticated private
  overlay or equivalent private network; firewall them from the public Internet;
- bind authorization to a stable enrolled `node_uid` and role, not a mutable
  hostname or possession of an SSH key alone;
- use mutually authenticated TLS or protocol-native node credentials for state
  and broker traffic, with distinct credentials per node and service;
- keep SSH as an operator/admin path, not an application mutation protocol;
- let nodes fetch immutable objects directly over TLS with read-only,
  prefix-scoped credentials; only the publisher receives object/manifest write
  scope;
- include request ID, trace ID, authority epoch, and idempotency key in every
  remote mutation and its receipt;
- deny shared writes when identity, epoch/lease validation, or the private route
  is unavailable.

Network encryption proves channel and peer identity. It does not choose the
state writer, promote a manifest, or turn transport acceptance into domain
completion.

## 12. Secret plane

### 12.1 Storage and delivery

Do not create a second provider-key registry. The existing compatibility owner
uses one key home, `~/.dharma/agent_keys.env`, read through `api_keys.py`
(`docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md:70-112`), and the known-breakage
register explicitly rejects another store/registry as the repair
(`docs/state/BROKEN_REGISTER.md:84-93`). Phase 0 first converges every provider
consumer on that loader and removes bypass paths.

A later ratified secret-delivery migration may place per-node encrypted bundles
or secret-manager records behind the same loader/registry boundary. That backend
must have one age/SOPS recipient or equivalent hardware/service identity per
node and must not share credentials with the artifact bucket. It is a delivery
backend, not another provider-name, alias, precedence, or liveness registry.
Non-provider node certificates and service identities follow the same per-node
least-privilege rule through their named identity owner.

At service start:

1. authenticate the node identity;
2. fetch only the bundle allowed by its role;
3. decrypt into tmpfs/systemd credentials or a process environment assembled
   without logging;
4. start the service with least privilege;
5. remove temporary plaintext and verify no child process inherited unrelated
   credentials.

The selected migration must define bootstrap identity issuance, bundle signing,
anti-rollback generation checks, trust-root rotation, and recovery. A proposed
recovery shape is one Mac secure-key-store identity plus a second encrypted
offline key outside all four machines; no rollout may assume that shape before
its owner is ratified and a recovery drill passes.

### 12.2 Rotation and revocation

- secret bundles carry generation and recipient-set metadata, never values,
  in fleet status;
- revocation disables the node identity and live sessions, rotates or revokes
  every provider/service credential the node could have read, removes the node
  from future encrypted bundles, rejects rollback to an old bundle generation,
  and proves old credentials are denied;
- unrelated credentials may remain only when policy proves the revoked node
  could never read them; removing an encryption recipient alone does not erase
  ciphertext, plaintext, private keys, or tokens already copied;
- provider credentials are role-specific and withdrawal/destructive scopes are
  absent unless explicitly required;
- rotation emits an audit receipt that names the generation and affected
  identities, not the secret;
- logs, command traces, process inventories, prompts, crash dumps, backups, and
  shell history are redaction surfaces.

Authentication proves identity. It does not by itself grant manifest or state
write authority; the authority policy and current epoch are still required.

## 13. Offline and reconnection semantics

The design chooses consistency over offline shared writes.

### 13.1 While disconnected

A node may:

- run the active admitted release;
- read its pinned current generation;
- serve cache hits whose digest and manifest root verify;
- perform node-local ephemeral work;
- create a `Candidate` proposal containing base epoch, base manifest root,
  intended mutations, evidence, and idempotency keys.

A node may not:

- advance the fleet epoch or manifest generation;
- mutate a shared owner database;
- perform a consequential external side effect whose idempotency/authorization
  owner cannot be reached; recording an intent locally does not make the effect
  safe to replay;
- queue an unbounded set of assumed-authority operations;
- serve safety-sensitive data beyond its declared staleness TTL;
- claim that its local candidate is published truth.

### 13.2 Reconnection gate

Before resuming shared work, verify:

1. node identity and secret generation;
2. admitted release-manifest digest, source commit, and platform runtime;
3. current authority epoch and writer;
4. required/observed state revision and owner schema version;
5. manifest root and closure;
6. candidate base epoch/root;
7. idempotency status for every proposed side effect;
8. disk reserve and cache integrity.

If the candidate base is stale, rebase it as a proposal. Never auto-merge an
offline filesystem tree.

### 13.3 Staleness visibility

Every read projection displays:

```text
{source_epoch, source_revision, manifest_root, observed_at,
 age_seconds, staleness_limit_seconds, verdict}
```

Wall-clock age is for operator visibility and TTL policy. Authority epoch and
owner-assigned revision, not timestamps, determine ordering.

Initial **PROPOSED** staleness classes are:

| Surface/use | Disconnected allowance | Initial limit | Expiry behavior |
|---|---|---:|---|
| writer lease/shared mutation | none beyond cached lease | 30-second maximum lease | reject mutation |
| idempotency check before external effect | none | 0 seconds | record proposal only |
| task/claim operational projection | labeled read | 60 seconds | mark `STALE`; no action from it |
| active manifest pointer | labeled offline read | 15 minutes normal, 24 hours explicit offline mode | serve only already pinned objects, then block |
| immutable object bytes | inherits manifest/pin validity | no independent age TTL | verify digest; membership may still expire |
| node status | on-demand signed projection | 120 seconds | reject envelope |

On receipt, convert durations to a local monotonic deadline. A suspended process
does not extend the deadline. After reboot or loss of monotonic continuity,
recontact the owner before using a lease or safety-sensitive projection. Signed
wall-clock expiry is an additional anti-replay check; if trusted-time health is
outside the allowed skew, fail closed for writes and label reads `CLOCK_UNSURE`.

## 14. Authority, promotion, and split-brain prevention

### 14.1 Typed publication and authority-transfer rules

```text
publish_generation(
  candidate: Candidate<
      HashVerified,
      ManifestClosed,
      RebasedOn<CurrentEpoch>,
      ExpectedParent<CurrentGeneration>,
      IdempotencyChecked
  >,
  authority: Authority<
      FleetManifest,
      WriterNode,
      Epoch = CurrentEpoch,
      Lease = Unexpired
  >,
  durability: Proof<RequiredObjectCopiesPersisted>
) -> PublishedTruth<
    FleetManifest,
    Generation = CurrentGeneration + 1,
    Epoch = CurrentEpoch
>

transfer_authority(
  surface: Surface,
  recovery: Candidate<IntegrityChecked, ReconciledEffects>,
  coordinator: AuthorityRegistryUpdate<ExpectedEpoch = CurrentEpoch>,
  fencing: Proof<PreviousWriterCannotWrite>,
  durability: Proof<RecoveryCheckpointPersisted>
) -> Authority<
    Surface,
    NewWriterNode,
    Epoch = CurrentEpoch + 1,
    Lease = Unexpired
>
```

Normal publication advances `generation` within one writer epoch; only a writer
handoff/failover advances `authority_epoch`. An offline node can construct
`Candidate`; it cannot construct current `Authority` or
`Proof<PreviousWriterCannotWrite>`. A backup can construct a recovery candidate;
it cannot promote itself. A model council can supply review evidence; it cannot
mint authority.

This is the small language-design contribution: epistemic modality and
authority are constructor/evaluator obligations, not prose fields attached to
a receipt.

### 14.2 Durable epoch and expiring writer lease

The state database cannot safely be its own only fencing authority. Each
single-writer surface therefore needs two distinct records outside the writer's
local disk:

```text
AuthorityEpochRecord = {
  surface,
  authority_epoch,
  writer_node_uid,
  registry_generation,
  parent_epoch_record_sha256,
  created_at,
  previous_fence_witness_digest
}

WriterLeaseGrant = {
  surface,
  authority_epoch,
  epoch_record_sha256,
  writer_node_uid,
  registry_generation,
  lease_id_digest,
  lease_kv_revision,
  issued_at,
  lease_duration
}
```

The immutable epoch record body contains
`{schema, surface, authority_epoch, parent_epoch_record_sha256,
writer_node_uid, registry_generation, created_at,
previous_fence_witness_digest}`. Its envelope uses the same JCS,
domain-separated SHA-256, Ed25519 key-ID, rotation, and revocation rules as
section 9.3, with an authority-controller signing key named by the identity
owner. The short lease binds `epoch_record_sha256`; a numeric epoch without its
signed chain record is invalid. The epoch record immutably chooses exactly one
writer. Lease renewal may extend only that writer and epoch. Changing the
writer—even after KV expiry—requires a new epoch record, old-writer fencing and
credential revocation, and waiting out the prior maximum lease.

The proposed initial coordinator has two layers:

1. **Durable manual epoch:** the authority controller writes a signed,
   create-only object at
   `authority/<surface>/epochs/<20-digit-epoch>.json` in the independent
   versioned store. Transfer reads the highest contiguous valid epoch and creates
   exactly `epoch + 1` using a backend conditional create (`If-None-Match: *` or
   equivalent), then read-back-verifies bytes and version ID. A backend must pass
   concurrent-create and stale-read tests before use; without proven atomic
   create, enrollment is blocked. The winning signed record is copied and
   read-back-verified in an independent second failure domain **before** an
   online lease is issued. If that copy fails, no writer lease is issued and no
   higher epoch may be created. The controller retries copying the **exact
   winning signed record** with conditional create and read-back verification
   until the two stores contain the same contiguous chain. If the primary copy
   becomes unavailable first, use the registry-generation recovery procedure
   below rather than reusing or skipping the epoch.
   Both authority stores use dedicated buckets/accounts and controller-only
   credentials, separate from artifact publisher credentials.
2. **Short online lease:** a dedicated authority-controller identity—writers
   have read/renew-request scope but no KV-write scope—publishes the signed lease
   in proposed JetStream KV bucket `DS_AUTHORITY_LEASES` using revision CAS. The
   repository's transport doctrine reserves KV for ephemeral presence/leases
   (`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:305-319`). Use a 30-second
   maximum lease with renewal at 10 seconds.

The authority signing key and controller role are selected by the ratified
roster/identity owner, not by a node self-claim. The short lease is accepted only
when it binds the newest durable epoch object and its same writer. A writer
caches it only until a
monotonic local deadline derived from `lease_duration`; inability to renew makes
the writer reject mutations. Every mutation carries epoch/lease identity, and
the database advances its per-surface revision in that same transaction.
Gateways and clients reject responses from an older epoch, mismatched writer,
or expired lease. Multiple controller replicas, if later deployed, use one
leader/conditional-update discipline; each recomputes the epoch/writer binding
and cannot rebind a live epoch.

Never reuse an epoch number within one `registry_generation`. If the primary
epoch store disappears after conditional create but before the second copy,
freeze writes, revoke/fence the old store identity, ratify a higher registry
generation, seed it from the newest record present in both prior domains, and
issue no lease until the new two-copy chain verifies. A later reappearing old
store cannot rejoin the new registry generation.

This deliberately makes NATS loss a shared-write outage rather than an epoch
loss: the durable epoch survives off-broker, while the short lease expires. A
copied JSON file, Git pull interval, mtime, DNS change, process check, or ordinary
NATS message alone is not fencing. Until concurrent-create, KV-CAS, expiry,
partition, and former-writer tests pass, manual provider fencing and credential
revocation remain mandatory.

### 14.3 Initial failover policy: manual and fenced

This proposal does not admit automatic failover until reliable fencing is
implemented and partition drills pass. The initial state-primary failover
procedure is:

1. Declare the incident and freeze shared writes at clients/gateways.
2. Prove the old writer is stopped or fenced. Initial acceptable proof is
   provider power-off/fencing plus revocation of its writer credential and
   failed private-network reachability; process absence alone is insufficient.
3. Read the external authority epoch, the last independently witnessed owner
   revision, and the newest valid Litestream recovery point.
4. Restore into a clean local filesystem on the replacement node.
5. Run SQLite integrity and application invariants without opening writes.
6. Compare the recovered revision with every acknowledged receipt/effect after
   it. If any acknowledged effect is newer, keep writes disabled: query each
   external system by idempotency key; classify it `COMMITTED`,
   `PROVEN_UNCOMMITTED`, or `UNKNOWN`; reconstruct missing committed records,
   replay only proven-uncommitted operations, and require manual resolution for
   every unknown. Re-run integrity and invariants on the reconciled candidate.
7. After fencing and waiting out any prior lease, conditionally create the next
   immutable epoch record bound to the replacement writer, verify its second
   copy, then issue the new writer lease.
8. Start exactly one replacement writer and update the private endpoint.
9. Run write/read/idempotency smoke tests and publish a failover receipt.
10. Rejoin the former primary as a blank read-only candidate; never let its
    newer mtime overwrite the new epoch.

If fencing cannot be proven, remain read-only. Availability loss is safer than
two accepted writers.

## 15. Backup and restoration architecture

### 15.1 Recovery targets

These are proposed targets and remain unproven until the proof suite passes:

| State class | Proposed RPO | Proposed RTO | Recovery source |
|---|---:|---:|---|
| code release | zero only after the accepted commit exists in both required Git failure domains | 30 minutes | GitHub plus independent Git mirror |
| authority epoch record | zero after lease issuance because both required signed copies precede the lease | 60 minutes | primary conditional-create store plus independent signed copy |
| immutable generation envelopes | zero for bytes only when publication waits for every required copy; membership pointer inherits state RPO until `RECOVERABLE` witness | 30 minutes | versioned manifest stores plus reconciled state publication row |
| immutable objects | zero only when durability class requires and verifies both copies before manifest promotion; otherwise measured replication lag | 60 minutes | versioned/object-locked primary plus cross-provider copy |
| runtime SQLite | target at most 60 seconds; publish observed worst-case lag | 60 minutes | encrypted off-fleet Litestream plus clean-host restore |
| broker transport | no domain-truth RPO claim | 60 minutes to recreate | stream config plus state/idempotency owners; optional stream snapshot |
| secrets | latest independently escrowed bundle generation; rotation promotion should wait for escrow verification | 120 minutes | primary secret authority plus offline recovery identity |

### 15.2 Independent copies

- Git: the owner GitHub repository plus an independent mirror.
- Objects/manifests: versioning, object lock where available, and replication to
  a second provider/account.
- Databases: encrypted Litestream/base backup plus WAL/PITR chain outside the
  writer host and outside the primary object-account blast radius where
  possible.
- Broker: configuration in code; critical domain truth written elsewhere;
  snapshot only if replay position itself has business value.
- Mac pull: defense-in-depth cold verification, never the only off-host copy.
- Recovery keys: encrypted offline escrow, not inside the data backup they
  unlock.

### 15.3 Restore order

1. Establish clean infrastructure, private network, node identities, and time
   sanity.
2. Restore the selected secret-delivery owner, recipients, and node identities
   without starting workloads.
3. Install and admit the exact signed release manifest and platform runtime.
4. Restore the mutable-state database read-only and verify integrity.
5. Restore/verify the manifest pointer and immutable object closure.
6. Start the single state writer at a new epoch.
7. Recreate bounded NATS streams and durable consumers.
8. Rebuild projections and caches from owners.
9. Enable worker nodes one at a time.
10. Record RPO, RTO, missing data, integrity results, and operator decision in a
    restore witness.

Quarterly, perform this onto a clean host. Monthly, restore at least one random
database recovery point and one random object generation. A backup dashboard
without restore evidence remains AMBER.

## 16. Disk lifecycle and capacity recovery

### 16.1 What never belongs in a fleet mirror

- `.git` working trees and abandoned worktrees;
- virtual environments, `node_modules`, package caches, compiler caches;
- model weights unless explicitly pinned to a model-serving node;
- live database files and WAL;
- process logs without rotation;
- NATS JetStream storage copied as ordinary files;
- secrets, environment files, OAuth material, or provider credentials;
- Desktop/media archives unrelated to the node role;
- backups of another host inside a small VPS active filesystem;
- caches inside caches, generated reports, transient receipts, and temp output.

### 16.2 Proposed lifecycle controls

- current + previous release retention;
- byte and inode caps on object caches;
- logrotate/journald caps per service;
- NATS `max_age` **and** `max_bytes`;
- session/event JSONL rotation or compaction;
- object-store lifecycle for unreferenced objects and expired backups;
- preflight disk-reserve check before release build, artifact fetch, or model
  download;
- daily capacity report and alert at 75%, 80%, and 90%.

The repository's append-only event and session stores have no evident global
retention boundary (`dharma_swarm/event_log.py:1-47,112-163`;
`dharma_swarm/operator_core/session_store.py:57-67,83-118,242-270`). They must
be included in the census and lifecycle work rather than copied indefinitely.

### 16.3 Rushabdev recovery sequence

Do not delete the existing mirror merely because a Mac directory has a similar
size.

1. Freeze any creator: inventory systemd units, timers, cron, user crontabs,
   containers, tmux jobs, and remote Mac push jobs that mention `dhyana_mirror`;
   stop/disable the identified creator under a separate approved action and
   verify it stays stopped.
2. Because the root is full, stream deterministic file manifests off-host for
   the Rushabdev directory and Mac cold copy: relative path, size, and SHA-256
   for every regular file; record unreadable paths and symlinks separately. Use
   a filesystem snapshot or two stable passes to detect concurrent mutation.
3. Compare manifest roots and investigate every mismatch.
4. Open representative critical files from the Mac copy and verify that its
   storage is healthy.
5. Copy the manifest and verification witness to the independent object/backup
   authority.
6. Rename the VPS directory to a quarantine name on the same filesystem as a
   namespace barrier only. It frees zero bytes, does not invalidate open file
   descriptors, and does not stop a process from recreating the old path.
7. Obtain explicit operator approval for deletion after the validation receipt.
8. Re-run `df`, service health, and scheduled-job census; keep the proof of what
   was removed and whether it remains recoverable.

Deletion is intentionally outside this reference and requires a separate,
scoped operator action.

## 17. Fleet convergence and health contract

Every node should expose an expiring signed **projection** similar to:

```json
{
  "body": {
    "schema": "dharma.fleet.node_status.v1",
    "node_uid": "<roster-node-uid>",
    "profile_version": 3,
    "fleet_coordinate_digest": "sha256:...",
    "status_sequence": 812,
    "issued_at": "2026-08-14T00:00:00Z",
    "expires_at": "2026-08-14T00:02:00Z",
    "challenge_nonce": "...",
    "reported_ready": true,
    "release": {
      "source_commit": "...",
      "lock_sha256": "...",
      "runnable_artifact_sha256": "...",
      "admitted": true
    },
    "observed_authority": {
      "surface": "runtime",
      "epoch": 7,
      "writer_node_uid": "<state-writer-node-uid>",
      "lease_id_digest": "sha256:..."
    },
    "state": {
      "revision": 99127,
      "mode": "read_only_projection",
      "age_seconds": 8
    },
    "manifest": {
      "root": "sha256:...",
      "generation": 184,
      "closure_verified": true
    },
    "cache": {
      "bytes": 1728000000,
      "cap_bytes": 2147483648,
      "pinned_bytes": 1200000000,
      "corrupt_objects": 0
    },
    "filesystem": {
      "use_percent": 62,
      "free_bytes": 44000000000,
      "reserve_satisfied": true
    },
    "secrets": {
      "generation": 12,
      "recipient": "<roster-node-uid>"
    },
    "backup": {
      "last_verified_restore_receipt": "sha256:..."
    }
  },
  "signature": {
    "key_id": "<enrolled-node-signing-key>",
    "algorithm": "ed25519",
    "body_hash": "sha256:...",
    "value": "..."
  }
}
```

Compute `body_hash` as
`SHA256(UTF8("dharma.fleet.node-status.v1\0") || RFC8785(body))` and sign a
domain-separated payload containing the body hash, node UID, status sequence,
and expiry.

Verification rejects an unknown/revoked key, bad body hash, repeated or
nonmonotonic status sequence, wrong challenge nonce, or expired envelope. The
signature authenticates what the node reported; `reported_ready`,
`closure_verified`, and `observed_authority` remain self-attested projections.
Compare them with the roster, external `AuthorityEpochRecord` and
`WriterLeaseGrant`, state-owned publication
row, object closure, and independent restore receipts.

Fleet-level convergence requires:

- every ready node's source commit/lock and release-manifest digest match the
  desired release, and its platform runtime matches an allowed entry;
- every ready node knows the same current state writer and authority epoch;
- each state projection meets the required revision or remains within its
  service-specific allowed-staleness policy;
- every ready node verifies the same manifest root;
- node pin closures are complete;
- no two nodes report the same single-writer surface; such a conflict is an
  incident detector, while the external lease and write-path rejection are the
  fencing proof;
- disk reserves are satisfied;
- backup freshness and last restore witness meet policy;
- any drift has a typed reason: `UPGRADING`, `OFFLINE_ALLOWED`, `STALE`,
  `DISK_PRESSURE`, `AUTHORITY_CONFLICT`, `CORRUPT`, or `BLOCKED`.

## 18. Failure behavior

| Failure | Proposed response | Unsafe response |
|---|---|---|
| object store unavailable | serve verified pinned cache; reject uncached reads with explicit outage | invent empty files or promote cache to authority |
| corrupt cached blob | quarantine, emit receipt, refetch, verify | serve because filename matches |
| corrupt remote blob | block generation, use prior complete generation, restore clean version | overwrite digest key silently |
| manifest publish interrupted | keep prior pointer; leave unreferenced objects for grace-period GC | expose partial generation |
| state writer unreachable | shared writes fail closed; reads use labeled projection within TTL | let every node write locally |
| old writer returns after failover | reject old epoch; rebuild/rejoin read-only | select by latest mtime |
| NATS unavailable | preserve state/idempotency; report transport unavailable; shared writer stops when its lease expires | write filesystem inbox and claim live delivery |
| authority record store unavailable | issue/renew no epoch or lease; shared writer stops when its lease expires | elect from node self-claims or mtime |
| node disk high watermark | stop prefetch/build; evict unpinned cache | delete current release, DB, or pinned closure |
| secret revoked | service loses access and reports generation mismatch | fall back to a shared fleet credential |
| Mac offline | fleet continues; Mac catches up read-only on return | make Mac an implicit quorum member |
| clock skew | order by authority epoch and owner revision, display skew warning | use timestamp for winner selection |

## 19. Rollout plan

No phase begins until the preceding exit gate has evidence. Dual-read and hash
comparison are allowed; ambiguous dual-write is not.

Lifecycle terms are distinct: **inventoried** means read-only facts captured;
**profiled** means identity/role/budget adopted; **installed** means inactive
software present; **canary** means bounded traffic behind a rollback gate; and
**enrolled** means the node passes its role's coordinate and proof gates.

### Phase 0 — freeze evidence and recover safety margin

**Actions**

- capture fresh capacity, inode, service, process, timer, database, and path
  census on all four nodes;
- identify every job that copies whole trees;
- validate the Rushabdev Mac cold copy and reclaim storage under a separate
  approved cleanup action;
- rotate/redact any credentials found in logs or session artifacts before
  building new synchronization paths.

**Exit gate**

- Rushabdev has an operator-selected emergency margin and no new nonessential
  writes; formal reserves are adopted in Phase 1;
- no unknown full-tree mirror job remains active;
- cleanup has a recoverability witness.

**Rollback**

- restore only from the validated cold/object copy; do not restart the old
  mirror job.

### Phase 1 — authority and storage registry

**Actions**

- ratify a fleet node roster or equivalent owner;
- add node profiles and one database/path classification registry;
- label every state surface with writer, readers, backup, retention, and
  failover mode;
- reject duplicate writer declarations mechanically.

**Exit gate**

- zero unclassified mutable stores in the selected migration scope;
- zero surfaces with two writers;
- registry validates and cites its owner module;
- each profiled node's whole-disk envelope and reserve fit fresh census data.

**Rollback**

- remove the registry from candidate consumers and return to read-only
  inventory; do not change a live writer or restore an old mirror job.

### Phase 2 — off-fleet recovery first

**Actions**

- point Litestream at an independent S3-compatible target;
- enable encryption, versioning, retention, and freshness alerts;
- restore onto a clean temporary host and run integrity/application checks;
- establish independent Git and recovery-key copies.

**Exit gate**

- measured RPO/RTO witness for `runtime.db`;
- primary-host deletion can be recovered without its disk.

**Rollback**

- stop the new replica process and revoke its scoped credentials; leave the
  source database and prior backup path untouched until the new restore proof
  is accepted.

### Phase 3 — converge immutable releases

**Actions**

- converge all provider consumers on the existing `api_keys.py`/single-key-home
  loader and remove bypass paths;
- implement and canary the selected per-node identity/secret-delivery backend,
  signed bundle generation, anti-rollback, rotation, recovery, and revocation;
- install the stable release runner/controller on all nodes;
- build separate admitted macOS/Linux runtimes from the same SHA/lock;
- retain current + previous only;
- repair and prove container provenance before using compose as a release path.

**Exit gate**

- every enrolled node reports the same release-manifest/source/lock identity,
  its allowed platform runtime, and clean admission;
- retained-old-credential and old-bundle revocation drills pass on one canary;
- rollback to previous passes on one canary.

**Rollback**

- atomically reactivate the previous signed release manifest; schema-changing
  releases require proven backward compatibility or a forward recovery plan
  before canary activation. Disable the new secret backend only after restoring
  the prior loader path without widening credential scope; never restore a
  revoked credential.

### Phase 4 — external immutable objects and thin caches

**Actions**

- implement the SHA-256 object adapter behind existing artifact manifests;
- implement node pin sets, `.partial` download, digest verification, atomic
  rename, quarantine, byte/inode quotas, and LRU GC;
- publish read-only generation manifests while existing paths remain primary;
- canary on the Mac first; use Rushabdev as the small-node pressure canary only
  after its reserve gate passes.

**Exit gate**

- old and new reads hash-identically for the canary corpus;
- disk-fill test evicts only unpinned cache;
- interrupted upload/publish never exposes a partial generation.

**Rollback**

- repoint readers to the previous path adapter/generation; keep uploaded
  immutable objects for the GC grace window and disable the new resolver without
  deleting evidence.

### Phase 5 — single shared state service

**Actions**

- deploy the two-copy durable epoch stores, authority controller, and bounded
  `DS_AUTHORITY_LEASES` KV; prove concurrent epoch create, controller partition,
  stale-KV restore, lease expiry, and same-epoch rebind denial before cutover;
- place the selected runtime DB locally on the state-primary;
- route other nodes through authenticated, idempotent state operations;
- build read-only projections and staleness labels;
- freeze old writers, record cutover epoch, then enable the new writer once.

**Exit gate**

- exactly one writer accepts mutations;
- the active writer rejects expired/mismatched leases and every direct DB bypass;
- old paths are read-only or retired;
- state/API and backup positions reconcile;
- partition and former-primary restart tests pass.

**Rollback**

- before the first accepted new-writer mutation, restore the old endpoint and
  writer only after the write barrier is explicitly released; after any new
  mutation, freeze both paths and reconcile forward from receipts/idempotency—do
  not blindly reactivate the old database. Schema changes need an accepted
  backward/forward compatibility matrix and checkpoint.

### Phase 6 — enroll remaining nodes and remove legacy mirrors

**Actions**

- promote installed/canary nodes to enrolled profiles one at a time in
  dependency order: selected state primary, Agni transport, Rushabdev worker,
  then Mac operator client;
- disable and archive legacy sync configuration with owner, checksum, date, and
  removal gate; remove it only in a later scoped action after the rollback
  window;
- update operator runbooks and dashboards to display the fleet coordinate;
- retain compatibility mirrors only where a named consumer still exists.

**Exit gate**

- every active service uses an owner, projection, or cache path intentionally;
- no bidirectional shared-state synchronization remains;
- all four nodes pass the proof suite applicable to their role.

**Rollback**

- unenroll only the failing role, restore the prior read path or archived
  compatibility configuration in read-only mode, and preserve the newest owner
  data; any writer rollback follows the stricter Phase 5 reconciliation rule.

## 20. Proposed promotion proof suite

This proposal remains **HOLD / NOT READY** until these drills produce command
logs, exit codes, artifacts, and postconditions on the real topology:

1. Partition the current writer; prove at most one side accepts shared writes.
2. Fail over, then restart the fenced former primary; prove its old epoch is
   rejected.
3. Disconnect each node; prove cached reads and offline-promotion denial match
   policy.
4. Fill Rushabdev past the high watermark; prove only unpinned cache is evicted
   and the reserve remains.
5. Kill blob upload and manifest publish at every boundary; prove readers see
   only complete generations.
6. Corrupt one cached and one remote object; prove rejection, quarantine, and
   recovery.
7. Crash the SQLite owner during a transaction; prove database recovery and
   backup consistency.
8. Restore a selected point in time to a clean host and compare state revision
   with domain receipts.
9. Revoke one node identity and every credential it could read; prove old
   identity/tokens lose access and independently scoped unaffected nodes retain
   access.
10. Destroy or quarantine the authority host and restore the full system within
    the proposed RTO.
11. Introduce clock skew; prove epochs/revisions, not timestamps, order state.
12. Rejoin a node with a newer wall-clock file but older epoch; prove it remains
    a proposal.
13. Corrupt the active release or dependency lock; prove admission fails and
    previous release rollback works.
14. Lose NATS while state remains healthy; prove no filesystem fallback is
    reported as live delivery.
15. Race two authority transfers and two manifest publishers; prove conditional
    epoch create, KV revision CAS, expected-parent checks, and stale signed
    replay admit one winner. Kill the primary epoch store before and after the
    second-copy verification; prove no lease precedes two durable copies and a
    failed copy retries the exact epoch rather than skipping it. Run duplicated
    controllers, restore stale KV state, and attempt sequential same-epoch
    leases for different writers; prove rebind is impossible.
16. Inject crashes at object upload/read-back, envelope storage, DB publication
    candidate transaction, durability-witness copy, activation CAS, outbox
    publish, NATS delivery/ACK, domain commit, and API reply; prove each
    intermediate state reconciles without a duplicate effect. Kill the DB host
    after each database commit but before Litestream frame push and prove the
    PENDING candidate never activates while a RECOVERABLE candidate can be
    reconstructed exactly.
17. Attempt direct database writes from every censused legacy caller and OS
    identity after cutover; prove only the state service can open it writable.
18. Test API method authorization, replay/expiry, idempotency-key payload
    conflict, schema mismatch, rate limit, bounded queue, and overload behavior.
19. Inject NATS duplicate, reorder, redelivery, poison/DLQ, and lost ACK after
    domain commit; prove receipts/idempotency preserve the truth levels.
20. Race cache fetch, reservation, GC, and reads; exhaust bytes and inodes
    separately; grow `.partial` and quarantine; prove reserve and pinned objects
    survive. Race remote publication against deletion claim and exact-version
    delete; prove the serialized tombstone admits either publication or deletion,
    never deletion of a newly referenced object.
21. Fuzz path traversal, percent decoding, Unicode normalization, case
    collisions, symlink/hardlink, permissions, oversize fields, duplicate JSON
    keys, and malformed manifest signatures across macOS/Linux.
22. Exercise release and database schema forward/backward compatibility,
    including rollback after a schema-changing write and corrupt toolchain
    attestation.
23. Test compromised, revoked, unknown, and old signing keys; replay an expired
    node-status envelope and an old-but-valid manifest from a prior epoch.
24. Revoke a node while it retains its old private key, ciphertext, decrypted
    secret, provider token, and session; prove each access path is denied.
25. Delete the primary object account, delay secondary replication, lose one
    backup key, and exercise immutable-retention controls; measure actual RPO/RTO.
26. Force WAL growth/checkpoint pressure and restore every classified mutable
    store, not only `runtime.db`.
27. Suspend/resume and reboot nodes, jump clocks in both directions, and lose
    trusted time; prove monotonic TTL and fail-closed restart behavior.
28. Re-enable a retired mirror from systemd, cron, launchd, tmux, container, or
    remote push after cutover; prove the census/guard detects and blocks it.
29. Exhaust JetStream account/file ceilings, logs, scratch/build reservations,
    and database/WAL envelopes independently and concurrently; prove reserve,
    explicit overload behavior, and non-eviction of owner state.

## 21. Implementation slices

Build in small, independently challengeable slices and reuse existing owners:

| Slice | Deliverable | Reuse | Proof |
|---|---|---|---|
| F0 | read-only `fleet inventory` and database/path registry generator | current owner modules and node probes | stable inventory fixture; no mutation |
| F1 | registry validator rejecting duplicate writers, missing retention, and forbidden live-DB replication | governance check patterns | negative fixtures for every rejection |
| F1S | existing-loader convergence plus selected per-node secret delivery | `api_keys.py`, provider registry, node identity owner | anti-rollback, rotation, recovery, retained-token revocation |
| F2 | all-node signed release-manifest status/controller | release runner and runtime admission | same source/lock plus allowed platform artifacts; rollback |
| F3 | external `ObjectBackend` plus existing manifest integration | `ArtifactManifest`, `ArtifactRecord` | upload/fetch/corruption/property tests |
| F4 | bounded local cache manager | node profiles and object resolver | byte/inode/high-water fault tests |
| F5 | durable epoch objects, authority controller, and expiring KV leases | NATS lease doctrine plus selected object backend | concurrent transfer, expiry, partition, former-writer denial |
| F6 | JCS generation publisher plus two-phase candidate/durability/activation outbox and serialized GC tombstones | existing manifest fields, current state writer, runtime receipt | crash matrix, stale-parent rejection, and publish/delete race |
| F7 | authenticated state service for selected runtime operations | `RuntimeStateStore`, identity, idempotency, runtime receipt | remote write, direct-bypass denial, overload, partition |
| F8 | Litestream/restore harness | existing config and compose sidecar | clean-host measured RPO/RTO witness |
| F9 | `fleet status` convergence checker | owner records plus signed node projections | replay/freshness/drift matrix and honest nonzero exits |
| F10 | operator failover/rollback runbook and gated helper | state epoch/fencing proofs | former-primary restart and effect-reconciliation drill |

No slice creates a second artifact ontology, receipt ledger, command ledger, or
transport. Generation envelopes are a fleet index over existing
`ArtifactManifest`/`ArtifactRecord` identities, and node status is a disposable
projection. Convergence, corruption, rotation, publication, and failover events
use the existing `RuntimeReceipt` envelope and correlation/idempotency fields
(`dharma_swarm/runtime_state.py:252-282,715-728`) with versioned
`receipt_type`/payload schemas. A restore witness may be a separate evidence
document, but it is not a competing live receipt owner.

## 22. Acceptance criteria

This architecture is implemented only when all are true:

- [ ] A ratified node/profile owner identifies the Mac and all three VPSes,
      with role, capacity policy, writer eligibility, and current contact
      evidence.
- [ ] Every shared path is classified by state class and owner.
- [ ] Every mutable database has exactly one writer and a tested recovery path.
- [ ] No live DB/WAL, secret, cache, venv, log tree, worktree, or full home
      directory is mirrored.
- [ ] Every node runs the same admitted release identity with platform-specific
      runtime attestation.
- [ ] Large immutable artifacts live under SHA-256 identity in independent
      object storage.
- [ ] Generation manifests publish atomically and stale-epoch promotion fails.
- [ ] Rushabdev operates with a hard cache cap and required free-space reserve.
- [ ] Agni and every NATS stream have byte and age limits.
- [ ] Offline nodes are visibly stale and cannot advance shared truth.
- [ ] Secrets are per-node, least-privilege, revocable, and excluded from shared
      storage and logs.
- [ ] Backups restore on clean infrastructure within measured RPO/RTO.
- [ ] Former-primary restart, partition, disk-fill, corruption, clock-skew, and
      total-restore drills pass.
- [ ] `fleet status` reports release, epoch/revision, manifest root, authority,
      staleness, cache pressure, backup age, and blockers without overclaim.
- [ ] Legacy full-tree sync jobs and unowned compatibility mirrors are retired
      after a documented rollback window.

## 23. Rejected alternatives

| Alternative | Decision | Reason |
|---|---|---|
| Bidirectional Syncthing/rsync for all of `~/.dharma` | reject | cannot provide transactional ordering or split-brain prevention; copies DB/WAL, secrets, caches, and logs together |
| Git for runtime state | reject | Git orders reviewed immutable source changes, not live claims, leases, or database transactions |
| NFS/shared POSIX directory for SQLite | reject | WAL/local locking boundary is incompatible; one API writer is clearer and safer |
| Object-store/FUSE mount as the live filesystem | reject for authority | useful as read convenience only; object semantics do not supply DB locking or atomic multi-object promotion |
| NATS Object Store for every large artifact on every broker peer | reject as default | replicated broker storage crowds small nodes; external content-addressed storage with refs is more controllable |
| Mac as automatic primary/quorum member | reject | operator sleep/roaming/NAT reduce availability; keep it client/verifier/recovery target |
| Three-way automatic SQLite multi-primary | reject | no safe conflict merge for transactional state |
| Immediate PostgreSQL/consensus cluster | defer | unnecessary until measured concurrency/HA requirements justify its operational burden |
| Full copy on every node with periodic cleanup | reject | cleanup races growth; storage cost remains tied to the largest corpus |

## 24. Operator quick sequence

The shortest safe route from the current estate to the target is:

```text
1. Measure and classify; do not sync.
2. Recover Rushabdev disk with checksum-backed, approved cleanup.
3. Put SQLite recovery off-fleet and prove restore.
4. Converge immutable code releases on all nodes.
5. Put large immutable bytes in external SHA-256 object storage.
6. Give small nodes pin sets plus hard cache/reserve budgets.
7. Route all shared mutations through one state writer/API.
8. Publish generations under the current lease; advance epoch only on a fenced
   writer transfer.
9. Enroll one node at a time; never dual-write.
10. Break it deliberately: partition, disk-fill, corruption, failover, restore.
```

That yields one shared reality without pretending that four heterogeneous
machines should have four identical disks.

## 25. Source and verification map

| Concern | Current source/evidence |
|---|---|
| document ownership and live-state boundaries | `docs/AGENTS.md:13-49` |
| runtime truth and WAL | `dharma_swarm/runtime_state.py:1-6,30,437-454,1209-1218` |
| persistence role vocabulary | `docs/governance/ANTI_SLOP_RULES.md:41-63` |
| runtime receipts and idempotency | `dharma_swarm/runtime_state.py:252-282,715-742` |
| artifact checksums and lineage | `dharma_swarm/artifact_manifest.py:23-28,44-89,117-190,205-234` |
| deterministic manifest serialization | [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785) |
| local UUID artifact storage | `dharma_swarm/engine/artifacts.py:59-128`; `dharma_swarm/artifact_store.py:18-42` |
| immutable release admission | `scripts/runtime/dharma_swarm_release_runner.sh:3-5,40-73,91-139`; `dharma_swarm/runtime_admission.py:191-268,271-353` |
| state backup proposal | `scripts/ops/litestream.yml:1-16`; `docker-compose.yml:135-153` |
| Litestream v0.3 cadence/data-loss semantics | [configuration](https://litestream.io/v0.3/reference/config/); [tips and caveats](https://litestream.io/v0.3/tips/) |
| legacy five-DB backup list | `scripts/litestream.yml:1-61` |
| local filesystem requirement for SQLite WAL | `docs/ops/RUNBOOK.md:259-270` |
| NATS authority, truth levels, retention, object references, compatibility mirrors | `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md:19-46,80-116,171-212,297-319` |
| fleet roster gap | `docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md:242-255,331-337` |
| dated field roles | `docs/ops/FLEET_FIELD_REGISTRY.yaml:1-45,83-122,161-177` |
| existing provider-key boundary and known split | `docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md:70-112`; `docs/state/BROKEN_REGISTER.md:84-93` |
| append-only lifecycle gaps | `dharma_swarm/event_log.py:1-47,112-163`; `dharma_swarm/operator_core/session_store.py:57-67,83-118,242-270` |
| capacity witness at inspected commit | `docs/reports/FLEET_CAPACITY_WITNESS_2026-08-14.md:9-101`; re-run before operational use |
