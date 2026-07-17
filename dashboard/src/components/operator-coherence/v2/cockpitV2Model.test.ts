import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  DESIGN_SOURCES,
  LANE_ADMISSION_FIELDS,
  MODES,
  TRUTH_TAXONOMY,
  actionToInspect,
  buildAuthorityInspect,
  buildHandoff,
  buildLaneAdmissionInspect,
  buildTrackLifecycleReviews,
  buildTopPanels,
  cardFacetBadges,
  cardToInspect,
  classifyCardTruth,
  deriveBranchRiskProjection,
  deriveCheckoutAuthority,
  filterCards,
  formatCount,
  humanKind,
  humanRisk,
  metricNeedsAttention,
  modeMatches,
  readinessTone,
  sourceToInspect,
  summarizeTrackLifecycleProjection,
} from "./cockpitV2Model.ts";

function card(overrides: Record<string, unknown> = {}) {
  return {
    kind: "branch",
    id: "branch:demo",
    title: "branch demo (ahead 3)",
    status: "ahead_of_origin",
    lane: "Needs Decision",
    track: "unknown",
    branch: "demo",
    pr: "",
    risk: "unpushed_commits",
    next_action: "push local commits or declare why local",
    decision_type: "operator_decision",
    evidence: [{ kind: "git", source: "git for-each-ref refs/heads", detail: "demo upstream=none" }],
    facets: {
      tracked: false,
      live: false,
      stale: false,
      preserved: false,
      intentional: false,
      rogue: true,
      local_only: true,
      origin_backed: false,
      operator_decision: true,
    },
    ...overrides,
  } as Parameters<typeof cardToInspect>[0];
}

function report() {
  return {
    schema_version: "operator_coherence_cockpit.v0.1",
    generated_at: "2026-06-23T00:00:00+00:00",
    repo_root: "/repo",
    source_errors: [],
    executive: {
      health: "mixed",
      prod_readiness_estimate: 41.5,
      top_blockers: [],
      next_3_actions: [
        {
          title: "11 worktrees at preservation risk",
          kind: "preservation_risk",
          risk: "local_unpreserved_work",
          next_action: "push, PR, receipt, or preserve",
          evidence: [{ kind: "git", source: "git worktree/status", detail: "11 at risk" }],
        },
      ],
    },
    readiness: {
      score: 41.5,
      interpretation: "computed projection; not a final truth claim",
      weights: {},
      categories: {
        source_control_coherence: { score: 0, weight: 0.2, why: "207 branches, 70 stashes" },
        runtime_telemetry_liveness: { score: 5, weight: 0.15, why: "4/17 live" },
        preservation_safety: { score: 10, weight: 0.1, why: "11 worktrees at risk" },
      },
    },
    kanban: [
      { lane: "Needs Decision", count: 53, cards: [] },
      { lane: "Needs Repair", count: 41, cards: [] },
    ],
    cards: [
      card(),
      card({ id: "live:1", kind: "live_ops_surface", title: "Dharma daemon — stale", risk: "stale_liveness_claim", lane: "Needs Repair", branch: "" }),
      card({ id: "track:1", kind: "track", title: "Runtime Truth Reconciliation", risk: "stale_claim", lane: "Needs Repair", branch: "" }),
    ],
    track_portfolio: { active_count: 10, closed_count: 4, policy: { max_active: 10 }, tracks: [], proposed_tracks: [], broken_register: {} },
    rogue_work_radar: {
      cards: [],
      dirty_worktree_count: 8,
      local_only_count: 6,
      stash_count: 70,
      local_branch_total: 207,
      local_only_branch_count: 107,
      unpushed_branch_count: 40,
      orphaned_branch_count: 55,
    },
    agent_terminal_census: {},
    branch_census: { total: 207, local_only: 107, unpushed_ahead: 40, orphaned_gone: 55, stale: 87 },
    git: { main: { branch: "main", branch_line: "## main...origin/main", head: "0123456789abcdef0123456789abcdef01234567", dirty_count: 0, ahead: 0, behind: 0 } },
    live_ops: { enabled: true, summary: { total: 17, by_status: { live: 4, stale: 2, blocked: 2, stopped: 9 } } },
    onboarding: { status: "wired", target: "make onboard" },
    runtime_receipts: { runtime_dbs: [], receipt_count: 19, recent_receipts: [] },
    operator_surfaces: { surfaces: [], abandoned_dashboard_candidates: [] },
    preservation_ledger: { at_risk_worktree_count: 11 },
    pr_ci_triage: { enabled: false, reason: "gh_auth_unavailable" },
    definition_answers: {},
  } as Parameters<typeof buildTopPanels>[0];
}

test("MODES exposes the eight operator board lenses", () => {
  const ids = MODES.map((m) => m.id);
  for (const expected of ["overview", "triage", "git", "runtime", "tracks", "preservation", "evidence", "design"]) {
    assert.ok(ids.includes(expected as (typeof ids)[number]), `missing mode ${expected}`);
  }
});

test("DESIGN_SOURCES references the Desktop canon and inspiration packet", () => {
  const paths = DESIGN_SOURCES.map((s) => s.path).join("\n");
  assert.match(paths, /MANDALA_MISSION_CONTROL_CANON\.md/);
  assert.match(paths, /grafana new\.jpeg/);
  assert.match(paths, /proto_1_atlas_board\.png/);
  assert.match(paths, /COCKPIT_V2_DESKTOP_SOURCE_MANIFEST\.md/);
  assert.ok(DESIGN_SOURCES.length >= 6, "expected the full design source board");
});

test("buildTopPanels yields six evidence-backed stat panels with inspect payloads", () => {
  const panels = buildTopPanels(report());
  assert.equal(panels.length, 6);
  const ids = panels.map((p) => p.id);
  for (const expected of ["readiness", "source-control", "runtime", "needs-action", "preservation", "receipts"]) {
    assert.ok(ids.includes(expected), `missing panel ${expected}`);
  }
  const readiness = panels.find((p) => p.id === "readiness");
  assert.ok(readiness, "readiness panel present");
  assert.equal(readiness?.value, "41.5%");
  assert.equal(readiness?.title, "Evidence coherence");
  assert.equal(readiness?.inspect.title, "Evidence coherence");
  assert.doesNotMatch(`${readiness?.title} ${readiness?.inspect.title}`, /prod(?:uction)? readiness/i);
  assert.ok((readiness?.inspect.evidence ?? []).length >= 3, "readiness inspect carries category evidence");
});

test("filterCards honors mode scoping and free-text search", () => {
  const cards = report().cards;
  // git mode keeps branch/worktree/dirty/stash kinds only
  const git = filterCards(cards, "git", "");
  assert.ok(git.every((c) => ["branch", "worktree", "dirty_files", "stash"].includes(c.kind)));
  // runtime mode keeps live_ops surface
  const runtime = filterCards(cards, "runtime", "");
  assert.ok(runtime.some((c) => c.kind === "live_ops_surface"));
  // evidence mode shows everything
  assert.equal(filterCards(cards, "evidence", "").length, cards.length);
  // search narrows by text across fields
  const searched = filterCards(cards, "evidence", "reconciliation");
  assert.equal(searched.length, 1);
  assert.equal(searched[0].kind, "track");
});

test("modeMatches routes triage to operator-decision/needs lanes", () => {
  assert.equal(modeMatches(card({ lane: "Needs Repair" }), "triage"), true);
  assert.equal(modeMatches(card({ lane: "Verified", facets: { ...card().facets, operator_decision: false } }), "triage"), false);
});

test("drilldown converts cards/actions/sources into inspect items with evidence", () => {
  const c = cardToInspect(card());
  assert.equal(c.type, "card");
  assert.ok(c.evidence && c.evidence.length >= 1, "card inspect keeps evidence link");
  const a = actionToInspect(report().executive.next_3_actions[0]);
  assert.equal(a.type, "action");
  assert.equal(a.risk, humanRisk("local_unpreserved_work"));
  const s = sourceToInspect(DESIGN_SOURCES[0]);
  assert.equal(s.type, "source");
  assert.ok(s.evidence && s.evidence[0]?.path?.includes("MANDALA"), "source inspect links the design file");
});

test("buildHandoff produces a safe scoped agent prompt", () => {
  const handoff = buildHandoff(cardToInspect(card()));
  assert.match(handoff, /make onboard/);
  assert.match(handoff, /Do not reset\/stash\/delete/);
  assert.match(handoff, /Evidence:/);
});

test("human labels and readiness tone are operator-friendly", () => {
  assert.equal(humanRisk("local_only_branch"), "Local-only branch");
  assert.equal(humanKind("live_ops_surface"), "Live ops surface");
  assert.equal(readinessTone(80), "ok");
  assert.equal(readinessTone(50), "warn");
  assert.equal(readinessTone(20), "danger");
  assert.equal(metricNeedsAttention("Branches", 207, 207, 0.3), false);
  assert.equal(metricNeedsAttention("Live", 4, 17, 0.3), false);
  assert.equal(metricNeedsAttention("Local-only", 4, 10, 0.3), true);
  assert.equal(formatCount(null), "—");
});

test("truth taxonomy and facet badges distinguish candidate/live/stale/local state", () => {
  assert.ok(TRUTH_TAXONOMY.some((truth) => truth.code === "DIRTY_LOCAL_CANDIDATE"));
  assert.ok(TRUTH_TAXONOMY.some((truth) => truth.code === "CLEAN_LOCAL_MAIN"));
  assert.equal(classifyCardTruth(card()).code, "LOCAL_ONLY_BRANCH");
  assert.equal(classifyCardTruth(card({ facets: { ...card().facets, local_only: false, live: true } })).code, "LIVE_RUNTIME_PROOF");
  assert.equal(classifyCardTruth(card({ facets: { ...card().facets, local_only: false, stale: true } })).code, "STALE_RECEIPT");
  const badges = cardFacetBadges(card());
  for (const expected of ["untracked", "not preserved", "rogue", "local-only", "operator decision"]) {
    assert.ok(badges.includes(expected), `missing facet badge ${expected}`);
  }
});

test("checkout authority classifies a clean local main without claiming remote canonicality", () => {
  const authority = deriveCheckoutAuthority(report());
  assert.equal(authority.code, "CLEAN_LOCAL_MAIN");
  assert.equal(authority.head, "0123456789abcdef0123456789abcdef01234567");
  assert.equal(authority.dirtyCount, 0);
  assert.equal(authority.maxActive, 10);
  assert.match(authority.detail, /does not prove remote freshness/);

  const inspect = buildAuthorityInspect(report());
  assert.equal(inspect.status, "10/10 active · HEAD 0123456789ab");
  assert.match(inspect.subtitle ?? "", /CLEAN_LOCAL_MAIN/);
  assert.match(inspect.nextAction ?? "", /verify fetched origin\/main freshness separately/);
});

test("checkout authority classifies a clean non-main branch", () => {
  const cleanBranch = report();
  cleanBranch.git = { main: { branch: "agent/titanium", head: "abc123", dirty_count: 0, ahead: 0, behind: 0 } };
  assert.equal(deriveCheckoutAuthority(cleanBranch).code, "CLEAN_LOCAL_BRANCH");
});

test("checkout authority classifies a dirty observation", () => {
  const dirty = report();
  dirty.git = { main: { branch: "main", head: "abc123", dirty_count: 3, ahead: 0, behind: 0 } };
  assert.equal(deriveCheckoutAuthority(dirty).code, "DIRTY_LOCAL_CHECKOUT");
  assert.match(deriveCheckoutAuthority(dirty).detail, /3 local paths/);
});

test("checkout authority classifies incomplete git evidence as unavailable", () => {
  const unavailable = report();
  unavailable.git = { main: { branch: "main", dirty_count: 0 } };
  assert.equal(deriveCheckoutAuthority(unavailable).code, "CHECKOUT_STATE_UNAVAILABLE");

  const legacyBooleanOnly = report();
  legacyBooleanOnly.git = { main: { branch: "main", branch_line: "## main...origin/main", head: "abc123", dirty: true, ahead: 0, behind: 0 } };
  assert.equal(deriveCheckoutAuthority(legacyBooleanOnly).code, "CHECKOUT_STATE_UNAVAILABLE");
});

test("checkout authority fails closed on contradictory dirty signals", () => {
  const booleanConflict = report();
  booleanConflict.git = {
    main: {
      branch: "main",
      branch_line: "## main...origin/main",
      head: "abc123",
      dirty_count: 0,
      tracked_dirty_count: 0,
      untracked_count: 0,
      dirty: true,
      ahead: 0,
      behind: 0,
    },
  };
  assert.equal(deriveCheckoutAuthority(booleanConflict).code, "CHECKOUT_STATE_UNAVAILABLE");
  assert.match(deriveCheckoutAuthority(booleanConflict).detail, /Dirty-state evidence is contradictory/);

  const componentConflict = report();
  componentConflict.git = {
    main: {
      branch: "main",
      branch_line: "## main...origin/main",
      head: "abc123",
      dirty_count: 0,
      tracked_dirty_count: 2,
      untracked_count: 0,
      ahead: 0,
      behind: 0,
    },
  };
  assert.equal(deriveCheckoutAuthority(componentConflict).code, "CHECKOUT_STATE_UNAVAILABLE");
});

test("checkout authority treats producer sentinel values as unavailable", () => {
  const unavailable = report();
  unavailable.git = { main: { branch: "unknown", branch_line: "unknown", head: "abc123", dirty_count: 0, ahead: 0, behind: 0 } };
  assert.equal(deriveCheckoutAuthority(unavailable).code, "CHECKOUT_STATE_UNAVAILABLE");

  const detached = report();
  detached.git = { main: { branch: "HEAD (no branch)", branch_line: "## HEAD (no branch)", head: "abc123", dirty_count: 0, ahead: 0, behind: 0 } };
  assert.equal(deriveCheckoutAuthority(detached).code, "CHECKOUT_STATE_UNAVAILABLE");

  const dirtyDetached = report();
  dirtyDetached.git = { main: { branch: "HEAD (no branch)", branch_line: "## HEAD (no branch)", head: "abc123", dirty_count: 2, ahead: 0, behind: 0 } };
  assert.equal(deriveCheckoutAuthority(dirtyDetached).code, "DIRTY_LOCAL_CHECKOUT");

  const noUpstream = report();
  noUpstream.git = { main: { branch: "main", branch_line: "## main", head: "abc123", dirty_count: 0, ahead: 0, behind: 0 } };
  assert.equal(deriveCheckoutAuthority(noUpstream).code, "CHECKOUT_STATE_UNAVAILABLE");

  const goneUpstream = report();
  goneUpstream.git = { main: { branch: "main", branch_line: "## main...origin/main [gone]", head: "abc123", dirty_count: 0, ahead: 0, behind: 0 } };
  assert.equal(deriveCheckoutAuthority(goneUpstream).code, "CHECKOUT_STATE_UNAVAILABLE");
});

test("checkout authority exposes diverged local main without a clean-main claim", () => {
  const diverged = report();
  diverged.git = { main: { branch: "main", branch_line: "## main...origin/main [ahead 2, behind 1]", head: "abc123", dirty_count: 0, ahead: 2, behind: 1 } };
  const authority = deriveCheckoutAuthority(diverged);
  assert.equal(authority.code, "DIVERGED_LOCAL_MAIN");
  assert.match(authority.detail, /ahead 2.*behind 1/);
});

test("checkout authority fails closed when branch-line and numeric divergence disagree", () => {
  const contradictory = report();
  contradictory.git = {
    main: {
      branch: "main",
      branch_line: "## main...origin/main [ahead 2]",
      head: "abc123",
      dirty_count: 0,
      ahead: 0,
      behind: 0,
    },
  };
  const authority = deriveCheckoutAuthority(contradictory);
  assert.equal(authority.code, "CHECKOUT_STATE_UNAVAILABLE");
  assert.match(authority.detail, /contradicts the observed branch status/);
});

test("checkout authority fails closed when branch field and branch status disagree", () => {
  const contradictory = report();
  contradictory.git = {
    main: {
      branch: "main",
      branch_line: "## feature/titanium...origin/feature/titanium",
      head: "abc123",
      dirty_count: 0,
      ahead: 0,
      behind: 0,
    },
  };
  const authority = deriveCheckoutAuthority(contradictory);
  assert.equal(authority.code, "CHECKOUT_STATE_UNAVAILABLE");
  assert.match(authority.detail, /branch=main but branch status reports feature\/titanium/);
});

test("checkout authority fails closed when the git.status probe reports a source error", () => {
  const probeFailure = report();
  probeFailure.source_errors = [{ source: "git.status", error: "probe failed" }];
  const authority = deriveCheckoutAuthority(probeFailure);
  assert.equal(authority.code, "CHECKOUT_STATE_UNAVAILABLE");
  assert.notEqual(authority.code, "CLEAN_LOCAL_MAIN");
  assert.match(authority.detail, /git\.status probe failed/);

  const sameEvidenceWithoutError = report();
  assert.equal(deriveCheckoutAuthority(sameEvidenceWithoutError).code, "CLEAN_LOCAL_MAIN");
});

test("branch-risk projection uses producer fallbacks for partial census reports", () => {
  const partial = report();
  partial.branch_census = { total: 207 };
  partial.rogue_work_radar.local_only_branch_count = 91;
  partial.rogue_work_radar.unpushed_branch_count = 31;
  partial.rogue_work_radar.orphaned_branch_count = 17;
  const projection = deriveBranchRiskProjection(partial);
  assert.deepEqual(projection, {
    total: 207,
    localOnly: 91,
    unpushed: 31,
    orphaned: 17,
    source: "mixed",
    conflicts: [],
  });

  const fallbackOnly = report();
  fallbackOnly.branch_census = undefined;
  assert.equal(deriveBranchRiskProjection(fallbackOnly).source, "rogue_work_radar");
  assert.equal(deriveBranchRiskProjection(fallbackOnly).total, 207);
});

test("branch-risk projection fails closed on probe errors and duplicated-count conflicts", () => {
  const probeFailure = report();
  probeFailure.source_errors = [{ source: "git.for_each_ref", error: "probe failed" }];
  const unavailable = deriveBranchRiskProjection(probeFailure);
  assert.equal(unavailable.source, "unavailable");
  assert.equal(unavailable.total, null);
  assert.match(unavailable.conflicts[0], /probe failed/);

  const contradictory = report();
  contradictory.branch_census = { total: 207, local_only: 0, unpushed_ahead: 40, orphaned_gone: 55 };
  contradictory.rogue_work_radar.local_only_branch_count = 91;
  const projection = deriveBranchRiskProjection(contradictory);
  assert.equal(projection.source, "contradictory");
  assert.equal(projection.localOnly, null);
  assert.match(projection.conflicts[0], /branch_census=0.*rogue_work_radar=91/);
});

test("authority projection follows live portfolio counts", () => {
  const changed = report();
  changed.track_portfolio.active_count = 6;
  changed.track_portfolio.policy = { max_active: 12 };
  const inspect = buildAuthorityInspect(changed);
  assert.equal(inspect.status, "6/12 active · HEAD 0123456789ab");
});

test("active-track lifecycle review is live-data driven and SHIPPABLE is not production readiness", () => {
  const liveReport = report();
  liveReport.track_portfolio.tracks = [
    {
      id: "live-shippable-track",
      name: "Live shippable track",
      lifecycle: "active",
      status: "shippable",
      shippable: true,
      evidence_present: true,
      has_rigorous_evidence: true,
      readiness: 100,
    },
    {
      id: "live-stale-track",
      name: "Live stale track",
      lifecycle: "active",
      status: "active",
      stale: true,
      evidence_present: true,
      has_rigorous_evidence: true,
    },
    { id: "closed-history", name: "Closed history", lifecycle: "closed", status: "retired" },
  ];

  const reviews = buildTrackLifecycleReviews(liveReport);
  assert.deepEqual(reviews.map((review) => review.trackId), ["live-shippable-track", "live-stale-track"]);
  assert.equal(reviews[0].code, "OPERATOR_CLOSURE_REVIEW");
  assert.match(reviews[0].detail, /may reflect declared lifecycle state or generated checks/);
  assert.doesNotMatch(reviews[0].detail, /completion criteria pass/);
  assert.equal(reviews[0].reportedShippable, true);
  assert.equal(reviews[1].code, "REFRESH_STALE_EVIDENCE");
});

test("track lifecycle review only honors boolean-true SHIPPABLE evidence", () => {
  const stringShippable = report();
  stringShippable.track_portfolio.active_count = 1;
  stringShippable.track_portfolio.tracks = [
    {
      id: "string-shippable-track",
      name: "String shippable track",
      lifecycle: "active",
      status: "active",
      shippable: "false" as unknown as boolean,
      evidence_present: true,
      has_rigorous_evidence: true,
    },
  ];
  const reviews = buildTrackLifecycleReviews(stringShippable);
  assert.equal(reviews.length, 1);
  assert.notEqual(reviews[0].code, "OPERATOR_CLOSURE_REVIEW");
  assert.equal(reviews[0].code, "CONTINUE_ACTIVE_WORK");
  assert.equal(reviews[0].reportedShippable, false);
});

test("active-track lifecycle projection exposes missing rows and missing identities", () => {
  const missingRows = report();
  const missingSummary = summarizeTrackLifecycleProjection(missingRows);
  assert.equal(missingSummary.code, "TRACK_ROWS_INCONSISTENT");
  assert.match(missingSummary.detail, /declares 10 active tracks.*0 active rows/);

  const noActive = report();
  noActive.track_portfolio.active_count = 0;
  assert.equal(summarizeTrackLifecycleProjection(noActive).code, "NO_ACTIVE_TRACKS");

  const sourceFailure = report();
  sourceFailure.track_portfolio.active_count = 1;
  sourceFailure.track_portfolio.tracks = [
    {
      id: "residual-shippable-row",
      name: "Residual shippable row",
      lifecycle: "active",
      status: "shippable",
      shippable: true,
      evidence_present: true,
      has_rigorous_evidence: true,
    },
  ];
  sourceFailure.source_errors = [{ source: "docs/governance/ACTIVE_TRACK.yaml", error: "probe failed" }];
  const sourceFailureReviews = buildTrackLifecycleReviews(sourceFailure);
  assert.deepEqual(sourceFailureReviews, []);
  const sourceFailureSummary = summarizeTrackLifecycleProjection(sourceFailure, sourceFailureReviews);
  assert.equal(sourceFailureSummary.code, "TRACK_SOURCE_UNAVAILABLE");
  assert.equal(sourceFailureSummary.renderedReviewCount, 0);

  const missingIds = report();
  missingIds.track_portfolio.active_count = 2;
  missingIds.track_portfolio.tracks = [
    { lifecycle: "active", name: "Unbound A" },
    { lifecycle: "active", name: "Unbound B" },
  ];
  const reviews = buildTrackLifecycleReviews(missingIds);
  assert.equal(summarizeTrackLifecycleProjection(missingIds, reviews).code, "TRACK_REVIEWS_AVAILABLE");
  assert.deepEqual(reviews.map((review) => review.code), ["TRACK_ID_UNAVAILABLE", "TRACK_ID_UNAVAILABLE"]);
  assert.equal(new Set(reviews.map((review) => review.trackId)).size, 2);

  const duplicateIds = report();
  duplicateIds.track_portfolio.active_count = 2;
  duplicateIds.track_portfolio.tracks = [
    { id: "duplicate", lifecycle: "active", name: "Duplicate A" },
    { id: "duplicate", lifecycle: "active", name: "Duplicate B" },
  ];
  const duplicateReviews = buildTrackLifecycleReviews(duplicateIds);
  assert.deepEqual(duplicateReviews.map((review) => review.code), ["TRACK_ID_DUPLICATE", "TRACK_ID_DUPLICATE"]);
  assert.equal(new Set(duplicateReviews.map((review) => review.rowKey)).size, 2);
});

test("cockpit sources do not retain the stale June authority or verdict constants", () => {
  const source = [
    readFileSync(new URL("./cockpitV2Model.ts", import.meta.url), "utf8"),
    readFileSync(new URL("./CockpitV2Board.tsx", import.meta.url), "utf8"),
  ].join("\n");
  for (const stale of [
    "839fd25f43c76375f49e45012fe8f20a324aa74c",
    "governance/operator-coherence-cockpit-20260623",
    "canonicalActiveTracks",
    "PRODUCTION_READINESS_VERDICTS",
    "canonical baseline is 7/10",
    "\"Prod readiness\"",
    "const status = report.readiness.score >= 70 ? \"STABLE\"",
    '["Branches", report.branch_census?.total ?? 0, 207]',
    '["Stashes", report.rogue_work_radar.stash_count, 100]',
    '["Dirty worktrees", report.rogue_work_radar.dirty_worktree_count, 12]',
  ]) {
    assert.ok(!source.includes(stale), `stale authority constant remains: ${stale}`);
  }
});

test("lane admission contract exposes required packet fields for UI rendering", () => {
  for (const expected of ["lane_id", "agent_or_provider", "canonicality", "preservation_status", "promotion_recommendation"]) {
    assert.ok(LANE_ADMISSION_FIELDS.includes(expected as (typeof LANE_ADMISSION_FIELDS)[number]));
  }
  const inspect = buildLaneAdmissionInspect();
  assert.equal(inspect.status, "schema defined; live packets pending backplane ingestion");
  assert.ok(inspect.evidence?.[0]?.path?.includes("agent_lane_admission_packet.schema.json"));
});
