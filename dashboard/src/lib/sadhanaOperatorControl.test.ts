import assert from "node:assert/strict";
import { link, mkdtemp, mkdir, readFile, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  buildOperatorControlRequest,
  classifyControlProgress,
  describeDurableControlEvidence,
  evidenceFromSnapshot,
  isOperatorControlReason,
  OPERATOR_CONTROL_EVIDENCE_SCHEMA,
  OperatorControlDeliveryUnknown,
  parseOperatorControlEvidence,
  parseRequestAccepted,
  SADHANA_CONTROL_CSRF,
  SADHANA_CONTROL_ROUTE,
  submitOperatorControl,
  type OperatorControlEvidence,
  type PendingControl,
  type RequestAccepted,
} from "./sadhanaOperatorControl";
import {
  CONTROL_BODY_LIMIT,
  CONTROL_INTERNAL_URL,
  handleOperatorControlBridge,
  readBearerCredential,
} from "./sadhanaOperatorControlBridge";

const ORIGIN = "https://sadhana.example.ts.net";
const LOGIN = "operator@example.com";
const BEARER = "operator-bearer-test-value-with-32-bytes";
const DIGEST = `sha256:${"a".repeat(64)}`;
const RECEIPT_DIGEST = `sha256:${"b".repeat(64)}`;
const EFFECT_DIGEST = `sha256:${"c".repeat(64)}`;

function accepted(overrides: Partial<RequestAccepted> = {}): RequestAccepted {
  return {
    request_id: "request-001",
    idempotency_key: "idempotency-001",
    action: "pause",
    source_envelope_sha256: DIGEST,
    request_accepted: true,
    applied: false,
    decision_applied: false,
    effect_executed: false,
    ...overrides,
  };
}

function evidence(
  overrides: Partial<OperatorControlEvidence> = {},
): OperatorControlEvidence {
  return {
    schema_version: OPERATOR_CONTROL_EVIDENCE_SCHEMA,
    claim_stage: "authority_applied",
    control_state: "PAUSED",
    campaign_generation: 7,
    transition_sequence: 12,
    request_id: "request-001",
    idempotency_key: "idempotency-001",
    action: "pause",
    source_envelope_sha256: DIGEST,
    authority_receipt_ref: "campaign-control:receipt-001",
    authority_receipt_sha256: RECEIPT_DIGEST,
    authority_applied_at: "2026-08-23T01:02:03Z",
    effect_state: "unobserved",
    effect_receipt_ref: "",
    effect_receipt_sha256: "",
    effect_observed_at: null,
    ...overrides,
  };
}

function pending(
  overrides: Partial<PendingControl> = {},
): PendingControl {
  return {
    accepted: accepted(),
    baseline_campaign_generation: 7,
    baseline_transition_sequence: 11,
    ...overrides,
  };
}

function bridgeEnvironment() {
  return {
    SADHANA_CONTROL_INTERNAL_URL: CONTROL_INTERNAL_URL,
    SADHANA_CONTROL_BEARER_FILE: "/run/credentials/dashboard/operator_bearer",
    SADHANA_CONTROL_EXPECTED_ORIGIN: ORIGIN,
  };
}

function bridgeRequest(
  headers: Record<string, string> = {},
  body = JSON.stringify({ action: "pause" }),
): Request {
  return new Request(`${ORIGIN}${SADHANA_CONTROL_ROUTE}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: ORIGIN,
      "Tailscale-User-Login": LOGIN,
      "X-Sadhana-CSRF": SADHANA_CONTROL_CSRF,
      ...headers,
    },
    body,
  });
}

test("request builder emits only the exact six fields with a 90-second TTL", () => {
  const request = buildOperatorControlRequest("pause", "Operator pause", {
    now: new Date("2026-08-23T01:00:00.000Z"),
    requestId: "request-001",
    idempotencyKey: "idempotency-001",
  });
  assert.deepEqual(request, {
    action: "pause",
    request_id: "request-001",
    idempotency_key: "idempotency-001",
    issued_at: "2026-08-23T01:00:00.000Z",
    expires_at: "2026-08-23T01:01:30.000Z",
    reason: "Operator pause",
  });
  assert.throws(() => buildOperatorControlRequest("pause", " padded "));
  assert.throws(() => buildOperatorControlRequest("pause", "hidden\u200dformat"));
  assert.throws(() => buildOperatorControlRequest("pause", "private\ue000use"));
  assert.equal(isOperatorControlReason("Canonical operator reason"), true);
  assert.equal(isOperatorControlReason("decomposed e\u0301"), false);
  assert.equal(isOperatorControlReason("hidden\u200dformat"), false);
  assert.equal(isOperatorControlReason("private\ue000use"), false);
});

test("RequestAccepted parser requires fixed non-application claims and digest", () => {
  assert.deepEqual(parseRequestAccepted({ ...accepted(), harmless_extra: true }), accepted());
  assert.equal(parseRequestAccepted({ ...accepted(), applied: true }), null);
  assert.equal(parseRequestAccepted({ ...accepted(), source_envelope_sha256: "bad" }), null);
});

test("operator evidence is exact-set, privacy-preserving, and claim-consistent", () => {
  assert.deepEqual(parseOperatorControlEvidence(evidence()), evidence());
  assert.deepEqual(evidenceFromSnapshot({ operator_control_evidence: evidence() }), evidence());
  assert.equal(parseOperatorControlEvidence({ ...evidence(), operator_login: LOGIN }), null);
  assert.equal(
    parseOperatorControlEvidence({ ...evidence(), authority_receipt_sha256: "" }),
    null,
  );
  assert.equal(
    parseOperatorControlEvidence({
      ...evidence(),
      claim_stage: "effect_observed",
      effect_state: "unobserved",
    }),
    null,
  );
  assert.equal(
    parseOperatorControlEvidence({
      ...evidence(),
      authority_applied_at: "2026-02-31T01:02:03Z",
    }),
    null,
  );
  assert.equal(
    parseOperatorControlEvidence({ ...evidence(), request_id: "" }),
    null,
  );
  assert.equal(
    parseOperatorControlEvidence({ ...evidence(), transition_sequence: 0 }),
    null,
  );
  assert.equal(
    parseOperatorControlEvidence({ ...evidence(), control_state: "RUNNING" }),
    null,
  );
  assert.equal(
    parseOperatorControlEvidence({
      ...evidence(),
      claim_stage: "effect_observed",
      effect_state: "observed",
      effect_receipt_ref: "effect:receipt-001",
      effect_receipt_sha256: EFFECT_DIGEST,
      effect_observed_at: "2026-08-23T01:01:00Z",
    }),
    null,
  );
  assert.notEqual(
    parseOperatorControlEvidence({
      ...evidence(),
      claim_stage: "none",
      control_state: "RUNNING",
      transition_sequence: 0,
      request_id: "",
      idempotency_key: "",
      action: "",
      source_envelope_sha256: "",
      authority_receipt_ref: "",
      authority_receipt_sha256: "",
      authority_applied_at: null,
    }),
    null,
  );
  assert.equal(
    parseOperatorControlEvidence({
      ...evidence(),
      claim_stage: "none",
      transition_sequence: 0,
      request_id: "",
      idempotency_key: "",
      action: "",
      source_envelope_sha256: "",
      authority_receipt_ref: "",
      authority_receipt_sha256: "",
      authority_applied_at: null,
    }),
    null,
  );
});

test("progress joins all four coordinates and rejects stale generation or sequence", () => {
  assert.equal(
    classifyControlProgress(pending(), evidence()),
    "authority_applied_effect_unobserved",
  );
  assert.equal(
    classifyControlProgress(pending(), evidence({ request_id: "other" })),
    "request_accepted_awaiting_authority",
  );
  assert.equal(
    classifyControlProgress(pending(), evidence({ campaign_generation: 6 })),
    "evidence_unknown",
  );
  assert.equal(
    classifyControlProgress(pending(), evidence({ transition_sequence: 11 })),
    "evidence_unknown",
  );
  assert.equal(
    classifyControlProgress(
      pending(),
      evidence({ campaign_generation: 8, transition_sequence: 1 }),
    ),
    "evidence_unknown",
  );
  assert.equal(
    classifyControlProgress(
      pending(),
      evidence({
        claim_stage: "effect_observed",
        effect_state: "observed",
        effect_receipt_ref: "effect:receipt-001",
        effect_receipt_sha256: EFFECT_DIGEST,
        effect_observed_at: "2026-08-23T01:03:00Z",
      }),
    ),
    "effect_observed",
  );
});

test("durable control summary survives without browser pending state", () => {
  const summary = describeDurableControlEvidence(
    evidence({
      claim_stage: "effect_observed",
      effect_state: "observed",
      effect_receipt_ref: "observer:receipt-001",
      effect_receipt_sha256: EFFECT_DIGEST,
      effect_observed_at: "2026-08-23T01:03:00Z",
    }),
  );
  assert.equal(summary.controlState, "PAUSED");
  assert.equal(summary.claimStage, "effect_observed");
  assert.equal(summary.generationSequence, "7/12");
  assert.equal(summary.lastAction, "pause");
  assert.match(summary.authorityEvidence, /2026-08-23T01:02:03Z/);
  assert.match(summary.effectEvidence, /2026-08-23T01:03:00Z/);
  assert.equal(describeDurableControlEvidence(null).controlState, "UNKNOWN");
});

test("browser submission targets only the same-origin bridge and never carries a bearer", async () => {
  let observedUrl = "";
  let observed: RequestInit | undefined;
  const result = await submitOperatorControl(
    buildOperatorControlRequest("resume", "Resume same generation", {
      now: new Date("2026-08-23T01:00:00Z"),
      requestId: "request-001",
      idempotencyKey: "idempotency-001",
    }),
    async (url, init) => {
      observedUrl = String(url);
      observed = init;
      return Response.json(accepted({ action: "resume" }), { status: 202 });
    },
  );
  assert.equal(observedUrl, SADHANA_CONTROL_ROUTE);
  assert.equal(observed?.method, "POST");
  assert.deepEqual(observed?.headers, {
    "Content-Type": "application/json",
    "X-Sadhana-CSRF": SADHANA_CONTROL_CSRF,
  });
  assert.equal(JSON.stringify(observed).includes("18421"), false);
  assert.equal(JSON.stringify(observed).toLowerCase().includes("bearer"), false);
  assert.equal(result.action, "resume");
});

test("browser submission rejects mismatched accepted coordinates", async () => {
  const request = buildOperatorControlRequest("pause", "Pause exact request", {
    now: new Date("2026-08-23T01:00:00Z"),
    requestId: "request-001",
    idempotencyKey: "idempotency-001",
  });
  for (const mismatch of [
    { request_id: "request-other" },
    { idempotency_key: "idempotency-other" },
    { action: "resume" as const },
  ]) {
    await assert.rejects(
      submitOperatorControl(request, async () =>
        Response.json(accepted(mismatch), { status: 202 }),
      ),
      /operator_control_response_mismatch/,
    );
  }
});

test("emergency connection loss is typed unknown and never synthesized accepted", async () => {
  const request = buildOperatorControlRequest(
    "emergency_stop",
    "Stop before unsafe continuation",
    {
      now: new Date("2026-08-23T01:00:00Z"),
      requestId: "request-stop",
      idempotencyKey: "idempotency-stop",
    },
  );
  await assert.rejects(
    submitOperatorControl(request, async () => {
      throw new TypeError("connection disappeared after root stop");
    }),
    (error: unknown) =>
      error instanceof OperatorControlDeliveryUnknown &&
      /delivery outcome unknown/.test(error.message),
  );
});

test("bridge forwards only exact allowlisted headers and injects server bearer", async () => {
  let destination = "";
  let forwarded: RequestInit | undefined;
  const response = await handleOperatorControlBridge(
    bridgeRequest({
      Authorization: "Bearer browser-forgery",
      Cookie: "private=cookie",
      Forwarded: "for=203.0.113.9",
      "X-Real-IP": "203.0.113.9",
      "Tailscale-User-Name": "must-not-forward",
    }),
    {
      environment: bridgeEnvironment(),
      readBearer: async () => BEARER,
      signal: AbortSignal.abort(),
      fetchImpl: async (url, init) => {
        destination = String(url);
        forwarded = init;
        return Response.json(
          {
            status: "request_accepted",
            inbox: "normal",
            replayed: false,
            ...accepted(),
          },
          { status: 202 },
        );
      },
    },
  );
  assert.equal(response.status, 202);
  assert.equal(destination, CONTROL_INTERNAL_URL);
  assert.deepEqual(
    Object.keys(forwarded?.headers as Record<string, string>).sort(),
    [
      "Authorization",
      "Content-Type",
      "Origin",
      "Tailscale-User-Login",
      "X-Sadhana-CSRF",
    ].sort(),
  );
  assert.equal((forwarded?.headers as Record<string, string>).Authorization, `Bearer ${BEARER}`);
  assert.equal(forwarded?.redirect, "error");
  assert.equal(forwarded?.cache, "no-store");
  assert.deepEqual(await response.json(), accepted());
});

test("bridge rejects missing or folded identity, origin, CSRF, and content type", async () => {
  const cases: Array<[Record<string, string>, number]> = [
    [{ "Tailscale-User-Login": "" }, 403],
    [{ "Tailscale-User-Login": `${LOGIN}, ${LOGIN}` }, 403],
    [{ Origin: "https://evil.example" }, 403],
    [{ Origin: `${ORIGIN}, ${ORIGIN}` }, 403],
    [{ "X-Sadhana-CSRF": "1" }, 403],
    [{ "X-Sadhana-CSRF": `${SADHANA_CONTROL_CSRF}, ${SADHANA_CONTROL_CSRF}` }, 403],
    [{ "Content-Type": "application/json; charset=utf-8" }, 415],
  ];
  for (const [headers, expected] of cases) {
    const response = await handleOperatorControlBridge(bridgeRequest(headers), {
      environment: bridgeEnvironment(),
      readBearer: async () => BEARER,
      fetchImpl: async () => {
        throw new Error("rejected request reached upstream");
      },
    });
    assert.equal(response.status, expected);
  }
});

test("bridge rejects wrong configuration, blank bearer, and oversized body", async () => {
  const wrongUrl = await handleOperatorControlBridge(bridgeRequest(), {
    environment: {
      ...bridgeEnvironment(),
      SADHANA_CONTROL_INTERNAL_URL: "http://127.0.0.1:18420/",
    },
    readBearer: async () => BEARER,
  });
  assert.equal(wrongUrl.status, 503);
  const blank = await handleOperatorControlBridge(bridgeRequest(), {
    environment: bridgeEnvironment(),
    readBearer: async () => "",
  });
  assert.equal(blank.status, 503);
  const tooLong = await handleOperatorControlBridge(bridgeRequest(), {
    environment: bridgeEnvironment(),
    readBearer: async () => "x".repeat(513),
  });
  assert.equal(tooLong.status, 503);
  const oversized = await handleOperatorControlBridge(
    bridgeRequest({}, "x".repeat(CONTROL_BODY_LIMIT + 1)),
    { environment: bridgeEnvironment(), readBearer: async () => BEARER },
  );
  assert.equal(oversized.status, 413);
});

test("bridge does not relay an upstream non-202 body", async () => {
  const response = await handleOperatorControlBridge(bridgeRequest(), {
    environment: bridgeEnvironment(),
    readBearer: async () => BEARER,
    fetchImpl: async () =>
      new Response("secret upstream body and bearer", { status: 500 }),
  });
  assert.equal(response.status, 500);
  assert.equal((await response.text()).includes("secret upstream"), false);
});

test("bearer reader rejects missing, blank, directory, symlink, hardlink, and newline", async () => {
  const root = await mkdtemp(join(tmpdir(), "sadhana-bridge-"));
  const valid = join(root, "valid");
  await writeFile(valid, BEARER);
  assert.equal(await readBearerCredential(valid), BEARER);
  await assert.rejects(readBearerCredential(join(root, "missing")));
  const blank = join(root, "blank");
  await writeFile(blank, "");
  await assert.rejects(readBearerCredential(blank));
  const directory = join(root, "directory");
  await mkdir(directory);
  await assert.rejects(readBearerCredential(directory));
  const linked = join(root, "linked");
  await symlink(valid, linked);
  await assert.rejects(readBearerCredential(linked));
  const hardlinked = join(root, "hardlinked");
  await link(valid, hardlinked);
  await assert.rejects(readBearerCredential(hardlinked));
  const newline = join(root, "newline");
  await writeFile(newline, `${BEARER}\n`);
  await assert.rejects(readBearerCredential(newline));
  const tooLong = join(root, "too-long");
  await writeFile(tooLong, "x".repeat(513));
  await assert.rejects(readBearerCredential(tooLong));
});

test("route and bridge sources contain no public secret or broad rewrite", async () => {
  const route = await readFile(
    "src/app/dharma-internal/operator-control/route.ts",
    "utf8",
  );
  const bridge = await readFile("src/lib/sadhanaOperatorControlBridge.ts", "utf8");
  assert.match(route, /export async function POST/);
  assert.doesNotMatch(route, /export async function (GET|PUT|PATCH|DELETE)/);
  assert.doesNotMatch(route + bridge, /NEXT_PUBLIC|console\.|\/api\/:path/);
  assert.doesNotMatch(bridge, /Cookie.*headers|X-Forwarded-For.*headers/);
});
