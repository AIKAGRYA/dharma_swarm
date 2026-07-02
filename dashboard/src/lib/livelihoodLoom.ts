import fs from "node:fs";
import path from "node:path";

type JsonRecord = Record<string, unknown>;

export interface LivelihoodLoomCandidate {
  rank: number;
  source_rank: number;
  name: string;
  country: string;
  domain: string;
  prioritization_score: number;
  wedge_label: string;
  safety_status?: string;
}

export interface LivelihoodLoomDashboard {
  status: string;
  receiptId: string;
  generatedAt: string;
  providerStatus: "red" | "green" | "unknown";
  providerGreen: boolean;
  topCount: number;
  candidateCount: number;
  topCandidates: LivelihoodLoomCandidate[];
  wedges: Array<{
    rank: number;
    wedge_id: string;
    label: string;
    roi_score: number;
    candidate_count_in_top_50: number;
    roi_thesis: string;
  }>;
  safety: {
    allowed: number;
    needs_review: number;
    blocked: number;
    total: number;
    flag_counts: Record<string, number>;
  };
  packets: {
    packet_count: number;
    packets: Array<{ packet_id: string; json: string; md: string }>;
  };
  demand: {
    draft_only: boolean;
    sent: boolean;
    external_action_status: string;
    first_paid_offer: string;
    sponsor_briefs: string[];
  };
  promotion: {
    present: boolean;
    sponsorTarget: string;
    outreachStatus: string;
    actedReceiptStatus: string;
    providerGateStatus: string;
    sponsorOnePager: string;
    reviewPacket: string;
  };
  files: Record<string, string>;
}

export function loadLivelihoodLoomDashboard(reportRoot?: string): LivelihoodLoomDashboard {
  const root = reportRoot ?? livelihoodReportRoot();
  const cycle = readJson(path.join(root, "cycles/latest.json"));
  const top50 = readJson(path.join(root, "cultivation/top_50.json"));
  const wedges = readJson(path.join(root, "cultivation/wedges.json"));
  const safety = readJson(path.join(root, "safety/top_50_safety_review.json"));
  const packets = readJson(path.join(root, "enablement_packets/index.json"));
  const demand = readJson(path.join(root, "demand/index.json"));
  const promotion = readOptionalJson(path.join(root, "promotion/latest.json"));
  const actedGate = readOptionalJson(
    path.join(root, "promotion/external_acted_receipt_gate.json"),
  );
  const providerGate = readOptionalJson(
    path.join(root, "promotion/provider_readiness_gate.json"),
  );

  const safetyByName = new Map<string, string>();
  asArray(safety.reviews).forEach((item) => {
    const record = item as JsonRecord;
    safetyByName.set(String(record.name ?? ""), String(record.safety_status ?? ""));
  });

  const candidates = asArray(top50.candidates).slice(0, 8).map((item) => {
    const record = item as JsonRecord;
    const name = String(record.name ?? "");
    return {
      rank: Number(record.rank ?? 0),
      source_rank: Number(record.source_rank ?? 0),
      name,
      country: String(record.country ?? "unknown"),
      domain: String(record.domain ?? "unknown"),
      prioritization_score: Number(record.prioritization_score ?? 0),
      wedge_label: String(record.wedge_label ?? ""),
      safety_status: safetyByName.get(name) ?? "unknown",
    };
  });

  const promotionSteps = (promotion.steps as JsonRecord | undefined) ?? {};
  const sponsorTarget = (promotionSteps["5_first_sponsor_target"] as JsonRecord | undefined) ?? {};
  const promotionArtifacts = (promotion.artifacts as JsonRecord | undefined) ?? {};
  const promotionBoundary = (promotion.safety_boundary as JsonRecord | undefined) ?? {};

  return {
    status: String(cycle.status ?? "missing"),
    receiptId: String(cycle.receipt_id ?? ""),
    generatedAt: String(cycle.created_at ?? cycle.generated_at ?? ""),
    providerStatus: providerStatus(cycle, providerGate),
    providerGreen: Boolean(cycle.provider_green ?? false),
    topCount: asArray(top50.candidates).length,
    candidateCount: Number(top50.candidate_count ?? 0),
    topCandidates: candidates,
    wedges: asArray(wedges.wedges).map((item) => {
      const record = item as JsonRecord;
      return {
        rank: Number(record.rank ?? 0),
        wedge_id: String(record.wedge_id ?? ""),
        label: String(record.label ?? ""),
        roi_score: Number(record.roi_score ?? 0),
        candidate_count_in_top_50: Number(record.candidate_count_in_top_50 ?? 0),
        roi_thesis: String(record.roi_thesis ?? ""),
      };
    }),
    safety: {
      allowed: Number((safety.summary as JsonRecord | undefined)?.allowed ?? 0),
      needs_review: Number((safety.summary as JsonRecord | undefined)?.needs_review ?? 0),
      blocked: Number((safety.summary as JsonRecord | undefined)?.blocked ?? 0),
      total: Number((safety.summary as JsonRecord | undefined)?.total ?? 0),
      flag_counts: ((safety.summary as JsonRecord | undefined)?.flag_counts ??
        {}) as Record<string, number>,
    },
    packets: {
      packet_count: Number(packets.packet_count ?? 0),
      packets: asArray(packets.packets).map((item) => {
        const record = item as JsonRecord;
        return {
          packet_id: String(record.packet_id ?? ""),
          json: String(record.json ?? ""),
          md: String(record.md ?? ""),
        };
      }),
    },
    demand: {
      draft_only: Boolean(demand.draft_only ?? true),
      sent: Boolean(demand.sent ?? false),
      external_action_status: String(demand.external_action_status ?? "missing"),
      first_paid_offer: String(demand.first_paid_offer ?? ""),
      sponsor_briefs: asArray(demand.sponsor_briefs).map(String),
    },
    promotion: {
      present: Object.keys(promotion).length > 0,
      sponsorTarget: String(sponsorTarget.name ?? "pending"),
      outreachStatus: String(promotionBoundary.outreach_action_status ?? "not_drafted"),
      actedReceiptStatus: String(actedGate.status ?? "missing"),
      providerGateStatus: String(providerGate.status ?? "red"),
      sponsorOnePager: String(promotionArtifacts.sponsor_one_pager ?? ""),
      reviewPacket: String(promotionArtifacts.human_review_packet ?? ""),
    },
    files: {
      cycle: path.join(root, "cycles/latest.json"),
      top50: path.join(root, "cultivation/top_50.json"),
      wedges: path.join(root, "cultivation/wedges.json"),
      safety: path.join(root, "safety/top_50_safety_review.json"),
      packets: path.join(root, "enablement_packets/index.json"),
      demand: path.join(root, "demand/index.json"),
      promotion: path.join(root, "promotion/latest.json"),
    },
  };
}

export interface LivelihoodLoomCandidateDetail {
  rank: number;
  source_rank: number;
  company_id: string;
  name: string;
  country: string;
  domain: string;
  subdomain?: string;
  source_tag?: string;
  source_type?: string;
  source_url?: string;
  website?: string;
  description?: string;
  informal_economy_role?: string;
  candidate_score?: number;
  confidence?: string;
  cultivation_priority?: string;
  prioritization_score: number;
  wedge_id?: string;
  wedge_label?: string;
  reasons?: string[];
  score_components?: Record<string, number>;
  evidence_refs?: string[];
  safety_status?: string;
  safety_review?: LivelihoodLoomSafetyReviewEntry;
}

export interface LivelihoodLoomSafetyReviewEntry {
  name: string;
  company_id: string;
  safety_status: string;
  flags: string[];
  notes: string[];
  evidence_refs: string[];
  candidate?: LivelihoodLoomCandidateDetail;
}

export interface LivelihoodLoomWedgeDetail {
  rank: number;
  wedge_id: string;
  label: string;
  roi_score: number;
  roi_thesis: string;
  candidate_count_in_top_50: number;
  country_count: number;
  top_candidates: Array<{
    company_id: string;
    country: string;
    name: string;
    rank: number;
    score: number;
    source_rank: number;
  }>;
  evidence_refs?: string[];
  safety_caveats?: string[];
}

export interface LivelihoodLoomPacketDetail {
  packet_id: string;
  cell_id?: string;
  target_wedge?: string;
  beneficiary?: string;
  friction?: string;
  sponsor_value?: string;
  welfare_metric?: string;
  candidate_partners: Array<{
    company_id: string;
    name: string;
    country: string;
    rank: number;
    prioritization_score: number;
    safety_status?: string;
    evidence_refs?: string[];
    flags?: string[];
    wedge_id?: string;
  }>;
  evidence_refs?: string[];
  risks?: string[];
  next_safe_action?: string;
  generated_at?: string;
}

export interface LivelihoodLoomSponsorTarget {
  schema_version?: string;
  name: string;
  target_type?: string;
  website?: string;
  partner_page?: string;
  source_refs?: string[];
  fit_thesis?: string;
  safety_basis?: { allowed: number; blocked: number; needs_review: number };
  selected_wedge?: { wedge_id: string; label: string; roi_score: number };
  selection_status?: string;
  generated_at?: string;
}

export interface LivelihoodLoomStatusGate {
  name: string;
  status: string;
  detail: string;
  complete?: boolean;
  provider_green?: boolean;
  next_safe_step?: string;
  required_for_completion?: string[];
}

export interface LivelihoodLoomDataRoom {
  files: Record<string, string>;
  receipts: Array<{ name: string; path: string; status: string }>;
  gates: LivelihoodLoomStatusGate[];
  safety: LivelihoodLoomDashboard["safety"];
  promotion: LivelihoodLoomDashboard["promotion"];
  demand: LivelihoodLoomDashboard["demand"];
}

export function loadLivelihoodLoomCandidates(reportRoot?: string): LivelihoodLoomCandidateDetail[] {
  const root = reportRoot ?? livelihoodReportRoot();
  const top50 = readJson(path.join(root, "cultivation/top_50.json"));
  const safety = readJson(path.join(root, "safety/top_50_safety_review.json"));

  const reviewsByCompanyId = new Map<string, JsonRecord>();
  const reviewsByName = new Map<string, JsonRecord>();
  asArray(safety.reviews).forEach((item) => {
    const record = item as JsonRecord;
    const companyId = String(record.company_id ?? "");
    if (companyId.length > 0) reviewsByCompanyId.set(companyId, record);
    const name = String(record.name ?? "");
    if (name.length > 0) reviewsByName.set(name, record);
  });

  return asArray(top50.candidates).map((item) => {
    const record = item as JsonRecord;
    const companyId = String(record.company_id ?? "");
    const name = String(record.name ?? "");
    const review = (companyId.length > 0 ? reviewsByCompanyId.get(companyId) : undefined) ??
      reviewsByName.get(name);
    const safetyStatus = review ? String(review.safety_status ?? "") : undefined;

    return {
      rank: Number(record.rank ?? 0),
      source_rank: Number(record.source_rank ?? 0),
      company_id: companyId,
      name,
      country: String(record.country ?? "unknown"),
      domain: String(record.domain ?? "unknown"),
      subdomain: optionalString(record.subdomain),
      source_tag: optionalString(record.source_tag),
      source_type: optionalString(record.source_type),
      source_url: optionalString(record.source_url),
      website: optionalString(record.website),
      description: optionalString(record.description),
      informal_economy_role: optionalString(record.informal_economy_role),
      candidate_score: optionalNumber(record.candidate_score),
      confidence: optionalString(record.confidence),
      cultivation_priority: optionalString(record.cultivation_priority),
      prioritization_score: Number(record.prioritization_score ?? 0),
      wedge_id: optionalString(record.wedge_id),
      wedge_label: optionalString(record.wedge_label),
      reasons: asStringArray(record.reasons),
      score_components: asNumberRecord(record.score_components),
      evidence_refs: asStringArray(record.evidence_refs),
      safety_status: safetyStatus && safetyStatus.length > 0 ? safetyStatus : "unknown",
      safety_review: review ? coerceSafetyReview(review) : undefined,
    };
  });
}

export function loadLivelihoodLoomCandidateById(
  companyId: string,
  reportRoot?: string,
): LivelihoodLoomCandidateDetail | undefined {
  return loadLivelihoodLoomCandidates(reportRoot).find((candidate) => candidate.company_id === companyId);
}

export function loadLivelihoodLoomWedges(reportRoot?: string): LivelihoodLoomWedgeDetail[] {
  const root = reportRoot ?? livelihoodReportRoot();
  const wedges = readJson(path.join(root, "cultivation/wedges.json"));

  return asArray(wedges.wedges).map((item) => {
    const record = item as JsonRecord;
    return {
      rank: Number(record.rank ?? 0),
      wedge_id: String(record.wedge_id ?? ""),
      label: String(record.label ?? ""),
      roi_score: Number(record.roi_score ?? 0),
      roi_thesis: String(record.roi_thesis ?? ""),
      candidate_count_in_top_50: Number(record.candidate_count_in_top_50 ?? 0),
      country_count: Number(record.country_count ?? 0),
      top_candidates: asArray(record.top_candidates).map((candidate) => {
        const cand = candidate as JsonRecord;
        return {
          company_id: String(cand.company_id ?? ""),
          country: String(cand.country ?? ""),
          name: String(cand.name ?? ""),
          rank: Number(cand.rank ?? 0),
          score: Number(cand.score ?? 0),
          source_rank: Number(cand.source_rank ?? 0),
        };
      }),
      evidence_refs: asStringArray(record.evidence_refs),
      safety_caveats: asStringArray(record.safety_caveats),
    };
  });
}

export function loadLivelihoodLoomWedgeById(
  wedgeId: string,
  reportRoot?: string,
): LivelihoodLoomWedgeDetail | undefined {
  return loadLivelihoodLoomWedges(reportRoot).find((wedge) => wedge.wedge_id === wedgeId);
}

export function loadLivelihoodLoomPackets(reportRoot?: string): LivelihoodLoomPacketDetail[] {
  const root = reportRoot ?? livelihoodReportRoot();
  const index = readJson(path.join(root, "enablement_packets/index.json"));

  return asArray(index.packets)
    .map((item) => {
      const record = item as JsonRecord;
      const packetId = String(record.packet_id ?? "");
      return loadLivelihoodLoomPacketById(packetId, root);
    })
    .filter((packet): packet is LivelihoodLoomPacketDetail => packet !== undefined);
}

export function loadLivelihoodLoomPacketById(
  packetId: string,
  reportRoot?: string,
): LivelihoodLoomPacketDetail | undefined {
  const root = reportRoot ?? livelihoodReportRoot();
  const filePath = path.join(root, "enablement_packets", `${packetId}.json`);
  if (!fs.existsSync(filePath)) return undefined;

  const record = readJson(filePath);
  if (String(record.packet_id ?? "") !== packetId) return undefined;

  return {
    packet_id: packetId,
    cell_id: optionalString(record.cell_id),
    target_wedge: optionalString(record.target_wedge),
    beneficiary: optionalString(record.beneficiary),
    friction: optionalString(record.friction),
    sponsor_value: optionalString(record.sponsor_value),
    welfare_metric: optionalString(record.welfare_metric),
    candidate_partners: asArray(record.candidate_partners).map((candidate) => {
      const cand = candidate as JsonRecord;
      return {
        company_id: String(cand.company_id ?? ""),
        name: String(cand.name ?? ""),
        country: String(cand.country ?? ""),
        rank: Number(cand.rank ?? 0),
        prioritization_score: Number(cand.prioritization_score ?? 0),
        safety_status: optionalString(cand.safety_status),
        evidence_refs: asStringArray(cand.evidence_refs),
        flags: asStringArray(cand.flags),
        wedge_id: optionalString(cand.wedge_id),
      };
    }),
    evidence_refs: asStringArray(record.evidence_refs),
    risks: asStringArray(record.risks),
    next_safe_action: optionalString(record.next_safe_action),
    generated_at: optionalString(record.generated_at),
  };
}

export function loadLivelihoodLoomSponsorTarget(reportRoot?: string): LivelihoodLoomSponsorTarget | null {
  const root = reportRoot ?? livelihoodReportRoot();
  const filePath = path.join(root, "promotion/first_sponsor_target.json");
  if (!fs.existsSync(filePath)) return null;

  const record = readJson(filePath);
  const safetyBasis = record.safety_basis as JsonRecord | undefined;
  const selectedWedge = record.selected_wedge as JsonRecord | undefined;

  return {
    schema_version: optionalString(record.schema_version),
    name: String(record.name ?? ""),
    target_type: optionalString(record.target_type),
    website: optionalString(record.website),
    partner_page: optionalString(record.partner_page),
    source_refs: asStringArray(record.source_refs),
    fit_thesis: optionalString(record.fit_thesis),
    safety_basis: safetyBasis
      ? {
          allowed: Number(safetyBasis.allowed ?? 0),
          blocked: Number(safetyBasis.blocked ?? 0),
          needs_review: Number(safetyBasis.needs_review ?? 0),
        }
      : undefined,
    selected_wedge: selectedWedge
      ? {
          wedge_id: String(selectedWedge.wedge_id ?? ""),
          label: String(selectedWedge.label ?? ""),
          roi_score: Number(selectedWedge.roi_score ?? 0),
        }
      : undefined,
    selection_status: optionalString(record.selection_status),
    generated_at: optionalString(record.generated_at),
  };
}

export function loadLivelihoodLoomStatusGates(reportRoot?: string): LivelihoodLoomStatusGate[] {
  const root = reportRoot ?? livelihoodReportRoot();
  const cycle = readJson(path.join(root, "cycles/latest.json"));
  const providerGate = readOptionalJson(path.join(root, "promotion/provider_readiness_gate.json"));
  const actedGate = readOptionalJson(
    path.join(root, "promotion/external_acted_receipt_gate.json"),
  );

  const statusGates = cycle.status_gates as JsonRecord | undefined;
  const gates: LivelihoodLoomStatusGate[] = Object.entries(statusGates ?? {}).map(
    ([name, value]) => {
      const record = (value ?? {}) as JsonRecord;
      return {
        name,
        status: String(record.status ?? ""),
        detail: String(record.detail ?? ""),
        complete: optionalBoolean(record.complete),
        provider_green: optionalBoolean(record.provider_green),
        next_safe_step: optionalString(record.next_safe_step),
        required_for_completion: asStringArray(record.required_for_completion),
      };
    },
  );

  if (Object.keys(providerGate).length > 0) {
    gates.push({
      name: "Provider readiness",
      status: String(providerGate.status ?? ""),
      detail: String(providerGate.detail ?? ""),
      complete: optionalBoolean(providerGate.complete),
      provider_green: optionalBoolean(providerGate.provider_green),
      next_safe_step: optionalString(providerGate.next_safe_step),
      required_for_completion: asStringArray(providerGate.required_for_completion),
    });
  }

  if (Object.keys(actedGate).length > 0) {
    gates.push({
      name: "External acted receipt",
      status: String(actedGate.status ?? ""),
      detail: String(actedGate.detail ?? ""),
      complete: optionalBoolean(actedGate.complete),
      provider_green: optionalBoolean(actedGate.provider_green),
      next_safe_step: optionalString(actedGate.next_safe_step),
      required_for_completion: asStringArray(actedGate.required_for_completion),
    });
  }

  return gates;
}

export function loadLivelihoodLoomDataRoom(reportRoot?: string): LivelihoodLoomDataRoom {
  const root = reportRoot ?? livelihoodReportRoot();
  const dashboard = loadLivelihoodLoomDashboard(root);
  const gates = loadLivelihoodLoomStatusGates(root);

  const receipts: Array<{ name: string; path: string; status: string }> = [
    { name: "Cycle receipt", path: dashboard.files.cycle, status: dashboard.status },
    { name: "Top 50 candidates", path: dashboard.files.top50, status: "available" },
    { name: "Wedge map", path: dashboard.files.wedges, status: "available" },
    { name: "Safety review", path: dashboard.files.safety, status: "available" },
    { name: "Enablement packets", path: dashboard.files.packets, status: "available" },
    { name: "Demand index", path: dashboard.files.demand, status: dashboard.demand.external_action_status },
    {
      name: "Promotion artifacts",
      path: dashboard.files.promotion,
      status: dashboard.promotion.present ? "available" : "pending",
    },
  ];

  return {
    files: dashboard.files,
    receipts,
    gates,
    safety: dashboard.safety,
    promotion: dashboard.promotion,
    demand: dashboard.demand,
  };
}

export function livelihoodReportRoot(): string {
  const cwd = process.cwd();
  const local = path.join(cwd, "reports/livelihood_loom");
  if (fs.existsSync(local)) return local;
  return path.join(cwd, "..", "reports/livelihood_loom");
}

function readJson(filePath: string): JsonRecord {
  return JSON.parse(fs.readFileSync(filePath, "utf8")) as JsonRecord;
}

function readOptionalJson(filePath: string): JsonRecord {
  if (!fs.existsSync(filePath)) return {};
  return readJson(filePath);
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function providerStatus(cycle: JsonRecord, providerGate: JsonRecord): "red" | "green" | "unknown" {
  if (cycle.provider_green === true) return "green";
  if (providerGate.status === "red") return "red";
  const gap = cycle.provider_readiness_gap as JsonRecord | undefined;
  if (gap?.status === "red") return "red";
  return "unknown";
}

function optionalString(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  const str = String(value);
  return str.length > 0 ? str : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  if (value === undefined || value === null) return undefined;
  const num = Number(value);
  return Number.isNaN(num) ? undefined : num;
}

function optionalBoolean(value: unknown): boolean | undefined {
  if (value === undefined || value === null) return undefined;
  return Boolean(value);
}

function asStringArray(value: unknown): string[] {
  return asArray(value).map((item) => String(item));
}

function asNumberRecord(value: unknown): Record<string, number> {
  if (typeof value !== "object" || value === null) return {};
  const record = value as Record<string, unknown>;
  const result: Record<string, number> = {};
  for (const key of Object.keys(record)) {
    const num = Number(record[key]);
    if (!Number.isNaN(num)) result[key] = num;
  }
  return result;
}

function coerceSafetyReview(record: JsonRecord): LivelihoodLoomSafetyReviewEntry {
  return {
    name: String(record.name ?? ""),
    company_id: String(record.company_id ?? ""),
    safety_status: String(record.safety_status ?? ""),
    flags: asStringArray(record.flags),
    notes: asStringArray(record.notes),
    evidence_refs: asStringArray(record.evidence_refs),
  };
}
