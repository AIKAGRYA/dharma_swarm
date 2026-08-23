import { expect, test, type Page } from "@playwright/test";

const CONTROL_ROUTE = "/dashboard/sadhana-control";
const BRIDGE_ROUTE = "/dharma-internal/operator-control";
const DIGEST = `sha256:${"a".repeat(64)}`;
const AUTHORITY_DIGEST = `sha256:${"b".repeat(64)}`;
const EFFECT_DIGEST = `sha256:${"c".repeat(64)}`;

type Evidence = Record<string, unknown>;

function noClaimEvidence(): Evidence {
  return {
    schema_version: "dharma.sadhana.operator_control_evidence.v1",
    claim_stage: "none",
    control_state: "RUNNING",
    campaign_generation: 7,
    transition_sequence: 0,
    request_id: "",
    idempotency_key: "",
    action: "",
    source_envelope_sha256: "",
    authority_receipt_ref: "",
    authority_receipt_sha256: "",
    authority_applied_at: null,
    effect_state: "unobserved",
    effect_receipt_ref: "",
    effect_receipt_sha256: "",
    effect_observed_at: null,
  };
}

function snapshotEnvelope(operatorControlEvidence: Evidence) {
  return {
    status: "ok",
    error: "",
    timestamp: "2026-08-23T00:00:00Z",
    data: {
      schema_version: "dharma.control_surface.mission_snapshot.v1",
      request_id: "mobile-operator-control-proof",
      generated_at: "2026-08-23T00:00:00Z",
      source_errors: [],
      data: {
        schema_version: "dharma.control_surface.mission_snapshot.v1",
        mission_id: "sadhana-10-20260823",
        state: "observed",
        source_mode: "injected_read_only",
        snapshot: {
          mission: {
            mission_id: "sadhana-10-20260823",
            session_id: "campaign:sadhana-10-20260823",
            title: "SADHANA 10",
            goal: "Bounded campaign",
            operator_id: "operator",
            status: "running",
            metadata: {},
            created_at: "2026-08-23T00:00:00Z",
            updated_at: "2026-08-23T00:00:00Z",
          },
          tasks: [],
          attempts: [],
          leases: [],
          receipts: [],
          reconciliation: "read_only_fixture",
          observed_at: "2026-08-23T00:00:00Z",
          authority: "outer_campaign_projection",
          proves_executor_liveness: false,
        },
        operator_control_evidence: operatorControlEvidence,
        runtime_projection_ready: false,
        runtime_projection_mode: "unavailable",
        proves_executor_liveness: false,
      },
    },
  };
}

async function stubControlProjection(page: Page) {
  let currentEvidence = noClaimEvidence();
  let acceptedRequest: Record<string, unknown> | null = null;

  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (
      path ===
      "/api/control-surface/missions/sadhana-10-20260823/snapshot"
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(snapshotEnvelope(currentEvidence)),
      });
      return;
    }
    let data: unknown = {};
    if (path === "/api/control-surface/rows") data = [];
    if (path === "/api/control-surface/summary") {
      data = {
        total: 0,
        bound: 0,
        partial: 0,
        drifted: 0,
        declared_only: 0,
        unknown: 0,
        human_decision_required_count: 0,
        p0_count: 0,
        p1_count: 0,
        generated_at: "2026-08-23T00:00:00Z",
        sources_consulted: ["operator_control_fixture"],
      };
    }
    if (path.endsWith("/cards")) {
      data = { card_count: 0, cards: [] };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        data,
        error: "",
        timestamp: "2026-08-23T00:00:00Z",
      }),
    });
  });
  await page.route(`**${BRIDGE_ROUTE}`, async (route) => {
    acceptedRequest = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      headers: { "Cache-Control": "no-store" },
      body: JSON.stringify({
        request_id: acceptedRequest.request_id,
        idempotency_key: acceptedRequest.idempotency_key,
        action: acceptedRequest.action,
        source_envelope_sha256: DIGEST,
        request_accepted: true,
        applied: false,
        decision_applied: false,
        effect_executed: false,
      }),
    });
  });

  return {
    authorityApplied() {
      if (!acceptedRequest) throw new Error("request has not been accepted");
      currentEvidence = {
        ...noClaimEvidence(),
        claim_stage: "authority_applied",
        control_state: "PAUSED",
        transition_sequence: 1,
        request_id: acceptedRequest.request_id,
        idempotency_key: acceptedRequest.idempotency_key,
        action: acceptedRequest.action,
        source_envelope_sha256: DIGEST,
        authority_receipt_ref: "campaign-control:receipt-001",
        authority_receipt_sha256: AUTHORITY_DIGEST,
        authority_applied_at: "2026-08-23T00:01:00Z",
      };
    },
    effectObserved() {
      currentEvidence = {
        ...currentEvidence,
        claim_stage: "effect_observed",
        effect_state: "observed",
        effect_receipt_ref: "observer:receipt-001",
        effect_receipt_sha256: EFFECT_DIGEST,
        effect_observed_at: "2026-08-23T00:01:05Z",
      };
    },
  };
}

test("390px phone flow keeps acceptance, application, and effect distinct", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const projection = await stubControlProjection(page);
  await page.goto(CONTROL_ROUTE, { waitUntil: "domcontentloaded" });

  const control = page.getByTestId("sadhana-operator-control");
  await expect(control).toBeVisible();
  await expect(control.getByRole("button", { name: /Approve proposal/ })).toBeDisabled();
  await expect(control.getByRole("button", { name: /Reject proposal/ })).toBeDisabled();

  await control.getByRole("button", { name: /Pause campaign/ }).click();
  await expect(page.getByTestId("control-step-confirm")).toBeVisible();
  const confirm = control.getByRole("button", { name: "Confirm pause campaign" });
  await expect(confirm).toBeDisabled();
  await control.getByLabel("Operator reason").fill("Pause before operator inspection");
  await confirm.click();

  await expect(control.getByText("Accepted", { exact: true })).toBeVisible();
  await expect(control.getByText("Awaiting authority", { exact: true })).toBeVisible();
  await expect(control.getByText("Not proven", { exact: true })).toBeVisible();

  projection.authorityApplied();
  await expect(control.getByText("Authority applied", { exact: true })).toBeVisible({
    timeout: 8_000,
  });
  await expect(control.getByText("Not proven", { exact: true })).toBeVisible();

  projection.effectObserved();
  await expect(control.getByText("Independently observed", { exact: true })).toBeVisible({
    timeout: 8_000,
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(control.getByText("Not requested", { exact: true })).toBeVisible();
  const durable = control.getByLabel("Current campaign control");
  await expect(durable.getByText("PAUSED", { exact: true })).toBeVisible();
  await expect(durable.getByText("effect_observed", { exact: true })).toBeVisible();
  await expect(durable.getByText("pause", { exact: true })).toBeVisible();
  await expect(durable.getByText(/2026-08-23T00:01:00Z/)).toBeVisible();
  await expect(
    page
      .getByTestId("mobile-dashboard-nav")
      .getByRole("link", { name: "Operator control" }),
  ).toBeVisible();

  const geometry = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: Math.max(
      document.documentElement.scrollWidth,
      document.body.scrollWidth,
    ),
    controlWidth:
      document.querySelector<HTMLElement>("[data-testid=sadhana-operator-control]")
        ?.getBoundingClientRect().width ?? 0,
  }));
  expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.viewport);
  expect(geometry.controlWidth).toBeLessThanOrEqual(390);
});

test("Constellation and phone navigation discover the focused control route", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stubControlProjection(page);
  await page.goto("/dashboard/control-surface", {
    waitUntil: "domcontentloaded",
  });

  const constellationLink = page.getByTestId("constellation-operator-control-link");
  await expect(constellationLink).toBeVisible();
  await expect(constellationLink).toHaveAttribute(
    "href",
    "/dashboard/sadhana-control",
  );
  await constellationLink.click();
  await expect(page).toHaveURL(/\/dashboard\/sadhana-control$/);
  await expect(page.getByTestId("sadhana-operator-control")).toBeVisible();
});

test("emergency confirmation warns that disconnect is not effect proof", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stubControlProjection(page);
  await page.goto(CONTROL_ROUTE, { waitUntil: "domcontentloaded" });
  const control = page.getByTestId("sadhana-operator-control");

  await control.getByRole("button", { name: /Emergency stop/ }).click();
  await expect(
    control.getByText(
      "After HTTP 202 the dashboard may disconnect. Disconnect is expected, not effect proof.",
    ),
  ).toBeVisible();
  const confirm = control.getByRole("button", { name: "Confirm emergency stop" });
  await control.getByLabel("Operator reason").fill("Stop before unsafe continuation");
  await expect(confirm).toBeDisabled();
  await control.getByLabel("Type EMERGENCY STOP").fill("EMERGENCY STOP");
  await expect(confirm).toBeEnabled();
});
