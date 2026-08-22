import { expect, test, type Page } from "@playwright/test";

const CONTROL_SURFACE_ROUTE = "/dashboard/control-surface";

function envelope(data: unknown) {
  return {
    status: "ok",
    data,
    error: "",
    timestamp: "2026-08-23T00:00:00Z",
  };
}

async function stubReadOnlyControlSurface(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = {};
    if (path === "/api/control-surface/rows") {
      data = [];
    } else if (path === "/api/control-surface/summary") {
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
        sources_consulted: ["browser_read_only_fixture"],
      };
    } else if (path.endsWith("/snapshot")) {
      data = {
        schema_version: "dharma.control_surface.mission_snapshot.v1",
        request_id: "mobile-shell-layout-proof",
        generated_at: "2026-08-23T00:00:00Z",
        source_errors: [],
        data: {
          schema_version: "dharma.control_surface.mission_snapshot.v1",
          mission_id: "sadhana-10-20260823",
          state: "uninitialized",
          source_mode: "injected_read_only",
          snapshot: null,
          runtime_projection_ready: false,
          runtime_projection_mode: "unavailable",
          proves_executor_liveness: false,
        },
      };
    } else if (path.endsWith("/ds-goal/cards")) {
      data = { state_root: "fixture", mission_id: null, card_count: 0, cards: [] };
    } else if (path.endsWith("/agentops/cards")) {
      data = { work_packet_root: "fixture", packet_id: null, card_count: 0, cards: [] };
    } else if (path.endsWith("/a2a/cards")) {
      data = { receipt_root: "fixture", target: null, card_count: 0, cards: [] };
    } else if (path.endsWith("/semantic-receipts/cards")) {
      data = {
        receipt_root: "fixture",
        model: null,
        verdict: null,
        card_count: 0,
        cards: [],
      };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(envelope(data)),
    });
  });
}

test("mobile actual route has one readable constellation shell", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stubReadOnlyControlSurface(page);
  await page.goto(CONTROL_SURFACE_ROUTE, { waitUntil: "domcontentloaded" });

  await expect(page.getByTestId("mobile-dashboard-nav")).toBeVisible();
  await expect(page.getByTestId("desktop-dashboard-sidebar")).toBeHidden();
  await expect(
    page.getByRole("link", { name: "Constellation", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Dharma Constellation" }),
  ).toBeVisible();

  const geometry = await page.evaluate(() => {
    const main = document.querySelector("main");
    if (!(main instanceof HTMLElement)) throw new Error("main is missing");
    const rect = main.getBoundingClientRect();
    const overflowing = Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => {
        const bounds = element.getBoundingClientRect();
        return {
          tag: element.tagName,
          testId: element.dataset.testid ?? "",
          className: element.className.toString().slice(0, 160),
          left: Math.round(bounds.left),
          right: Math.round(bounds.right),
          width: Math.round(bounds.width),
          scrollWidth: element.scrollWidth,
        };
      })
      .filter((item) => item.right > window.innerWidth + 1 || item.width > window.innerWidth + 1)
      .sort((left, right) => right.right - left.right)
      .slice(0, 12);
    return {
      innerWidth: window.innerWidth,
      scrollWidth: Math.max(
        document.documentElement.scrollWidth,
        document.body.scrollWidth,
      ),
      mainLeft: rect.left,
      mainRight: rect.right,
      overflowing,
    };
  });

  expect(
    geometry.scrollWidth,
    `overflowing elements: ${JSON.stringify(geometry.overflowing)}`,
  ).toBeLessThanOrEqual(geometry.innerWidth);
  expect(Math.abs(geometry.mainLeft)).toBeLessThanOrEqual(1);
  expect(geometry.mainRight).toBeLessThanOrEqual(geometry.innerWidth + 1);
});

test("desktop actual route preserves the fixed navigation contract", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await stubReadOnlyControlSurface(page);
  await page.goto(CONTROL_SURFACE_ROUTE, { waitUntil: "domcontentloaded" });

  await expect(page.getByTestId("mobile-dashboard-nav")).toBeHidden();
  await expect(page.getByTestId("desktop-dashboard-sidebar")).toBeVisible();
  const mainBox = await page.getByTestId("dashboard-main").boundingBox();
  expect(mainBox).not.toBeNull();
  expect(Math.abs((mainBox?.x ?? 0) - 260)).toBeLessThanOrEqual(1);
  expect((mainBox?.x ?? 0) + (mainBox?.width ?? 0)).toBeLessThanOrEqual(1441);
});
