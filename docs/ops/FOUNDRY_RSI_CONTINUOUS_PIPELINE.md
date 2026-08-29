# Foundry/RSI candidate lane v1 operations

This is an operational reference, not promotion authority. The v1 lane moves one
graded RSI candidate into an immutable signed envelope, durably evaluates it in
Foundry, and records a terminal result. Live promotion is disabled by default and
these commands never enable it.

Runtime prerequisites are the pinned project environment with `nats-py`, a
version-compatible `nats-server`/`nats` CLI pair for disposable provisioning
proofs, and Bubblewrap for evaluator isolation. The evaluator release must be
relocatable beneath `/release` inside the sandbox and may depend only on the
allowlisted system runtime directories described below.

## Fixed contract

- Candidate subject: `dharma.foundry_rsi.candidate.v1`
- DLQ subject: `dharma.foundry_rsi.candidate.dlq.v1`
- Streams: `FOUNDRY_RSI_CANDIDATES_V1` and
  `FOUNDRY_RSI_CANDIDATES_DLQ_V1`
- Durable consumer: `foundry_rsi_evaluator_v1`
- Runtime accepts only a signed genesis `revision=1`/`submitted` envelope.
- Remote NATS endpoints require TLS. Authenticated non-TLS is allowed only for an
  explicit loopback endpoint.
- Provisioner, RSI publisher, and Foundry consumer are three distinct NKey users.
  Provisioning credentials can create, inspect, and journal-delete only this
  topology; runtime users cannot manage it. No role has live-promotion authority.
- Streams permit deletion only by the dedicated provisioner API ACL so a journaled
  failed install can be rolled back; runtime roles lack delete and purge rights.

Private NKey seeds remain in root-owned, single-link, mode-0600 regular files.
Only their public `U...` identities belong in templates, receipts, or source
control. Never put a seed in a command line, environment variable, diff, or
receipt.

## Stage authentication without replacing existing users

Generate the no-secret topology/ACL manifest first:

```sh
scripts/forge_lab/nats-foundry-rsi-topology-v1 \
  --provisioner-nkey UPROVISIONER... \
  --publisher-nkey UPUBLISHER... \
  --consumer-nkey UCONSUMER... > /root/staging/foundry-rsi-topology-v1.json
```

Do **not** concatenate that JSON or a second `authorization` block into the live
configuration. Render a complete private candidate config from the exact current
config. The renderer inserts or rotates one marked users-list block while proving
all bytes outside that block are unchanged. It always writes an exact immediate
pre-change rollback artifact and validates the complete config with
`nats-server -t -c`.

```sh
scripts/forge_lab/nats-foundry-rsi-render-config-v1 \
  --base /root/staging/exact-current-nats.conf \
  --output /root/staging/nats-with-foundry-rsi.conf \
  --rollback-output /root/staging/nats-with-foundry-rsi.conf.rollback \
  --provisioner-nkey UPROVISIONER... \
  --publisher-nkey UPUBLISHER... \
  --consumer-nkey UCONSUMER... \
  --self-test \
  --existing-user-env EXISTING_NATS_USER \
  --existing-password-env EXISTING_NATS_PASSWORD \
  --provisioner-nkey-file /run/credentials/foundry-rsi/provisioner.nk \
  --publisher-nkey-file /run/credentials/foundry-rsi/publisher.nk \
  --consumer-nkey-file /run/credentials/foundry-rsi/consumer.nk
```

The disposable proof authenticates an existing user and all three candidate-lane
identities, checks wrong-password rejection, creates the topology with the
provisioner, and exercises positive and denied publisher/consumer ACLs. It does
not contact or reload the live broker. Verify the receipt hashes before an
operator copies the staged file into place. Applying or reloading `/etc` remains
an external operator action outside this change.

For immediate configuration rollback, restore the exact `.rollback` bytes and
validate the full file before the operator reload. `--remove-managed` is only an
uninstall renderer for an unchanged configuration lineage; it is not a substitute
for the immediate pre-change rollback artifact.

## Provision, reconcile, and roll back topology

Use the provisioning NKey, never either runtime seed. `--create-missing` accepts
only an all-absent topology or a matching in-progress operation receipt. Existing
material drift and an unjournaled partial topology are refused; no stream or
consumer is silently updated.

```sh
NOW=2026-08-27T09:00:00Z
scripts/forge_lab/nats-foundry-rsi-provision-v1 \
  --endpoint nats://127.0.0.1:4222 \
  --loopback-authenticated-non-tls \
  --provisioner-nkey-file /run/credentials/foundry-rsi/provisioner.nk \
  --provisioner-public-nkey UPROVISIONER... \
  --operation-receipt /var/lib/foundry-rsi/topology-operation-v1.json \
  --now "$NOW" --create-missing
```

The private operation receipt records pre-state before mutation and is atomically
updated after each resource. A retained private sibling `flock` serializes the
complete inspect/mutate/journal transaction. Snapshot writes use unique temporary
names, so a killed writer's orphan cannot block recovery. Re-running the same
command reconciles a crash after broker mutation. To remove only resources proven
created by that receipt:

```sh
NOW=2026-08-27T09:05:00Z
scripts/forge_lab/nats-foundry-rsi-provision-v1 \
  --endpoint nats://127.0.0.1:4222 \
  --loopback-authenticated-non-tls \
  --provisioner-nkey-file /run/credentials/foundry-rsi/provisioner.nk \
  --provisioner-public-nkey UPROVISIONER... \
  --operation-receipt /var/lib/foundry-rsi/topology-operation-v1.json \
  --now "$NOW" --rollback
```

The rollback refuses drift and never deletes a resource recorded as pre-existing.

## Export and publish one actual graded candidate

Run from an immutable release environment containing the pinned project and
`nats-py`. Preparation re-exports the named graded archive row, binds its
deterministic digest into the template, signs the exact envelope, and proves the
source archive bytes did not change.

```sh
RELEASE=/opt/dharma/releases/foundry-rsi-v1
PYTHONPATH="$RELEASE/repo:$RELEASE/pydeps" "$RELEASE/.venv/bin/python" \
  scripts/forge_lab/candidate-foundry-rsi-publish-v1 prepare \
  --archive /var/lib/rsi/archive.jsonl --experiment-id RSI_RUN --candidate-id CANDIDATE \
  --envelope-template scripts/forge_lab/candidate-foundry-rsi-envelope-v1.json.in \
  --signing-key-file /run/credentials/foundry-rsi/source-ed25519.pem \
  --authority-epoch-sha256 EPOCH_SHA256 \
  --output /var/lib/foundry-rsi/envelopes/CANDIDATE.json
```

Issue a signed, envelope-bound delivery lease only after reviewing the resulting
envelope ID, then publish with the least-privilege publisher identity:

```sh
PYTHONPATH="$RELEASE/repo:$RELEASE/pydeps" "$RELEASE/.venv/bin/python" \
  scripts/forge_lab/candidate-foundry-rsi-publish-v1 publish \
  --archive /var/lib/rsi/archive.jsonl --experiment-id RSI_RUN --candidate-id CANDIDATE \
  --signed-envelope /var/lib/foundry-rsi/envelopes/CANDIDATE.json \
  --source-public-key SOURCE_ED25519_PUBLIC \
  --operator-lease-receipt /var/lib/foundry-rsi/leases/ENVELOPE.json \
  --operator-lease-public-key OPERATOR_ED25519_PUBLIC \
  --terminal-archive /var/lib/foundry-rsi/terminal.jsonl \
  --terminal-experiment-id foundry-rsi-v1 \
  --endpoint nats://127.0.0.1:4222 --loopback-authenticated-non-tls \
  --nkey-file /run/credentials/foundry-rsi/publisher.nk \
  --nkey-public-key UPUBLISHER...
```

## Pull and evaluate one candidate

The consumer accepts a dedicated-authority-signed deployment manifest binding the
evaluator ID, full release Git object ID, relative executable path, executable
SHA-256, and release-tree SHA-256. The same identities are fields in the signed
independent-evaluation v2 body and must exactly equal that verified manifest; an
evaluator cannot self-assert an arbitrary Git SHA. Keep the deployment signing
key separate from both the evaluator result key and runtime NATS identity.

The evaluator runs as uid/gid 65534 with all capabilities dropped in Bubblewrap
network/PID/user namespaces. Its root contains only the read-only evaluator
release, read-only `/usr/bin`, `/usr/lib`, `/usr/lib64`, and `/usr/share` runtime
material, private input/output mounts, synthetic `/proc` and `/dev`, and a tmpfs
`/tmp`. Host `/`, `/root`, `/etc`, `/run`, `/var`, and `/home` are not mounted;
provider environment forwarding is refused.

```sh
scripts/forge_lab/candidate-foundry-rsi-evaluator-identity-v1 \
  --evaluator-release-root /opt/foundry/evaluator-v1 \
  --evaluator-id foundry-offline-evaluator-v1 \
  --evaluator-release-sha RELEASE_GIT_SHA \
  --evaluator-executable /opt/foundry/evaluator-v1/bin/evaluate \
  --deployment-signing-key-file /run/credentials/foundry-rsi/deployment-ed25519.pem \
  --authority-epoch-sha256 DEPLOYMENT_EPOCH_SHA256 \
  --output /var/lib/foundry-rsi/evaluator-deployment-v1.json

scripts/forge_lab/candidate-foundry-rsi-consume-v1 \
  --terminal-archive /var/lib/foundry-rsi/terminal.jsonl \
  --terminal-experiment-id foundry-rsi-v1 \
  --source-public-key SOURCE_ED25519_PUBLIC \
  --operator-lease-receipt /var/lib/foundry-rsi/leases/ENVELOPE.json \
  --operator-lease-public-key OPERATOR_ED25519_PUBLIC \
  --evaluator-release-root /opt/foundry/evaluator-v1 \
  --evaluator-executable /opt/foundry/evaluator-v1/bin/evaluate \
  --evaluator-deployment-manifest /var/lib/foundry-rsi/evaluator-deployment-v1.json \
  --evaluator-deployment-public-key DEPLOYMENT_ED25519_PUBLIC \
  --evaluator-public-key EVALUATOR_ED25519_PUBLIC \
  --evaluation-receipt-dir /var/lib/foundry-rsi/evaluations \
  --evaluator-timeout 900 --fetch-timeout 5 \
  --endpoint nats://127.0.0.1:4222 --loopback-authenticated-non-tls \
  --nkey-file /run/credentials/foundry-rsi/consumer.nk \
  --nkey-public-key UCONSUMER...
```

Each invocation reconciles the durable DLQ outbox first, then pulls at most one
message. These are bounded one-shot entrypoints. This change does not install a
service or claim that the bridge is continuously supervised: an approved timer or
service must invoke them and alert on non-zero exit. RSI and Foundry can continue
their own loops independently while the transport remains one-shot supervised.

## Shadow promotion and forced rollback

Promotion accepts two distinct trusted evaluator signer lanes and dedicated
trusted signer keys for exact canary and rollback result bodies. Shadow canary is
the default outcome. A forced rollback records a signed, content-addressed result.
Live authorization additionally requires the exact signed operator lease and an
atomic durable one-shot consumption token. Even then, `live_enabled` defaults to
false; no command in this runbook enables or applies live promotion.

## Failure and recovery matrix

| Failure | Result | Recovery |
|---|---|---|
| Missing runtime topology | I/O refused; nothing created | Run the provisioner with its private operation receipt |
| Existing field drift or unjournaled partial topology | Provisioning refused | Inspect broker and receipt; restore the exact expected state or use a separately authorized manual recovery |
| Crash after one topology create | Receipt remains recoverable; exact broker state is rediscovered | Re-run `--create-missing` with the same receipt, or `--rollback` |
| Concurrent provision calls or killed journal temp writer | Sibling lock admits one complete transaction; stale unique temp is inert | Re-run with the canonical receipt path and retain the lock inode |
| NKey seed/public mismatch, unsafe file, remote non-TLS | Connection/mutation refused | Correct root-owned credentials or TLS endpoint; never bypass admission |
| Publish timeout or bad puback | Stable message ID retried with bounded backoff | Re-run after broker recovery; JetStream dedup makes the publish idempotent |
| Duplicate delivery after terminal store write | Original is ACKed without evaluator replay | No action; retain terminal receipt |
| Noncanonical JSON, duplicate key, missing/extra header, bad signature/lease/fence | Terminal DLQ path | Inspect the immutable DLQ record; do not repair and republish in place |
| Evaluator identity drift, host-secret probe, timeout, or failure | Evaluation is refused/NAKed; final delivery goes to durable DLQ outbox | Fix the immutable offline release or sandbox, then process a new authorized candidate |
| DLQ publish failure | Source NAKed only after durable outbox persistence | Re-run consumer; startup reconciliation republishes stable outbox identity |
| Crash after DLQ delivery before source ACK | Delivered outbox is recognized | Redelivery is ACKed without a second DLQ body |
| Candidate observed after expiry | Terminal state is `expired` at protocol expiry; DLQ receipt records later observation | Issue a new candidate and lease; never extend signed expiry |
| Canary unhealthy or forced rollback | Signed rollback invoked; live apply remains false | Review signed canary/rollback bodies and evidence |
| Untrusted/tampered canary or rollback result | Promotion refused | Repair dedicated runner trust/release; never substitute an evidence digest |
| Replayed live lease | Atomic token permits exactly one winner; replay refused | Obtain a new operator grant after review |
| Immediate NATS config regression | Operator restores exact `.rollback` bytes | Validate full rollback config, then perform the separately authorized reload |
