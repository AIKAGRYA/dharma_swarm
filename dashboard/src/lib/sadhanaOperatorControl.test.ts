import assert from "node:assert/strict";
import { link, mkdtemp, mkdir, readFile, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  ACCOUNT_UI_CONFIRMATION_REQUEST_SCHEMA,
  AccountUiConfirmationDeliveryUnknown,
  buildOperatorControlRequest,
  buildAccountUiConfirmationRequest,
  classifyControlProgress,
  describeDurableControlEvidence,
  evidenceFromSnapshot,
  isOperatorControlReason,
  normalOperatorControlsAuthorized,
  OPERATOR_CONTROL_EVIDENCE_SCHEMA,
  OperatorControlDeliveryUnknown,
  parseOperatorControlEvidence,
  parseRequestAccepted,
  SADHANA_ACCOUNT_UI_CONFIRMATION_ROUTE,
  SADHANA_CONTROL_CSRF,
  SADHANA_CONTROL_ROUTE,
  submitAccountUiConfirmation,
  submitOperatorControl,
  type AccountUiConfirmationAccepted,
  type AccountUiConfirmationRequest,
  type AccountUiMeasurements,
  type OperatorControlEvidence,
  type PendingControl,
  type RequestAccepted,
} from "./sadhanaOperatorControl";
import {
  ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_CANONICAL,
  ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256,
  ACCOUNT_UI_CONFIRMATION_INTERNAL_URL,
  CONTROL_BODY_LIMIT,
  CONTROL_INTERNAL_URL,
  handleAccountUiConfirmationBridge,
  handleOperatorControlBridge,
  readBearerCredential,
} from "./sadhanaOperatorControlBridge";

const ORIGIN = "https://sadhana.example.ts.net";
const LOGIN = "operator@example.com";
const BEARER = "operator-bearer-test-value-with-32-bytes";
const DIGEST = `sha256:${"a".repeat(64)}`;
const RECEIPT_DIGEST = `sha256:${"b".repeat(64)}`;
const EFFECT_DIGEST = `sha256:${"c".repeat(64)}`;
const RELEASE_SHA = "d".repeat(40);
const ACCOUNT_UI_REQUEST_ID = "123e4567-e89b-42d3-a456-426614174000";

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

function accountUiMeasurements(
  overrides: Partial<AccountUiMeasurements> = {},
): AccountUiMeasurements {
  return {
    viewportWidthCssPx: 390,
    documentWidthCssPx: 390,
    visualViewportWidthCssPx: 390,
    coarsePointer: true,
    touchCapability: true,
    trustedBrowserEvent: true,
    ...overrides,
  };
}

function accountUiRequest(): AccountUiConfirmationRequest {
  return buildAccountUiConfirmationRequest(accountUiMeasurements(), {
    now: new Date("2026-08-23T01:00:00.000Z"),
    requestId: ACCOUNT_UI_REQUEST_ID,
  });
}

function accountUiAccepted(
  overrides: Partial<AccountUiConfirmationAccepted> = {},
): AccountUiConfirmationAccepted {
  return {
    status: "account_ui_confirmation_accepted",
    replayed: false,
    account_authenticated: true,
    candidate_recorded: true,
    authority_applied: false,
    dispatch_authorized: false,
    physical_device_attested: false,
    human_identity_attested: false,
    ...overrides,
  };
}

function accountUiBridgeEnvironment() {
  return {
    ...bridgeEnvironment(),
    SADHANA_ACCOUNT_UI_CONFIRMATION_INTERNAL_URL:
      ACCOUNT_UI_CONFIRMATION_INTERNAL_URL,
    SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256:
      ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256,
    SADHANA_RELEASE_SHA: RELEASE_SHA,
  };
}

function accountUiBridgeRequest(
  headers: Record<string, string> = {},
  body = JSON.stringify(accountUiRequest()),
): Request {
  return new Request(`${ORIGIN}${SADHANA_ACCOUNT_UI_CONFIRMATION_ROUTE}`, {
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

test("account UI builder requires the exact 390px coarse-touch trusted click", () => {
  assert.deepEqual(accountUiRequest(), {
    schema_version: ACCOUNT_UI_CONFIRMATION_REQUEST_SCHEMA,
    campaign_id: "sadhana-10-20260823",
    client_request_id: ACCOUNT_UI_REQUEST_ID,
    issued_at: "2026-08-23T01:00:00.000Z",
    expires_at: "2026-08-23T01:01:30.000Z",
    viewport_width_css_px_reported: 390,
    document_width_css_px_reported: 390,
    visual_viewport_width_css_px_reported: 390,
    coarse_pointer_reported: true,
    touch_capability_reported: true,
    trusted_browser_event_reported: true,
    explicit_confirmation_gesture_reported: true,
    dashboard_rendered_reported: true,
  });
});

test("account UI builder rejects geometry or event drift", () => {
  for (const drift of [
    { viewportWidthCssPx: 389 },
    { documentWidthCssPx: 391 },
    { visualViewportWidthCssPx: 390.5 },
    { coarsePointer: false },
    { touchCapability: false },
    { trustedBrowserEvent: false },
  ] satisfies Array<Partial<AccountUiMeasurements>>) {
    assert.throws(
      () => buildAccountUiConfirmationRequest(accountUiMeasurements(drift)),
      /account_ui_confirmation_client_observation_invalid/,
    );
  }
  assert.throws(
    () =>
      buildAccountUiConfirmationRequest(accountUiMeasurements(), {
        now: new Date(Number.NaN),
      }),
    /account_ui_confirmation_time_invalid/,
  );
  assert.throws(
    () =>
      buildAccountUiConfirmationRequest(accountUiMeasurements(), {
        requestId: "not-a-v4-uuid",
      }),
    /account_ui_confirmation_request_id_invalid/,
  );
});

test("account UI browser response remains exact candidate-only NoAuthority NoDispatch", async () => {
  const request = accountUiRequest();
  let observedUrl = "";
  let observed: RequestInit | undefined;
  const result = await submitAccountUiConfirmation(
    request,
    async (url, init) => {
      observedUrl = String(url);
      observed = init;
      return Response.json(accountUiAccepted(), { status: 202 });
    },
  );

  assert.equal(observedUrl, SADHANA_ACCOUNT_UI_CONFIRMATION_ROUTE);
  assert.equal(observed?.method, "POST");
  assert.equal(observed?.cache, "no-store");
  assert.equal(observed?.credentials, "same-origin");
  assert.deepEqual(observed?.headers, {
    "Content-Type": "application/json",
    "X-Sadhana-CSRF": SADHANA_CONTROL_CSRF,
  });
  assert.deepEqual(JSON.parse(String(observed?.body)), request);
  assert.deepEqual(result, accountUiAccepted());
  assert.match(
    ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_CANONICAL,
    /http_202=CandidateRecorded<NoAuthority,NoDispatch>/,
  );
  assert.equal(result.authority_applied, false);
  assert.equal(result.dispatch_authorized, false);
  assert.equal(result.physical_device_attested, false);
  assert.equal(result.human_identity_attested, false);
});

test("account UI browser rejects response schema or authority drift", async () => {
  const valid = accountUiAccepted();
  const invalidResponses: unknown[] = [
    { ...valid, schema_version: "unexpected" },
    { ...valid, status: "candidate_recorded" },
    { ...valid, account_authenticated: false },
    { ...valid, candidate_recorded: false },
    { ...valid, authority_applied: true },
    { ...valid, dispatch_authorized: true },
    { ...valid, physical_device_attested: true },
    { ...valid, human_identity_attested: true },
    { ...valid, replayed: "false" },
    Object.fromEntries(
      Object.entries(valid).filter(
        ([key]) => key !== "human_identity_attested",
      ),
    ),
  ];
  for (const invalid of invalidResponses) {
    await assert.rejects(
      submitAccountUiConfirmation(accountUiRequest(), async () =>
        Response.json(invalid, { status: 202 }),
      ),
      (error: unknown) =>
        error instanceof AccountUiConfirmationDeliveryUnknown &&
        error.code === "account_ui_confirmation_delivery_unknown",
    );
  }
});

test("account UI transport failure is typed delivery-unknown", async () => {
  await assert.rejects(
    submitAccountUiConfirmation(accountUiRequest(), async () => {
      throw new TypeError("connection disappeared after the one-shot POST");
    }),
    (error: unknown) =>
      error instanceof AccountUiConfirmationDeliveryUnknown &&
      error.code === "account_ui_confirmation_delivery_unknown" &&
      /do not create a new request/.test(error.message),
  );
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

test("normal controls require a valid post-preparation transition", () => {
  const preparedPause = evidence({ transition_sequence: 1 });
  const activationResume = evidence({
    action: "resume",
    control_state: "RUNNING",
    request_id: "activation-resume-001",
    idempotency_key: "activation-resume-idempotency-001",
    transition_sequence: 2,
  });
  const laterPause = evidence({ transition_sequence: 3 });
  const noClaim = {
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
  };

  assert.equal(
    normalOperatorControlsAuthorized({
      operator_control_evidence: preparedPause,
    }),
    false,
  );
  assert.equal(
    normalOperatorControlsAuthorized({
      operator_control_evidence: activationResume,
    }),
    true,
  );
  assert.equal(
    normalOperatorControlsAuthorized({ operator_control_evidence: laterPause }),
    true,
  );
  assert.equal(normalOperatorControlsAuthorized({}), false);
  assert.equal(
    normalOperatorControlsAuthorized({
      operator_control_evidence: { ...activationResume, unexpected: true },
    }),
    false,
  );
  assert.equal(
    normalOperatorControlsAuthorized({ operator_control_evidence: noClaim }),
    false,
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

test("account UI bridge pins endpoint, release, identity, bearer, and body bytes", async () => {
  const body = JSON.stringify(accountUiRequest());
  let destination = "";
  let forwarded: RequestInit | undefined;
  const response = await handleAccountUiConfirmationBridge(
    accountUiBridgeRequest(
      {
        Authorization: "Bearer browser-forgery",
        Cookie: "private=cookie",
        Forwarded: "for=203.0.113.9",
        "X-Real-IP": "203.0.113.9",
        "X-Sadhana-Release-SHA": "browser-release-forgery",
      },
      body,
    ),
    {
      environment: accountUiBridgeEnvironment(),
      readBearer: async () => BEARER,
      signal: AbortSignal.abort(),
      fetchImpl: async (url, init) => {
        destination = String(url);
        forwarded = init;
        return Response.json(accountUiAccepted(), { status: 202 });
      },
    },
  );

  assert.equal(response.status, 202);
  assert.equal(destination, ACCOUNT_UI_CONFIRMATION_INTERNAL_URL);
  assert.equal(forwarded?.method, "POST");
  assert.equal(forwarded?.cache, "no-store");
  assert.equal(forwarded?.redirect, "error");
  assert.deepEqual(
    Object.keys(forwarded?.headers as Record<string, string>).sort(),
    [
      "Authorization",
      "Content-Type",
      "Origin",
      "Tailscale-User-Login",
      "X-Sadhana-CSRF",
      "X-Sadhana-Release-SHA",
    ].sort(),
  );
  assert.deepEqual(forwarded?.headers, {
    Authorization: `Bearer ${BEARER}`,
    "Content-Type": "application/json",
    Origin: ORIGIN,
    "Tailscale-User-Login": LOGIN,
    "X-Sadhana-CSRF": SADHANA_CONTROL_CSRF,
    "X-Sadhana-Release-SHA": RELEASE_SHA,
  });
  assert.equal(
    new TextDecoder().decode(forwarded?.body as ArrayBuffer),
    body,
  );
  assert.deepEqual(await response.json(), accountUiAccepted());
});

test("account UI bridge rejects endpoint, binding, release, header, and bearer drift", async () => {
  const environmentDrift = [
    {
      ...accountUiBridgeEnvironment(),
      SADHANA_ACCOUNT_UI_CONFIRMATION_INTERNAL_URL:
        "http://127.0.0.1:18421/v1/account-ui-confirmations/",
    },
    {
      ...accountUiBridgeEnvironment(),
      SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256: "0".repeat(64),
    },
    { ...accountUiBridgeEnvironment(), SADHANA_RELEASE_SHA: "D".repeat(40) },
  ];
  for (const environment of environmentDrift) {
    const response = await handleAccountUiConfirmationBridge(
      accountUiBridgeRequest(),
      {
        environment,
        readBearer: async () => BEARER,
        fetchImpl: async () => {
          throw new Error("invalid environment reached upstream");
        },
      },
    );
    assert.equal(response.status, 503);
  }

  const headerDrift: Array<[Record<string, string>, number]> = [
    [{ Origin: "https://evil.example" }, 403],
    [{ Origin: `${ORIGIN}, ${ORIGIN}` }, 403],
    [{ "Tailscale-User-Login": "" }, 403],
    [{ "Tailscale-User-Login": `${LOGIN},${LOGIN}` }, 403],
    [{ "X-Sadhana-CSRF": "wrong-campaign" }, 403],
    [{ "Content-Type": "application/json; charset=utf-8" }, 415],
  ];
  for (const [headers, status] of headerDrift) {
    const response = await handleAccountUiConfirmationBridge(
      accountUiBridgeRequest(headers),
      {
        environment: accountUiBridgeEnvironment(),
        readBearer: async () => BEARER,
        fetchImpl: async () => {
          throw new Error("invalid browser headers reached upstream");
        },
      },
    );
    assert.equal(response.status, status);
  }

  const blankBearer = await handleAccountUiConfirmationBridge(
    accountUiBridgeRequest(),
    {
      environment: accountUiBridgeEnvironment(),
      readBearer: async () => "",
      fetchImpl: async () => {
        throw new Error("blank bearer reached upstream");
      },
    },
  );
  assert.equal(blankBearer.status, 503);
});

test("account UI bridge rejects every malformed or authority-expanding 202", async () => {
  const valid = accountUiAccepted();
  const upstreamBodies: Array<() => Response> = [
    () => new Response("{", { status: 202 }),
    () => Response.json({ ...valid, extra: true }, { status: 202 }),
    () => Response.json({ ...valid, status: "wrong" }, { status: 202 }),
    () => Response.json({ ...valid, authority_applied: true }, { status: 202 }),
    () => Response.json({ ...valid, dispatch_authorized: true }, { status: 202 }),
    () =>
      Response.json({ ...valid, physical_device_attested: true }, { status: 202 }),
    () =>
      Response.json({ ...valid, human_identity_attested: true }, { status: 202 }),
    () =>
      Response.json(
        Object.fromEntries(
          Object.entries(valid).filter(([key]) => key !== "candidate_recorded"),
        ),
        { status: 202 },
      ),
  ];
  for (const upstreamBody of upstreamBodies) {
    const response = await handleAccountUiConfirmationBridge(
      accountUiBridgeRequest(),
      {
        environment: accountUiBridgeEnvironment(),
        readBearer: async () => BEARER,
        fetchImpl: async () => upstreamBody(),
      },
    );
    assert.equal(response.status, 502);
    assert.deepEqual(await response.json(), {
      status: "request_rejected",
      error_code: "account_ui_confirmation_response_invalid",
    });
  }
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
