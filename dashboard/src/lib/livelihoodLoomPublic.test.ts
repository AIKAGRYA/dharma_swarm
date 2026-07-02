import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { loadLivelihoodLoomPublicSite } from "./livelihoodLoomPublic.ts";

test("loadLivelihoodLoomPublicSite exposes investor copy without hiding gates", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "livelihood-loom-public-"));
  writeJson(path.join(root, "cycles/latest.json"), {
    receipt_id: "cycle_1",
    created_at: "2026-06-29T00:00:00Z",
    status: "cultivation_ready_provider_blocked",
    provider_green: false,
    provider_readiness_gap: { status: "red" },
  });
  writeJson(path.join(root, "cultivation/top_50.json"), {
    candidate_count: 1000,
    candidates: [
      {
        rank: 1,
        source_rank: 4,
        name: "Zeta Pay",
        country: "India",
        domain: "finance_rails",
        prioritization_score: 0.98,
        wedge_label: "Payment acceptance",
      },
    ],
  });
  writeJson(path.join(root, "cultivation/wedges.json"), {
    wedges: [
      {
        rank: 1,
        wedge_id: "payment_acceptance_cashflow",
        label: "Payment acceptance",
        roi_score: 1.1,
        candidate_count_in_top_50: 12,
        roi_thesis: "Cashflow rails help merchants.",
      },
    ],
  });
  writeJson(path.join(root, "safety/top_50_safety_review.json"), {
    summary: {
      allowed: 1,
      needs_review: 1,
      blocked: 1,
      total: 3,
      flag_counts: { high_fee_lending: 1 },
    },
    reviews: [{ name: "Zeta Pay", safety_status: "allowed" }],
  });
  writeJson(path.join(root, "enablement_packets/index.json"), {
    packet_count: 5,
    packets: [],
  });
  writeJson(path.join(root, "demand/index.json"), {
    draft_only: true,
    sent: false,
    external_action_status: "risk_reviewed",
    first_paid_offer: "first_paid_offer.md",
    sponsor_briefs: [],
  });
  writeJson(path.join(root, "promotion/latest.json"), {
    steps: { "5_first_sponsor_target": { name: "Accion" } },
    artifacts: {},
    safety_boundary: { outreach_action_status: "risk_reviewed" },
  });
  writeJson(path.join(root, "promotion/external_acted_receipt_gate.json"), {
    status: "blocked_pending_human_governor_approval_and_external_act",
  });
  writeJson(path.join(root, "promotion/provider_readiness_gate.json"), {
    status: "red",
  });

  const site = loadLivelihoodLoomPublicSite(root);

  assert.equal(site.brand, "Livelihood Loom");
  assert.equal(site.sponsorTarget, "Accion");
  assert.equal(site.heroStats[0]?.value, "1,000");
  assert.match(site.statusNote, /provider proof remains pending/i);
  assert.match(site.proofBoundary, /External acted receipt is not claimed/i);
});

function writeJson(filePath: string, payload: unknown) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload)}\n`, "utf8");
}
