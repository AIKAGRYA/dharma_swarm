import type {
  CoherenceAction,
  CoherenceCard,
  CoherenceEvidence,
  OperatorCoherenceReport,
} from "@/lib/operatorCoherence";

export type CockpitMode =
  | "overview"
  | "triage"
  | "git"
  | "runtime"
  | "tracks"
  | "preservation"
  | "evidence"
  | "design";

export interface InspectItem {
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

export interface TruthBadgeDatum {
  code: string;
  label: string;
  detail: string;
  tone: TruthTone;
}

export const MODES: { id: CockpitMode; label: string; hint: string }[] = [
  { id: "overview", label: "Overview", hint: "morning check" },
  { id: "triage", label: "Triage", hint: "needs action" },
  { id: "git", label: "Git", hint: "branches/worktrees" },
  { id: "runtime", label: "Runtime", hint: "live ops" },
  { id: "tracks", label: "Tracks", hint: "portfolio" },
  { id: "preservation", label: "Preservation", hint: "safety" },
  { id: "evidence", label: "Evidence", hint: "raw truth" },
  { id: "design", label: "Design Sources", hint: "Desktop canon" },
];

export const CANDIDATE_AUTHORITY = {
  status: "CANDIDATE_HIGH_PRIORITY_NOT_CANONICAL",
  canonicalRef: "origin/main",
  canonicalCommit: "839fd25f43c76375f49e45012fe8f20a324aa74c",
  canonicalSubject: "[codex] governance: refresh active track and fitness properties [impact-checked] (#647)",
  canonicalActiveTracks: 7,
  canonicalMaxActive: 10,
  recommendedBranch: "governance/operator-coherence-cockpit-20260623",
  admissionReviewPath: "reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.json",
  closeoutPath: "reports/governance/prod_readiness/PROD_READINESS_FINAL_CLOSEOUT_2026-06-23.json",
} as const;

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

export const PRODUCTION_READINESS_VERDICTS = [
  {
    trackId: "runtime-truth-reconciliation-2026-06",
    verdict: "CLOSE_READY_WITH_FOLLOWUP",
    action: "Candidate closure only after dependency-honest operator rendering and fresh runtime DB receipt snapshot.",
  },
  {
    trackId: "runtime-truth-nats-2026-06",
    verdict: "KEEP_ACTIVE_PROD_HARDENING",
    action: "Keep active until live NATS/JetStream ack proof and owned-surface reconciliation exist.",
  },
  {
    trackId: "truth-graph-platform-2026-06",
    verdict: "KEEP_ACTIVE_PROD_HARDENING",
    action: "Keep active until fresh NATS/presence proof and dependency-honest make orient exist.",
  },
  {
    trackId: "composer-holon-spine-longrun-2026-06",
    verdict: "SPLIT_BEFORE_CLOSE",
    action: "Split Build A readiness from standing composer / Holon L4 production proof before closure.",
  },
  {
    trackId: "provider-routing-consolidation-2026-06",
    verdict: "CLOSE_READY_WITH_FOLLOWUP",
    action: "Candidate closure only after live-provider canary / egress proof is recorded or explicitly environment-gated.",
  },
] as const;

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
    type: "action",
    title: action.title,
    subtitle: humanKind(action.kind),
    risk: humanRisk(action.risk),
    nextAction: action.next_action,
    evidence: action.evidence,
    raw: action,
  };
}

export function sourceToInspect(source: (typeof DESIGN_SOURCES)[number]): InspectItem {
  return {
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
  return {
    type: "panel",
    title: "Canonical vs dirty candidate authority",
    subtitle: `${CANDIDATE_AUTHORITY.status} · ${candidateBranch}`,
    status: `canonical ${CANDIDATE_AUTHORITY.canonicalActiveTracks}/${CANDIDATE_AUTHORITY.canonicalMaxActive} · local ${report.track_portfolio.active_count}/${asText(localMax)}`,
    risk: "Dirty local candidate projection must not be treated as origin/main truth",
    nextAction: `Extract candidate into ${CANDIDATE_AUTHORITY.recommendedBranch} only with operator approval; do not raw-merge dirty checkout.`,
    evidence: [
      {
        kind: "admission_review",
        source: CANDIDATE_AUTHORITY.admissionReviewPath,
        path: CANDIDATE_AUTHORITY.admissionReviewPath,
        detail: `${CANDIDATE_AUTHORITY.canonicalRef} @ ${CANDIDATE_AUTHORITY.canonicalCommit}`,
      },
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
    ],
    raw: { candidate_authority: CANDIDATE_AUTHORITY, local_git: report.git?.main, local_track_portfolio: report.track_portfolio },
  };
}

export function buildLaneAdmissionInspect(): InspectItem {
  return {
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

export function productionVerdictTone(verdict: string): CockpitPanelDatum["tone"] {
  if (verdict === "KEEP_ACTIVE_PROD_HARDENING" || verdict === "SPLIT_BEFORE_CLOSE") return "danger";
  if (verdict === "CLOSE_READY_WITH_FOLLOWUP") return "warn";
  return "info";
}

export function productionVerdictToInspect(verdict: (typeof PRODUCTION_READINESS_VERDICTS)[number]): InspectItem {
  return {
    type: "track",
    title: verdict.trackId,
    subtitle: "Production readiness verdict; not checker SHIPPABLE",
    status: verdict.verdict,
    risk: verdict.verdict === "KEEP_ACTIVE_PROD_HARDENING" ? "Keep active until live production proof exists" : "Do not close without follow-up proof",
    nextAction: verdict.action,
    evidence: [
      {
        kind: "prod_readiness",
        source: "reports/governance/prod_readiness/PROD_READINESS_FINAL_CLOSEOUT_2026-06-23.json",
        path: "reports/governance/prod_readiness/PROD_READINESS_FINAL_CLOSEOUT_2026-06-23.json",
        detail: verdict.verdict,
      },
    ],
    raw: verdict,
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
