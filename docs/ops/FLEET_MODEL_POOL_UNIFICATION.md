# Fleet Model Pool Unification — One Key Store, One Router, Identical Resolution

**Status**: PHASE 1 — DESIGN. Decision register D1–D6 below; implementation gated on operator answers.
**Date**: 2026-07-16. **Author**: fleet routing engineer session (Mac hub).
**Goal spec**: `~/handoffs/2026-07-16_fleet_model_pool_unification_GOAL.md` (authoritative prompt).
**Branch**: `ops/fleet-model-pool-unification-20260716` off `origin/main` @ `9cc3739d5`.

Parity here means **deterministic routing parity**: the same request resolves to the
identical `(provider, model, base_url)` triple on every participating node. It does
NOT mean token-identical LLM outputs.

---

## 1. The canon (Mac), re-verified 2026-07-16

Every claim cited. THE ONE WAY (`docs/ops/MODEL_KEY_ROUTING.md:9-24`):

| Layer | Owner | Verified |
|---|---|---|
| Key store | `~/.dharma/agent_keys.env` — mode 0600, 42 entries (key NAMES inventoried §A.0) | `ls -la` 2026-07-16 |
| Key manager | `dkeys` at `~/.dharma/bin/dkeys` (list/test/find/add/safe-json/exec/path; `env` disabled by design) | `dkeys --help` |
| Code reader | `dharma_swarm/api_keys.py` — `runtime_env_paths()` puts `~/.dharma/agent_keys.env` in the load order (`api_keys.py:220-227`); `bootstrap_runtime_env()` is the ONLY loader, never-overwrite semantics (`api_keys.py:288`, `scripts/load_runtime_env.sh:1-16`) |  |
| Resolver | `dharma_swarm/runtime_provider.py:191` `resolve_runtime_provider_config()` → `:523` `create_runtime_provider()` |  |
| Order | `dharma_swarm/model_hierarchy.py:46-93` — TIER_FREE/CHEAP/SUBSCRIPTION/PAID_API → `CANONICAL_SEED_ORDER` (`:91-93`); lane roles `:201-221` |  |
| Model-grain | `dharma_swarm/model_pool.py` (routes, K2.6 power floor `model_pool.py:48`), defaults projected via `model_defaults.py` (`model_hierarchy.py:242-244`) |  |
| Liveness oracle | `dharma_swarm/key_oracle.py:1-19` — reads `~/.dharma/keys_status.json` (dkeys test output), never key material, fail-open |  |

**Anthropic lane on the Mac**: `runtime_provider.py:213-218` — `ProviderType.ANTHROPIC`
is rewritten to `ProviderType.CLAUDE_CODE` (Max-plan CLI) unless
`DHARMA_FORCE_ANTHROPIC_API=1`. `CLAUDE_CODE` resolves to a **binary path**, not a
key (`runtime_provider.py:308-318`) — this lane physically cannot exist on a headless
VPS (OAuth keychain + interactive login). See D6.

**dkeys live status** (as of `dkeys safe-json`, last_test 2026-07-14T08:21 JST):
live = ollama_cloud, gemini, zai_coding, minimax, deepseek, groq, nvidia_nim, kimi,
claude_code (Max OAuth), codex (OpenAI OAuth). NOT live = **anthropic metered
(HTTP 400)**, **openrouter (HTTP 404)**, xai (funds=0), zai_global (funds=0),
openai metered (429), qwen (no creds). Per MODEL_KEY_ROUTING.md:154-158, only a
completion through the runtime's own provider class counts as a "lane works" receipt —
these dkeys statuses are probe results, cited as such.

**UPDATE 2026-07-15 16:17 UTC (§8 apply log)**: three of those failures were dkeys
PROBER artifacts, now fixed: ollama_cloud probed a retired endpoint (`/api/chat` →
410); openrouter probed a delisted free model (404 misread as auth-fail — the key is
VALID, adjudicated via completion probe + `GET /api/v1/key` 200); anthropic's 400 is
"credit balance is too low" = **valid key, zero credits**, now classified `$ funds=0`.
Post-fix truth: **11 live · 3 valid-no-funds · 0 auth-fail · 1 no-key**.

**ProviderType coverage gap** (design-relevant): `dharma_swarm/models.py:117-138` has
no `DEEPSEEK` or `MINIMAX` provider, while dkeys tracks live `deepseek`/`minimax` keys
and agni's hermes routes a `deepseek` lane. The renderer (D3) must therefore treat
some hermes lanes as *pass-through* (no dharma ProviderType behind them) — mapped
table in §5.3.

**Prior art found on disk**: `~/.dharma/bin/dkeys-sync-agni` (bash, 110 lines) already
implements push-from-Mac vault sync: scp's `dkeys` + the **FULL** `agent_keys.env` to
`<host>:/root/.dharma/`, merges the remote's existing `~/.hermes/.env` vars into it,
installs a shell-rc source block, chmod 0600. This is the seed of `dkeys sync` — but
its full-vault scope is exactly the D2 question, and its rc-block install must be
reconciled with the one-loader doctrine (MODEL_KEY_ROUTING.md:136-143) before reuse.

**Doctrine-vs-disk contradiction (report, not resolved here)**: `dkeys --help` states
"Canonical source: repository scripts/dkeys.py" — that path exists in **neither**
`origin/main` @ 9cc3739d5 nor the local magpie-seed tree. The installed
`~/.dharma/bin/dkeys` is currently the only copy on this Mac. Implementation phase
should land dkeys (+ its sync extension) into git as part of the PR (new file
`scripts/dkeys.py` matching the installed copy, diffed and reviewed first).

## 2. The unification model — one truth, three channels

The Mac stays the single source of truth. VPSes cannot reach the Mac (NAT, Bali), so
truth flows outward only. Three channels, no new services, no new formats:

1. **Routing truth = code, via git.** `model_hierarchy.py` / `model_pool.py` /
   `runtime_provider.py` are already the canonical order and already distributed by
   `git pull` from GitHub (reachable from all VPSes). A node's routing order is pinned
   by a dharma_swarm **commit SHA**, not by a hand-edited config.
2. **Key truth = vault, via dkeys push over SSH.** `dkeys sync <host> [--profile <name>]`
   (extension of the existing `dkeys-sync-agni`) pushes the operator-approved per-node
   key subset to `<host>:/root/.dharma/agent_keys.env` (0600). Secrets transit SSH/scp
   only — never git, logs, or chat.
3. **Hermes projection = rendered, never hand-edited.** A renderer in dharma_swarm
   (D3) generates each node's `/root/.hermes/.env` (keys) and the `provider_routing`
   block of `/root/.hermes/config.yaml` (order) FROM channels 1+2. Inline keys are
   scrubbed out of config.yaml as part of the first render.

A request then resolves identically everywhere because all three inputs are identical:
same code SHA, same (subset of) key names, same rendered hermes order. The parity
harness (§6) proves it instead of asserting it.

---

## 3. Decision register (operator)

Every decision below is **BLOCKED-ON-OPERATOR** until answered in writing. Each has a
recommendation; none has been executed. Per the goal spec, stopping after Phase 1 with
this register open is valid completion.

### D1 — Topology: push-from-Mac vs VPS broker vs hybrid

**Constraint**: VPSes cannot initiate to the Mac (NAT). A Mac-hosted key server is
physically impossible; "pull from Mac" is off the table.

| Option | Mechanism | Threat model | Verdict |
|---|---|---|---|
| (a) Pure push-from-Mac | Mac renders keys AND hermes configs, scp's everything | Mac compromise = fleet compromise (already true today — Mac holds the vault). No new listeners. Staleness risk: nothing updates while the Mac is asleep/travelling; bounded by push cadence + `keys_status.json` timestamps. | Safe, simple, but couples routing-order updates to operator presence |
| (b) VPS-hosted broker | One VPS (realistically meghadharma — only box with dharma_swarm + vault shape) serves keys/config to the other two | Concentrates the full pool on an internet-facing box **with a prior exposure incident** (meghadharma, guard now fail-closed). Adds a new secret-serving service — collides with the "no new vault service" doctrine. Widens blast radius from 1 hub to 2. | Rejected as default |
| (c) Hybrid (RECOMMENDED) | **Keys**: push-from-Mac via `dkeys sync` (SSH only). **Routing order**: git — each node pins dharma_swarm at an operator-chosen SHA and pulls from GitHub (VPS→GitHub works; no Mac needed). **Hermes projection**: rendered ON the node from the two local inputs (`render --apply` run via SSH from Mac, diff-first). | Same blast radius as (a) for keys; routing updates decouple from Mac liveness (a node can `git pull` a pinned tag when told to); GitHub becomes a dependency for routing truth — acceptable: it already is for all code. | **Recommended** |

**Recommendation**: (c). Keys move only Mac→VPS over SSH; order moves via git pins;
render happens where the config lives. No new services, no new formats.
**Status: BLOCKED-ON-OPERATOR.**

### D2 — Key scope per node: full mirror vs per-node subset vs attenuated tokens

The existing `dkeys-sync-agni` pushes the FULL vault. Against incident history that is
the wrong default. Blast-radius analysis (key-name inventories in §A):

| Node | Exposure surface | Incident history | Proposed scope |
|---|---|---|---|
| meghadharma | NATS :4222/:8222 world-bound (§A.2); fail-closed guard verified live (`DHARMA_EVOLUTION_SHADOW=1`, `DGC_AUTONOMY_LEVEL=1`, `DHARMA_ALLOW_LIVE_MUTATION=0`) — must not be weakened | 2026-07 exposure incident (73h forensics on file) | **Reconcile, not just push**: its existing 29-name vault diverges from Mac canon in BOTH directions (§A.2) and already holds ANTHROPIC+OPENAI keys. Unification = replace with the operator-approved subset; names dropped are an explicit operator line-item, not a silent deletion. |
| agni | Public gateway (Caddy/HTTPS, Telegram), nginx flap, one live inline key in config.yaml (§A.1) | Inline-key duplication (config.yaml:668 + 2 key-bearing baks + env bak); a **full-vault push already landed** at `/root/.dharma/agent_keys.env` on Jul 8 (6772B, unused by hermes) — today's de-facto scope is near-FULL and unwired | Subset: exactly its hermes `provider_routing` lanes + infra tokens it needs (Telegram if used there). Prune the Jul-8 full mirror down to the approved profile in the same apply. Scrub inline copies (D3). |
| rushabdev | Openclaw gateway world; divergent ~10-key mix; ambiguous admission status | "REVOKED" in doctrine vs working SSH (D4) | **No dharma vault keys until D4 is adjudicated.** |
| Mac | Hub; holds everything | — | Full vault (status quo). |

Proposed default subset for VPS lanes (operator edits): `OLLAMA_API_KEY`,
`GLM_API_KEY` (+`ZAI_API_KEY` alias), `KIMI_API_KEY`/`MOONSHOT_API_KEY`,
`DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY`/`NVIDIA_NIM_API_KEY`,
`GEMINI_API_KEY`/`GOOGLE_AI_API_KEY`, `OPENROUTER_API_KEY` (once its HTTP 404 status is
resolved — see §1). Explicitly NOT synced to any VPS: `ANTHROPIC_API_KEY` (D6),
`OPENAI_API_KEY`, `GH_TOKEN`/`GITHUB_TOKEN` (deploy-key or fine-grained per-node token
instead), `CDP_API_KEY_JSON`, `FAL_KEY`, `SAKANA_API_KEY`, `XAI_API_KEY`, Mac-local
Slack/Telegram tokens unless that node runs the corresponding bot.

Mechanism: `dkeys sync <host> --profile <node>` reading a committed, **names-only**
profile file (e.g. `docs/ops/fleet_key_profiles.yaml` — names only, never values, so
it is safe in git). Attenuated/child tokens (e.g. OpenRouter provisioning keys) are a
good follow-up hardening but not required for v1.
**Status: BLOCKED-ON-OPERATOR** (the per-node allowlists are a security call).

### D3 — Hermes unification: render config.yaml provider_routing + .env from canon

**What exists today** (evidence §A.1–A.3): three hand-divergent hermes configs.
agni: `provider_routing.order` hand-edited (zai → kimi-coding → openrouter →
ollama-cloud → deepseek → anthropic), raw keys inline in `config.yaml` (auxiliary.*,
delegation, mcp_servers.vibe_trading.env) and in 4 key-bearing `.bak` files; `.env`
holds 5 provider keys; no `model_capability_floor`. meghadharma: **no
provider_routing section at all** — defaults to `tencent/hy3:free` via the Nous
inference API (config.yaml:1-4), .env has only OPENROUTER (+Discord/Telegram).
rushabdev: default `gpt-5.6-sol` via openai-codex, fallback glm-5.2 via ollama.com,
40-name .env. Three boxes, three routing realities, none derived from canon.

**Design** (a renderer, not hand-edits):
- New `scripts/ops/render_hermes_config.py` in dharma_swarm. Inputs: (1) the node
  profile (D2 names-only allowlist), (2) `model_hierarchy` order + `model_pool`
  defaults resolved through `resolve_runtime_provider_config()` — the SAME door the
  swarm uses, no second router; (3) the node's existing `config.yaml` (everything
  outside `provider_routing` and key fields is preserved byte-for-byte).
- Outputs: `/root/.hermes/.env` carrying ONLY the profile's key lines (values injected
  at apply time on the node, sourced from `/root/.dharma/agent_keys.env` — the render
  artifact in git/transit carries names, never values), and a `config.yaml` whose
  `provider_routing.order` is generated from the canon order filtered to lanes the
  profile actually credentials, with inline key fields replaced by env-var references
  (hermes ${VAR} interpolation — verify support in the pinned hermes version first;
  if unsupported, keys live in .env only and config fields reference the env name).
- **Hermes-lane ↔ canon mapping** (from `models.py:117-138` + agni's config):
  `zai`→ZHIPU, `kimi-coding`→KIMI_CODE, `openrouter`→OPENROUTER,
  `ollama-cloud`→OLLAMA, `anthropic`→(D6), `deepseek`/`minimax`→pass-through lanes
  (no dharma ProviderType; rendered from dkeys key presence only, flagged in output).
- **Scrub step** (same PR, applied per-box only after D-approval): timestamped
  `config.yaml.bak.<ts>` of the current file (kept 0600), inline keys removed from the
  live config, and the 4 existing key-bearing `.bak*` files moved to
  `/root/.hermes/secure_archive/` (0700 dir) or deleted after the operator confirms the
  rendered config passes a live completion — operator picks archive-vs-delete.
- Apply discipline per box: render → `diff -u` shown → operator/goal-approved apply →
  `.bak` alongside → hermes restart → live completion receipt → parity check.

**Status: BLOCKED-ON-OPERATOR** (renderer design above; approval = build it).

### D4 — rushabdev: re-admit, quarantine, or decommission

**Contradiction on record (not silently resolved)**: memory/doctrine says rushabdev
access was REVOKED (~2026-07-08, remote-mesh v1.1 register) — yet the 2026-07-16 audit
(§A.3) found the opposite of a revoked box: root SSH live; `/root/.ssh/authorized_keys`
**modified Jul 10 13:15 UTC** (after the alleged revocation) and holding 7 keys
(4× `dhyana@MacBook-Pro-4.local`, `johnvincentshrader@gmail.com`, `root@agni-openclaw`,
`dhyana@old-mac`); root logins on Jul 8/10/11/13/14; `/root/.dharma/nats/
remote_agent_bridge.env` written **Jul 15 01:21**. The box is an ACTIVE fleet node —
running dharma-a2a-mailbox-gateway, dharma-a2a-rushabdev-hermes-bridge, fleet-hub
(NATS), fleet-collab-loop, dashboard API/web, sab-flywheel — with ufw scoping the
gateway/NATS ports to agni only. Whatever "REVOKED" recorded, it was never executed
on this box, or it referred to something narrower than SSH admission.

It also hosts the openclaw gateway (out of scope) and the **irreplaceable PSMV mirror**
at `/home/openclaw/dhyana_mirror` (35G — must be rsynced off before ANY decommission
per standing memory), plus live Polymarket trading-wallet credentials
(`/root/rushabdev/keys/vault.env`, names in §A.3) that raise its blast-radius class.

Options:
(i) **formal re-admit**: acknowledge de-facto fleet membership, give it a D2 subset +
   hermes render + parity seat, and fix the hygiene findings (two group/world-readable
   env files, §A.3) as part of the apply;
(ii) quarantine: push NO dharma keys, exclude from parity v1 — but note this leaves a
   live, actively-operated node running on its current divergent 40-name key mix, so
   "quarantine" here means *not unified*, not *inert*;
(iii) execute the recorded revocation for real (disable fleet units, prune
   authorized_keys) — blocked by the PSMV mirror and by whatever depends on its live
   A2A/fleet services.

No recommendation is safe to make unilaterally: (i) contradicts the recorded
revocation decision; (iii) breaks running fleet services. The operator must say which
record is true. **Status: BLOCKED-ON-OPERATOR.**

### D5 — Hermes version policy: pin vs upgrade

The audit found hermes in **three different distribution forms at three versions**:
agni = git checkout at `/opt/hermes-agent` (~305 commits behind; §A.1); meghadharma =
Docker image `nousresearch/hermes-agent:v2026.7.7.2` (§A.2); rushabdev = `/root/.hermes`
install v0.18.2, 167 revisions behind (§A.3). Upgrading mid-unification confounds
every parity signal (config schema may shift under the renderer), and each form has a
different upgrade mechanism.

**Recommendation**: **pin** per node for v1 — record each node's hermes
version/commit/image-tag in the parity output (part of the effective-config hash),
render against the installed version's schema, and treat any upgrade — including
converging the three install forms to one — as its own operator-gated task after
parity is green. openclaw npm-deploys are untouched (out of scope).
**Status: BLOCKED-ON-OPERATOR.**

### D6 — The Anthropic lane for headless VPSes

Physics: the Mac's Anthropic lane IS the Max plan via the `claude` CLI
(`runtime_provider.py:213-218,308-318`) — keychain OAuth + interactive login, unusable
headless. Additional fact: the metered `ANTHROPIC_API_KEY` in the vault is **valid but
has ZERO credits** ("credit balance is too low", adjudicated 2026-07-15 §8) — the
"just use the API key" fallback needs funding, not fixing.

Ground truth from the audit: **no VPS routes to real Anthropic today.** agni's
hermes `anthropic` lane actually points at `https://api.kimi.com/coding` (§A.1/A.4);
meghadharma's hermes has no provider_routing at all and defaults to Nous inference
(§A.2); rushabdev defaults to openai-codex (§A.3). Unification does not remove an
Anthropic lane from any VPS — there is none to remove.

Options for VPS-side `ProviderType.ANTHROPIC` requests:
1. **No Anthropic on VPSes (RECOMMENDED for v1)**: the resolver returns
   `available=False` (no key → `runtime_provider.py:220-227`), callers fall through the
   hierarchy to the same next lane on every node — still deterministic. Parity is then
   defined over a **fleet profile** (the probe set §6 excludes subscription lanes);
   Mac-only `claude_code`/`codex` divergence is documented and expected, not a parity
   failure.
2. Fund/fix the metered key and sync it to chosen VPSes: real Anthropic parity, real
   metered spend, wider blast radius (an Anthropic key on an incident-history box).
3. Anthropic via OpenRouter: paid, and OPENROUTER key currently probes 404.

**Status: BLOCKED-ON-OPERATOR** (option 2/3 are money decisions).

---

## 4. Hard rules honored (unchanged by any decision)

- No live mutation without: diff shown first → timestamped `.bak` → documented
  rollback command (§7) → live receipt after.
- meghadharma `SHADOW=1` / `AUTONOMY=1` fail-closed guard is never weakened; the
  renderer must not touch guard env or container config.
- No new vault service, router, or config format — dkeys / runtime_provider /
  model_hierarchy extensions only.
- Secrets never in git/logs/chat — key NAMES only; SSH/scp transport only.
- Out of scope: openclaw internals, trading_lab, PSMV mirror, agni nginx/disk
  (reported in §A.1, not fixed).

## 5. Implementation plan (post-approval; nothing here has run)

1. **PR-1 (dharma_swarm, worktree-isolated)**: land `scripts/dkeys.py` (installed copy
   → git, resolving the §1 contradiction) + `dkeys sync <host> --profile` +
   `docs/ops/fleet_key_profiles.yaml` (names only) + `scripts/ops/render_hermes_config.py`
   + `scripts/ops/model_pool_parity.py` (§6) + tests. Secret-scan the diff
   (`git diff | grep -iE 'key|token|secret'` reviewed by eye) before commit.
2. **Per-box apply, sequential (agni → meghadharma → rushabdev-if-admitted)**: dkeys
   sync with the node profile → render → diff → apply with `.bak` → restart hermes →
   one live completion receipt per box → parity run. Stop on first divergence.
3. **Receipts**: parity JSON from all participating nodes committed to
   `~/.dharma/` receipts (never git per repo rule "runtime receipts never enter git");
   the doc gets the side-by-side table + hashes.

## 6. Parity harness spec

`scripts/ops/model_pool_parity.py` — runs identically on every node (dharma_swarm
checkout pinned to the same SHA; agni needs a clone or a packaged copy — decided with
D1(c)):

- **Probe set** (fixed, versioned in the script): for each fleet-profile lane
  (ZHIPU, KIMI_CODE, OLLAMA, GROQ, NVIDIA_NIM, GOOGLE_AI, OPENROUTER,
  OPENROUTER_FREE + pass-through deepseek/minimax) and each role list head
  (`PRIMARY_REASONING_PRIORITY`, `DELEGATED_BUILDER_PRIORITY`, `VALIDATOR_PRIORITY`
  filtered to the fleet profile), call `resolve_runtime_provider_config()` and emit
  `(provider, model, base_url, available)`.
- **Effective-config hash**: sha256 over (dharma_swarm SHA, sorted present key NAMES,
  hermes commit + normalized `provider_routing` block, probe results). Key VALUES
  never enter the hash input in raw form (names only).
- **Output**: one JSON per node → Mac collects over SSH → side-by-side diff table.
  PASS = identical triples + identical hash across all participating nodes.
- **Live receipts**: separately, one real completion per VPS through the unified pool
  (provider class, not curl — MODEL_KEY_ROUTING.md:154-158), timestamped.

## 7. Rollback commands (template — instantiated per box at apply time)

Every applied file gets `cp -p <file> <file>.bak.$(date -u +%Y%m%dT%H%M%SZ)` BEFORE
replacement. Rollback per box:

```bash
# hermes config (agni example)
ssh agni 'cp -p /root/.hermes/config.yaml.bak.<TS> /root/.hermes/config.yaml \
  && cp -p /root/.hermes/.env.bak.<TS> /root/.hermes/.env \
  && systemctl restart <hermes-unit>'   # unit name in §A.1
# vault (any VPS)
ssh <host> 'cp -p /root/.dharma/agent_keys.env.bak.<TS> /root/.dharma/agent_keys.env'
```

The exact `<TS>` values and unit names are recorded in this doc's §8 at apply time.

## 8. Apply log

**2026-07-15 16:03–16:05 UTC — Mac vault z.ai rotation (operator-supplied key)**
- Backup: `~/.dharma/agent_keys.env.bak.20260715T160315Z` (0600).
  Rollback: `cp -p ~/.dharma/agent_keys.env.bak.20260715T160315Z ~/.dharma/agent_keys.env`
- Updated via `dkeys add --stdin` (values never in argv/history): `GLM_API_KEY`,
  `ZAI_API_KEY`, `GLM_API_KEY_ID`, `ZAI_API_KEY_ID` (the `_ID` vars held the old
  key's id-part — verified stale before update).
- **Receipts**: `dkeys test` @ 16:04:33 UTC → `zai_coding HTTP 200 live` on the new
  key (16 providers refreshed); direct completion probe through the coding endpoint
  → HTTP 200 valid response.
- **Fingerprint discovery (corrects §B)**: Mac canonical GLM/ZAI (old fp
  `ac6eb6ef1b87`) and agni's z.ai key (fp `2cb7f68e4179` = Mac's
  `AGNI_GLM_API_KEY` = agni config.yaml:668 per §A.1 fingerprint match) are **two
  DISTINCT keys**. The transcript-exposed fragment belongs to the AGNI key.
- **Liveness probes @ ~16:05 UTC**: old agni key → **HTTP 200 STILL ACTIVE**
  (exposure risk remains live); old Mac canonical key → HTTP 200 STILL ACTIVE.
  Neither has been deactivated at the z.ai console yet — deactivation sequencing is
  the open operator action below.
- **Daemon staleness (doctrine MODEL_KEY_ROUTING.md:151-153)**: running Mac daemons
  (com.dharma.a2a.fable-composer-inbox-bridge, fugu-ultra-semantic-responder,
  sab-server, cron-daemon, ai.hermes.gateway et al.) hold pre-rotation env
  snapshots; kickstart or accept documented staleness.
- **Open sequencing decision**: deactivating the exposed AGNI key breaks agni's
  hermes `zai` lane (FIRST in its routing order) + the vibe_trading MCP until
  agni's `.env`/config are updated (a D3-scoped mini-apply). Deactivating the old
  Mac canonical key strands any consumer still on it (Mac daemons until restart;
  possibly meghadharma's `ZHIPU_API_KEY` — fingerprint not yet compared). Safe
  order: update agni (mini-apply, .bak'd) → restart Mac daemons → THEN deactivate
  both old keys at the console → re-probe both return 401.
  **Operator ruling 2026-07-16: key-exposure risk accepted ("not worried about the
  key being hacked at all") — old keys stay active; no deactivation, no daemon
  churn. Item closed unless reopened.**

**2026-07-15 16:16–16:17 UTC — Mac dkeys prober repair (smoothness sweep)**
- Backup: `~/.dharma/bin/dkeys.bak.20260715T161631Z`.
  Rollback: `cp -p ~/.dharma/bin/dkeys.bak.20260715T161631Z ~/.dharma/bin/dkeys`
- Fixes: ollama_cloud probe `https://ollama.com/api/chat`+`glm-5:cloud` (endpoint
  retired, 410) → `https://ollama.com/v1/chat/completions`+`glm-5.2`; openrouter
  probe delisted-free-model POST (404→✗) → `GET /api/v1/key` (engine gained a
  3-line GET path); classifier learned "credit balance is too low" → `$ funds=0`
  (anthropic was misrendered ✗ auth-fail).
- **Receipt**: `dkeys test` @ 16:17:03 UTC → 11 live · 3 valid-no-funds ·
  **0 auth-fail** (was 9/2/3). key_oracle (`dharma_swarm/key_oracle.py`) now feeds
  routing the truth — the TIER_FREE head lane (OLLAMA) is no longer falsely dead.
- Reminder: `~/.dharma/bin/dkeys` still has no git home (§9 item 2) — this patch
  widens that gap; land `scripts/dkeys.py` in the implementation PR.

## 9. Contradictions & corrections register (doctrine vs disk — reported, not resolved)

1. **rushabdev "REVOKED" vs live**: memory records access revoked ~2026-07-08; disk
   shows authorized_keys rewritten Jul 10, root logins through Jul 14, fleet services
   live, configs written Jul 15 (§A.3, D4). Operator adjudicates.
2. **dkeys canonical source missing**: `dkeys --help` claims `scripts/dkeys.py` in the
   repo; absent from origin/main @ 9cc3739d5 and the local tree. Only copy =
   `~/.dharma/bin/dkeys` (§1). Fix: land it in git during implementation.
3. **Goal-spec .bak count**: "4 key-bearing config.yaml.bak*" → audit found 2
   key-bearing config baks + 1 key-bearing .env bak; other 2 config baks clean (§A.1).
4. **agni "anthropic" lane is Kimi**: auth.json routes it to `api.kimi.com/coding`
   (§A.4) — lane names in hermes configs cannot be trusted as provider identities;
   the renderer must emit both name AND base_url from canon.
5. **"meghadharma closest to canon" is only shape-deep**: it has the vault path and a
   dharma_swarm clone, but its vault name-set diverges from the Mac in both directions
   and its hermes routes to Nous by default with no provider_routing block (§A.2).
6. **Mac lane probe failures — RESOLVED 2026-07-15 as prober rot** (§1 update, §8):
   `OPENROUTER_API_KEY` is valid (probe model was delisted → 404), `OLLAMA_API_KEY`
   is live (probe endpoint retired → 410), `ANTHROPIC_API_KEY` is valid with ZERO
   CREDITS (400 credit-balance error, now `$ funds=0`). Lesson for the fleet design:
   probe endpoints/models rot — the parity harness must version its probe set and
   distinguish auth-fail from probe-rot.
7. **agni already holds a full-vault push (Jul 8) that nothing reads** (§A.1) — the
   de-facto key scope on agni exceeds both its hermes wiring and any D2 proposal;
   reconciliation is part of implementation, not optional cleanup.

---

## Appendix A — Per-box audit (read-only, 2026-07-16)

### A.0 Mac (hub) — key-name inventory

`~/.dharma/agent_keys.env` (0600, 42 entries, names only):
AGNI_GATEWAY_ALLOW_ALL_USERS, AGNI_GATEWAY_WELCOME_MESSAGE, AGNI_GLM_API_KEY,
AGNI_GLM_BASE_URL, AGNI_TELEGRAM_ALLOWED_USERS, AGNI_TELEGRAM_HOME_CHANNEL,
AGNI_TELEGRAM_HOME_CHANNEL_NAME, ANTHROPIC_API_KEY, CDP_API_KEY_JSON,
DEEPSEEK_API_KEY, DHARMA_A2A_REGISTRY_READ_TOKEN, DHARMA_A2A_REGISTRY_WRITE_TOKEN,
DHARMA_NATS_URL, DHARMA_NATS_VERIFY, FAL_KEY, GEMINI_API_KEY, GH_TOKEN, GITHUB_TOKEN,
GLM_API_KEY, GLM_API_KEY_ID, GOOGLE_AI_API_KEY, GROQ_API_KEY, KIMI_ANTHROPIC_BASE_URL,
KIMI_API_KEY, KIMI_BASE_URL, KIMI_MODEL, MINIMAX_API_KEY, MOONSHOT_API_KEY,
NGC_API_KEY, NVIDIA_API_KEY, NVIDIA_NIM_API_KEY, OLLAMA_API_KEY, OPENAI_API_KEY,
OPENROUTER_API_KEY, SAKANA_API_KEY, SLACK_APP_TOKEN, SLACK_BOT_TOKEN, TAVILY_API_KEY,
TELEGRAM_BOT_TOKEN, XAI_API_KEY, ZAI_API_KEY, ZAI_API_KEY_ID.

Mac also carries a legacy `~/.hermes/.env` (0600, hermes-m5) whose provider-key names
are: DEEPSEEK_API_KEY, GEMINI_API_KEY, GH_TOKEN, GITHUB_TOKEN, OPENROUTER_API_KEY,
SLACK_APP_TOKEN, SLACK_BOT_TOKEN (×2 — duplicate line), TELEGRAM_BOT_TOKEN + hermes
runtime settings. dkeys already tracks this file (`dkeys path`).

### A.1 agni — audited 2026-07-15 15:46 UTC (read-only)

Host `agni-openclaw`, Ubuntu 6.8.0-101. Disk 82% (22G free), mem 7.9G/5.5G avail,
Python 3.12.3, Node 22 (report-only).

**Hermes**: git checkout `/opt/hermes-agent`, `main` @ aaf569126 (2026-07-12),
`git describe` **v2026.7.7.2-400-gaaf569126**, **305 commits behind** origin/main
(fresh figure — hermes' own update checker fetched 15:29 UTC same day;
`/root/.hermes/.update_check` records `{"behind": 305, "ver": "0.18.2"}`).
**6 locally modified files** incl. `hermes_cli/runtime_provider.py` — local patches
will collide with any upgrade (D5 input). Launch: root **user-scope** systemd unit
`/root/.config/systemd/user/hermes-gateway.service` (`ExecStart=/opt/hermes-agent/
venv/bin/python -m hermes_cli.main gateway run`, `WorkingDirectory=/root/.hermes`,
**no EnvironmentFile**) — effective key substrate is `/root/.hermes/.env` + one
inline config key; the live gateway process env holds zero API keys
(agni:/proc/2948273/environ).

**`/root/.hermes/.env`** (0600, mtime Jun 29): 12 names — OPENROUTER_API_KEY,
ANTHROPIC_API_KEY, OPENAI_API_KEY, GLM_API_KEY, MINIMAX_API_KEY, GLM_BASE_URL,
TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS, TELEGRAM_HOME_CHANNEL(+NAME),
GATEWAY_ALLOW_ALL_USERS, GATEWAY_WELCOME_MESSAGE. Absent: KIMI, DEEPSEEK, ZAI,
OLLAMA key names.

**`/root/.hermes/config.yaml`** (0600, `_config_version: 33`): `provider_routing`
at :609-617, order = zai → kimi-coding → openrouter → ollama-cloud → deepseek →
anthropic, `ignore: []`. Models: default `gpt-5.6-sol`/`openai-api` (:1-5),
delegation `gpt-5.5` (:389-392), fallback `glm-5-turbo` (:618-620), auxiliary/moa
glm-family. Inline-secret census: 27 pattern hits, **exactly one real inline value**
— `mcp_servers.vibe_trading.env.ZAI_API_KEY` at **config.yaml:668** (49 chars;
sha256 prefix matches `.env` `GLM_API_KEY` — a duplicated copy of the z.ai key).
All 16 `auxiliary.*.api_key` fields EMPTY; bitwarden block disabled with env-var
NAME only.

**Backups (all 0600)**: key-bearing = `config.yaml.bak-ginko-mcp-20260705T161745Z`
(:661 ZAI key) and `config.yaml.bak-provider-20260705T015350Z` (:670 ZAI key) +
`.env.bak.20260701` (same 12 names as live .env). Clean =
`config.yaml.bak-pre-kimi-default-20260629T104023Z`, `config.yaml.bak.20260701`.
This **corrects the goal-spec context** of "4 key-bearing config.yaml.bak*" → 2
key-bearing config baks + 1 env bak.

**`auth.json`** (0600, mtime Jul 13): `credential_pool` with 12 lanes, every entry an
env-REFERENCE (`source: env:<NAME>` + fingerprint) — no raw key material. Notable:
the `anthropic` lane's base_url is **`https://api.kimi.com/coding`** — agni's
"anthropic" is a Kimi Anthropic-compatible endpoint fed by `ANTHROPIC_API_KEY`'s
value, not Anthropic at all. `minimax` lane `last_status: exhausted /
insufficient_balance_error`.

**Canon shape**: `/root/.dharma/agent_keys.env` EXISTS — 0600, 6772B, **mtime Jul 8
01:47** (+ `.bak.20260708T014743Z`): a prior `dkeys-sync-agni` full-vault push,
sitting UNUSED by hermes. `/root/dharma_swarm` exists but is NOT a git repo (only
`spec-forge/`, Mar 27). No `model_capability_floor` anywhere at depth ≤4.

**Report-only health**: nginx `failed`+`disabled` — bind :80 already held by caddy
(the intended proxy); something attempted an nginx start within the last 24h.
1.5GB `/root/.hermes/state.db`.

### A.4 Dead-lane verdicts (agni hermes `provider_routing.order`)

| Lane | Verdict | Evidence |
|---|---|---|
| zai | CREDENTIALED (duplicated) | `.env` GLM_API_KEY + inline config.yaml:668 (same value by fingerprint) |
| kimi-coding | **DEAD** | pool sources `env:KIMI_API_KEY`; name absent from .env, gateway process env, /root/agni/.env, /opt/openclaw.env, /root/.dharma/agent_keys.env, shell rc files, /etc/environment, config inline |
| openrouter | CREDENTIALED on-box | `.env` OPENROUTER_API_KEY. NOTE: the Mac's OPENROUTER key probes HTTP 404 (dkeys 07-14); whether agni's is the same value is unknown (auth.json fingerprints allow comparison in implementation phase, no values needed) |
| ollama-cloud | **DEAD at gateway runtime** | sources `env:OLLAMA_API_KEY` — exported only in /root/.bashrc (login shells); the user-scope systemd gateway never sees it |
| deepseek | **DEAD** | sources `env:DEEPSEEK_API_KEY`; absent everywhere checked (same list as kimi-coding) |
| anthropic | CREDENTIALED but MISLABELED | base_url `https://api.kimi.com/coding` (auth.json) — a Kimi lane wearing the anthropic name |
| (primary model) openai-api | CREDENTIALED | `.env` OPENAI_API_KEY; default `gpt-5.6-sol` |
| minimax | EXHAUSTED | auth.json `last_status: exhausted / insufficient_balance_error` |

Of the 6-lane routing order, only zai, openrouter, and anthropic(→Kimi) are
demonstrably credentialed at gateway runtime. Per the receipts discipline
(MODEL_KEY_ROUTING.md:154-158) these are credential verdicts, not completion
receipts — live receipts land in §8 during implementation.

### A.5 Inline-secret scrub list (operator-gated; nothing scrubbed yet)

1. `agni:/root/.hermes/config.yaml:668` — live inline ZAI/GLM key → replace with an
   env reference (or hermes-native secrets mechanism) at first render.
2. `agni:/root/.hermes/config.yaml.bak-ginko-mcp-20260705T161745Z:661` — archive to
   `/root/.hermes/secure_archive/` (0700) or delete; operator picks.
3. `agni:/root/.hermes/config.yaml.bak-provider-20260705T015350Z:670` — same.
4. `agni:/root/.hermes/.env.bak.20260701` — key-bearing env snapshot; same choice.
5. rushabdev (if admitted, D4): chmod 0600 `/home/openclaw/.openclaw/.env` (0644) and
   `/home/openclaw/dharmic-agora/.env` (0664) — report-only finding §A.3.
6. **Rotate the z.ai key** (see §B security events) — after rotation, items 1-4
   become moot for that key, but the scrub still applies as hygiene.

meghadharma: zero inline secrets found in hermes config or its 3 baks (§A.2) —
nothing to scrub there.

### A.6 Fleet smoothness sweep — 2026-07-15 16:13–16:17 UTC (live lane probes per box)

Probes ran ON each box with that box's own keys (status codes only; python via SSH):

| Lane | Mac | agni | meghadharma | rushabdev |
|---|---|---|---|---|
| z.ai coding | ✓200 (rotated key) | ✓200 (own key, fp 2cb7f68e) | ✓200 (own key, fp **d2cd585ace8c** — a THIRD distinct z.ai key) | ✗ `GLM_API_KEY` **EMPTY** in .env |
| openrouter | ✓200 valid | ✓200 | ✓200 | auth ✓200, but completions 402 — **account credits exhausted 07-14** |
| ollama cloud | ✓200 | dead at gateway runtime (§A.4) | n/a | ✓200; `last_status: ok` |
| kimi | ✓200 | ✗**401 both auth schemes** (key rejected — contradicts §A.4 "CREDENTIALED"; live probe wins) | n/a | n/a |
| openai | oauth ✓ / metered 429 | ✓200 | n/a | oauth **exhausted until 2026-07-19 22:36 UTC** — auto-degraded gpt-5.6-sol→gpt-5.5, functioning |
| anthropic metered | $ funds=0 | (name repurposed → kimi) | key present, unprobed | name in trading vault only |

Service truth: rushabdev = 0 failed units, all 10 dharma units + both gateways active.
agni = gateway/telegram/openclaw healthy; but 'A2A Journal Summary' hermes cron
dead-stalled every 2h on config drift (unpinned job vs global default change
zai→openai-api; fix = in-agent `cronjob action=update job_id=fbfae3b26e3b` — the
`hermes cron edit` CLI has no provider/model flags), AGNI Health Monitor cron in
alert state (exit 1 every 15m), codex-claude-sync + codex-maint units failed (exit 1).
meghadharma = **dharma-swarm container unhealthy ×39** (health API on :7433 hangs;
process alive; restart is the remedy — DENIED by session policy pending operator
approval), litestream still crash-looping (destination NEVER configured anywhere
on-box: all three LITESTREAM_* env names present with **length 0**; needs an
S3-compatible target + creds = operator decision), dharmic-quant-cron "unhealthy" is
a mis-copied healthcheck (curls :8080 which belongs to the web container),
hermes-on-megha Discord adapter looping `PrivilegedIntentsRequired` ×154/6h (Discord
dev-portal toggle needed) and Firecrawl tools erroring (no FIRECRAWL key on that box;
rushabdev has one — divergence), loopback-binding compose fix STILL uncommitted.
Disks: agni 82%, rushabdev 85% (~2G reclaimable in .npm/.cache), megha 30%.

## Appendix B — Security events during this audit

**Partial key-fragment exposure (disclosed by the agni auditor)**: while
shape-classifying `config.yaml:668`, the auditor's redaction pipeline split a long
string on a `.` character and a ~16-char TAIL FRAGMENT of the z.ai key value appeared
in one intermediate command output inside that agent's transcript (local file under
the session task directory on this Mac). The full value was never printed; nothing
entered git or this document. Because the same key value exists in 4 places on agni
(§A.5 items 1-4) and its fragment touched a transcript, **recommend precautionary
rotation of the z.ai (GLM_API_KEY/ZAI_API_KEY) key**: obtain a new key → `dkeys add
GLM_API_KEY` on the Mac → re-sync per D2 once approved → update agni `.env` +
scrubbed config in the same apply.

**CORRECTION (2026-07-15 apply log, §8)**: fingerprinting during the rotation showed
the exposed fragment belongs to agni's own z.ai key (= Mac `AGNI_GLM_API_KEY`,
fp `2cb7f68e4179`), which is a **different key** from Mac canonical GLM/ZAI. Mac
canon was rotated anyway (operator supplied a new key; receipts in §8); the exposed
AGNI key was probed **still active** and its deactivation is pending the sequencing
decision in §8.

### A.2 meghadharma — audited 2026-07-15 15:46 UTC (read-only)

Host `meghadharma-cloud`, up 12d, disk 30% used (82G free), Python 3.12.3, Node 22.

**Vault**: `/root/.dharma/agent_keys.env` — 0600 root, 762B, mtime Jul 12 03:28,
**29 names**: ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY,
OLLAMA_BASE_URL, OLLAMA_API_KEY, NVIDIA_NIM_BASE_URL, NVIDIA_NIM_API_KEY,
CEREBRAS_API_KEY, SILICONFLOW_API_KEY, TOGETHER_API_KEY, FIREWORKS_API_KEY,
GOOGLE_AI_API_KEY, SAMBANOVA_API_KEY, MISTRAL_API_KEY, CHUTES_API_KEY, KIMI_API_KEY,
KIMI_BASE_URL, MOONSHOT_API_KEY, MOONSHOT_BASE_URL, ZHIPU_API_KEY, ZHIPU_BASE_URL,
DEVIN_NATS_USER/PW/URL, LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST, SAKANA_API_KEY.
**NOT a Mac mirror**: carries 10+ names absent from the Mac vault (CEREBRAS,
SILICONFLOW, TOGETHER, FIREWORKS, MISTRAL, CHUTES, SAMBANOVA, ZHIPU_API_KEY,
LANGFUSE_*) while lacking Mac names (GLM_API_KEY, ZAI_API_KEY, DEEPSEEK_API_KEY,
MINIMAX_API_KEY, GEMINI_API_KEY…). Even the "closest to canon" box has a divergent
key-name set. **No dkeys on the box** (find + which: absent).

**dharma_swarm clone**: `/root/dharma_swarm` on `main` @ 0beef758 (2026-07-09,
PR #821 merge), ≥123 commits behind origin/main (remote refs stale since Jul 12
03:08), 4 dirty items (docker-compose.yml, Dockerfile.swarm modified + 2 untracked).
All four routing-canon files present (runtime_provider.py, model_hierarchy.py,
api_keys.py, docs/ops/MODEL_KEY_ROUTING.md — mtimes Jul 9 09:45).

**Hermes**: Docker container `hermes`, image `nousresearch/hermes-agent:v2026.7.7.2`
(no /opt/hermes-agent). `/root/.hermes/.env` 0600, 5 names: OPENROUTER_API_KEY,
DISCORD_BOT_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_HOME_CHANNEL,
TELEGRAM_HOME_CHANNEL_THREAD_ID. `config.yaml` (mtime Jul 15 10:43): **no
provider_routing section** (it exists only commented-out in
config.yaml.bak-20260712T060137Z:147); model default `tencent/hy3:free`,
`provider: nous`, `base_url: https://inference-api.nousresearch.com/v1`
(config.yaml:1-4). Inline-secret census of config.yaml + all 3 .baks: **zero inline
secret values** (all hits were prose/field names).

**Guards (live container env, docker inspect — CONFIRMED fail-closed)**:
`DHARMA_EVOLUTION_SHADOW=1`, `DGC_AUTONOMY_LEVEL=1`, `DHARMA_ALLOW_LIVE_MUTATION=0`,
`DHARMA_SELF_IMPROVE=0`, `DHARMA_ALLOW_CUSTODIAN_MERGE=0`, `DHARMA_SPINE_DISPATCH=1`;
compose defaults agree (docker-compose.yml:98-101). The dharma-swarm container also
carries ~40 provider key env NAMES (values not read). Nothing in this design touches
these flags.

**Report-only findings**: (1) off-host backup DOWN — `dharma-litestream` container
crash-looping every ~60s on `file replica path required`; root cause
`LITESTREAM_REPLICA_URL` set-but-EMPTY (docker inspect); only on-host snapshots
(15-min `dharma-command-backup.timer`) exist. (2) `dharmic-quant-cron` container
unhealthy 11 days. (3) NATS `*:4222` (authed, 5 users in /etc/nats-server.conf) and
`*:8222` monitoring (likely unauthenticated) are world-bound. (4) one-shot
`dharma-command-revoke-cursor-key.timer` queued to fire **2026-07-16 12:28 UTC**.
(5) root cron `*/10` `rsi-keys-refresh` is a read-only HTTP probe — will NOT fight a
config push (verified script contents).

### A.3 rushabdev — audited 2026-07-15 15:46 UTC (read-only)

Host `openclaw23onubuntu-s-2vcpu-4gb-120gb-intel-sgp1-01` (167.172.95.184, DO SGP1),
up 118 days, disk 85% used (19G free — report-only), mem 3.9G/2.2G available.

**Access**: `/root/.ssh/authorized_keys` 0600, mtime Jul 10 13:15 UTC, 7 ed25519 keys
(comments): dhyana@MacBook-Pro-4.local ×4, johnvincentshrader@gmail.com,
root@agni-openclaw, dhyana@old-mac. Root logins recorded Jul 2–14 (last Jul 14 10:00).
`/home/openclaw/.ssh/authorized_keys`: one key `agni@trishula`.

**Hermes**: at `/root/.hermes/` (NOT /opt), **v0.18.2, 167 revisions behind**
(`/root/.hermes/.update_check`). `config.yaml` (0600, `_config_version: 33`, mtime
Jul 15 07:10): default `model: gpt-5.6-sol` / `provider: openai-codex` /
`base_url: https://chatgpt.com/backend-api/codex` (config.yaml:1-8); fallback
`glm-5.2` via `https://ollama.com/v1`. Secret-bearing lines (values not read):
session_key:114, api_key:187-290 (auxiliary block), secret:362, record_key:416,
secrets:652. `auth.json` (mtime Jul 14): top-level keys active_provider,
credential_pool, providers, updated_at, version.

**Key inventory (names only)**: `/root/.hermes/.env` (0600, mtime Jul 10 14:41,
40 names) incl. OPENROUTER_API_KEY, GLM_API_KEY, KIMI_API_KEY, MINIMAX_API_KEY,
MINIMAX_CN_API_KEY, OPENCODE_ZEN_API_KEY, OPENCODE_GO_API_KEY, PARALLEL_API_KEY,
FIRECRAWL_API_KEY, FAL_KEY, HONCHO_API_KEY, BROWSERBASE_API_KEY/PROJECT_ID,
VOICE_TOOLS_OPENAI_KEY, TINKER_API_KEY, WANDB_API_KEY, DISCORD_BOT_TOKEN,
SLACK_BOT_TOKEN, SLACK_APP_TOKEN, OLLAMA_API_KEY, TELEGRAM_BOT_TOKEN, GROQ_API_KEY.
Copies: `/root/.config/x-cli/.env` (symlink to same), state-snapshot copy of Jul 14.
Other stores: `/root/rushabdev/keys/vault.env` (0600, Apr 14 — ANTHROPIC_API_KEY +
Polymarket wallet/keystore credential names), `/root/.hermes/.secrets` (NEAR_AI,
MOLTBOOK, DEALWORK, TOKU, ABS names), `/root/x402-api/.env` (CDP_API_KEY_ID/SECRET),
`/root/.dharma/nats/remote_agent_bridge.env` (NATS_USER/PASSWORD; mtime **Jul 15
01:21** — freshest write on the box), `/root/.dharma/a2a_gateway/gateway.env`,
codex `auth.json` ×3 (OAuth tokens). **Hygiene findings (report-only)**:
`/home/openclaw/.openclaw/.env` is 0644 (world-readable; Slack/Gmail/Discord names)
and `/home/openclaw/dharmic-agora/.env` is 0664 (SAB_JWT_SECRET, OPENROUTER_API_KEY,
NVIDIA_API_KEY, LLAMA_CLOUD_API_KEY names).

**dharma**: `/root/.dharma/` live (22 dirs, mtime Jul 15 07:12; a2a_bus, fleet, nats,
ontology.db …). `/root/dharma_swarm` **absent** — no repo checkout.

**Runs**: dharma-a2a-mailbox-gateway, dharma-a2a-rushabdev-hermes-bridge,
dharma-command-node, dharma-dashboard-api (:8420), dharma-dashboard-web (:3420),
dharma-swarm (cron daemon), fleet-collab-loop, fleet-hub (NATS), sab-flywheel(+web),
rushabdev-watchdog, chaiwala-bridge, caddy, redis, ollama, docker, tailscaled.
openclaw gateway: system unit disabled, but LIVE as root **user-scope** systemd unit
`openclaw-gateway.service` (pid 289565, up ~18.7d) — resolves the "not under systemd"
memory note. Network: public listeners :22/:80/:443/:5000/:18789 (18789 ufw-denied
publicly, allowed from agni only); ufw ACTIVE, agni (157.245.193.15) granted full
access + :18789 + :4222 (NATS). Cron: vps-sync every 5m, trishula rsync every 1m,
nightly Polymarket backup 03:10; two Telegram keepalive jobs disabled 07-05/06.

### A.4 Dead-lane verdicts — PENDING (fed by A.1)

### A.5 Inline-secret scrub list — PENDING (fed by A.1)
