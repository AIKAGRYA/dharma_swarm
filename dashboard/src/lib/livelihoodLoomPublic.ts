import {
  loadLivelihoodLoomDashboard,
  type LivelihoodLoomDashboard,
} from "./livelihoodLoom.ts";

export interface LivelihoodLoomPublicSite {
  brand: string;
  headline: string;
  subheadline: string;
  heroStats: Array<{ label: string; value: string; detail: string }>;
  investorSignals: Array<{ label: string; value: string; detail: string }>;
  wedges: LivelihoodLoomDashboard["wedges"];
  topCandidates: LivelihoodLoomDashboard["topCandidates"];
  sponsorTarget: string;
  safetySummary: string;
  statusNote: string;
  proofBoundary: string;
  sourceLinks: string[];
}

export function loadLivelihoodLoomPublicSite(reportRoot?: string): LivelihoodLoomPublicSite {
  const data = loadLivelihoodLoomDashboard(reportRoot);
  const topWedge = data.wedges[0];

  return {
    brand: "Livelihood Loom",
    headline: "Capital-grade maps for the informal economy.",
    subheadline:
      "A sponsor and investor intelligence layer that turns public livelihood infrastructure data into safety-reviewed markets, partner packets, and approval-ready action queues.",
    heroStats: [
      {
        label: "Source Rows",
        value: formatNumber(data.candidateCount),
        detail: "public-source enabler records",
      },
      {
        label: "Prioritized",
        value: formatNumber(data.topCount),
        detail: "highest-signal candidates",
      },
      {
        label: "ROI Wedges",
        value: formatNumber(data.wedges.length),
        detail: "ranked sponsor lanes",
      },
      {
        label: "Packets",
        value: formatNumber(data.packets.packet_count),
        detail: "draft enablement packets",
      },
    ],
    investorSignals: [
      {
        label: "First Market",
        value: topWedge?.label ?? "Payment acceptance and cashflow rails",
        detail: topWedge
          ? `${topWedge.candidate_count_in_top_50} candidates in the Top 50`
          : "candidate concentration pending",
      },
      {
        label: "Safety Posture",
        value: `${data.safety.allowed} allowed / ${data.safety.blocked} blocked`,
        detail: `${data.safety.needs_review} require human review before action`,
      },
      {
        label: "Sponsor Target",
        value: data.promotion.sponsorTarget || "Pending",
        detail: "draft target, not contacted",
      },
    ],
    wedges: data.wedges,
    topCandidates: data.topCandidates,
    sponsorTarget: data.promotion.sponsorTarget,
    safetySummary: `${data.safety.allowed} allowed, ${data.safety.needs_review} needs review, ${data.safety.blocked} blocked`,
    statusNote:
      data.providerGreen
        ? "Provider proof is green."
        : "Pilot packet is built; provider proof remains pending before any provider-green claim.",
    proofBoundary:
      data.promotion.actedReceiptStatus === "blocked_pending_human_governor_approval_and_external_act"
        ? "External acted receipt is not claimed. Outreach remains draft-only until human approval and a real counterparty action exist."
        : data.promotion.actedReceiptStatus,
    sourceLinks: [
      "/api/livelihood-loom",
      data.files.promotion,
      data.files.top50,
      data.files.safety,
    ],
  };
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}
