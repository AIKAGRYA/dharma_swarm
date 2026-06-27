import type {
  CoherenceAction,
  CoherenceCard,
  CoherenceEvidence,
  OperatorCoherenceReport,
} from "@/lib/operatorCoherence";

export type CockpitMode =
  | "overview"
  | "triage"
  | "topology"
  | "recursive"
  | "git"
  | "runtime"
  | "tracks"
  | "preservation"
  | "evidence"
  | "errors"
  | "design";

export interface InspectItem {
  id?: string;
  type: "panel" | "card" | "action" | "track" | "source";
  title: string;
  subtitle?: string;
  status?: string;
  risk?: string;
  nextAction?: string;
  evidence?: CoherenceEvidence[];
  raw?: unknown;
}

export interface CockpitPanelDatum {
  id: string;
  title: string;
  eyebrow: string;
  value: string;
  detail: string;
  tone: "ok" | "warn" | "danger" | "info" | "muted";
  inspect: InspectItem;
}

export type TruthTone = "ok" | "warn" | "danger" | "info" | "muted";

export interface ReportSourceSummary {
  mode: "live" | "cached" | "partial" | "stale" | "unavailable";
  label: string;
  detail: string;
  tone: TruthTone;
  ageHours: number | null;
}

export interface ActionPacket {
  id: string;
  title: string;
  rank: number;
  urgency: "low" | "medium" | "high" | "critical";
  why: string;
  evidence: CoherenceEvidence[];
  targets: string[];
  expectedImpact: string;
  risk: string;
  operatorDecision: boolean;
  allowedNow: false;
  raw: CoherenceAction;
}

export interface TruthBadgeDatum {
  code: string;
  label: string;
  detail: string;
  tone: TruthTone;
}

export const MODES: { id: CockpitMode; label: string; hint: string }[] = [
  { id: "overview", label: "Overview", hint: "morning check" },
  { id: "triage", label: "Triage", hint: "needs action" },
  { id: "topology", label: "Topology", hint: "repo graph" },
  { id: "recursive", label: "Recursive", hint: "mandala" },
  { id: "git", label: "Git", hint: "branches/worktrees" },
  { id: "runtime", label: "Runtime", hint: "live ops" },
  { id: "tracks", label: "Tracks", hint: "portfolio" },
  { id: "preservation", label: "Preservation", hint: "safety" },
  { id: "evidence", label: "Evidence", hint: "raw truth" },
  { id: "errors", label: "Errors", hint: "uncertainty" },
  { id: "design", label: "Design Sources", hint: "Desktop canon" },
];

export const TRUTH_TAXONOMY: TruthBadgeDatum[] = [
  { code: "CANONICAL_ORIGIN_MAIN", label: "Canonical", detail: "Confirmed origin/main baseline, not local candidate state.", tone: "ok" },
  { code: "CLEAN_RECONCILIATION_WORKTREE", label: "Clean worktree", detail: "Reconciliation checkout with no dirty local projection.", tone: "ok" },
  { code: "DIRTY_LOCAL_CANDIDATE", label: "Dirty candidate", detail: "Local checkout or worktree state that must not be treated as canonical.", tone: "danger" },
  { code: "OPEN_PR_REMOTE", label: "Open PR/remote", detail: "Remote-backed review surface; confirm CI before promotion.", tone: "info" },
  { code: "LOCAL_ONLY_BRANCH", label: "Local only", detail: "Branch or commits exist locally and need preservation/review.", tone: "danger" },
  { code: "STASHED_PRESERVED", label: "Stashed", detail: "Hidden local work exists in stash; inspect before cleanup.", tone: "warn" },
  { code: "OFF_REPO_ARTIFACT", label: "Off-repo artifact", detail: "Evidence or artifact exists outside canonical repo state.", tone: "info" },
  { code: "LIVE_RUNTIME_PROOF", label: "Live proof", detail: "Runtime probe currently reports liveness.", tone: "ok" },
  { code: "STALE_RECEIPT", label: "Stale receipt", detail: "Receipt/proof exists but is stale or insufficiently fresh.", tone: "warn" },
  { code: "UNAVAILABLE_UNCERTAIN", label: "Uncertain", detail: "Required source or proof is unavailable.", tone: "muted" },
  { code: "INFERRED", label: "Inferred", detail: "UI classification inferred from facets; verify source before acting.", tone: "info" },
];

export const LANE_ADMISSION_FIELDS = [
  "lane_id",
  "agent_or_provider",
  "branch",
  "worktree",
  "base_ref",
  "intended_surfaces",
  "actual_touched_surfaces",
  "dirty_untracked_count",
  "verification_commands",
  "receipt_paths",
  "status",
  "candidate_track",
  "depends_on",
  "conflicts_with",
  "promotion_recommendation",
  "canonicality",
  "preservation_status",
] as const;

export const DESIGN_SOURCES = [
  {
    id: "canon",
    label: "Mandala Mission Control canon",
    path: "Desktop/DharmaSwarm FrontEnd/MANDALA_MISSION_CONTROL_CANON.md",
    role: "Linear/Grafana first, Recursive later; matte indigo-sumi instrument; no decorative glow.",
  },
  {
    id: "living-ontology",
    label: "Living Ontology v1",
    path: "Desktop/DharmaSwarm FrontEnd/LIVING_ONTOLOGY_v1_DESIGN_2026-06-15.md",
    role: "Same object model can become mandala/motherboard/Grafana board later.",
  },
  {
    id: "rug-to-instrument",
    label: "Art Direction v2 — Rug → Instrument",
    path: "Desktop/DharmaSwarm FrontEnd/ART_DIRECTION_v2_2026-06-15_RUG_TO_INSTRUMENT.md",
    role: "Build a usable instrument from real data; avoid generated painting as hero surface.",
  },
  {
    id: "live-ops-v2",
    label: "Live Ops Cockpit v2 Goal Spec",
    path: "Desktop/LIVE_OPS_COCKPIT_V2_GOAL_SPEC.md",
    role: "Observe → classify → rank → propose → require operator authority → record receipt.",
  },
  {
    id: "grafana-ref",
    label: "Grafana board inspiration",
    path: "Desktop/DharmaSwarm FrontEnd/01_John's Inspiration/COCKPIT/new cockpit fusion ideas/grafana new.jpeg",
    role: "Dense panel wall, stat blocks, status breakdowns, charts, and inspectable metrics.",
  },
  {
    id: "atlas-board",
    label: "Codex Proto 1 — Atlas Board",
    path: "Desktop/DharmaSwarm FrontEnd/02_Codex Prototypes/CODEX_PROTOTYPES_2026-06-14/screenshots/proto_1_atlas_board.png",
    role: "Immediate shippable shell: left object list, central metrics, right inspector.",
  },
  {
    id: "command-synthesis",
    label: "Claude Proto v2b — Command Synthesis",
    path: "Desktop/DharmaSwarm FrontEnd/03_Claude Prototypes/Claude opus 4.8 Protoypes/proto_v2b_command_synthesis.png",
    role: "Needs Action rail, Ten Organs grid, telemetry side rail, dense command-board hierarchy.",
  },
  {
    id: "anti-pattern",
    label: "Proto v14 postmortem",
    path: "Desktop/DharmaSwarm FrontEnd/03_Claude Prototypes/POSTMORTEM_proto_v14_waste.md",
    role: "Do not ship a pretty image. Verify real use, real data, real evidence.",
  },
  {
    id: "manifest",
    label: "Full Desktop source inventory",
    path: "docs/design/COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.md",
    role: "147 image references, 29 prototype/code files, 30 design docs, 5 JSON artifacts, 1 Blender asset.",
  },
];

const RISK_LABELS: Record<string, string> = {
  local_unpreserved_work: "Local work at risk",
  dirty_worktree: "Dirty worktree",
  local_only_work: "Local-only file changes",
  local_only_branch: "Local-only branch",
  unpushed_commits: "Unpushed commits",
  orphaned_upstream_gone: "Branch lost upstream",
  hidden_local_work: "Hidden stash work",
  stale_liveness_claim: "Stale live claim",
  live_ops_blocked: "Live ops blocked",
  desired_live_but_stopped: "Expected live, stopped",
  stale_claim: "Stale governance claim",
  known_breakage: "Known breakage",
  stale_surface_proof: "Stale surface proof",
  ci_failed: "CI failed",
  stale_pr: "Stale PR",
  onboarding_entrypoint_drift: "Onboarding drift",
  stale_runtime_db: "Stale runtime DB",
};

const KIND_LABELS: Record<string, string> = {
  branch: "Branch",
  worktree: "Worktree",
  dirty_files: "Dirty files",
  stash: "Stash",
  live_ops_surface: "Live ops surface",
  launchd_job: "launchd job",
  tmux_session: "tmux session",
  operator_surface: "Operator surface",
  track: "Track",
  broken_register: "Broken register",
  preservation_risk: "Preservation risk",
  runtime_db: "Runtime DB",
  runtime_receipts: "Runtime receipts",
  onboarding: "Onboarding",
  proposed_track: "Proposed track",
  pull_request: "Pull request",
};

export function humanRisk(risk: string): string {
  return RISK_LABELS[risk] ?? risk.replaceAll("_", " ");
}

export function humanKind(kind: string): string {
  return KIND_LABELS[kind] ?? kind.replaceAll("_", " ");
}

export function asText(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export function formatCount(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value ?? 0);
  if (!Number.isFinite(n)) return "0";
  return new Intl.NumberFormat("en-US").format(n);
}

export function readinessTone(score: number): CockpitPanelDatum["tone"] {
  if (score >= 70) return "ok";
  if (score >= 40) return "warn";
  return "danger";
}

export function reportAgeHours(report: OperatorCoherenceReport, now = new Date()): number | null {
  const generated = Date.parse(report.generated_at);
  if (!Number.isFinite(generated)) return null;
  return Math.max(0, (now.getTime() - generated) / 3_600_000);
}

export function buildReportSourceSummary(report: OperatorCoherenceReport, now = new Date()): ReportSourceSummary {
  const explicit = String(report.status ?? "").toLowerCase();
  const ageHours = reportAgeHours(report, now);
  const staleByAge = ageHours != null && ageHours > 24;
  const hasErrors = (report.source_errors ?? []).length > 0;
  const missingCore = !report.cards?.length || !Object.keys(report.readiness?.categories ?? {}).length;
  let mode: ReportSourceSummary["mode"] = "live";
  if (explicit.includes("unavailable") || missingCore) mode = "unavailable";
  else if (explicit.includes("partial") || hasErrors) mode = "partial";
  else if (explicit.includes("stale") || staleByAge) mode = "stale";
  else if (explicit.includes("cached")) mode = "cached";

  const tone: TruthTone =
    mode === "live" ? "ok" : mode === "cached" || mode === "stale" ? "warn" : mode === "partial" ? "danger" : "muted";
  const label =
    mode === "live"
      ? "live report"
      : mode === "cached"
        ? "cached report"
        : mode === "partial"
          ? "partial report"
          : mode === "stale"
            ? "stale report"
            : "report unavailable";
  const ageText = ageHours == null ? "age unknown" : `${Math.round(ageHours)}h old`;
  const detail = `${label}; ${ageText}; ${report.source_errors?.length ?? 0} source error(s); generated ${report.generated_at}`;
  return { mode, label, detail, tone, ageHours };
}

export function cardTone(card: CoherenceCard): CockpitPanelDatum["tone"] {
  if (card.lane === "Needs Repair" || card.risk.includes("dirty") || card.risk.includes("blocked")) return "danger";
  if (card.lane === "Needs Decision" || card.facets.operator_decision || card.facets.stale) return "warn";
  if (card.lane === "Verified" || card.facets.live || card.facets.preserved) return "ok";
  return "info";
}

export function truthByCode(code: string): TruthBadgeDatum {
  return TRUTH_TAXONOMY.find((truth) => truth.code === code) ?? TRUTH_TAXONOMY[TRUTH_TAXONOMY.length - 1];
}

export function classifyCardTruth(card: CoherenceCard): TruthBadgeDatum {
  if (card.kind === "runtime_receipts" || card.risk.includes("stale") || card.facets.stale) return truthByCode("STALE_RECEIPT");
  if (card.facets.live) return truthByCode("LIVE_RUNTIME_PROOF");
  if (card.kind === "stash") return truthByCode("STASHED_PRESERVED");
  if (card.facets.local_only) return truthByCode(card.kind === "branch" ? "LOCAL_ONLY_BRANCH" : "DIRTY_LOCAL_CANDIDATE");
  if (card.kind === "worktree" || card.kind === "dirty_files" || card.risk.includes("dirty")) return truthByCode("DIRTY_LOCAL_CANDIDATE");
  if (card.pr || card.facets.origin_backed) return truthByCode("OPEN_PR_REMOTE");
  if (card.facets.preserved) return truthByCode("OFF_REPO_ARTIFACT");
  if (card.facets.tracked || card.facets.intentional) return truthByCode("INFERRED");
  return truthByCode("UNAVAILABLE_UNCERTAIN");
}

export function cardFacetBadges(card: CoherenceCard): string[] {
  const badges = [
    card.facets.tracked ? "tracked" : "untracked",
    card.facets.live ? "live" : card.facets.stale ? "stale" : "not live",
    card.facets.preserved ? "preserved" : "not preserved",
    card.facets.intentional ? "intentional" : card.facets.rogue ? "rogue" : "unknown intent",
    card.facets.local_only ? "local-only" : card.facets.origin_backed ? "origin-backed" : "no origin proof",
    card.facets.operator_decision ? "operator decision" : "engineering task",
  ];
  return badges;
}

export function cardToInspect(card: CoherenceCard): InspectItem {
  const truth = classifyCardTruth(card);
  return {
    id: card.id,
    type: "card",
    title: card.title,
    subtitle: `${humanKind(card.kind)} · ${truth.code} · ${card.track || "unknown track"}`,
    status: card.status,
    risk: `${humanRisk(card.risk)} · ${truth.label}`,
    nextAction: card.next_action,
    evidence: card.evidence,
    raw: card,
  };
}

export function actionToInspect(action: CoherenceAction): InspectItem {
  return {
    id: `action:${action.kind}:${action.title}`,
    type: "action",
    title: action.title,
    subtitle: humanKind(action.kind),
    risk: humanRisk(action.risk),
    nextAction: action.next_action,
    evidence: action.evidence,
    raw: action,
  };
}

function urgencyForRisk(risk: string, rank: number): ActionPacket["urgency"] {
  const text = risk.toLowerCase();
  if (text.includes("critical") || text.includes("blocked") || text.includes("breakage")) return "critical";
  if (text.includes("dirty") || text.includes("unpreserved") || text.includes("local") || rank === 1) return "high";
  if (text.includes("stale") || text.includes("orphaned") || text.includes("unpushed")) return "medium";
  return "low";
}

export function buildActionPackets(report: OperatorCoherenceReport): ActionPacket[] {
  return (report.executive?.next_3_actions ?? []).slice(0, 3).map((action, index) => {
    const evidence = action.evidence ?? [];
    return {
      id: `action:${index + 1}:${action.kind}:${action.title}`.replace(/[^a-zA-Z0-9_.:-]/g, "_"),
      title: action.title || humanRisk(action.risk),
      rank: index + 1,
      urgency: urgencyForRisk(action.risk ?? "", index + 1),
      why: action.next_action || action.title || "operator action proposed by report",
      evidence,
      targets: evidence.map((ev) => ev.path ?? ev.source).filter(Boolean).slice(0, 5),
      expectedImpact: action.next_action || "resolve or preserve the highest-ranked report risk",
      risk: action.risk,
      operatorDecision: true,
      allowedNow: false,
      raw: action,
    };
  });
}

export function actionPacketToInspect(packet: ActionPacket): InspectItem {
  return {
    id: packet.id,
    type: "action",
    title: packet.title,
    subtitle: `rank ${packet.rank} · ${packet.urgency} · proposal only`,
    status: packet.allowedNow ? "approved" : "proposal_only",
    risk: humanRisk(packet.risk),
    nextAction: packet.expectedImpact,
    evidence: packet.evidence,
    raw: packet,
  };
}

export function sourceToInspect(source: (typeof DESIGN_SOURCES)[number]): InspectItem {
  return {
    id: `source:${source.id}`,
    type: "source",
    title: source.label,
    subtitle: source.path,
    status: "design source",
    nextAction: source.role,
    evidence: [{ kind: "file", source: source.path, path: source.path, detail: source.role }],
    raw: source,
  };
}

export function buildAuthorityInspect(report: OperatorCoherenceReport): InspectItem {
  const localMax = (report.track_portfolio as { policy?: { max_active?: unknown } }).policy?.max_active;
  const candidateBranch = report.git?.main?.branch ?? "unknown local branch";
  const source = buildReportSourceSummary(report);
  return {
    id: "panel:authority",
    type: "panel",
    title: "Report authority and source mode",
    subtitle: `${candidateBranch} · ${source.label}`,
    status: `local ${report.track_portfolio.active_count}/${asText(localMax)} active tracks · report ${report.status ?? "snapshot"}`,
    risk: "This panel reports only fields available in the operator-coherence report; missing canonical baseline evidence is uncertainty.",
    nextAction: "Use the report evidence and receipts before promoting, merging, or treating this checkout as canonical.",
    evidence: [
      {
        kind: "git",
        source: "report.git.main",
        detail: report.git?.main?.branch_line ?? candidateBranch,
      },
      {
        kind: "track_portfolio",
        source: "reports/governance/operator_coherence_cockpit.json",
        detail: `local projection active_count=${report.track_portfolio.active_count}, max_active=${asText(localMax)}`,
      },
      {
        kind: "source_mode",
        source: "/api/operator-coherence/report",
        detail: source.detail,
      },
    ],
    raw: { report_status: report.status, local_git: report.git?.main, local_track_portfolio: report.track_portfolio, source_refs: report.source_refs },
  };
}

export function buildLaneAdmissionInspect(): InspectItem {
  return {
    id: "panel:lane-admission",
    type: "panel",
    title: "Agent Lane Admission Packet contract",
    subtitle: "UI consumer contract for parallel agent lanes",
    status: "schema defined; live packets pending backplane ingestion",
    risk: "Without packets, parallel lanes remain hard to promote safely",
    nextAction: "Render every lane as a cockpit-visible packet before ACTIVE_TRACK admission, fold-in, or archive.",
    evidence: [
      {
        kind: "schema",
        source: "docs/governance/schemas/agent_lane_admission_packet.schema.json",
        path: "docs/governance/schemas/agent_lane_admission_packet.schema.json",
        detail: `${LANE_ADMISSION_FIELDS.length} required fields`,
      },
    ],
    raw: { required_fields: LANE_ADMISSION_FIELDS },
  };
}

export function buildHandoff(item: InspectItem): string {
  const evidence = (item.evidence ?? []).map((ev) => `- ${ev.source}${ev.detail ? ` — ${ev.detail}` : ""}`).join("\n");
  return [
    "You are taking over a scoped Cockpit V2 object from DharmaSwarm.",
    "Start with `make onboard`. Do not reset/stash/delete/kill anything.",
    "",
    `Object: ${item.title}`,
    item.subtitle ? `Context: ${item.subtitle}` : "",
    item.status ? `Status: ${item.status}` : "",
    item.risk ? `Risk: ${item.risk}` : "",
    item.nextAction ? `Next action: ${item.nextAction}` : "",
    "",
    "Evidence:",
    evidence || "- no evidence attached; verify source before acting",
    "",
    "Expected output: recommendation, safe plan, verification command, and receipt path.",
  ].filter(Boolean).join("\n");
}

/* ============================================================
   Freshness — REQ-007, REQ-062: stale must be visually distinct
   ============================================================ */

export type Freshness = "fresh" | "aging" | "stale" | "unknown";

export function freshnessFromAge(ageHours: number | null | undefined): Freshness {
  if (ageHours == null || !Number.isFinite(ageHours)) return "unknown";
  if (ageHours < 24) return "fresh";
  if (ageHours < 24 * 7) return "aging";
  return "stale";
}

export function freshnessTone(freshness: Freshness): TruthTone {
  switch (freshness) {
    case "fresh":
      return "ok";
    case "aging":
      return "warn";
    case "stale":
      return "danger";
    default:
      return "muted";
  }
}

export function freshnessLabel(freshness: Freshness): string {
  switch (freshness) {
    case "fresh":
      return "fresh";
    case "aging":
      return "aging";
    case "stale":
      return "stale";
    default:
      return "unknown age";
  }
}

export function cardFreshness(card: CoherenceCard): Freshness {
  if (card.facets?.live) return "fresh";
  const ages = (card.evidence ?? [])
    .map((ev) => ev.age_hours)
    .filter((age): age is number => typeof age === "number" && Number.isFinite(age));
  if (card.facets?.stale) {
    // Stale facet wins unless evidence proves fresh.
    if (ages.length && Math.min(...ages) < 24) return "aging";
    return "stale";
  }
  if (!ages.length) return "unknown";
  return freshnessFromAge(Math.min(...ages));
}

/* ============================================================
   Answer Ribbon — REQ-013/REQ-014, spec 11.3
   Under-60-second answers bound to report.definition_answers.
   ============================================================ */

export type AnswerKey =
  | "safe"
  | "dirty"
  | "abandoned"
  | "live"
  | "blocked"
  | "rogue"
  | "next"
  | "readiness";

export interface AnswerDatum {
  key: AnswerKey;
  label: string;
  question: string;
  value: string;
  count: number | null;
  topEvidence: string;
  tone: TruthTone;
  /** filter mode this answer maps to when clicked; null = inspect only */
  filterStatus: string | null;
  inspect: InspectItem;
}

type DefinitionAnswers = {
  what_is_safe?: CoherenceCard[];
  what_is_dirty?: CoherenceCard[];
  what_is_abandoned?: CoherenceCard[];
  what_is_live?: CoherenceCard[];
  what_is_blocked?: CoherenceCard[];
  what_might_be_rogue?: CoherenceCard[];
  what_should_i_do_next?: CoherenceAction[];
  [key: string]: unknown;
};

function answerCards(report: OperatorCoherenceReport, key: keyof DefinitionAnswers): CoherenceCard[] {
  const da = (report.definition_answers ?? {}) as DefinitionAnswers;
  const value = da[key];
  return Array.isArray(value) ? (value as CoherenceCard[]) : [];
}

function topEvidenceText(cards: CoherenceCard[]): string {
  const first = cards[0];
  if (!first) return "no items — verify source before trusting blank";
  const ev = first.evidence?.[0];
  const base = first.title || first.id;
  return ev?.detail ? `${base} — ${ev.detail}` : ev?.source ? `${base} — ${ev.source}` : base;
}

function cardsToInspect(title: string, question: string, cards: CoherenceCard[]): InspectItem {
  return {
    type: "panel",
    title,
    subtitle: question,
    status: cards.length ? `${cards.length} items` : "0 items",
    evidence: cards.slice(0, 12).flatMap((card) =>
      (card.evidence ?? []).slice(0, 1).map((ev) => ({
        ...ev,
        source: `${card.title || card.id} · ${ev.source}`,
      })),
    ),
    raw: cards,
  };
}

export function buildAnswerRibbon(report: OperatorCoherenceReport): AnswerDatum[] {
  const safe = answerCards(report, "what_is_safe");
  const dirty = answerCards(report, "what_is_dirty");
  const abandoned = answerCards(report, "what_is_abandoned");
  const live = answerCards(report, "what_is_live");
  const blocked = answerCards(report, "what_is_blocked");
  const rogue = answerCards(report, "what_might_be_rogue");
  const da = (report.definition_answers ?? {}) as DefinitionAnswers;
  const next = Array.isArray(da.what_should_i_do_next) ? da.what_should_i_do_next : [];
  const readiness = report.readiness?.score ?? 0;

  return [
    {
      key: "safe",
      label: "Safe",
      question: "What is safe?",
      value: String(safe.length),
      count: safe.length,
      topEvidence: topEvidenceText(safe),
      tone: safe.length ? "ok" : "muted",
      filterStatus: "safe",
      inspect: cardsToInspect("What is safe", "No immediate action indicated", safe),
    },
    {
      key: "dirty",
      label: "Dirty",
      question: "What is dirty?",
      value: String(dirty.length),
      count: dirty.length,
      topEvidence: topEvidenceText(dirty),
      tone: dirty.length ? "danger" : "ok",
      filterStatus: "dirty",
      inspect: cardsToInspect("What is dirty", "Local uncommitted / unmerged work", dirty),
    },
    {
      key: "abandoned",
      label: "Abandoned",
      question: "What is abandoned?",
      value: String(abandoned.length),
      count: abandoned.length,
      topEvidence: topEvidenceText(abandoned),
      tone: abandoned.length ? "warn" : "ok",
      filterStatus: "abandoned",
      inspect: cardsToInspect("What is abandoned", "Stale, orphaned, or upstream-gone work", abandoned),
    },
    {
      key: "live",
      label: "Live",
      question: "What is live?",
      // REQ-006/anti-pattern: empty live is uncertainty, not blank success.
      value: live.length ? String(live.length) : "0",
      count: live.length,
      topEvidence: live.length ? topEvidenceText(live) : "no fresh live surfaces proven — treat as uncertainty",
      tone: live.length ? "ok" : "warn",
      filterStatus: "live",
      inspect: cardsToInspect("What is live", "Surface actively running and fresh", live),
    },
    {
      key: "blocked",
      label: "Blocked",
      question: "What is blocked?",
      value: String(blocked.length),
      count: blocked.length,
      topEvidence: topEvidenceText(blocked),
      tone: blocked.length ? "danger" : "ok",
      filterStatus: "blocked",
      inspect: cardsToInspect("What is blocked", "Known blocker prevents progress", blocked),
    },
    {
      key: "rogue",
      label: "Rogue",
      question: "What might be rogue?",
      value: String(rogue.length),
      count: rogue.length,
      topEvidence: topEvidenceText(rogue),
      tone: rogue.length ? "warn" : "ok",
      filterStatus: "rogue",
      inspect: cardsToInspect("What might be rogue", "Work not attached to a canonical active track/owner", rogue),
    },
    {
      key: "next",
      label: "Next",
      question: "What should I do next?",
      value: String(next.length),
      count: next.length,
      topEvidence: next[0]?.next_action ?? next[0]?.title ?? "no ranked action",
      tone: next.length ? "info" : "muted",
      filterStatus: null,
      inspect: {
        type: "panel",
        title: "What should I do next",
        subtitle: "Top operator actions — proposal only",
        status: `${next.length} ranked`,
        evidence: next.flatMap((a) => a.evidence ?? []),
        raw: next,
      },
    },
    {
      key: "readiness",
      label: "Readiness",
      question: "Is the system okay?",
      value: `${readiness}%`,
      count: null,
      topEvidence: report.readiness?.interpretation ?? "computed projection",
      tone: readinessTone(readiness),
      filterStatus: null,
      inspect: {
        type: "panel",
        title: "Prod readiness",
        subtitle: "Weighted score from evidence categories",
        status: `${readiness}%`,
        evidence: Object.entries(report.readiness?.categories ?? {}).map(([source, item]) => ({
          kind: "score",
          source,
          detail: `${item.score}% × ${Math.round(item.weight * 100)}% — ${item.why}`,
        })),
        raw: report.readiness,
      },
    },
  ];
}

/* ============================================================
   Uncertainty / external systems — REQ-006, REQ-052, REQ-070,
   REQ-072, anti-patterns 2/3/4. Make uncertainty impossible to miss.
   ============================================================ */

export interface UncertaintyDatum {
  id: string;
  label: string;
  /** unavailable | partial | degraded */
  state: "unavailable" | "partial" | "degraded";
  detail: string;
  source: string;
  evidence: CoherenceEvidence[];
}

function sourceErrorFor(report: OperatorCoherenceReport, needle: string): { source: string; error: string; timestamp?: string } | undefined {
  return report.source_errors.find((err) => err.source.includes(needle) || err.error.includes(needle));
}

export function buildUncertainty(report: OperatorCoherenceReport): UncertaintyDatum[] {
  const out: UncertaintyDatum[] = [];

  // Raw source errors from the probe pipeline.
  for (const err of report.source_errors) {
    out.push({
      id: `source:${err.source}`,
      label: err.source,
      state: "unavailable",
      detail: err.error.trim() || "source error reported",
      source: err.source,
      evidence: [{ kind: "source_error", source: err.source, detail: err.error.trim(), observed_at: err.timestamp }],
    });
  }

  // gh auth / PR-CI (REQ-070): explicit uncertainty, never silent success.
  const ghErr = sourceErrorFor(report, "github") ?? sourceErrorFor(report, "gh");
  const prCi = report.pr_ci_triage as { enabled?: boolean; reason?: string } | undefined;
  if (prCi?.enabled === false || ghErr) {
    const already = out.some((u) => u.id === `source:${ghErr?.source ?? ""}`);
    if (!already) {
      out.push({
        id: "external:gh",
        label: "GitHub PR/CI",
        state: "unavailable",
        detail: prCi?.reason ?? ghErr?.error?.trim() ?? "gh auth unavailable; PR/CI triage omitted",
        source: "github.auth",
        evidence: [{ kind: "external", source: "pr_ci_triage", detail: prCi?.reason ?? "gh_auth_unavailable" }],
      });
    }
  }

  // tmux (REQ-052): unavailable is uncertainty, not health.
  const tmuxErr = sourceErrorFor(report, "tmux");
  if (!tmuxErr && (report.agent_terminal_census?.tmux_sessions ?? []).length === 0) {
    out.push({
      id: "external:tmux",
      label: "tmux sessions",
      state: "unavailable",
      detail: "no tmux socket/session observed; agent terminal liveness is uncertain, not healthy",
      source: "tmux.ls",
      evidence: [{ kind: "external", source: "agent_terminal_census.tmux_sessions", detail: "0 sessions observed" }],
    });
  }

  // gcx / Grafana Cloud (REQ-072, spec 11.10): not wired into report yet.
  out.push({
    id: "external:gcx",
    label: "Grafana / gcx",
    state: "unavailable",
    detail: "gcx context not wired into the operator-coherence report; external observability shown as unavailable, never faked",
    source: "gcx.config",
    evidence: [{ kind: "external", source: "gcx", detail: "no datasource/SLO/alert telemetry available until configured" }],
  });

  return out;
}

export function uncertaintyInspect(item: UncertaintyDatum): InspectItem {
  return {
    type: "source",
    title: item.label,
    subtitle: `${item.source} · ${item.state}`,
    status: item.state,
    risk: "Missing evidence — do not read absence as success",
    nextAction: "Restore the source (auth/session/config) or treat dependent claims as uncertain.",
    evidence: item.evidence,
    raw: item,
  };
}

/* ============================================================
   Topology — REQ-030/031/032/034/035, spec 7.1/7.2/8.5/11.6
   Derived CockpitNode / CockpitEdge with stable IDs.
   ============================================================ */

export type NodeKind =
  | "readiness_category"
  | "track"
  | "card"
  | "branch"
  | "worktree"
  | "surface"
  | "receipt"
  | "source_error"
  | "action"
  | "system";

export interface CockpitNode {
  id: string;
  label: string;
  kind: NodeKind;
  status: string;
  risk: "none" | "low" | "medium" | "high" | "critical" | "unknown";
  freshness: Freshness;
  authority: "read_only" | "proposal_required" | "operator_required" | "unavailable";
  cluster: string;
  track?: string;
  branch?: string;
  sourcePath?: string;
  score?: number;
  evidenceCount: number;
  nextAction?: string;
  tone: TruthTone;
  pulse: boolean;
  inspect: InspectItem;
}

export interface CockpitEdge {
  id: string;
  source: string;
  target: string;
  relation:
    | "belongs_to"
    | "depends_on"
    | "evidence_for"
    | "blocks"
    | "runs_on"
    | "checked_by"
    | "upstream_of"
    | "receipt_for"
    | "proposes";
  status: string;
  strength: number;
  freshness: Freshness;
  uncertain: boolean;
  evidence: string[];
}

export interface CockpitGraph {
  nodes: CockpitNode[];
  edges: CockpitEdge[];
}

const ROOT_ID = "system:readiness";

function riskLevel(card: CoherenceCard): CockpitNode["risk"] {
  const r = card.risk ?? "";
  if (card.lane === "Needs Repair") return "high";
  if (r.includes("blocked") || r.includes("breakage") || r.includes("ci_failed")) return "critical";
  if (r.includes("dirty") || r.includes("orphaned") || r.includes("local_only")) return "high";
  if (r.includes("stale")) return "medium";
  if (card.facets?.operator_decision) return "medium";
  if (card.facets?.preserved || card.facets?.live) return "low";
  return "unknown";
}

function cardAuthority(card: CoherenceCard): CockpitNode["authority"] {
  if (card.facets?.operator_decision) return "operator_required";
  if (card.lane === "Needs Repair" || card.lane === "Needs Decision") return "proposal_required";
  return "read_only";
}

function safeId(prefix: string, value: string, index: number): string {
  const base = (value || `${index}`).replace(/[^a-zA-Z0-9_.:-]/g, "_").slice(0, 60);
  return `${prefix}:${base}:${index}`;
}

export function buildTopology(report: OperatorCoherenceReport): CockpitGraph {
  const nodes: CockpitNode[] = [];
  const edges: CockpitEdge[] = [];
  const trackNodeByName = new Map<string, string>();

  // Root: readiness.
  const readiness = report.readiness?.score ?? 0;
  nodes.push({
    id: ROOT_ID,
    label: `Readiness ${readiness}%`,
    kind: "system",
    status: report.executive?.health ?? "unknown",
    risk: readiness >= 70 ? "low" : readiness >= 40 ? "medium" : "high",
    freshness: "fresh",
    authority: "read_only",
    cluster: "system",
    score: readiness,
    evidenceCount: Object.keys(report.readiness?.categories ?? {}).length,
    tone: readinessTone(readiness),
    pulse: false,
    inspect: {
      type: "panel",
      title: "System readiness",
      subtitle: report.readiness?.interpretation,
      status: `${readiness}%`,
      evidence: Object.entries(report.readiness?.categories ?? {}).map(([source, item]) => ({
        kind: "score",
        source,
        detail: `${item.score}% × ${Math.round(item.weight * 100)}%`,
      })),
      raw: report.readiness,
    },
  });

  // Readiness categories: evidence_for root.
  Object.entries(report.readiness?.categories ?? {}).forEach(([name, cat], index) => {
    const id = safeId("cat", name, index);
    nodes.push({
      id,
      label: name.replaceAll("_", " "),
      kind: "readiness_category",
      status: cat.score >= 70 ? "done" : cat.score >= 40 ? "warn" : "danger",
      risk: cat.score >= 70 ? "low" : cat.score >= 40 ? "medium" : "high",
      freshness: "fresh",
      authority: "read_only",
      cluster: "readiness",
      score: cat.score,
      evidenceCount: 1,
      tone: readinessTone(cat.score),
      pulse: false,
      inspect: {
        type: "panel",
        title: name.replaceAll("_", " "),
        subtitle: `${cat.score}% × ${Math.round(cat.weight * 100)}% weight`,
        status: `${cat.score}%`,
        evidence: [{ kind: "score", source: name, detail: cat.why }],
        raw: cat,
      },
    });
    edges.push({
      id: `e:${id}->${ROOT_ID}`,
      source: id,
      target: ROOT_ID,
      relation: "evidence_for",
      status: nodes[nodes.length - 1].status,
      strength: cat.weight,
      freshness: "fresh",
      uncertain: false,
      evidence: [cat.why],
    });
  });

  // Tracks: belongs_to root (organ clusters).
  const tracks = (report.track_portfolio?.tracks ?? []) as Record<string, unknown>[];
  tracks.forEach((track, index) => {
    const name = asText(track.name);
    const id = safeId("track", asText(track.id) || name, index);
    const stale = Boolean(track.stale);
    trackNodeByName.set(name, id);
    nodes.push({
      id,
      label: name,
      kind: "track",
      status: stale ? "stale" : asText(track.status) || "unknown",
      risk: stale ? "medium" : "low",
      freshness: stale ? "stale" : "aging",
      authority: "read_only",
      cluster: "tracks",
      evidenceCount: track.evidence_present ? 1 : 0,
      tone: stale ? "warn" : "info",
      pulse: false,
      inspect: {
        type: "track",
        title: name,
        subtitle: asText(track.id),
        status: asText(track.status),
        raw: track,
      },
    });
    edges.push({
      id: `e:${id}->${ROOT_ID}`,
      source: id,
      target: ROOT_ID,
      relation: "belongs_to",
      status: stale ? "stale" : "safe",
      strength: 0.4,
      freshness: stale ? "stale" : "aging",
      uncertain: !track.evidence_present,
      evidence: [asText(track.evidence_path ?? track.status ?? track.id)],
    });
  });

  // Live surfaces: runs_on root, pulse only if live AND fresh.
  const surfaces = (report.live_ops?.surfaces ?? []) as Record<string, unknown>[];
  surfaces.forEach((surface, index) => {
    const status = asText(surface.status) || "unknown";
    const id = safeId("surface", asText(surface.id), index);
    const fresh = freshnessFromAge(typeof surface.age_hours === "number" ? surface.age_hours : null);
    const isLive = status === "live" && fresh === "fresh";
    const tone: TruthTone = status === "live" ? "ok" : status === "blocked" ? "danger" : status === "stale" ? "warn" : "muted";
    nodes.push({
      id,
      label: asText(surface.label) || asText(surface.id),
      kind: "surface",
      status,
      risk: status === "blocked" ? "critical" : status === "stale" ? "medium" : "low",
      freshness: status === "live" ? (fresh === "unknown" ? "stale" : fresh) : fresh,
      authority: surface.human_authority_required ? "operator_required" : "read_only",
      cluster: "live_ops",
      evidenceCount: status === "unknown" ? 0 : 1,
      nextAction: asText(surface.desired_state) === "live" && status !== "live" ? "Desired live but stopped" : undefined,
      tone,
      pulse: isLive,
      inspect: {
        type: "card",
        title: asText(surface.label) || asText(surface.id),
        subtitle: `live-ops surface · ${status}`,
        status,
        risk: asText(surface.desired_state) === "live" && status !== "live" ? "Desired live, not live" : undefined,
        evidence: [{ kind: "live_ops", source: "scripts/runtime/live_ops_census.py", detail: `status=${status} desired=${asText(surface.desired_state)}`, age_hours: typeof surface.age_hours === "number" ? surface.age_hours : null }],
        raw: surface,
      },
    });
    edges.push({
      id: `e:${id}->${ROOT_ID}`,
      source: id,
      target: ROOT_ID,
      relation: "runs_on",
      status,
      strength: 0.5,
      freshness: status === "live" ? (fresh === "unknown" ? "stale" : fresh) : fresh,
      uncertain: status === "unknown",
      evidence: [`status=${status} desired=${asText(surface.desired_state)}`],
    });
  });

  // Cards attach to their track or root. Node kind preserves branch/worktree/receipt semantics.
  report.cards.forEach((card, index) => {
    const semanticKind: CockpitNode["kind"] =
      card.kind === "branch"
        ? "branch"
        : card.kind === "worktree" || card.kind === "dirty_files"
          ? "worktree"
          : card.kind === "runtime_receipts" || card.kind === "runtime_db" || card.kind.includes("receipt")
            ? "receipt"
            : "card";
    const id = safeId(semanticKind, card.id, index);
    const truth = classifyCardTruth(card);
    const fresh = cardFreshness(card);
    const trackTarget = card.track && trackNodeByName.get(card.track);
    nodes.push({
      id,
      label: card.title || card.id,
      kind: semanticKind,
      status:
        card.facets?.live ? "live" :
          card.facets?.local_only || card.kind === "dirty_files" || card.kind === "worktree" ? "dirty" :
            card.facets?.rogue ? "rogue" :
              card.facets?.stale ? "stale" :
                card.lane === "Needs Repair" ? "danger" :
                  card.facets?.operator_decision ? "needs" : "warn",
      risk: riskLevel(card),
      freshness: fresh,
      authority: cardAuthority(card),
      cluster: card.track && trackTarget ? card.track : card.lane,
      track: card.track,
      branch: card.branch,
      sourcePath: card.evidence?.find((ev) => ev.path)?.path ?? card.evidence?.[0]?.source,
      evidenceCount: card.evidence?.length ?? 0,
      nextAction: card.next_action,
      tone: truth.tone,
      pulse: false,
      inspect: cardToInspect(card),
    });
    edges.push({
      id: `e:${id}->${trackTarget ?? ROOT_ID}`,
      source: id,
      target: trackTarget ?? ROOT_ID,
      relation: card.lane === "Needs Repair" ? "blocks" : "belongs_to",
      status: card.lane === "Needs Repair" ? "blocked" : "needs",
      strength: 0.3,
      freshness: fresh,
      uncertain: (card.evidence?.length ?? 0) === 0,
      evidence: (card.evidence ?? []).map((ev) => ev.detail || ev.source).slice(0, 3),
    });
  });

  // Action packets: proposal-only action objects from report.executive.next_3_actions.
  buildActionPackets(report).forEach((packet) => {
    nodes.push({
      id: packet.id,
      label: packet.title,
      kind: "action",
      status: "needs",
      risk: packet.urgency === "critical" ? "critical" : packet.urgency === "high" ? "high" : packet.urgency === "medium" ? "medium" : "low",
      freshness: "fresh",
      authority: "proposal_required",
      cluster: "actions",
      evidenceCount: packet.evidence.length,
      nextAction: packet.expectedImpact,
      sourcePath: packet.targets[0],
      tone: packet.urgency === "critical" || packet.urgency === "high" ? "danger" : "warn",
      pulse: false,
      inspect: actionPacketToInspect(packet),
    });
    edges.push({
      id: `e:${packet.id}->${ROOT_ID}`,
      source: packet.id,
      target: ROOT_ID,
      relation: "proposes",
      status: "needs",
      strength: 0.65,
      freshness: "fresh",
      uncertain: packet.evidence.length === 0,
      evidence: packet.evidence.map((ev) => ev.detail || ev.source).slice(0, 3),
    });
  });

  // Receipt files not already represented as cards get explicit receipt nodes.
  const receipts = (report.runtime_receipts?.recent_receipts ?? []) as Record<string, unknown>[];
  receipts.slice(0, 24).forEach((receipt, index) => {
    const path = asText(receipt.path);
    const age = typeof receipt.age_hours === "number" ? receipt.age_hours : null;
    const fresh = freshnessFromAge(age);
    const id = safeId("receipt", path, index);
    if (nodes.some((node) => node.sourcePath === path)) return;
    nodes.push({
      id,
      label: path.split("/").pop() ?? path,
      kind: "receipt",
      status: fresh === "stale" ? "stale" : fresh === "unknown" ? "unknown" : "done",
      risk: fresh === "stale" ? "medium" : fresh === "unknown" ? "unknown" : "low",
      freshness: fresh,
      authority: "read_only",
      cluster: "receipts",
      sourcePath: path,
      evidenceCount: 1,
      tone: freshnessTone(fresh),
      pulse: false,
      inspect: {
        id,
        type: "source",
        title: path.split("/").pop() ?? path,
        subtitle: "receipt evidence",
        status: freshnessLabel(fresh),
        evidence: [{ kind: "receipt", source: path, path, age_hours: age }],
        raw: receipt,
      },
    });
    edges.push({
      id: `e:${id}->${ROOT_ID}`,
      source: id,
      target: ROOT_ID,
      relation: "receipt_for",
      status: fresh === "stale" ? "stale" : "done",
      strength: 0.25,
      freshness: fresh,
      uncertain: fresh === "unknown",
      evidence: [path],
    });
  });

  // Source errors: checked_by root, always uncertain/dashed.
  report.source_errors.forEach((err, index) => {
    const id = safeId("err", err.source, index);
    nodes.push({
      id,
      label: err.source,
      kind: "source_error",
      status: "unknown",
      risk: "unknown",
      freshness: "unknown",
      authority: "unavailable",
      cluster: "uncertainty",
      evidenceCount: 1,
      tone: "muted",
      pulse: false,
      inspect: {
        type: "source",
        title: err.source,
        subtitle: "source unavailable",
        status: "unavailable",
        risk: "Missing evidence is uncertainty, not success",
        evidence: [{ kind: "source_error", source: err.source, detail: err.error.trim(), observed_at: err.timestamp }],
        raw: err,
      },
    });
    edges.push({
      id: `e:${id}->${ROOT_ID}`,
      source: id,
      target: ROOT_ID,
      relation: "checked_by",
      status: "unknown",
      strength: 0.2,
      freshness: "unknown",
      uncertain: true,
      evidence: [err.error.trim()],
    });
  });

  return { nodes, edges };
}

export function nodeMatchesFilter(node: CockpitNode, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    node.id,
    node.label,
    node.kind,
    node.status,
    node.risk,
    node.freshness,
    node.authority,
    node.cluster,
    node.track,
    node.branch,
    node.sourcePath,
    node.nextAction,
    node.inspect.title,
    node.inspect.subtitle,
    node.inspect.risk,
    node.inspect.nextAction,
    ...(node.inspect.evidence ?? []).map((ev) => `${ev.source} ${ev.path ?? ""} ${ev.detail ?? ""}`),
  ].join(" ").toLowerCase();
  return haystack.includes(q);
}

/** Stable cluster ordering used by topology + recursive layouts. */
export const CLUSTER_ORDER = ["system", "readiness", "actions", "tracks", "live_ops", "receipts", "uncertainty"] as const;

/** All status codes the UI may render; used by the token-coverage test. */
export const STATUS_TOKENS = [
  "safe",
  "dirty",
  "abandoned",
  "live",
  "blocked",
  "rogue",
  "stale",
  "unknown",
  "needs",
  "warn",
  "danger",
  "running",
  "done",
  "special",
] as const;

export type StatusToken = (typeof STATUS_TOKENS)[number];

/** Map any status string to a visual tone — guarantees no unmapped status. */
export function statusTone(status: string): TruthTone {
  switch (status) {
    case "safe":
    case "done":
    case "live":
      return "ok";
    case "needs":
    case "warn":
    case "stale":
    case "abandoned":
    case "rogue":
      return "warn";
    case "dirty":
    case "blocked":
    case "danger":
      return "danger";
    case "running":
    case "special":
      return "info";
    default:
      return "muted";
  }
}

/* ============================================================
   Receipt / event tape — REQ-060/061/062, spec 11.9
   History not yet wired: single-snapshot honesty.
   ============================================================ */

export interface TapeEvent {
  id: string;
  label: string;
  kind: "report" | "receipt" | "runtime_db" | "source_error" | "live_ops" | "pr_ci";
  freshness: Freshness;
  detail: string;
  tone: TruthTone;
  evidence: CoherenceEvidence[];
}

export function buildEventTape(report: OperatorCoherenceReport): TapeEvent[] {
  const events: TapeEvent[] = [];

  events.push({
    id: "event:report",
    label: "Report generated",
    kind: "report",
    freshness: "fresh",
    detail: report.generated_at,
    tone: "info",
    evidence: [{ kind: "report", source: "/api/operator-coherence/report", detail: report.generated_at }],
  });

  const receipts = (report.runtime_receipts?.recent_receipts ?? []) as Record<string, unknown>[];
  receipts.slice(0, 8).forEach((receipt, index) => {
    const age = typeof receipt.age_hours === "number" ? receipt.age_hours : null;
    const fresh = freshnessFromAge(age);
    events.push({
      id: safeId("receipt", asText(receipt.path), index),
      label: asText(receipt.path).split("/").pop() ?? asText(receipt.path),
      kind: "receipt",
      freshness: fresh,
      detail: `${asText(receipt.path)} · ${age != null ? `${Math.round(age)}h old` : "age unknown"}`,
      tone: freshnessTone(fresh),
      evidence: [{ kind: "receipt", source: asText(receipt.path), path: asText(receipt.path), age_hours: age }],
    });
  });

  for (const err of report.source_errors) {
    events.push({
      id: `event:err:${err.source}`,
      label: `${err.source} unavailable`,
      kind: "source_error",
      freshness: "unknown",
      detail: err.error.trim(),
      tone: "muted",
      evidence: [{ kind: "source_error", source: err.source, detail: err.error.trim(), observed_at: err.timestamp }],
    });
  }

  const prCi = report.pr_ci_triage as { enabled?: boolean; reason?: string } | undefined;
  if (prCi?.enabled === false) {
    events.push({
      id: "event:pr_ci",
      label: "PR/CI unavailable",
      kind: "pr_ci",
      freshness: "unknown",
      detail: prCi.reason ?? "gh auth unavailable",
      tone: "muted",
      evidence: [{ kind: "external", source: "pr_ci_triage", detail: prCi.reason ?? "gh_auth_unavailable" }],
    });
  }

  return events;
}

export function tapeEventInspect(event: TapeEvent): InspectItem {
  return {
    type: "source",
    title: event.label,
    subtitle: `${event.kind} · ${freshnessLabel(event.freshness)}`,
    status: event.kind === "source_error" || event.kind === "pr_ci" ? "unavailable" : event.freshness,
    evidence: event.evidence,
    raw: event,
  };
}

export function modeMatches(card: CoherenceCard, mode: CockpitMode): boolean {
  switch (mode) {
    case "triage":
      return card.lane === "Needs Repair" || card.lane === "Needs Decision" || card.facets.operator_decision;
    case "git":
      return ["branch", "worktree", "dirty_files", "stash"].includes(card.kind);
    case "runtime":
      return ["live_ops_surface", "launchd_job", "tmux_session", "runtime_db", "runtime_receipts", "operator_surface"].includes(card.kind);
    case "tracks":
      return ["track", "proposed_track", "broken_register"].includes(card.kind);
    case "preservation":
      return card.kind.includes("preservation") || card.facets.preserved || card.risk.includes("preserved") || card.risk.includes("receipt");
    case "evidence":
      return true;
    case "design":
      return false;
    default:
      return true;
  }
}

export function filterCards(cards: CoherenceCard[], mode: CockpitMode, query: string): CoherenceCard[] {
  const q = query.trim().toLowerCase();
  return cards
    .filter((card) => modeMatches(card, mode))
    .filter((card) => {
      if (!q) return true;
      const haystack = [
        card.kind,
        card.title,
        card.status,
        card.lane,
        card.track,
        card.branch,
        card.pr,
        card.risk,
        card.next_action,
        ...(card.evidence ?? []).map((ev) => `${ev.source} ${ev.detail ?? ""}`),
      ].join(" ").toLowerCase();
      return haystack.includes(q);
    });
}

export function buildTopPanels(report: OperatorCoherenceReport): CockpitPanelDatum[] {
  const liveStatus = report.live_ops?.summary?.by_status ?? {};
  const runtimeTotal = report.live_ops?.summary?.total ?? 0;
  const receiptCount = report.runtime_receipts?.receipt_count ?? 0;
  const sourceControl = report.readiness.categories.source_control_coherence;
  const runtime = report.readiness.categories.runtime_telemetry_liveness;
  const preservation = report.readiness.categories.preservation_safety;
  const needsDecision = report.kanban.find((lane) => lane.lane === "Needs Decision")?.count ?? 0;
  const needsRepair = report.kanban.find((lane) => lane.lane === "Needs Repair")?.count ?? 0;

  return [
    {
      id: "readiness",
      eyebrow: "System verdict",
      title: "Prod readiness",
      value: `${report.readiness.score}%`,
      detail: report.readiness.interpretation,
      tone: readinessTone(report.readiness.score),
      inspect: {
        type: "panel",
        title: "Prod readiness",
        subtitle: "Weighted score from 8 evidence categories",
        status: String(report.readiness.score),
        evidence: Object.entries(report.readiness.categories).map(([source, item]) => ({
          kind: "score",
          source,
          detail: `${item.score}% × ${Math.round(item.weight * 100)}% — ${item.why}`,
        })),
        raw: report.readiness,
      },
    },
    {
      id: "source-control",
      eyebrow: "Git coherence",
      title: "Source control",
      value: `${sourceControl?.score ?? 0}%`,
      detail: `${report.branch_census?.total ?? 0} branches · ${report.rogue_work_radar.stash_count} stashes`,
      tone: readinessTone(sourceControl?.score ?? 0),
      inspect: {
        type: "panel",
        title: "Source control radar",
        subtitle: sourceControl?.why,
        risk: "Local-only / unpushed / orphaned work",
        evidence: [{ kind: "git", source: "git for-each-ref refs/heads", detail: sourceControl?.why }],
        raw: { branch_census: report.branch_census, rogue_work_radar: report.rogue_work_radar },
      },
    },
    {
      id: "runtime",
      eyebrow: "Live ops",
      title: "Runtime liveness",
      value: `${runtime?.score ?? 0}%`,
      detail: `${liveStatus.live ?? 0}/${runtimeTotal} live · ${liveStatus.stale ?? 0} stale · ${liveStatus.blocked ?? 0} blocked`,
      tone: readinessTone(runtime?.score ?? 0),
      inspect: {
        type: "panel",
        title: "Runtime liveness",
        subtitle: runtime?.why,
        risk: "Stale / blocked / stopped desired-live surfaces",
        evidence: [{ kind: "live_ops", source: "scripts/runtime/live_ops_census.py", detail: runtime?.why }],
        raw: report.live_ops,
      },
    },
    {
      id: "needs-action",
      eyebrow: "Operator queue",
      title: "Needs action",
      value: `${needsDecision + needsRepair}`,
      detail: `${needsDecision} decision · ${needsRepair} repair`,
      tone: needsRepair > 0 ? "danger" : needsDecision > 0 ? "warn" : "ok",
      inspect: {
        type: "panel",
        title: "Needs action queue",
        subtitle: "Cards requiring operator decision or engineering repair",
        risk: "Highest-leverage cockpit work",
        evidence: report.executive.next_3_actions.flatMap((a) => a.evidence ?? []),
        raw: report.executive.next_3_actions,
      },
    },
    {
      id: "preservation",
      eyebrow: "Safety",
      title: "Preservation",
      value: `${preservation?.score ?? 0}%`,
      detail: `${report.preservation_ledger.at_risk_worktree_count ?? 0} worktrees at risk`,
      tone: readinessTone(preservation?.score ?? 0),
      inspect: {
        type: "panel",
        title: "Preservation safety",
        subtitle: preservation?.why,
        risk: "Local work can be lost or remain unreviewed",
        evidence: [{ kind: "preservation", source: "git worktree/status", detail: preservation?.why }],
        raw: report.preservation_ledger,
      },
    },
    {
      id: "receipts",
      eyebrow: "Proof ledger",
      title: "Runtime receipts",
      value: formatCount(receiptCount),
      detail: `${report.runtime_receipts?.runtime_dbs?.length ?? 0} DB paths checked`,
      tone: receiptCount > 0 ? "ok" : "warn",
      inspect: {
        type: "panel",
        title: "Runtime DB / receipt ledger",
        subtitle: "Read-only runtime DBs and receipt artifacts",
        evidence: [{ kind: "receipt", source: "runtime_receipts probe", detail: `${receiptCount} receipt files discovered` }],
        raw: report.runtime_receipts,
      },
    },
  ];
}
