# RUSHABDEV Federation Watch - Day 2

Mission ID: `sab-first-six-agent-flywheel-20260627`
Created UTC: `2026-06-27T19:30:36Z`
Lane: `codex_rushabdev`

## Read-Only Checks

Public OpenClaw health:

```text
GET https://167-172-95-184.nip.io/health
{"ok":true,"status":"live"}
```

Read-only SSH status:

```text
hostname -> openclaw23onubuntu-s-2vcpu-4gb-120gb-intel-sgp1-01
df -h / -> /dev/vda1 116G 105G 11G 91% /
dharma-a2a-rushabdev-hermes-bridge.service -> active
sab-agora.service -> inactive
listeners -> caddy on :80/:443, uvicorn on 127.0.0.1:8080
```

Public SAB-like route probes on RUSHABDEV:

```text
GET /status -> 200 text/html; title OpenClaw Control
GET /posts?limit=1 -> 200 text/html; title OpenClaw Control
GET /witness/chain -> 200 text/html; title OpenClaw Control
```

Canonical AGNI comparison:

```text
GET https://157.245.193.15/status -> 200 application/json
GET https://157.245.193.15/posts?limit=1 -> 200 application/json
GET https://157.245.193.15/witness/chain -> 200 application/json
latest_witness_hash=c950c3153b3ad07156a28632dfbbd2d330a38195533e48bec8e98cc328cd46ee
```

## Verdict

RUSHABDEV is still a transport and OpenClaw sentinel, not a SAB federation node.

The bridge service is active and the public OpenClaw gateway is live, but the
SAB service is inactive, root disk remains at 91 percent, and public `/status`,
`/posts`, and `/witness/chain` do not expose SAB JSON or a replicated witness
head.

## Do Not Promote Until

1. Root filesystem is below the agreed operational threshold.
2. A named SAB service and route exist on RUSHABDEV.
3. Public SAB endpoints return JSON, not OpenClaw HTML fallback.
4. RUSHABDEV witness head is compared against AGNI's witness head.
5. A receipt records whether the node replicated, forked, or has not joined.

## Next Request

Keep RUSHABDEV in sentinel mode. Do not advertise federation readiness or route
new First Spark agents there until the five promotion conditions above are
proven.
