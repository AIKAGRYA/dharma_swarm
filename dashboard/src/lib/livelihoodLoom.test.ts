import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  loadLivelihoodLoomCandidateById,
  loadLivelihoodLoomCandidates,
  loadLivelihoodLoomDashboard,
  loadLivelihoodLoomDataRoom,
  loadLivelihoodLoomPacketById,
  loadLivelihoodLoomPackets,
  loadLivelihoodLoomSponsorTarget,
  loadLivelihoodLoomStatusGates,
  loadLivelihoodLoomWedgeById,
  loadLivelihoodLoomWedges,
} from "./livelihoodLoom.ts";

test("loadLivelihoodLoomDashboard projects local receipts without provider-green inflation", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "livelihood-loom-dashboard-"));
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
    wedge_count: 1,
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
      needs_review: 0,
      blocked: 0,
      total: 1,
      flag_counts: { high_fee_lending: 0 },
    },
    reviews: [
      {
        name: "Zeta Pay",
        safety_status: "allowed",
      },
    ],
  });
  writeJson(path.join(root, "enablement_packets/index.json"), {
    packet_count: 5,
    packets: [{ packet_id: "packet_01", json: "packet_01.json", md: "packet_01.md" }],
  });
  writeJson(path.join(root, "demand/index.json"), {
    draft_only: true,
    sent: false,
    external_action_status: "risk_reviewed",
    first_paid_offer: "first_paid_offer.md",
    sponsor_briefs: ["sponsor_brief_01.md"],
  });
  writeJson(path.join(root, "promotion/latest.json"), {
    steps: { "5_first_sponsor_target": { name: "Accion" } },
    artifacts: {
      sponsor_one_pager: "sponsor_one_pager.md",
      human_review_packet: "human_review_packet.json",
    },
    safety_boundary: {
      outreach_action_status: "risk_reviewed",
    },
  });
  writeJson(path.join(root, "promotion/external_acted_receipt_gate.json"), {
    status: "blocked_pending_human_governor_approval_and_external_act",
  });
  writeJson(path.join(root, "promotion/provider_readiness_gate.json"), {
    status: "red",
  });

  const dashboard = loadLivelihoodLoomDashboard(root);

  assert.equal(dashboard.status, "cultivation_ready_provider_blocked");
  assert.equal(dashboard.providerStatus, "red");
  assert.equal(dashboard.providerGreen, false);
  assert.equal(dashboard.topCandidates[0]?.safety_status, "allowed");
  assert.equal(dashboard.promotion.sponsorTarget, "Accion");
  assert.equal(
    dashboard.promotion.actedReceiptStatus,
    "blocked_pending_human_governor_approval_and_external_act",
  );
});

test("public data loaders return full candidate, wedge, packet, sponsor, gate, and data-room detail", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "livelihood-loom-public-"));
  writeFullFixtures(root);

  const candidates = loadLivelihoodLoomCandidates(root);
  assert.equal(candidates.length, 2);
  assert.equal(candidates[0]?.company_id, "zeta_pay_in");
  assert.equal(candidates[0]?.safety_status, "allowed");
  assert.equal(candidates[0]?.safety_review?.company_id, "zeta_pay_in");
  assert.equal(candidates[1]?.safety_status, "needs_review");

  const byId = loadLivelihoodLoomCandidateById("zeta_pay_in", root);
  assert.ok(byId);
  assert.equal(byId?.name, "Zeta Pay");
  assert.equal(byId?.wedge_label, "Payment acceptance");
  assert.equal(loadLivelihoodLoomCandidateById("missing", root), undefined);

  const wedges = loadLivelihoodLoomWedges(root);
  assert.equal(wedges.length, 1);
  assert.equal(wedges[0]?.wedge_id, "payment_acceptance_cashflow");
  assert.equal(wedges[0]?.country_count, 3);
  assert.equal(wedges[0]?.top_candidates.length, 1);
  assert.equal(wedges[0]?.top_candidates[0]?.company_id, "zeta_pay_in");

  const wedgeById = loadLivelihoodLoomWedgeById("payment_acceptance_cashflow", root);
  assert.ok(wedgeById);
  assert.equal(wedgeById?.label, "Payment acceptance");
  assert.equal(loadLivelihoodLoomWedgeById("missing", root), undefined);

  const packets = loadLivelihoodLoomPackets(root);
  assert.equal(packets.length, 1);
  assert.equal(packets[0]?.packet_id, "packet_01");
  assert.equal(packets[0]?.candidate_partners.length, 1);

  const packetById = loadLivelihoodLoomPacketById("packet_01", root);
  assert.ok(packetById);
  assert.equal(packetById?.target_wedge, "Payment acceptance");
  assert.equal(loadLivelihoodLoomPacketById("missing", root), undefined);

  const sponsor = loadLivelihoodLoomSponsorTarget(root);
  assert.ok(sponsor);
  assert.equal(sponsor?.name, "Accion");
  assert.equal(sponsor?.safety_basis?.allowed, 1);
  assert.equal(sponsor?.selected_wedge?.wedge_id, "payment_acceptance_cashflow");

  const gates = loadLivelihoodLoomStatusGates(root);
  const gateNames = gates.map((g) => g.name);
  assert.ok(gateNames.includes("cultivation_ready"));
  assert.ok(gateNames.includes("Provider readiness"));
  assert.ok(gateNames.includes("External acted receipt"));

  const dataRoom = loadLivelihoodLoomDataRoom(root);
  assert.ok(Object.keys(dataRoom.files).length > 0);
  assert.equal(dataRoom.gates.length, gates.length);
  assert.equal(dataRoom.safety.total, 2);
  assert.equal(dataRoom.promotion.sponsorTarget, "Accion");
  assert.equal(dataRoom.demand.draft_only, true);
  assert.ok(dataRoom.receipts.some((r) => r.name === "Cycle receipt"));
});

function writeFullFixtures(root: string) {
  writeJson(path.join(root, "cycles/latest.json"), {
    receipt_id: "cycle_1",
    created_at: "2026-06-29T00:00:00Z",
    status: "cultivation_ready_provider_blocked",
    provider_green: false,
    provider_readiness_gap: { status: "red" },
    status_gates: {
      cultivation_ready: {
        status: "green",
        detail: "Top 50 candidates and wedges are ready.",
      },
    },
  });
  writeJson(path.join(root, "cultivation/top_50.json"), {
    candidate_count: 1000,
    candidates: [
      {
        rank: 1,
        source_rank: 4,
        company_id: "zeta_pay_in",
        name: "Zeta Pay",
        country: "India",
        domain: "finance_rails",
        subdomain: "merchant payments",
        prioritization_score: 0.98,
        wedge_id: "payment_acceptance_cashflow",
        wedge_label: "Payment acceptance",
        reasons: ["High merchant density", "Cash-to-digital tailwind"],
        score_components: { market_size: 0.9, safety: 1.0 },
        evidence_refs: ["source_a.json"],
      },
      {
        rank: 2,
        source_rank: 7,
        company_id: "beta_kiosk_ke",
        name: "Beta Kiosk",
        country: "Kenya",
        domain: "agent_networks",
        prioritization_score: 0.92,
        wedge_label: "Agent networks",
      },
    ],
  });
  writeJson(path.join(root, "cultivation/wedges.json"), {
    wedge_count: 1,
    wedges: [
      {
        rank: 1,
        wedge_id: "payment_acceptance_cashflow",
        label: "Payment acceptance",
        roi_score: 1.1,
        candidate_count_in_top_50: 12,
        country_count: 3,
        roi_thesis: "Cashflow rails help merchants.",
        top_candidates: [
          {
            company_id: "zeta_pay_in",
            country: "India",
            name: "Zeta Pay",
            rank: 1,
            score: 0.98,
            source_rank: 4,
          },
        ],
        evidence_refs: ["wedge_evidence.json"],
        safety_caveats: ["Watch merchant fee transparency"],
      },
    ],
  });
  writeJson(path.join(root, "safety/top_50_safety_review.json"), {
    summary: {
      allowed: 1,
      needs_review: 1,
      blocked: 0,
      total: 2,
      flag_counts: { high_fee_lending: 0 },
    },
    reviews: [
      {
        name: "Zeta Pay",
        company_id: "zeta_pay_in",
        safety_status: "allowed",
        flags: [],
        notes: ["No red-team flags"],
        evidence_refs: ["safety_zeta_pay.json"],
      },
      {
        name: "Beta Kiosk",
        company_id: "beta_kiosk_ke",
        safety_status: "needs_review",
        flags: ["agent_kyc_gap"],
        notes: ["Needs agent KYC review"],
        evidence_refs: [],
      },
    ],
  });
  writeJson(path.join(root, "enablement_packets/index.json"), {
    packet_count: 1,
    packets: [{ packet_id: "packet_01", json: "packet_01.json", md: "packet_01.md" }],
  });
  writeJson(path.join(root, "enablement_packets/packet_01.json"), {
    packet_id: "packet_01",
    cell_id: "cell_payment_acceptance_01",
    target_wedge: "Payment acceptance",
    beneficiary: "Informal merchants",
    friction: "Cash collection and reconciliation",
    sponsor_value: "Lower cost merchant acceptance",
    welfare_metric: "Merchant daily cash flow stability",
    candidate_partners: [
      {
        company_id: "zeta_pay_in",
        name: "Zeta Pay",
        country: "India",
        rank: 1,
        prioritization_score: 0.98,
        safety_status: "allowed",
        evidence_refs: ["safety_zeta_pay.json"],
        flags: [],
        wedge_id: "payment_acceptance_cashflow",
      },
    ],
    evidence_refs: ["packet_evidence.json"],
    risks: ["Provider readiness not proven"],
    next_safe_action: "Complete provider readiness review",
    generated_at: "2026-06-29T00:00:00Z",
  });
  writeJson(path.join(root, "demand/index.json"), {
    draft_only: true,
    sent: false,
    external_action_status: "risk_reviewed",
    first_paid_offer: "first_paid_offer.md",
    sponsor_briefs: ["sponsor_brief_01.md"],
  });
  writeJson(path.join(root, "promotion/latest.json"), {
    steps: { "5_first_sponsor_target": { name: "Accion" } },
    artifacts: {
      sponsor_one_pager: "sponsor_one_pager.md",
      human_review_packet: "human_review_packet.json",
    },
    safety_boundary: {
      outreach_action_status: "risk_reviewed",
    },
  });
  writeJson(path.join(root, "promotion/external_acted_receipt_gate.json"), {
    status: "blocked_pending_human_governor_approval_and_external_act",
    detail: "No external counterparty action recorded.",
  });
  writeJson(path.join(root, "promotion/provider_readiness_gate.json"), {
    status: "red",
    detail: "Provider proof incomplete.",
  });
  writeJson(path.join(root, "promotion/first_sponsor_target.json"), {
    schema_version: "1.0",
    name: "Accion",
    target_type: "nonprofit_financial_inclusion",
    website: "https://www.accion.org",
    fit_thesis: "Global financial inclusion nonprofit with fintech partnerships.",
    safety_basis: { allowed: 1, blocked: 0, needs_review: 1 },
    selected_wedge: {
      wedge_id: "payment_acceptance_cashflow",
      label: "Payment acceptance",
      roi_score: 1.1,
    },
    selection_status: "draft",
    generated_at: "2026-06-29T00:00:00Z",
  });
}

function writeJson(filePath: string, payload: unknown) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload)}\n`, "utf8");
}

