# SADHANA deployment candidate

This is a deliberately non-canonical, unmerged, time-bounded release lane. It
does not promote a branch, merge a PR, transfer writer authority, expose a
public listener, spend money, or convert process health into evidence of work.

The release envelope binds one exact Git commit to the canonical
`AIKAGRYA/dharma_swarm` origin, accepted-base ancestry, an exact fully
integrated sole parent, full Git bundle, a controller-authored closed ledger of
every tracked commit-object byte,
tracked implementation packet, passed external closeout receipt, zero-dollar
budget, exact campaign end, loopback listeners, and manual-only failover.

The host topology is fixed:

- `meghadharma-cloud` is the sole writer. The supervisor works in
  `/var/lib/dharma-sadhana/workspace`; its canonical state is under
  `/var/lib/dharma-sadhana/state`.
- `agni-openclaw` receives timestamped SQLite online backups and projection
  bytes. Its writer services remain disabled and masked. A snapshot explicitly
  says `writer_authority_transferred=false`.
- FastAPI listens only on `127.0.0.1:18420` and composes only the admitted
  immutable projection provider. Its scratch root is the separate
  `/var/lib/dharma-sadhana/api-state`.
- The Next dashboard runs as the distinct `dharma-sadhana-dashboard` identity
  and listens only on
  `/run/dharma-sadhana/dashboard/constellation.sock`; there is no TCP dashboard
  listener. Tailscale Serve is the exclusive private HTTPS ingress to that
  root-custodied Unix socket. Its build-time rewrite and server-side requests bind both
  `DHARMA_API_PROXY_URL` and `DHARMA_API_INTERNAL_URL` exactly to
  `http://127.0.0.1:18420`; `NEXT_PUBLIC_API_URL` is explicitly unset. No public
  route is installed.
- The separately authenticated operator-control API listens only on
  `127.0.0.1:18421`. The browser posts to a same-origin Next server route; its
  exact internal bridge destination is
  `http://127.0.0.1:18421/v1/operator-control/requests`, and only that server
  receives the bearer credential. The API requires the exact
  Tailscale login, Origin, and `X-Sadhana-CSRF: sadhana-10-20260823`, then
  writes a canonical HMAC envelope to the normal or emergency inbox. HTTP 202
  means request admission only, never that authority applied it. Pause/resume
  are reconciled by the campaign supervisor; the independent root emergency
  unit stops the entire target and proves every campaign listener absent before
  attempting the best-effort durable stop marker or publishing an applied
  receipt. Marker failure never delays cessation: the receipt records
  `durable_stop_marker_persisted=false`, and the root-only inflight claim stays
  in place as a restart barrier while the separately enabled recovery unit
  retries the marker without rewriting the immutable terminal.
- G10 held-out evaluation is delegated through canonical request and terminal
  files to a distinct `dharma-sadhana-oracle` identity. Its one-shot evaluator
  unit has `PrivateNetwork=yes`, a strict read-only host filesystem, empty
  capabilities, no credentials or inherited environment, and one fresh
  root-custodied output directory. It admits only the fixed evaluator, policy,
  and verifier-input path shapes and their pinned hashes. The supervisor never
  executes or reads evaluator or policy bytes and cannot accept G10 without a
  matching sandbox-probe receipt and terminal digest. A final Linux unit-context
  probe remains an activation gate; the local tests do not claim that proof.
- Dispatch is a separate, explicit systemd phase. `dharma-sadhana.target`
  starts only the observer, control API, dashboard, private Serve route, and
  durability helpers; it cannot start the supervisor. The root health one-shot
  proves the exact observer process, loopback listener, canonical-path
  isolation, and twenty consecutive accepted `/api/health` responses while the
  supervisor MainPID remains zero. A later, non-enabled
  `dharma-sadhana-dispatch.target` runs the no-effect dispatch gate, which
  revalidates that health receipt plus the runtime-staging, Unix-ingress,
  authenticated 390px tailnet, rollback, and two-reader bearer-custody
  receipts. Only its immutable `dispatch-enabled.v1.json` marker makes the
  supervisor runnable. Health remains availability evidence, never evidence of
  useful work or executor liveness.
- `dharma-sadhana-campaign-stop.timer` fires at
  `2026-09-01 17:15:12 UTC`, first stops the target and every `PartOf` process
  and replication timer, then best-effort persists the durable campaign stop.
  This order prevents a stuck state writer from delaying cessation. Its
  one-second accuracy and persistent catch-up are part of the checked contract.
  The independently guarded stop unit is not `PartOf` the target and writes a
  private `stop-enforcement-receipt.json` recording whether marker persistence
  succeeded; it never records child stdout or stderr.

## External inputs

Never commit values from these mode-0600, root-custodied files:

- `/etc/dharma-sadhana/supervisor.env`
- `/etc/dharma-sadhana/api.env`
- `/etc/dharma-sadhana/dashboard.env`
- `/etc/dharma-sadhana/control.env`
- `/etc/dharma-sadhana/replication.env`
- `/etc/dharma-sadhana/verifier.env`
- `/etc/dharma-sadhana/known_hosts`
- `/etc/dharma-sadhana/replication_authorized_key.pub` (AGNI only)
- `/etc/dharma-sadhana/credentials/{operator_bearer,control_hmac_key,tailscale_operator_login}`

The API environment must bind `SADHANA_API_PORT=18420`, bind
`DHARMA_STATE_DIR` to the separate API state root, and provide all five
`DHARMA_MISSION_SNAPSHOT_*` values. The dashboard environment points its
internal proxy at the loopback API and carries the same exact, non-secret
`SADHANA_CONTROL_EXPECTED_ORIGIN` as `control.env`; drift is rejected. Neither
file may contain a public bearer, HMAC, login, token, or control port. The
supervisor
environment supplies only contract paths, digests, bounded cadence values,
the seven-seat roster binding, and any provider credentials required by the
roster. The replication environment names only the scoped SSH key path. Values
are admitted in memory but never included in release output or error messages.
The verifier environment contains only a nonempty `OLLAMA_API_KEY`; absence is
a deployment blocker. The authorized deployment may transfer that assignment
exactly once from the current local process environment to Megh over SSH
standard input. The exact release script's `install-verifier-env --role writer`
command atomically installs it as `/etc/dharma-sadhana/verifier.env`, a
root-owned, nonlinked mode-0600 regular file. The secret never enters the
repository, bundle, snapshot, shell arguments, command tracing, output,
receipts, or AGNI. Never emit its value, hash, length, or byte content. Run that
command only on `meghadharma-cloud`; no secret is installed or replicated to
AGNI.
The three operator-control credentials are installed by the root-only
`install-control-credential --role writer --credential NAME` command from
exact stdin bytes with no trailing newline or normalization. Existing bytes
are accepted only when identical. The bearer is visible ASCII 32--512 bytes;
the HMAC key is 32--4096 exact bytes excluding CR/LF; and the login is validated
by the shared operator-control schema. Values, hashes, lengths, and contents
never enter argv, output, receipts, the Git bundle, snapshots, or AGNI.
The bearer-custody acceptance first requires the root credential directory to
contain exactly the three admitted regular, single-link, mode-0600 files; an
extra file or symlink blocks activation before any credential is read. It reads
the bearer source and dashboard/control systemd copies only in root memory and
compares both copies in constant time before and after a bounded positive-read
probe. That probe uses only the dashboard Unix socket and public identity,
Origin, and CSRF headers. On the exact connected AF_UNIX socket, Linux
`SO_PEERCRED` must match the admitted dashboard MainPID/uid/gid before the
request is sent; a rename/bind/restore pathname substitution therefore cannot
stand in for the dashboard reader. The full dashboard UDS identity and the
unique exact control MainPID/argv/uid/gid/NoNewPrivs/127.0.0.1:18421 listener
are also stable on both sides. The authenticated unsupported action is not
accepted and the normal/emergency inbox inode inventories remain unchanged.
This proves the two intended bearer readers; it explicitly does not claim
global decision or effect state. The acceptance also proves forbidden
principals cannot read either namespace and scans unit bytes, admitted process
argv/environments, service journals, release source, and browser-public
configuration for the bearer itself. It never emits the bearer or a
bearer-derived digest.

Initial staging validates the original three-file root credential custody. The
supervisor receives the HMAC key only through systemd's exact
`LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/control_hmac_key`
mapping and reads the fixed `${CREDENTIALS_DIRECTORY}/control_hmac_key` file
after checking its runtime custody. No HMAC source path, runtime credential
path, hash, size, or content enters process arguments or environment. The
dispatch namespace keeps the bearer and login readable while the original
HMAC source is inaccessible. This is not a claim that an unadmitted future
filename is namespace-invisible: the live code first requires the exact
three-name inventory and rejects any extra name before it opens an admitted
credential. The live receipt is deliberately narrow: it reproves current
bearer-copy equality and the inaccessible source boundary, while systemd owns
delivery of the HMAC credential and the private staging receipt remains the
evidence for original source custody.
The roster, replication key, and `known_hosts` inputs arrive root-owned and
mode 0600. After validating the roster's pinned digest, deploy makes only that
non-secret manifest service-owned mode 0600 because its runtime loader requires
same-euid custody; mutation therefore produces a hash-detectable self-denial,
not new authority. The SSH key and `known_hosts` remain root-owned and are
narrowed to mode 0640 for the static service group. No contents are printed.
On AGNI, deploy accepts only one bare, unique-line Ed25519 public key and
installs it with `restrict` and the forced command
`/usr/bin/python3.12 /usr/bin/rrsync -wo -no-del` in write-only mode for
`/var/lib/dharma-sadhana/snapshot-incoming`. The replication identity receives no
interactive shell, cannot delete existing snapshots, and cannot write outside
the incoming root. A root receiver validates a completed random-attempt upload,
runs the SQLite/hash restore drill, finalizes it append-only under
`/var/lib/dharma-sadhana/snapshots`, and only then publishes the exact
root-owned standby ACK.

The separately hash-pinned immutable input set carries the objective, ten goal
contracts, roster, telos and topology warrants, bootstrap and Day-1 evidence,
and the pre-bootstrap observed-input source. It also carries the private G10
evaluator and policy bytes, but never the verifier secret. The canonical
runtime database remains the only mutable campaign truth store. The three
runtime manifests under
`/etc/dharma-sadhana/inputs/runtime/sadhana-10-20260823/` cannot be presealed:
they bind task IDs and creation hashes that exist only after bootstrap. The
service-owned preparation transaction consumes the byte-identical staged
release-admission projection at
`/var/lib/dharma-sadhana/state/release-admission/staged-release-admission.v1.json`,
writes only inside the service-owned state root (the canonical
`state/runtime.db`, task database, bootstrap lock, prepared-manifest staging
directory, and preparation receipt), and performs no provider dispatch. It
publishes `sadhana-runtime-preparation.v1.json` as a typed
`Prepared<Mission,Release,InputSet,Config,TaskSet>` `NoEffect` proof. Root then
independently revalidates the frozen Gitless release, the projection and
preparation receipt, the nonsecret supervisor configuration, and all five
typed indices. `publish-runtime-binding` exact-copies the three prepared files,
derives the two preparation-selected runtime values into root-owned mode-0600
`/etc/dharma-sadhana/supervisor-runtime.env`, requires authority schema
`dharma.sadhana.campaign_authority_manifest.v4`, and publishes
`runtime-binding-activation.v2.json` last. Crash replay revalidates the source,
installed bytes, and exact runtime environment instead of trusting an existing
receipt.

## Release flow

After integration is fixed and the implementation packet has a passed external
closeout receipt, run the `seal` command from a clean exact checkout. It emits a
mode-0600 full Git bundle, copied receipt, self-digested release manifest, exact
static input-set manifest and archive, a canonical `tracked-source.manifest.json`
rendered from the release commit's blob objects (never the mutable index or
worktree), and the exact Linux x86_64 `uv==0.11.2` wheel.
The seal command requires the exact integration-parent SHA and refuses a merge
commit or any additional release commit. The wheel is fixed to SHA-256
`be4bb136bbc8840ede58663e8ba5a9bbf3b5376f7f933f915df28d4078bb9095`.
Transfer the admitted envelope files out of band, then run `verify` on each host before
any host preparation or `deploy`. `verify` clones the transferred bundle into a disposable directory,
checks out the exact manifest SHA, restores the canonical origin identity, and
re-runs SHA, ancestry, packet, and receipt gates without changing host runtime
state. `--repo` is optional and adds equality checks against a separate clean
source checkout when one is available.
From that verified checkout, run `prepare-host --role writer` on Megh and
`prepare-host --role standby` on AGNI. This hostname-bound, root-only phase
first receipts the exact pre-existing empty `/opt/dharma-sadhana` and
`/var/lib/dharma-sadhana` scaffolding, then creates the fixed non-root accounts
and campaign-owned directory roots. It
does not install units, create a writer marker, modify Tailscale, activate a
process, install a secret, or transfer authority. Root may then install the
scoped external inputs; only the authorized SSH-standard-input command above
may install the verifier secret, on Megh alone.
The deploy command stages a new SHA-named directory; it refuses to replace an
existing release. Every Git checkout, `uv`/venv execution, npm lifecycle, and
Next build runs as the dedicated unprivileged build identity in one bounded
transient cgroup with no-new-privileges, empty capabilities, an undumpable
trusted driver, and ptrace/process-vm calls denied. Once every child has exited,
the build-owned Git metadata is removed. Root freezes the tree and then rehashes
the exact tracked set through no-follow file descriptors against the sealed
commit-object ledger; it never asks candidate-owned Git metadata whether the
tree is clean. Root durably retains that ledger and the isolated-build receipt
under `/etc/dharma-sadhana/receipts/releases/SHA/`, independently verifies the
Gitless frozen tree again, and publishes `staged-release-admission.v1.json`
last. The service-owned preparation projection is byte-identical to that root
receipt. Only then may root promote the release. It extracts the
hash-pinned uv executable without trusting host `PATH` or pip, creates the copied Python environment with
`uv venv --python 3.12 --copies`, runs the frozen dependency sync, builds the
dashboard, rejects every broken or venv-escaping link, and renders exact-SHA
units. There is no `deploy --activate` option: deployment stages and completes
only the no-effect preparation boundary. After installing the writer unit it
reloads systemd, proves the preparation oneshot is static (not enableable),
starts it, requires its successful active/exited state, and root-validates its
paused receipt and prepared bytes. The separate root-binding and predispatch
commands must pass before
any target can start. Staging does not create the writer marker and refuses a
pre-existing marker, so copied units cannot become an unbound runnable
interval. Git, Python, npm,
Node, SSH, rsync, systemctl, useradd, and Tailscale are invoked through the
absolute paths probed on both hosts; build subprocesses receive a sterile
environment. Writer activation first proves both fixed IPv4 loopback ports are
bindable, so it cannot replace the existing service on `127.0.0.1:8420` or a
new occupant of `18420`/`18421`. It separately proves the dashboard Unix socket
has no TCP or alternate local ingress. Before dispatch it also requires a fresh
strict-host-key AGNI proof that the complete 2,880-snapshot immutable series
fits above the 8-GiB reserve, and binds that proof to the still-disabled
writer's exact two database sizes and projection size. No retention or silent
deletion is permitted. Each snapshot independently binds its ID to the exact
campaign UTC second and release prefix, enforces the timebox, transitions to a
root-owned nonwritable local final, persists a durable outbox intent, and fsyncs
all content/custody metadata before its published directory entry. Its v2
manifest may claim only `stable_committed_point`: the writer retains one
long-lived connection and path-identity witness for each SQLite owner, compares
each same-connection `data_version` before and after both online backups, and
compares the projection inode, metadata, and digest across the same window. It
then rebuilds the canonical mission view from the copied databases and requires
an exact match to the copied projection, campaign coordinates, latest-cycle
receipt, and explicit `reconciliation=coherent`. Any owner mutation, path
replacement, stale or wrong-schema projection, or crash-intermediate
reconciliation rejects the whole candidate. AGNI reruns that joined semantic
validator after transfer and again in the disposable restore drill before it
may receipt `standby_restore_verified=true`. Failed older replication attempts
remain visible but cannot starve later outbox items.
Activation also refuses a
nonempty pre-existing Tailscale Serve
configuration rather than replacing an unrelated route. Before its first
effect, the Serve unit publishes a durable root-owned intent under
`/etc/dharma-sadhana/receipts/preactivation/`; after the live route exactly
matches the intended empty-to-owned transition, it finalizes a separate durable
ownership receipt. A crash between those steps is replayed against live state.
On stop it re-reads that config and invokes node-wide `tailscale serve reset`
only when the live canonical config still equals the ownership receipt, then
publishes a durable release-bound stop receipt; drift leaves every handler
untouched for manual review. This check deliberately covers both
Tailscale configuration representations: `get-config --all` must show no named
Services and the raw `status --json` TCP/Web map must be empty before start and
exactly receipt-equal before reset. The probed `tailscale` runtime is separately
pinned to version `1.102.2`; version drift also preserves the live config for
manual review rather than exercising changed reset semantics.

Staging derives `/etc/dharma-sadhana/receipts/releases/SHA/runtime-prep.env`
from the validated sealed input-set manifest, the Gitless admission, and only
the four allowlisted operator/cadence values in the closed root-custodied
`supervisor.env`. It stores that exact projection root-owned mode 0600 beside
the immutable release receipts. Systemd reads only this nonsecret file before
dropping to `dharma-sadhana`; no service-writable configuration, verifier
secret, HMAC value, provider credential, or HMAC path/hash enters the
preparation process.

The release-owned activation sequence is:

1. Confirm `deploy` completed its automatic, never-enabled
   `dharma-sadhana-runtime-prepare.service` boundary. Its private-network
   non-root oneshot consumes only the sealed per-release environment, fixed
   installed inputs, and byte-identical admission projection. Its paused
   `Prepared<...>:NoEffect` receipt grants no campaign authority by itself.
2. Run `publish-runtime-binding --role writer --release-sha SHA`. Root replays
   every no-effect preparation and staged-release check, exact-copies the three
   manifests, exact-publishes `supervisor-runtime.env`, and publishes the v2
   binding receipt last.
3. Over the pinned strict-host-key SSH channel, run
   `clock-proof --role writer --release-sha SHA --controller-utc UTC --known-hosts-sha256 DIGEST --strict-host-key-channel`,
   then immediately run `activate-predispatch --role writer --release-sha SHA`.
   The mode-0600 proof is fixed under the root preactivation receipt root and
   binds the staged admission, role, hostname, known-hosts digest, synchronized
   host clock, at-most-30-second controller skew, and byte-identical installed
   writer stop timer. It expires after 120 seconds. Activation validates it
   before publishing/replaying the binding or staging and before any marker,
   Tailscale, or systemd effect. One durable
   lifecycle transaction rechecks the disabled runtime staging, refuses any
   pre-existing active or enabled lifecycle unit, writes its intent and exact
   writer marker, then enables and starts the campaign stop timer, emergency
   recovery path, and `dharma-sadhana.target` in that order. Its final receipt
   requires all three active and enabled while the dispatch target, dispatch
   marker, and supervisor remain absent. Crash replay revalidates that exact
   state; partial failure compensates only units owned by this transaction and
   removes only its marker. This is the no-provider-dispatch observation phase;
   the observer-health one-shot records twenty accepted 18420 responses.
4. While the supervisor MainPID is still zero, run
   `probe-dashboard-rollback`, obtain the root-custodied real authenticated
   tailnet observation at exactly 390 CSS pixels, then run
   `record-dashboard-identity --authenticated-probe ABS` and
   `record-operator-credential`.
5. Refresh the exact writer `clock-proof` over the same pinned SSH channel, then
   start, but never enable, `dharma-sadhana-dispatch.target`. On both first
   creation and an existing-marker replay, its one shared gate revalidates the
   fresh clock proof, active predispatch target, absent supervisor, fresh observer identity and
   20-probe receipt, dashboard UDS, exact private Serve/no-Funnel configuration,
   exact three-entry credential root, two credential copies and positive
   readers, service PIDs, and runtime/staging binding. Only then may it write or
   return the immutable no-effect dispatch marker before systemd starts the
   supervisor.

`rollback --role writer --release-sha SHA` is the executable reverse path. It
stops the deliberately static dispatch target first and proves it both static
and inactive, then disables and stops the predispatch target, emergency
recovery path, and campaign stop timer; proves every campaign process and
listener absent; removes only an unchanged campaign-owned Serve route and the
exact writer marker; retains release and snapshot evidence; records
`authority_transferred=false`; and publishes an immutable rollback receipt that
all later writer clock guards deny. Receipt replay reruns every live quiet-state
and retention check and removes no additional state.

AGNI is activated only by first recording a fresh
`clock-proof --role standby` against the installed
`dharma-sadhana-standby-stop.timer`, then running the receipted
`activate-standby --role standby --release-sha SHA` transaction. That command
masks and stops every writer lifecycle unit before enabling the standby target
and its independent stop timer; replay requires the exact final receipt and
live fence. Missing, stale, mis-custodied, wrong-role, or timer-drifted proof
causes no new effect. An intent-only crash replay may only compensate back to a
masked, disabled, authority-quiet state. The receiver path and reconciliation
timer are `PartOf` the standby target. At
`2026-09-01T17:15:12Z`, the independent persistent standby-stop timer disables
and stops the target, proves the receiver path/timer/service quiet, and writes a
root-owned immutable deadline marker. The marker prevents receiver restart on
reboot and never transfers writer authority.

There is intentionally no promotion or automatic-failover command. A future
failover needs its own packet proving Megh fencing, snapshot freshness and
integrity, and one explicit authority transfer before any AGNI writer marker
can exist.
