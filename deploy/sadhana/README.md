# SADHANA deployment candidate

This is a deliberately unpromoted, unmerged, time-bounded release lane. It is
not an authority source and does not promote a branch, merge a PR, transfer writer authority, expose a
public listener, spend money, or convert process health into evidence of work.

The release envelope binds one exact Git commit to the pinned
`AIKAGRYA/dharma_swarm` origin, accepted-base ancestry, an exact fully
integrated sole parent, full Git bundle, a controller-authored closed ledger of
every tracked commit-object byte,
tracked implementation packet, passed external closeout receipt, zero-dollar
budget, exact campaign end, loopback listeners, and manual-only failover.

The host topology is fixed:

- `meghadharma-cloud` is the sole writer. The supervisor works in
  `/var/lib/dharma-sadhana/workspace`; its mutable state is under
  `/var/lib/dharma-sadhana/state`.
- `agni-openclaw` receives timestamped SQLite online backups and projection
  bytes. Its writer services remain disabled and masked. A snapshot explicitly
  says `writer_authority_transferred=false`. Tailscale SSH still owns tailnet
  port 22, so this release never sends replication there. A separately
  receipted Tailscale Serve TCP handler exposes AGNI's ordinary OpenSSH daemon
  only at tailnet port 2222 (`tcp://localhost:22`); the ordinary SSH daemon then
  enforces the campaign key's forced `rrsync` command. Start, ownership, and
  stop are exact-handler transactions. Teardown uses only
  `tailscale serve --tcp=2222 off` after drift validation and never performs a
  node-wide reset.
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
  writes an authenticated HMAC envelope to the normal or emergency inbox. HTTP
  202 means request admission only, never that authority applied it. Normal
  pause/resume is view-only and unqueueable during predispatch: the API requires
  the exact current `dharma.sadhana.campaign_activation.v1` sequence-2 proof,
  release, campaign epoch, and `operator_login_sha256`, and binds the proof
  digest into the HMAC envelope. A direct POST, stale or foreign proof, or
  sequence-1 proof fails without creating a normal inbox entry. The campaign
  supervisor revalidates that same activation epoch while reconciling and, at
  the activation CAS boundary, requires both the normal and inflight inboxes to
  be empty. Emergency stop remains a separate transport and authority path; it
  is deliberately available before sequence 2 and never borrows normal-control
  authority. The independent root emergency unit stops the entire target and
  proves every campaign listener absent before attempting the best-effort
  durable stop marker or publishing an applied receipt. Marker failure never
  delays cessation: the receipt records
  `durable_stop_marker_persisted=false`, and the root-only inflight claim stays
  in place as a restart barrier while the separately enabled recovery unit
  retries the marker without rewriting the immutable terminal.
  A distinct same-origin
  `/dharma-internal/account-ui-confirmation` route can create exactly one
  fixed-path, HMAC-bound predispatch candidate. It requires the same allowlisted
  Tailscale account, exact HTTPS Origin, bearer and CSRF bindings, plus the
  immutable release SHA. HTTP 202 means only
  `CandidateRecorded<NoAuthority,NoDispatch>`; it does not attest a physical
  phone, a human identity, human presence, or server-measured client geometry.
  The v2 candidate records client-reported exact-390px/coarse-touch
  observations, a client-reported browser `isTrusted` flag from one explicit
  click, and only that both control inboxes were empty at its last
  prepublication scan. That observation is not an atomic claim about candidate
  commit or publication. Only the fixed root consumer can promote it, after
  resampling time, proving the dispatch marker and supervisor absent, and
  independently checking both normal and emergency control inboxes before the
  candidate read and again after freezing it. Any control write seen at either
  root inventory rejects promotion without consuming that request.
- G10 held-out evaluation is delegated through fixed-path request and terminal
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
  proves the exact observer process, loopback listener, resolved-path
  isolation, and twenty consecutive accepted `/api/health` responses while the
  supervisor MainPID remains zero. A later, non-enabled
  `dharma-sadhana-dispatch.target` runs the no-effect dispatch gate, which
  revalidates that health receipt plus the runtime-staging, Unix-ingress,
  authenticated-account UI confirmation, rollback, and two-reader
  bearer-custody receipts. Only its immutable `dispatch-enabled.v1.json` marker makes the
  supervisor runnable. The marker does not itself resume the campaign. Once
  started, the supervisor must first acquire sole-writer custody, prove a
  read-only boot with an empty executor pool, reconcile the exact seven-seat
  roster and its authority inputs, and pass the final clock, projection,
  capacity, and authenticated-account gates. Only then does it perform the
  marker-bound sequence-2 resume in-process and publish the campaign activation
  epoch consumed by normal controls. Health remains availability evidence,
  never evidence of useful work or executor liveness.
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
- `/etc/dharma-sadhana/inputs/contracts/agent-roster.v1.json`
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
The one admitted roster path is exactly
`/etc/dharma-sadhana/inputs/contracts/agent-roster.v1.json`; a duplicate roster,
alternate path, extra seat, or repeated seat name is an activation failure. The
roster, replication key, and `known_hosts` inputs arrive root-owned and mode
0600. After validating the roster's pinned digest, deploy makes only that
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
root-owned standby ACK. The writer's SSH policy additionally pins port 2222,
the bracketed `[100.79.111.89]:2222` host-key entry, public-key-only
authentication, `IdentitiesOnly`, no password or keyboard-interactive fallback,
no TTY, and a bounded connection timeout. Before dispatch, a fresh root probe
must match the live bracketed key, complete a dry-run rsync, and prove arbitrary
commands, an interactive shell, and an out-of-root rsync destination all fail.

The separately hash-pinned immutable input set carries the objective, ten goal
contracts, roster, telos and topology warrants, bootstrap and Day-1 evidence,
and the pre-bootstrap observed-input source. It also carries the private G10
evaluator and policy bytes, but never the verifier secret. The
runtime database remains the only mutable campaign truth store. The three
runtime manifests under
`/etc/dharma-sadhana/inputs/runtime/sadhana-10-20260823/` cannot be presealed:
they bind task IDs and creation hashes that exist only after bootstrap. The
service-owned preparation transaction consumes the byte-identical staged
release-admission projection at
`/var/lib/dharma-sadhana/state/release-admission/staged-release-admission.v1.json`,
writes only inside the service-owned state root (the fixed
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
static input-set manifest and archive, an exact `tracked-source.manifest.json`
rendered from the release commit's blob objects (never the mutable index or
worktree), and the exact Linux x86_64 `uv==0.11.2` wheel.
The seal command requires the exact integration-parent SHA and refuses a merge
commit or any additional release commit. The wheel is fixed to SHA-256
`be4bb136bbc8840ede58663e8ba5a9bbf3b5376f7f933f915df28d4078bb9095`.
Transfer the admitted envelope files out of band to a private bootstrap root
outside `/opt/dharma-sadhana` and `/var/lib/dharma-sadhana`. AGNI receives only
the shared release artifacts; never transfer the private input-set manifest or
archive, verifier assignment, writer credentials, roster, or private
replication key there. Megh receives the shared artifacts plus the exact input
set. Before any host preparation, make each host's bootstrap directory and
artifacts privately owned by a dedicated non-root verification identity, clone
the bundle into a clean checkout as that identity, and run `verify` there. Root
verification is deliberately rejected. `verify` also clones the transferred
bundle into a disposable directory, checks out the exact manifest SHA, restores
the pinned origin identity, and re-runs SHA, ancestry, packet, receipt,
tracked-source, and role gates without changing runtime state. Pass `--repo`
against the clean non-root checkout for the additional local-source equality
gate. Only after it passes may root take custody of that checkout and artifacts;
the controller checkout used for every later root command must be root-owned and
not writable by the verification identity.

The remote order is mandatory: completely prepare, deploy, clock-prove, and
activate the fenced AGNI standby before preparing Megh. On each host,
`prepare-host` is a hostname-bound, root-only phase that
first receipts the exact pre-existing empty `/opt/dharma-sadhana` and
`/var/lib/dharma-sadhana` scaffolding, then creates the fixed non-root accounts
and campaign-owned directory roots. After the service and oracle identities
exist, it also creates the exact persistent oracle topology:
`/var/lib/dharma-sadhana/oracle-inputs` as
`dharma-sadhana:dharma-sadhana` mode 0700,
`/var/lib/dharma-sadhana/oracle-claims` as `root:root` mode 0700,
`/var/lib/dharma-sadhana/oracle-runs` as `root:dharma-sadhana-oracle` mode 0710,
`/var/lib/dharma-sadhana/oracle-quarantine` as `root:root` mode 0700, and
`/etc/dharma-sadhana/receipts/oracle` as `root:root` mode 0700. A symlink,
foreign owner, or mode drift is a preparation failure; these roots are not
deferred to a namespace-visible service start. `prepare-host` does not
install units, create a writer marker, modify Tailscale, activate a process,
install a secret, or transfer authority. Root may then install the scoped
external inputs. Both verifier and operator-control credential installers read
exact bytes from standard input; only the authorized verifier command may
receive the current process assignment, and only on Megh.
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
hash-pinned uv executable without trusting host `PATH` or pip, creates the
copied Python environment with `/usr/bin/python3.12 -m venv --copies .venv`,
then runs pinned `uv sync --active --frozen --no-dev` and builds the dashboard.
After every lifecycle command exits and the solo-process proof succeeds, it
converges only uv 0.11.2's exact empty `.venv/.lock` inode from `0666` to
owner-private `0600` before trusted candidate reads. It rejects every broken
or venv-escaping link. After the final tracked-checkout proof and second
solo-process proof, it removes only pinned Next 16.3.0's exact 288-byte ignored
`dashboard/next-env.d.ts` declaration. It then admits pinned uv 0.11.2's exact
ignored six-file `dharma_swarm.egg-info` directory by producer-specific modes,
sizes, bytes, ownership, and single-link custody, and removes only those bound
inodes and their exact directory before Git metadata removal; arbitrary
source-root output remains rejected. It then renders exact-SHA units. There is no
`deploy --activate` option: deployment stages and completes
only the no-effect preparation boundary. After installing the writer unit it
reloads systemd, proves the preparation oneshot is static (not enableable),
starts it, and requires its successful active/exited state. That oneshot creates
or replays the exact campaign session in paused sequence 1 and publishes the
initial canonical projection at
`/var/lib/dharma-sadhana/projection-source/mission-projection.json`. Root then
validates the projection contract, the prepared manifests and receipt, the
empty global claim/run rows, and `NoProviderDispatch`; status or process health
cannot substitute for those proofs. `activate-predispatch`, not the operator,
later publishes the runtime binding, finalizes disabled runtime staging, and
refreshes those paused bytes before it may start infrastructure. Staging does
not create the writer marker and refuses a pre-existing marker, so copied units
cannot become an unbound runnable interval. Git, Python, npm,
Node, SSH, rsync, systemctl, useradd, and Tailscale are invoked through the
absolute paths probed on both hosts; build subprocesses receive a sterile
environment. Writer activation also treats unit-file bytes as insufficient
evidence of effective systemd authority. Before any writer lifecycle unit is
enabled, after the predispatch units start, and again immediately before
dispatch marker creation or replay, the root gate binds the immutable release
templates to the installed main fragments, requires the exact `FragmentPath`,
empty `DropInPaths`, and `NeedDaemonReload=no`, and compares the loaded control
and dashboard identity, capability, sandbox, write-path, environment-file,
expanded non-secret environment, and ordered `ExecStartEx`/`ExecStartPreEx`
argv and privilege flags. It checks the loaded state, performs a root
`daemon-reload`, and checks it again; each writer service also performs the
same loaded-state check in `guard-start`. Thus a stale drop-in or a
mutate/reload/restore manager cache cannot hide behind valid main-unit bytes.
Writer activation then proves both fixed IPv4 loopback ports are
bindable, so it cannot replace the existing service on `127.0.0.1:8420` or a
new occupant of `18420`/`18421`. It separately proves the dashboard Unix socket
has no TCP or alternate local ingress. Before dispatch it also requires a fresh
strict-host-key AGNI proof that the complete 2,880-snapshot immutable series
fits above the 8-GiB reserve, and binds that proof to the still-disabled
writer's exact two database sizes and projection size. The renewable v2 proof
includes an ordered append-only ledger of every existing
`{snapshot_id,snapshot_digest,tree_digest}`. A replacement must be newer and
retain the prior ledger as an exact prefix; deletion, substitution, tree drift,
foreign entries, or a count-only claim is rejected, while a verified appended
snapshot can be admitted by a fresh proof. No retention or silent deletion is
permitted. Its canonical newline-terminated transport is hard-capped at 1 MiB
on producer validation, controller stdin, prior-receipt replacement, and every
on-disk guard read. The fixed three-field ledger is bounded at 2,880 entries;
the maximum shape is below that cap, so the contract never truncates the series
or raises the unrelated general JSON limit. A passing capacity proof still
requires at least one remaining snapshot slot, making 2,879 the final renewable
PASS state; a future 2,880-entry completion attestation would require a distinct
schema rather than pretending capacity remains. Each snapshot independently
binds its ID to the exact campaign UTC second and release prefix, enforces the
timebox, transitions to a
root-owned nonwritable local final, persists a durable outbox intent, and fsyncs
all content/custody metadata before its published directory entry. Its v2
manifest may claim only `stable_committed_point`: the writer retains one
long-lived connection and path-identity witness for each SQLite owner, compares
each same-connection `data_version` before and after both online backups, and
compares the projection inode, metadata, and digest across the same window. It
then rebuilds the joined mission view from the copied databases and requires
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
only when the live exact config still equals the ownership receipt, then
publishes a durable release-bound stop receipt; drift leaves every handler
untouched for manual review. This check deliberately covers both
Tailscale configuration representations: `get-config --all` must show no named
Services and the raw `status --json` TCP/Web map must be empty before start and
exactly receipt-equal before reset. The probed `tailscale` runtime is separately
pinned to version `1.102.2`; version drift also preserves the live config for
manual review rather than exercising changed reset semantics.

AGNI uses a distinct, narrower Serve contract. Its raw status must transition
from `{}` to exactly `{"TCP":{"2222":{"TCPForward":"localhost:22"}}}` while
the named-Service representation remains empty. The standby unit records intent
before the effect, ownership only after that exact live poststate, and on stop
removes only port 2222 after proving the handler still equals its receipt. It
then proves the poststate is the prestate minus that one owned handler. Missing
ownership, any extra handler, named-Service drift, version drift, or an
unexpected empty route is preserved for manual review rather than broadened
into destructive Tailscale authority.

Staging derives `/etc/dharma-sadhana/receipts/releases/SHA/runtime-prep.env`
from the validated sealed input-set manifest, the Gitless admission, and only
the four allowlisted operator/cadence values in the closed root-custodied
`supervisor.env`. It stores that exact projection root-owned mode 0600 beside
the immutable release receipts. Systemd reads only this nonsecret file before
dropping to `dharma-sadhana`; no service-writable configuration, verifier
secret, HMAC value, provider credential, or HMAC path/hash enters the
preparation process.

The release-owned activation sequence is:

1. Complete AGNI first. Run non-root `verify --role standby` without either
   input-set argument, restore the verified checkout and shared artifacts to
   root custody, and run `prepare-host --role standby`. Install only the exact
   deployment `known_hosts` bytes and replication public key, then run
   `deploy --role standby` without input-set arguments. Over the pinned
   strict-host-key controller channel, publish a fresh
   `clock-proof --role standby` and immediately run
   `activate-standby --role standby --release-sha SHA`. The transaction masks
   and stops every writer lifecycle unit before it enables the independent
   stop timer and standby target. That target requires the separately
   receipted port-2222 Serve bridge plus the receiver path and timer. Capture
   the exact Serve ownership receipt digest over the same strict channel;
   activation explicitly records that end-to-end replication is still
   unproven. Missing, stale, mis-custodied, wrong-role, timer-drifted, or
   nonempty-Serve evidence produces no new effect.
2. Only after AGNI is fenced and live, perform Megh's non-root
   `verify --role writer` with the private input-set manifest and archive,
   restore root custody, and run `prepare-host --role writer`. Install
   `supervisor.env` before `deploy`; automatic preparation consumes it. Do not
   preinstall the roster or any partial input tree: writer `deploy` installs the
   exact roster from the sealed immutable input set and rejects a pre-existing
   partial topology. Install the deployment `known_hosts`, replication private
   key, replication/dashboard/control environments, verifier assignment, and
   the exact three operator credentials. Never put any of these values on argv
   or AGNI. Run `deploy --role writer`, then require its automatic, never-enabled
   `dharma-sadhana-runtime-prepare.service` boundary to publish the canonical
   initial projection, paused sequence 1, empty global dispatch rows, and
   `Prepared<...>:NoEffect`. Read the exact
   `.proof.parameters.config_digest` from that preparation receipt and only
   then create root-owned mode-0600 `api.env` with the same digest and the
   fixed projection bindings. These bytes grant no campaign authority by
   themselves.
3. Capture a fresh canonical AGNI capacity proof over the strict channel using
   the writer's stable runtime-database, task-database, and projection sizes;
   install and guard it on Megh. Then run
   `clock-proof --role writer --release-sha SHA --controller-utc UTC --known-hosts-sha256 DIGEST --strict-host-key-channel`,
   then immediately run `activate-predispatch --role writer --release-sha SHA`.
   The mode-0600 proof is fixed under the root preactivation receipt root and
   binds the staged admission, role, hostname, known-hosts digest, synchronized
   host clock, at-most-30-second controller skew, and byte-identical installed
   writer stop timer. It expires after 120 seconds. Activation validates it,
   internally publishes or replays the exact v2 runtime binding, finalizes the
   disabled runtime staging, restarts the static preparation oneshot, refreshes
   and copies the paused no-provider projection, and resamples the campaign
   clock before publishing any lifecycle intent. One durable transaction then
   refuses pre-existing lifecycle activity, writes its intent and exact writer
   marker, and enables and starts the campaign stop timer, emergency recovery
   path, and `dharma-sadhana.target` in that order. Its final receipt requires
   all three active and enabled while the dispatch target, dispatch marker, and
   supervisor remain absent. Crash replay revalidates that exact state; partial
   failure compensates only units owned by this transaction and removes only
   its marker. This is the no-provider-dispatch observation phase; the
   observer-health one-shot records twenty accepted 18420 responses.
4. While the supervisor MainPID is still zero, run
   `probe-dashboard-rollback`. Until sequence 2 exists, the dashboard is
   view-only for normal pause/resume and the backend also rejects a crafted
   direct POST without queueing it; emergency stop remains independently
   available. Do not record the one-shot account UI confirmation yet.
5. Renew short-lived evidence immediately before dispatch. Run
   `refresh-predispatch --role writer --release-sha SHA` with the supervisor
   still absent, obtain a fresh strict-host-key AGNI
   `dharma.sadhana.standby_capacity_proof.v2`, and install its canonical bytes
   on Megh. A renewal may only append newly verified ledger entries to the exact
   prior ledger; it cannot hide deletion, substitution, or tree drift. Guard
   that proof against the writer's stable database and projection sizes. Run
   `probe-standby-replication-route --role writer --release-sha SHA
   --standby-serve-ownership-receipt-digest DIGEST`; it must re-execute the
   bracketed host-key check, dry-run rsync, and all three forced-key negative
   probes and publish a fresh receipt. Refresh the exact writer `clock-proof`
   over the same pinned controller channel. Only after these renewable gates
   are ready, use the live private dashboard at exactly 390 CSS pixels and make
   one explicit confirmation click; the browser's `isTrusted` flag remains a
   client-reported fact, not a human-presence proof. This produces only the fixed
   `dharma.sadhana.authenticated_account_ui_confirmation_candidate.v2` under
   the control runtime; it cannot be supplied as an arbitrary controller path
   or boolean. It binds the SHA-256 of the exact allowlisted Tailscale login
   without exposing the login and explicitly records
   `physical_device_attested=false`, `human_identity_attested=false`, and
   `control_inboxes_empty_at_last_prepublication_scan=true`. The latter is a
   bounded observation, not commit-time emptiness or promotion evidence.
   Immediately run `record-account-ui-confirmation --role writer
   --release-sha SHA`, then the pathless `record-dashboard-identity --role
   writer --release-sha SHA`, and `record-operator-credential`. The resulting
   root-custodied `dharma.sadhana.authenticated_account_ui_confirmation.v1`
   and `dharma.sadhana.dashboard_identity_acceptance.v5` receipts bind the
   same release and operator-account digest. Resample the final renewable
   route, clock, capacity and projection gates as required, then dispatch while
   the ten-minute confirmation remains fresh. The candidate is immutable and
   cannot be renewed: delivery uncertainty requires inspection of its fixed
   path, and expiry requires rollback/redeployment rather than a second click
   or fabricated receipt. Once root freezes the candidate, runtime preparation
   also refuses to restore control-group write access to that sealed directory.
6. Start, but never enable, `dharma-sadhana-dispatch.target`. On both first
   creation and marker replay, its shared no-effect gate revalidates the fresh
   clock and projection receipts, renewable capacity ledger, active predispatch
   target, absent supervisor, observer identity and 20-probe receipt, dashboard
   v5/authenticated-account confirmation binding, dashboard UDS, exact private Serve/no-Funnel
   configuration, fresh proven AGNI port-2222 route, exact three-entry
   credential root, two credential copies and positive readers, service PIDs,
   oracle evidence, and runtime/staging binding.
   It resamples the clock and live gates again before it may publish or return
   the immutable `dispatch-enabled.v1.json` marker.
7. Systemd may now start the supervisor, but the marker is still only a typed
   authorization source. The campaign process acquires the sole writer lock,
   boots read-only with an empty executor pool, reconciles exactly the seven
   digest-pinned roster seats from the one admitted roster path, and validates
   every authority, oracle, clock, freshness, capacity, projection, and
   authenticated-account preflight. Immediately before its compare-and-set resume it
   requires both the normal and inflight control directories to be stably empty.
   It then applies the marker-bound PAUSED-to-RUNNING sequence-2 transition
   in-process, with `external_effect_performed=false`, and publishes the exact
   group-readable `dharma.sadhana.campaign_activation.v1` epoch. Only normal
   HMAC envelopes bound to that epoch can thereafter be admitted and reconciled;
   the emergency transport and root stop authority remain separate.

`rollback --role writer --release-sha SHA` is the executable reverse path. It
stops the deliberately static dispatch target first and proves it both static
and inactive, then disables and stops the predispatch target, emergency
recovery path, and campaign stop timer; proves every campaign process and
listener absent; removes only an unchanged campaign-owned Serve route and the
exact writer marker; retains release and snapshot evidence; records
`authority_transferred=false`; and publishes an immutable rollback receipt that
all later writer clock guards deny. Receipt replay reruns every live quiet-state
and retention check and removes no additional state. Rollback is a manual,
root-custodied fencing operation, not an automatic failover or a license to
delete retained evidence. If live Serve ownership or another quiet-state proof
has drifted, it leaves the disputed resource in place for manual review instead
of broad-resetting the node.

A host reboot is intentionally terminal and fail-closed for this bounded R2
canary. The static dispatch target is never enabled, the volatile sequence-2
activation epoch does not survive as reusable normal-control authority, and no
campaign or provider work may resume automatically. Do not manually restart
  the supervisor, reuse old account-confirmation/clock/capacity receipts, or treat retained
markers as post-boot authority. Keep the release, rollback, stop, and snapshot
evidence; fence the affected writer state; then require a new governed packet,
redeploy, and full predispatch/reactivation sequence. A reboot never transfers
authority to AGNI.

An intent-only AGNI activation crash replay may only compensate back to a
masked, disabled, authority-quiet state and remove the exact owned port-2222
handler. The Serve unit, receiver path, and reconciliation timer are `PartOf`
the standby target. At
`2026-09-01T17:15:12Z`, the independent persistent standby-stop timer disables
and stops the target, proves the Serve unit and receiver path/timer/service
quiet, removes only the unchanged owned handler, and writes a root-owned
immutable deadline marker. The marker prevents receiver restart on reboot and
never transfers writer authority.

There is intentionally no promotion or automatic-failover command. A future
failover needs its own packet proving Megh fencing, snapshot freshness and
integrity, and one explicit authority transfer before any AGNI writer marker
can exist.
