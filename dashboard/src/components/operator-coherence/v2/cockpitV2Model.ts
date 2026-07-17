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

export type CheckoutAuthorityCode =
  | "CLEAN_LOCAL_MAIN"
  | "DIVERGED_LOCAL_MAIN"
  | "CLEAN_LOCAL_BRANCH"
  | "DIRTY_LOCAL_CHECKOUT"
  | "CHECKOUT_STATE_UNAVAILABLE";

export interface CheckoutAuthorityDatum {
  code: CheckoutAuthorityCode;
  label: string;
  detail: string;
  tone: TruthTone;
  branch: string | null;
  head: string | null;
  dirtyCount: number | null;
  ahead: number | null;
  behind: number | null;
  activeCount: number;
  maxActive: number | null;
}

export type TrackLifecycleReviewCode =
  | "TRACK_ID_UNAVAILABLE"
  | "TRACK_ID_DUPLICATE"
  | "REFRESH_STALE_EVIDENCE"
  | "ADD_COMPLETION_EVIDENCE"
  | "STRENGTHEN_EVIDENCE"
  | "OPERATOR_CLOSURE_REVIEW"
  | "CONTINUE_ACTIVE_WORK";

export interface TrackLifecycleReviewDatum {
  rowKey: string;
  trackId: string;
  trackName: string;
  code: TrackLifecycleReviewCode;
  action: string;
  detail: string;
  tone: CockpitPanelDatum["tone"];
  reportedShippable: boolean;
  raw: OperatorCoherenceReport["track_portfolio"]["tracks"][number];
}

export interface BranchRiskProjection {
  total: number | null;
  localOnly: number | null;
  unpushed: number | null;
  orphaned: number | null;
  source: "branch_census" | "rogue_work_radar" | "mixed" | "contradictory" | "unavailable";
  conflicts: string[];
}

export type TrackLifecycleProjectionCode =
  | "TRACK_REVIEWS_AVAILABLE"
  | "TRACK_ROWS_INCONSISTENT"
  | "TRACK_SOURCE_UNAVAILABLE"
  | "NO_ACTIVE_TRACKS";

export interface TrackLifecycleProjectionSummary {
  code: TrackLifecycleProjectionCode;
  declaredActiveCount: number;
  renderedReviewCount: number;
  detail: string;
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

export const TRUTH_TAXONOMY: TruthBadgeDatum[] = [
  { code: "CLEAN_LOCAL_MAIN", label: "Clean local main", detail: "The observed local main checkout is clean; remote canonicality is not proven here.", tone: "ok" },
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
  if (value == null || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US").format(n);
}

function observedNonNegativeCount(...candidates: unknown[]): number | null {
  for (const value of candidates) {
    if (typeof value === "number" && Number.isFinite(value) && value >= 0) return value;
  }
  return null;
}

function hasSourceError(report: OperatorCoherenceReport, source: string): boolean {
  return report.source_errors.some((error) => error.source === source);
}

export function deriveBranchRiskProjection(report: OperatorCoherenceReport): BranchRiskProjection {
  if (hasSourceError(report, "git.for_each_ref")) {
    return {
      total: null,
      localOnly: null,
      unpushed: null,
      orphaned: null,
      source: "unavailable",
      conflicts: ["git.for_each_ref probe failed"],
    };
  }
  const census = report.branch_census;
  const radar = report.rogue_work_radar;
  const censusValues = [census?.total, census?.local_only, census?.unpushed_ahead, census?.orphaned_gone];
  const fallbackValues = [
    radar.local_branch_total,
    radar.local_only_branch_count,
    radar.unpushed_branch_count,
    radar.orphaned_branch_count,
  ];
  const usedCensus = censusValues.some((value) => observedNonNegativeCount(value) !== null);
  const usedFallback = censusValues.some(
    (value, index) => observedNonNegativeCount(value) === null && observedNonNegativeCount(fallbackValues[index]) !== null,
  );
  const conflicts: string[] = [];
  const resolve = (label: string, primary: unknown, fallback: unknown): number | null => {
    const primaryCount = observedNonNegativeCount(primary);
    const fallbackCount = observedNonNegativeCount(fallback);
    if (primaryCount !== null && fallbackCount !== null && primaryCount !== fallbackCount) {
      conflicts.push(`${label}: branch_census=${primaryCount}, rogue_work_radar=${fallbackCount}`);
      return null;
    }
    return primaryCount ?? fallbackCount;
  };
  return {
    total: resolve("total", census?.total, radar.local_branch_total),
    localOnly: resolve("local_only", census?.local_only, radar.local_only_branch_count),
    unpushed: resolve("unpushed", census?.unpushed_ahead, radar.unpushed_branch_count),
    orphaned: resolve("orphaned", census?.orphaned_gone, radar.orphaned_branch_count),
    source: conflicts.length
      ? "contradictory"
      : usedCensus && usedFallback
      ? "mixed"
      : usedCensus
        ? "branch_census"
        : usedFallback || fallbackValues.some((value) => observedNonNegativeCount(value) !== null)
          ? "rogue_work_radar"
          : "unavailable",
    conflicts,
  };
}

export function readinessTone(score: number): CockpitPanelDatum["tone"] {
  if (score >= 70) return "ok";
  if (score >= 40) return "warn";
  return "danger";
}

export function metricNeedsAttention(label: string, value: number, total: number, dangerAt: number): boolean {
  if (label === "Live" || label === "Branches") return false;
  return value / Math.max(1, total) >= dangerAt;
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

export function deriveCheckoutAuthority(report: OperatorCoherenceReport): CheckoutAuthorityDatum {
  const main = report.git?.main;
  const normalizeObservation = (value: unknown): string | null => {
    if (typeof value !== "string" || !value.trim()) return null;
    const normalized = value.trim();
    const lower = normalized.toLowerCase();
    if (
      ["unknown", "unavailable", "n/a", "none", "null", "head", "(no branch)", "detached"].includes(lower)
      || lower.startsWith("head (")
      || lower.includes("no branch")
    ) return null;
    return normalized;
  };
  const branch = normalizeObservation(main?.branch);
  const head = normalizeObservation(main?.head);
  const branchLine = typeof main?.branch_line === "string" ? main.branch_line.trim() : "";
  const branchLineBranch = branchLine.startsWith("## ")
    ? normalizeObservation(branchLine.slice(3).split("...", 1)[0].split(" [", 1)[0])
    : null;
  const upstreamObserved = branchLine.includes("...");
  const upstreamGone = branchLine.toLowerCase().includes("[gone]");
  const observedDirtyTotal = observedNonNegativeCount(main?.dirty_count);
  const trackedDirtyCount = observedNonNegativeCount(main?.tracked_dirty_count);
  const untrackedCount = observedNonNegativeCount(main?.untracked_count);
  const componentDirtyTotal = trackedDirtyCount !== null && untrackedCount !== null
    ? trackedDirtyCount + untrackedCount
    : null;
  const dirtyCount = observedDirtyTotal ?? componentDirtyTotal;
  const dirtyFlag = typeof main?.dirty === "boolean" ? main.dirty : null;
  const dirtyContradictions: string[] = [];
  if (observedDirtyTotal !== null && componentDirtyTotal !== null && observedDirtyTotal !== componentDirtyTotal) {
    dirtyContradictions.push(`dirty_count=${observedDirtyTotal} but tracked+untracked=${componentDirtyTotal}`);
  }
  if (dirtyCount !== null && dirtyFlag !== null && dirtyFlag !== (dirtyCount > 0)) {
    dirtyContradictions.push(`dirty=${dirtyFlag} but numeric dirty total=${dirtyCount}`);
  }
  if (observedDirtyTotal !== null && trackedDirtyCount !== null && trackedDirtyCount > observedDirtyTotal) {
    dirtyContradictions.push(`tracked_dirty_count=${trackedDirtyCount} exceeds dirty_count=${observedDirtyTotal}`);
  }
  if (observedDirtyTotal !== null && untrackedCount !== null && untrackedCount > observedDirtyTotal) {
    dirtyContradictions.push(`untracked_count=${untrackedCount} exceeds dirty_count=${observedDirtyTotal}`);
  }
  const ahead = observedNonNegativeCount(main?.ahead);
  const behind = observedNonNegativeCount(main?.behind);
  const maxActive = observedNonNegativeCount(report.track_portfolio.policy?.max_active);
  const shared = {
    branch,
    head,
    dirtyCount,
    ahead,
    behind,
    activeCount: report.track_portfolio.active_count,
    maxActive,
  };
  const unavailable = (detail: string): CheckoutAuthorityDatum => ({
    ...shared,
    code: "CHECKOUT_STATE_UNAVAILABLE",
    label: "Checkout state unavailable",
    detail,
    tone: "muted",
  });

  if (hasSourceError(report, "git.status")) {
    return unavailable(
      "git.status probe failed; no checkout authority claim is safe.",
    );
  }
  if (!head) {
    return unavailable("HEAD evidence is missing or carries an unavailable sentinel; no checkout authority claim is safe.");
  }
  if (dirtyContradictions.length) {
    return unavailable(`Dirty-state evidence is contradictory (${dirtyContradictions.join("; ")}); no clean-checkout authority claim is safe.`);
  }
  if (dirtyCount === null) {
    const knownDirtySignal = dirtyFlag === true || (trackedDirtyCount ?? 0) > 0 || (untrackedCount ?? 0) > 0;
    return unavailable(knownDirtySignal
      ? "Dirty-state evidence indicates local changes, but an exact reconciled dirty count is unavailable; no clean-checkout authority claim is safe."
      : "Dirty-count evidence is missing or carries an unavailable sentinel; no checkout authority claim is safe.");
  }
  if (dirtyCount > 0) {
    return {
      ...shared,
      code: "DIRTY_LOCAL_CHECKOUT",
      label: "Dirty local checkout",
      detail: `${dirtyCount} local path${dirtyCount === 1 ? "" : "s"} differ from HEAD; preserve or extract them before promotion.`,
      tone: "danger",
    };
  }
  if (!branch) {
    return unavailable("Branch evidence is missing or carries an unavailable sentinel; no clean-checkout authority claim is safe.");
  }
  if (branchLine && !branchLineBranch) {
    return unavailable("The observed branch status line is malformed or unavailable; no clean-checkout authority claim is safe.");
  }
  if (branchLineBranch && branchLineBranch !== branch) {
    return unavailable(
      `Branch evidence is contradictory (branch=${branch} but branch status reports ${branchLineBranch}); no clean-checkout authority claim is safe.`,
    );
  }
  if (branch === "main") {
    if (upstreamGone) {
      return unavailable("The observed upstream for local main is gone; alignment is not established.");
    }
    if (!upstreamObserved) {
      return unavailable("The local main checkout is clean, but no upstream relation is present in the observed branch status; alignment is not established.");
    }
    if (ahead === null || behind === null) {
      return unavailable("The local main checkout is clean, but ahead/behind evidence is unavailable; upstream alignment is not established.");
    }
    const branchLineAhead = Number(main?.branch_line?.match(/\bahead\s+(\d+)/i)?.[1] ?? 0);
    const branchLineBehind = Number(main?.branch_line?.match(/\bbehind\s+(\d+)/i)?.[1] ?? 0);
    if (ahead !== branchLineAhead || behind !== branchLineBehind) {
      return unavailable(
        `Numeric ahead/behind evidence (${ahead}/${behind}) contradicts the observed branch status (${branchLineAhead}/${branchLineBehind}); alignment is not established.`,
      );
    }
    if (ahead > 0 || behind > 0) {
      return {
        ...shared,
        code: "DIVERGED_LOCAL_MAIN",
        label: "Diverged local main",
        detail: `The observed local main is ahead ${ahead} and behind ${behind}; reconcile it before any clean-main promotion claim.`,
        tone: "warn",
      };
    }
    return {
      ...shared,
      code: "CLEAN_LOCAL_MAIN",
      label: "Clean local main",
      detail: "The observed local main is clean and reports no ahead/behind divergence. This does not prove remote freshness; verify the fetched origin/main identity separately.",
      tone: "ok",
    };
  }
  return {
    ...shared,
    code: "CLEAN_LOCAL_BRANCH",
    label: "Clean local branch",
    detail: "The observed branch checkout is clean. Review its upstream and diff before any promotion or canonical claim.",
    tone: "info",
  };
}

export function buildAuthorityInspect(report: OperatorCoherenceReport): InspectItem {
  const authority = deriveCheckoutAuthority(report);
  const shortHead = authority.head?.slice(0, 12) ?? "unknown";
  const branch = authority.branch ?? "unknown";
  const portfolio = `${authority.activeCount}/${authority.maxActive ?? "?"} active`;
  const nextAction = authority.code === "DIRTY_LOCAL_CHECKOUT"
    ? "Preserve or extract local changes, then refresh the report before promotion."
    : authority.code === "DIVERGED_LOCAL_MAIN"
      ? "Reconcile local main with its fetched upstream, then refresh the report."
      : authority.code === "CLEAN_LOCAL_MAIN"
        ? "Treat this as aligned local-main evidence only; verify fetched origin/main freshness separately before a canonical claim."
        : authority.code === "CLEAN_LOCAL_BRANCH"
          ? "Review upstream, ahead/behind state, and branch diff before promotion."
          : "Restore complete git observation and refresh the report before acting on checkout authority.";
  return {
    type: "panel",
    title: "Observed checkout authority",
    subtitle: `${authority.code} · ${branch}`,
    status: `${portfolio} · HEAD ${shortHead}`,
    risk: authority.detail,
    nextAction,
    evidence: [
      {
        kind: "git",
        source: "report.git.main",
        detail: `${report.git?.main?.branch_line ?? branch}; head=${shortHead}; dirty_count=${authority.dirtyCount ?? "unknown"}; ahead=${authority.ahead ?? "unknown"}; behind=${authority.behind ?? "unknown"}`,
      },
      {
        kind: "track_portfolio",
        source: "report.track_portfolio",
        detail: `active_count=${authority.activeCount}, max_active=${authority.maxActive ?? "unknown"}`,
      },
    ],
    raw: { checkout_authority: authority, local_git: report.git?.main, track_portfolio: report.track_portfolio },
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

export function buildTrackLifecycleReviews(report: OperatorCoherenceReport): TrackLifecycleReviewDatum[] {
  if (hasSourceError(report, "docs/governance/ACTIVE_TRACK.yaml")) return [];
  const activeTracks = report.track_portfolio.tracks.filter((track) => track.lifecycle === "active");
  const observedIds = activeTracks.map((track) => (
    typeof track.id === "string" && track.id.trim() ? track.id.trim() : null
  ));
  const idCounts = observedIds.reduce<Map<string, number>>((counts, trackId) => {
    if (trackId) counts.set(trackId, (counts.get(trackId) ?? 0) + 1);
    return counts;
  }, new Map());
  return activeTracks
    .map((track, index) => {
      const observedId = observedIds[index];
      const observedName = typeof track.name === "string" && track.name.trim() ? track.name.trim() : null;
      const trackId = observedId ?? `unidentified-active-row-${index + 1}`;
      const rowKey = observedId && idCounts.get(observedId) === 1
        ? observedId
        : `${trackId}::row-${index + 1}`;
      const trackName = observedName ?? observedId ?? `Unidentified active track row ${index + 1}`;
      const shared = { rowKey, trackId, trackName, reportedShippable: track.shippable === true, raw: track };
      if (!observedId) {
        return {
          ...shared,
          code: "TRACK_ID_UNAVAILABLE",
          action: "Restore the canonical track identifier before lifecycle review or promotion.",
          detail: "The report emitted an active lifecycle row without a track ID; the row cannot be bound to portfolio authority.",
          tone: "danger",
        };
      }
      if ((idCounts.get(observedId) ?? 0) > 1) {
        return {
          ...shared,
          code: "TRACK_ID_DUPLICATE",
          action: "Repair duplicate track identifiers before lifecycle review or promotion.",
          detail: `The report emitted ${idCounts.get(observedId)} active lifecycle rows with ID ${observedId}; none can be bound uniquely to portfolio authority.`,
          tone: "danger",
        };
      }
      if (track.stale) {
        return {
          ...shared,
          code: "REFRESH_STALE_EVIDENCE",
          action: "Refresh the expired evidence and re-run lifecycle checks before considering closure.",
          detail: "The active track's verification window is stale.",
          tone: "danger",
        };
      }
      if (!track.evidence_present) {
        return {
          ...shared,
          code: "ADD_COMPLETION_EVIDENCE",
          action: "Attach completion evidence that exercises the declared criteria.",
          detail: "The active-track declaration has no matching generated evidence row.",
          tone: "danger",
        };
      }
      if (!track.has_rigorous_evidence) {
        return {
          ...shared,
          code: "STRENGTHEN_EVIDENCE",
          action: "Replace existence-only signals with behavioral proof before lifecycle promotion.",
          detail: track.readiness_capped
            ? "Displayed readiness is capped because the evidence is not rigorous."
            : "Evidence exists, but it is not classified as rigorous behavioral proof.",
          tone: "warn",
        };
      }
      if (track.shippable === true) {
        return {
          ...shared,
          code: "OPERATOR_CLOSURE_REVIEW",
          action: "Review closure kind, claim boundary, unresolved obligations, and any explicit production proof before closing.",
          detail: "The live report marks this active track SHIPPABLE. That may reflect declared lifecycle state or generated checks; independently verify completion evidence before closure. It is not production proof.",
          tone: "info",
        };
      }
      return {
        ...shared,
        code: "CONTINUE_ACTIVE_WORK",
        action: "Continue the declared next items and keep evidence current.",
        detail: `Active lifecycle status: ${asText(track.status)}; checker readiness ${asText(track.readiness)}%.`,
        tone: "info",
      };
    });
}

export function summarizeTrackLifecycleProjection(
  report: OperatorCoherenceReport,
  reviews: TrackLifecycleReviewDatum[] = buildTrackLifecycleReviews(report),
): TrackLifecycleProjectionSummary {
  const declaredActiveCount = observedNonNegativeCount(report.track_portfolio.active_count) ?? 0;
  const renderedReviewCount = reviews.length;
  if (hasSourceError(report, "docs/governance/ACTIVE_TRACK.yaml")) {
    return {
      code: "TRACK_SOURCE_UNAVAILABLE",
      declaredActiveCount,
      renderedReviewCount,
      detail: "The ACTIVE_TRACK governance probe failed; lifecycle rows and active counts are unavailable and must not be treated as an empty portfolio.",
    };
  }
  if (declaredActiveCount === 0 && renderedReviewCount === 0) {
    return {
      code: "NO_ACTIVE_TRACKS",
      declaredActiveCount,
      renderedReviewCount,
      detail: "No active tracks are present in the live portfolio projection.",
    };
  }
  if (declaredActiveCount !== renderedReviewCount) {
    return {
      code: "TRACK_ROWS_INCONSISTENT",
      declaredActiveCount,
      renderedReviewCount,
      detail: `Lifecycle rows are incomplete or contradictory: the portfolio declares ${declaredActiveCount} active track${declaredActiveCount === 1 ? "" : "s"}, but ${renderedReviewCount} active row${renderedReviewCount === 1 ? " is" : "s are"} available. Refresh the report before lifecycle claims.`,
    };
  }
  return {
    code: "TRACK_REVIEWS_AVAILABLE",
    declaredActiveCount,
    renderedReviewCount,
    detail: `${renderedReviewCount} active lifecycle review row${renderedReviewCount === 1 ? "" : "s"} available.`,
  };
}

export function trackLifecycleReviewToInspect(review: TrackLifecycleReviewDatum): InspectItem {
  return {
    type: "track",
    title: review.trackName,
    subtitle: `${review.trackId} · active-track lifecycle review`,
    status: review.code,
    risk: review.detail,
    nextAction: review.action,
    evidence: [
      {
        kind: "track_lifecycle",
        source: "report.track_portfolio.tracks",
        detail: `${review.code}; reported_shippable=${review.reportedShippable}`,
      },
    ],
    raw: review.raw,
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
  const branchRisk = deriveBranchRiskProjection(report);
  const runtime = report.readiness.categories.runtime_telemetry_liveness;
  const preservation = report.readiness.categories.preservation_safety;
  const needsDecision = report.kanban.find((lane) => lane.lane === "Needs Decision")?.count ?? 0;
  const needsRepair = report.kanban.find((lane) => lane.lane === "Needs Repair")?.count ?? 0;

  return [
    {
      id: "readiness",
      eyebrow: "Heuristic projection",
      title: "Evidence coherence",
      value: `${report.readiness.score}%`,
      detail: `Heuristic evidence score · ${report.readiness.interpretation}`,
      tone: readinessTone(report.readiness.score),
      inspect: {
        type: "panel",
        title: "Evidence coherence",
        subtitle: "Weighted heuristic from 8 evidence categories; not a production-readiness verdict",
        status: String(report.readiness.score),
        risk: "This score is a projection, not production proof.",
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
      value: sourceControl ? `${sourceControl.score}%` : "—",
      detail: `${formatCount(branchRisk.total)} branches · ${report.rogue_work_radar.stash_count} stashes · ${branchRisk.source.replaceAll("_", " ")}${branchRisk.conflicts.length ? ` · ${branchRisk.conflicts.join("; ")}` : ""}`,
      tone: sourceControl ? readinessTone(sourceControl.score) : "muted",
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
