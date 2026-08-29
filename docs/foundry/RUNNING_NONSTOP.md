# Sublimation Foundry: unattended-operation runbook

This is a deployment reference, not evidence that a service is installed or
healthy. It grants no runtime, resume, merge, or promotion authority. A dry
pilot proves control flow only.

## Enforced operating contract

- One fenced canonical writer owns state and spend settlement. Crash-held
  reservations remain charged, including across a UTC month boundary.
- Candidate paths and static tripwires are checked before canonicalization,
  application, or evaluation. Model-generated code runs only in the pinned,
  no-network Docker oracle with bounded resources and output.
- Provider requests use pinned models, bounded retries/cooldowns, and a
  pre-dispatch total-token liability. Every attempt records endpoint, model,
  tariff, validity window, usage basis, and fallback result.
- STOP, HALT, and KILL are durable control events. Deleting their projection
  files does not resume the process. Only a halt-bound, short-lived signed
  resume transition resolves an active stop.
- Promotions require repeated finite evaluation, immutable evaluator-image
  digest, cumulative replay lineage, and append-only receipt evidence.
- The main unit verifies the canonical origin, exact HEAD, clean/cache-free
  package tree, full tracked-worktree hashes, installed artifacts, and Python
  executable before every start. The status job performs the same verification
  before importing or executing checkout code.

## Offline proof

From a reviewed checkout, with caches outside it:

```sh
PYTHONPYCACHEPREFIX=/tmp/foundry-pycache \
  python scripts/foundry/foundry_pilot.py \
  --state-root /tmp/foundry-pilot \
  --repo-root "$PWD" --runs 5 --max-proposals-per-run 2 --max-spend-usd 0
```

This makes five simulation-only cycles, no provider calls, and no external
claim.

## Provider and tariff reality

One admissible route is enough; two keys are not required. The existing staged
credential file is `/root/.dharma/foundry.env` (root, mode `0600`). Point the
unit directly at it. Do not copy it, change its permissions, hash its contents,
or print it.

`moonshot-v1-8k` retires on 2026-08-31 and is deliberately excluded even if
`MOONSHOT_API_KEY` is present. The staged Moonshot lane has also produced 429
responses, so it is not a production fallback. The built-in Z.AI route pins
`glm-4.6` on the general `https://api.z.ai/api/paas/v4` endpoint. Built-in
Z.AI and pinned OpenRouter-free tariff evidence expires on 2026-09-03; deploy a
reviewed pricing refresh or provide a fresh operator tariff binding before
then.

Groq, Cerebras, and NVIDIA are not assumed free. An account-dependent route is
admitted only when its key and all four matching fields exist:

```text
FOUNDRY_GROQ_USD_PER_MTOK_UPPER_BOUND=...
FOUNDRY_GROQ_TARIFF_PROVENANCE=...
FOUNDRY_GROQ_TARIFF_CHECKED_AT=2026-08-27T00:00:00Z
FOUNDRY_GROQ_TARIFF_VALID_UNTIL=2026-09-03T00:00:00Z
```

Use the corresponding provider prefix. The window must be UTC-aware, current,
no longer than 31 days, and bound to the pinned model/account entitlement.
Zhipu/OpenRouter may use the same fields to refresh their dated built-ins. A
missing, future, stale, expired, or model-mismatched binding fails before any
network dispatch. Status reports the next durable tariff expiry.

## Legacy evidence: classify, never seed

The audited legacy root `/root/.dharma/foundry` contained 39 legacy receipts,
zero chained receipts, three missing-artifact references, and 15 orphan
artifacts. Its pre-v2 champions lack cumulative lineage and are non-seedable.
Do not configure the new service to use that root and do not claim they replay.

Generate the digest-bound classification plan, then explicitly quarantine it:

```sh
python scripts/foundry/migrate_legacy_state.py \
  --state-root /root/.dharma/foundry
sudo python scripts/foundry/migrate_legacy_state.py \
  --state-root /root/.dharma/foundry --apply
```

The applied report must show `post_audit.ok=true`,
`seedability_after.all_seedable_replay_verified=true`, and
`success_criteria_met=true`. Bytes are moved, not deleted, and a hashed
`QUARANTINE.json` remains for operator review. This does not make a legacy
champion seedable. Start the canonical service only from a separately created,
empty audited state root.

## Prepare the host without changing credential authority

The hardened service runs as root because the only authorized credential file
is root-private and must not be copied or relaxed. The existing resume identity
is `/root/.ssh/id_ed25519.pub`; the private key is never copied, generated, or
used by the installer.

```sh
sudo install -d -o root -g root -m 0700 /etc/dharma-foundry
sudo install -d -o root -g root -m 0700 /var/lib/sublimation-foundry
sudo systemctl disable --now foundry-campaign.service foundry-daemon.service
systemctl is-active foundry-campaign.service foundry-daemon.service
systemctl is-enabled foundry-campaign.service foundry-daemon.service
```

The last two commands must show no active legacy writer and a disabled, masked,
or not-found enablement state. The installer refuses an active or enabled
legacy unit; it does not make that authority transition for you.

The immutable offline oracle image must already exist:

```text
foundry/openevolve-cpu@sha256:13526567bc4d878d367ae2ad1d1f18a686b3cdad2be6c09942c92dd34db5ca53
```

## Transactional, inert installation

Use the reviewed clean checkout and its exact 40-hex commit. The installer is
inert unless `--start` is supplied:

```sh
sudo scripts/foundry/install_service.sh \
  --repo /root/foundry-rsi-continuous-20260827 \
  --python /root/.dharma/venvs/dharma-swarm-agentops-py312/bin/python \
  --user root \
  --environment-file /root/.dharma/foundry.env \
  --trusted-resume-public-key /root/.ssh/id_ed25519.pub \
  --expected-sha <reviewed-40-hex-sha> \
  --state-root /var/lib/sublimation-foundry
```

The installer transaction backs up and can roll back every unit, alert helper,
logrotate rule, status environment, cron file, installed verifier/helper, and
status symlink. The deployment manifest binds their bytes/metadata, the full
tracked release inventory, external public key, interpreter, secret-file path
and permissions (never secret bytes), canonical origin, and exact HEAD.

After reviewing the manifest and all start gates, repeat the same command with
`--start`. Start refuses unresolved control evidence, quarantine, dirty or
untracked runtime bytes (including ignored bytecode), bad receipt/artifact
audit, missing Docker/image, stale tariffs, or no admissible provider. It makes
no live provider probe during installation.

## Stop, budget idle, and signed resume

Unexpected failures restart with watchdog supervision. Exit 42/43 is terminal
and excluded from restart. Monthly budget exhaustion idles and wakes after the
month rolls over; STOP/KILL never auto-clear. Marker deletion is not a resume.

Prepare an exact halt-bound body, sign it with the existing private identity,
then apply it with the trusted public key:

```sh
python scripts/foundry/foundry_resume.py \
  --state-root /var/lib/sublimation-foundry \
  --prepare-body /tmp/foundry-resume.json \
  --authority-id operator --lease-id <unique-lease-id> --ttl-seconds 300

ssh-keygen -Y sign -f /root/.ssh/id_ed25519 \
  -n foundry-resume /tmp/foundry-resume.json

python scripts/foundry/foundry_resume.py \
  --state-root /var/lib/sublimation-foundry \
  --body /tmp/foundry-resume.json \
  --signature /tmp/foundry-resume.json.sig \
  --trusted-public-key /root/.ssh/id_ed25519.pub
```

Do not generate an operator key or sign an envelope on the operator's behalf.
Bodies expire within 15 minutes, bind the active halt digest, and have
single-use nonces.

## Health and durable alerts

```sh
/usr/local/bin/foundry-status.sh
systemctl status sublimation-foundry.service
journalctl -u sublimation-foundry.service --since '1 hour ago'
```

Exit codes are 0 healthy, 1 degraded/stopped, 2 unhealthy, and 3 terminal.
The 15-minute installed job emits deduplicated, bounded, append-only alert
receipts for stale progress, high no-op ratio, receipt age, checkout drift,
probe timeout/launch failure, disk pressure, and other nonzero verdicts.
`OnFailure=` invokes the separately installed and hash-bound alert unit.

Implementation authority lives in `dharma_swarm/foundry/` and
`scripts/foundry/`; this runbook intentionally uses no fragile line anchors.
