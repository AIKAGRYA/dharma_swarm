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
  deriveCheckoutAuthority,
  filterCards,
  humanKind,
  humanRisk,
  modeMatches,
  readinessTone,
  sourceToInspect,
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
    git: { main: { branch: "main", branch_line: "## main...origin/main", head: "3482cdfa6a2f3330b1c6df6d332836d7f4b6c9cf", dirty_count: 0 } },
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
  assert.equal(authority.head, "3482cdfa6a2f3330b1c6df6d332836d7f4b6c9cf");
  assert.equal(authority.dirtyCount, 0);
  assert.equal(authority.maxActive, 10);
  assert.match(authority.detail, /does not independently prove origin\/main/);

  const inspect = buildAuthorityInspect(report());
  assert.equal(inspect.status, "10/10 active · HEAD 3482cdfa6a2f");
  assert.match(inspect.subtitle ?? "", /CLEAN_LOCAL_MAIN/);
  assert.match(inspect.nextAction ?? "", /verify origin\/main separately/);
});

test("checkout authority classifies a clean non-main branch", () => {
  const cleanBranch = report();
  cleanBranch.git = { main: { branch: "agent/titanium", head: "abc123", dirty_count: 0 } };
  assert.equal(deriveCheckoutAuthority(cleanBranch).code, "CLEAN_LOCAL_BRANCH");
});

test("checkout authority classifies a dirty observation", () => {
  const dirty = report();
  dirty.git = { main: { branch: "main", head: "abc123", dirty_count: 3 } };
  assert.equal(deriveCheckoutAuthority(dirty).code, "DIRTY_LOCAL_CHECKOUT");
  assert.match(deriveCheckoutAuthority(dirty).detail, /3 local paths/);
});

test("checkout authority classifies incomplete git evidence as unavailable", () => {
  const unavailable = report();
  unavailable.git = { main: { branch: "main", dirty_count: 0 } };
  assert.equal(deriveCheckoutAuthority(unavailable).code, "CHECKOUT_STATE_UNAVAILABLE");
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
  assert.match(reviews[0].detail, /not a production-readiness verdict/);
  assert.equal(reviews[1].code, "REFRESH_STALE_EVIDENCE");
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
