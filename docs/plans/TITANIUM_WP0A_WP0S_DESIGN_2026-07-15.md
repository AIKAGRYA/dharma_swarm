# Titanium WP-0A + WP-0S — Design Notes (prep-only, warm-start)

**Doc role (per `docs/AGENTS.md`):** `working_plan` — prep-only design notes
subordinate to `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md`
(spec:373-502, the authority). No code changes here; this records the current-state
anchors and the smallest-change design so execution starts warm the moment the gate
clears. Every anchor is a `file:line` or an observed command exit.

**Author seat:** fable_claude_code. **Date:** 2026-07-15. **Entry SHA:** `971923a71c18`.
**Both packets depend on WP-00 admission** (spec:377, spec:436) — nothing here is
executable in PREP-ONLY mode.

---

## WP-0A — Hermetic Python bootstrap (Findings: TIT-004; spec:432-502)

**Allowed files (spec:438-443):** `Makefile`, `.github/workflows/hermetic.yml`,
`Dockerfile`, `tests/test_bootstrap_contract.py` (new). `pyproject.toml` and
`uv.lock` are **read-only inputs** (spec:445) — any manifest defect is a separate
DharmaGraph-owned packet.

### Current state (measured)

- **The hard part is already done in CI.** `.github/workflows/hermetic.yml:25,42,44-50`
  already pins `UV_VERSION: "0.11.2"`, installs it, then runs
  `uv lock --check` (drift oracle) followed by `uv sync --frozen --extra dev`. This
  is exactly the WP-0A frozen path (spec:456-463). The CI hermetic lane is correct
  today; WP-0A's job is to surface the same path locally and reconcile the two
  remaining unpinned installers.
- **No `bootstrap` target exists.** `grep '^bootstrap:' Makefile` → none. This is the
  net-new target (spec:449).
- **`install` is unpinned editable.** `Makefile:277-278` — `install: pip install -e ".[dev]"`.
  This is precisely what spec:451 (step 3) replaces with delegation to the frozen path.
- **`.venv` resolution is already partly wired.** `Makefile:22` defines
  `VENV_PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,$(PYTHON))`;
  test targets use it (`Makefile:317-321`). `ruff` is still called bare
  (`Makefile:324,331`) — spec:452 wants `.venv/bin/ruff` resolved explicitly after
  bootstrap.
- **The Dockerfile uses live pip resolution, not the lock.** `Dockerfile:11-12`
  installs `requirements-ginko.txt` via `pip install --no-cache-dir`; `Dockerfile:19`
  does `pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir .`
  — unpinned, and the `2>/dev/null || ...` **swallows the failure of the editable
  install** (spec:454 "Do not download unpinned executable scripts"; spec:492 "Docker
  dependency failure must not be swallowed"). It cannot claim hermeticity while
  resolving live (spec:453).
- **Frozen path works off-pin here (design evidence, not authority).** On this host
  (uv `0.8.17`, not the pinned `0.11.2`): `uv lock --check` → **exit 0** ("Resolved
  145 packages"); `uv sync --frozen --extra dev` → **exit 0** (built `.venv`). So the
  check/sync path is resolver-tolerant, but the spec pins `0.11.2` deliberately so the
  *drift verdict* is a function of a fixed resolver (hermetic.yml:23-25). `make
  bootstrap` must **install the pinned uv** (spec:459), not reuse whatever is present.

### Smallest-change design

1. **Add `make bootstrap`** mirroring the proven CI path (spec:456-463):
   ```make
   UV_VERSION ?= 0.11.2
   bootstrap:
   	python3 -m pip install --user "uv==$(UV_VERSION)"
   	UV_BIN="$$(python3 -m site --user-base)/bin/uv"; \
   	"$$UV_BIN" lock --check && "$$UV_BIN" sync --frozen --extra dev
   ```
   Keep it idempotent (spec:501). If the base env later ships uv, reuse only after
   confirming the exact version (spec:465).
2. **Delegate `install`** to the frozen path (spec:451) instead of
   `pip install -e ".[dev]"` — likely `install: bootstrap` or a shared recipe.
3. **Resolve `.venv/bin/ruff`** in lint targets after bootstrap (spec:452); `VENV_PYTHON`
   already exists, add a `VENV_RUFF` sibling.
4. **Reconcile the Dockerfile** (spec:453-454): either build against the locked
   closure (`uv sync --frozen` inside the image) **or** label it an explicit
   non-hermetic legacy lane. Remove the `2>/dev/null || ...` failure-swallow at
   `Dockerfile:19` so a dependency failure fails the build (spec:492).

### Contract test `tests/test_bootstrap_contract.py` (spec:469-475)

Reads the **real** Makefile + `hermetic.yml` and asserts:
- the pinned uv version is installed/found (not `latest`);
- `uv.lock` is checked **before** sync;
- the frozen lock is used (`--frozen`);
- verification resolves tools inside `.venv`;
- Docker dependency failure is **not** swallowed.
Must fail if bootstrap regresses to unpinned editable install or bypasses lock drift
(spec:475). This is a structural contract test over file contents, so it runs
hermetically without a live network.

### Verification (spec:479-484) & negatives (spec:488-492)

`make bootstrap` → `.venv/bin/python -m pytest --collect-only -q` → `make install`
→ `make lint-blockers`, from a container with python+pip but no uv/user-site/venv.
Negatives: modified `pyproject.toml` w/o lock refresh → fails at `uv lock --check`;
pinned-uv install failure → nonzero; Docker dep-resolution failure → image build fails.

### Risk / watch-items

- **uv pin availability:** spec pins uv `0.11.2` (spec:449) but this host has `0.8.17`.
  WP-0A's owner must confirm `uv==0.11.2` installs on the clean-room Linux x86_64
  before ratifying; if not, amend the toolchain table through a reviewed packet
  (spec:288) — never silently substitute.
- **Docker legacy-lane decision** is a fork in the design (align vs label). Labeling
  is lower-risk for Phase 0 and defers image hardening to Phase 7 (spec:1369).

---

## WP-0S — Minimum fail-closed ingress (Findings: TIT-010; spec:373-431)

**Owner (spec:376):** proposed `repository-titanium-hardening-2026-07` for the narrow
API containment seam; **operator owns deployment containment.**
**Depends on:** WP-00, WP-0A (spec:377).
**Allowed files (spec:379-385):** `api/main.py`; the existing API auth/config module
used directly by `api/main.py` (**that module exists**: `dharma_swarm/api_keys.py`,
imported at `api/main.py:27`); `tests/test_api_auth.py`; `tests/test_verify_api.py`;
one new focused ingress-contract test if needed. Deployment files owned elsewhere are
**read-only** (spec:387).

### Current state (measured — this is TIT-010, confirmed live)

- **Bearer enforcement, key-absent = fully open.** `BearerAuthMiddleware`
  (`api/main.py:313`) reads the key per-request from `DASHBOARD_API_KEY_ENV`
  (`api/main.py:290-291`, module `dharma_swarm/api_keys.py`). When the key is `None`
  it returns `await call_next(request)` for **every** route (`api/main.py:316,322-326`),
  including all mutating `/api` routes. A dev-mode warning is logged
  (`api/main.py:61-68`) but startup is **not** refused.
- **Scope test is a path prefix, so non-`/api` transports bypass the bearer even when
  a key is set.** `needs_auth = path.startswith("/api")` (`api/main.py:336-338`).
  Escapes: GraphQL (`api/routers/graphql_router.py:18`, mounted no-prefix at
  `api/main.py:427`), holon **POST** `/holon/{name}/chat`
  (`api/routers/holon.py:43`, mounted `api/main.py:415`), chat WS
  `/ws/chat/session/{id}` (`api/routers/chat.py:1353`). Agents WS is under `/api`
  (`api/routers/agents.py:24,601`) but `BearerAuthMiddleware` derives from
  `BaseHTTPMiddleware`, which never runs on ASGI `websocket` scope — the in-middleware
  WS token branch (`api/main.py:340-345`) is effectively dead for real WS handshakes.
- **No production-shaped mode exists.** The only axis today is key-present vs
  key-absent. There is no explicit local-dev vs production-shaped selector, so
  "ambiguous → safer" (spec:391) is unimplementable as written until a mode signal is
  introduced.
- **No regression test pins the invariant.** `tests/test_api_auth.py` is **absent**;
  `tests/test_verify_api.py` exists but pins the verify subsystem + webhook HMAC, not
  the dashboard bearer route matrix.
- **A2A gateway is NOT the bearer surface** (do not touch it): it enforces its own
  `X-A2A-Key` (`dharma_swarm/a2a/node_gateway.py:144-165`) and is owned elsewhere.

### Smallest-change design (the minimum default-deny floor, spec:389-396)

1. **Explicit modes** (spec:391): add a `production-shaped` vs `local-development`
   selector (e.g. `DHARMA_API_MODE`, or infer from a deployment signal already
   present); ambiguous selects the safer (production-shaped) behavior.
2. **Refuse production-shaped startup with no key** (spec:392): in production-shaped
   mode, missing `DASHBOARD_API_KEY` (or equivalent material) fails startup rather
   than logging a warning and opening. Local-development mode retains the open path
   only when explicitly selected, loopback-bound, logged, and tested (spec:395).
3. **Replace the `/api`-prefix scope with an explicit transport classification**
   (spec:393): classify REST, GraphQL, WebSocket, webhook, A2A, and health/readiness
   as public / authenticated-read / authenticated-mutate / disabled, and apply **one**
   fail-closed authorization decision across every enabled mutation transport
   (spec:394). This is what closes the GraphQL/WS/holon bypass — the decision must not
   live in `path.startswith("/api")`. WS needs an ASGI-level check (pure
   `BaseHTTPMiddleware` cannot see websocket scope), so route the WS auth through a
   dependency or an ASGI middleware that covers `scope["type"] == "websocket"`.
4. **Do not claim full boundary closure** (spec:396). WP-0S is the floor; the full
   route matrix + rate/resource limits + Pydantic bounds are Phase 1 (spec:1157-1186).

### Behavioral tests (spec:398-406) — all in the allowed test files

Production-shaped + no key → startup fails; invalid creds fail across every enabled
protected ingress class; valid creds reach only their declared scope; GraphQL and WS
mutation paths cannot bypass the REST bearer decision; webhook signatures fail closed
when material is absent/malformed; public health/readiness expose no
mutation/secret payload; loopback-dev bypass (if retained) is rejected on non-loopback
binding. Negative controls at spec:417-420.

### Sequencing / operator gate (do not skip)

- **Operator records deployment exposure first** (spec:313-320, spec:1419;
  operator-decision queue item 7). Status ∈
  {`CONTAINED`, `PRIVATE_ONLY`, `NOT_DEPLOYED`, `BLOCKED_OPERATOR`}. If public or
  ambiguous exposure exists, **containment happens immediately** (spec:320), before
  the packet stack — because TIT-010 is confirmed reachable in code today.
- WP-0S result is `CLOSED_NOT_PROD` unless fresh deployment evidence proves
  `CLOSED_LIVE` (spec:430); `BLOCKED_OPERATOR` prevents Phase 0 closure (spec:429).

### Risk / watch-items

- **Mode signal choice** is the main design decision — reusing an existing env
  (`DHARMA_ORGANISM_ROOT` at `api/main.py:84`, or a deploy flag) avoids inventing a
  parallel config surface (CLAUDE.md naming SSOT). Prefer extending `api_keys.py`
  (already the auth/config module, spec:382) over a new module.
- **WS auth** is the trickiest technical piece: `BaseHTTPMiddleware` is structurally
  blind to websocket scope, so the fix is not a tweak to the existing middleware but a
  dependency/ASGI-layer decision applied at the WS route.
- **Rollback** (spec:422-424): revert the code-and-test packet; if rollback would
  reopen a reachable deployment, keep the service contained until a corrected packet
  lands.
