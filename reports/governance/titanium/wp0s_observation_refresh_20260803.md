# WP-0S Observation Refresh — 2026-08-03 (appended dated section)

- **Relation to prior record**: this file APPENDS a dated 2026-08-03 observation to the WP-0S
  exposure record. The 2026-08-01 receipt
  (`reports/governance/titanium/wp0s_observation_receipt_20260801.json`) is NOT rewritten and
  remains byte-identical; it stays authoritative for what was observed on 2026-08-01 and for the
  schema-validated evidence classes of that day.
- **Work packet**: WP-0S · **Active track**: repository-titanium-hardening-2026-07
- **Authority**: implementation_observer (unchanged)
- **Observation window (this section)**: 2026-08-03T14:15:42Z – 2026-08-03T14:16:09Z (live HTTP
  probes and local listener checks); commit-graph, SSH-alias-inventory, fleet-registry, and
  docker-compose reads completed by 2026-08-03T14:30:00Z.
- **Probe policy today (stricter than 08-01)**: read-only; unauthenticated HTTP GETs to the two
  governed public endpoints already named in the 08-01 receipt ONLY; no SSH sessions; no auth
  attempts; no port or route enumeration beyond the governed endpoints; local control-host reads
  and git/GitHub commit-graph reads only. Consequence: every evidence item the 08-01 receipt
  obtained via SSH vantage is NOT re-collected today and is classified NEEDS_HOST below — the
  08-01 values stand as last-known, not as fresh.
- **Secret policy**: environment-variable NAMES and presence booleans only; no secret values
  accessed, requested, or recorded (unchanged).
- **Repository references at observation time**: origin/main = `f3eb5b39759f4f6deae5f0562530d7ed38792458`;
  packet base = `61df22a85e2083a96a7b0a9500b611e384d40730`; integrated WP-0S implementation
  reference = `e96674d27d90144f22bc55b64ac7ea2baff63b52` (merge of #1164, 2026-07-31T04:11:43Z).

## Fresh probes and delta vs 2026-08-01

| # | Probe (vantage today) | 2026-08-01 observation | 2026-08-03 observation | Delta |
|---|---|---|---|---|
| 1 | GET `https://dashboard.167-172-95-184.nip.io/health` (external control-host HTTP client; no credentials sent) | HTTP 401; route observation via SSH: Caddy config names the host and a loopback :8420 target | HTTP 401 at 2026-08-03T14:15:42Z; `server: Caddy`; `www-authenticate: Basic realm="restricted"`; empty body; remote IP 167.172.95.184 | NO CHANGE in status. Refresh upgrades the route claim's vantage: the Caddy basic-auth challenge is now confirmed from the external side, not only from SSH-side config. |
| 2 | GET `http://178.128.87.170:8080/health` (external control-host HTTP client; no credentials sent) | HTTP 200; public_bind 0.0.0.0:8080 (SSH vantage); container `dharmic-quant-web` started 2026-07-21T15:05:26Z | HTTP 200 at 2026-08-03T14:15:43Z; unauthenticated JSON body; `server: uvicorn` | NO CHANGE in status — the Meghadharma route is still publicly reachable with no authentication, 13 days after the runtime started. NEW DETAIL: the body self-identifies as an A2A gateway — `node_id="dharma-hub"`, `status="online"`, `gateway_version="2.0.0"`, `spec_version="a2a-1.0"` — i.e. the exposed surface presents as an agent-to-agent hub gateway, not only a quant dashboard. |
| 3 | Governed secret names on the Meghadharma public runtime | All three names absent from the `dharmic-quant-web` environment (SSH env inspection, names-only) | All three names (`DASHBOARD_API_KEY`, `DHARMA_VERIFY_WEBHOOK_SECRET`, `DHARMA_API_MODE`) absent from the public HTTP response surface (headers + body) | CONSISTENT, but the vantages are distinct and must not be pooled: today's check covers only the HTTP surface; the env-level names-only check is NEEDS_HOST today. The 08-01 env-level finding (all three absent → no configured auth name set on the public runtime) stands as last-known. |
| 4 | Runtime restart / redeploy since 08-01 (inferred, external) | Container start 2026-07-21T15:05:26Z (SSH/docker vantage) | Live body reports app `started_at=2026-07-21T15:05:50Z` — matches the 07-21 container start plus app boot | NO restart or redeploy of the exposed Meghadharma runtime since 2026-07-21; the same instance observed on 08-01 is still serving. |
| 5 | Local control-host (Mac) listeners on TCP 8000, 8080, 8420, 7433 (local vantage) | No listeners | No listeners at 2026-08-03T14:16:09Z | NO CHANGE. |
| 6 | Rushabdev deployed code vs integrated WP-0S reference (commit graph) | Observed API head `a370d3cd51aa5d9f97b2c2654d99fa63b8ab9466`; `e96674d27` not its ancestor per LOCAL graph; remote clone lacked the integrated object, so the head could not be placed in the shared graph | Placed via GitHub commit graph (read-only API): `a370d3cd…` = merge of PR #931, committed 2026-07-14T03:32:10Z; it IS an ancestor of main, now 181 commits behind main `f3eb5b39…`; `e96674d27` (2026-07-31) is NOT an ancestor of it | SAME CONCLUSION, STRONGER EVIDENCE: the 08-01 "not descended" finding is confirmed in the shared graph and sharpened — Rushabdev serves a 2026-07-14-vintage main, predating the WP-0S auth implementation by 17 days; repository work is NOT deployed protection there. Drift has grown since 08-01 as main advanced. |
| 7 | docker-compose port declarations on current main (repo read; not in the 08-01 receipt's evidence set) | — (not recorded on 08-01) | At main `f3eb5b39…`: service `web` (container `dharmic-quant-web`) declares `"8080:8080"` — world-bound, matching the observed public bind on Meghadharma; service `swarm` declares `"127.0.0.1:7433:7433"` loopback-only (comment cites 2026-07-09 forensics). `docker-compose.yml` is UNCHANGED between packet base `61df22a…` and today's main. | NEW EVIDENCE CLASS (code-declaration vantage): the Meghadharma 8080 exposure is code-declared on current main — a clean redeploy of main reproduces it. Containment by host action alone would not survive a redeploy without a compose change (or an operator decision that the exposure is intended). |

## Inventory-gap completion (the 08-01 receipt's own unchecked items)

The 08-01 receipt declared `inventory_complete: false` and bounded itself to "the named control
host and three configured SSH aliases". Items below enumerate what that left unchecked, and what
of it is checkable read-only from this Mac today.

### Checked today (read-only, control-host vantage)

1. **Control-host SSH alias inventory is now enumerated and closed**: `~/.ssh/config` on the
   control host defines exactly three fleet aliases — `agni` → 157.245.193.15, `rushabdev` →
   167.172.95.184, `meghadharma`/`meghadharma_cloud` → 178.128.87.170. There are no additional
   configured aliases that the 08-01 receipt failed to visit. This also binds endpoint identity:
   the 401 endpoint's IP (167.172.95.184) is the `rushabdev` alias host; the 200 endpoint's IP
   (178.128.87.170) is the `meghadharma` alias host.
2. **Declared fleet inventory beyond SSH aliases**: `docs/ops/FLEET_FIELD_REGISTRY.yaml` at main
   lists 7 agent identities; the only host-shaped runtimes are the AGNI hub VPS
   (157.245.193.15), the Rushabdev VPS, and the Meghadharma host — i.e. the same three hosts.
   Remaining identities are ephemeral cloud sandboxes / git seats with no probe surface from this
   vantage. No fourth VPS-class host is declared in the repository's fleet registry.
3. **Rushabdev head placement in the shared commit graph** (open on 08-01 because the remote
   clone lacked the integrated object): completed via read-only GitHub API — see delta row 6.
4. **Code-declaration state of the exposed port on current main**: completed — see delta row 7.

### NEEDS_HOST (requires SSH vantage; excluded by today's read-only HTTP-only policy)

These are NOT promoted; the 08-01 values are last-known only.

1. Listener bind states on agni / rushabdev / meghadharma (`sab-agora` 127.0.0.1:8000,
   `dharma-dashboard-api` 127.0.0.1:8420, legacy backend 127.0.0.1:8420, `dharmic-quant-web`
   0.0.0.0:8080).
2. Environment-name presence booleans per runtime (names-only), including whether the legacy
   Meghadharma backend still holds `DASHBOARD_API_KEY` by name and whether the public web runtime
   still holds none of the three governed names at env level.
3. Caddy configuration-level route confirmation on rushabdev (external side confirmed today;
   config side needs host).
4. Container image tags and Docker-level restart evidence on meghadharma (externally corroborated
   unchanged via `started_at`, but the Docker vantage needs host).
5. agni `sab-agora` loopback state and release marker (agni exposes no governed public endpoint in
   the 08-01 receipt, and probing agni's IP would exceed the governed endpoint set — forbidden
   today).
6. Enumeration of any ADDITIONAL public routes beyond the two governed endpoints: route/port
   enumeration is a scan and is forbidden under today's policy; the honest closure is an on-host
   socket-table read (NEEDS_HOST), not an external sweep.

### BLOCKED_OPERATOR (no observer can produce these)

1. Operator-attested exact deployment inventory (`exact_host_scope` attestation).
2. The containment decision for the two observed public routes. The operator must choose and
   attest one of:
   - **CONTAINED** — exposure closed by host/proxy action AND the compose declaration reconciled
     so a redeploy does not reopen it;
   - **PRIVATE_ONLY** — routes retained but bound/authenticated per the governed name set, with
     auth re-tested from an external vantage;
   - **NOT_DEPLOYED** — the runtimes are decommissioned.

## Verdict (unchanged)

- **status: BLOCKED_OPERATOR** — `inventory_complete` remains false; live exposure remains
  observed (both public routes reproduced today); operator action remains required; Phase-0
  promotion remains forbidden.
- Nothing in this refresh weakens the 08-01 findings. The material movement since 08-01 is
  evidential, not environmental: the Rushabdev version-drift claim is now anchored in the shared
  commit graph (and has grown to 181 commits), the Meghadharma exposure is shown to be
  code-declared on current main and serving an unauthenticated A2A hub-gateway surface, and the
  same exposed runtime instance has now been up without redeploy since 2026-07-21.

## Actions not taken (today)

- No SSH session, no remote command execution, no auth attempt, no credential sent or created.
- No port scan, route enumeration, or request to any endpoint beyond the two governed URLs.
- No deployment, restart, firewall/proxy change, settings mutation, containment action, or merge.
