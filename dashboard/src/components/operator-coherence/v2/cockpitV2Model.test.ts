import assert from "node:assert/strict";
import test from "node:test";

import {
  DESIGN_SOURCES,
  LANE_ADMISSION_FIELDS,
  MODES,
  TRUTH_TAXONOMY,
  actionToInspect,
  buildActionPackets,
  buildAuthorityInspect,
  buildReportSourceSummary,
  buildHandoff,
  buildLaneAdmissionInspect,
  buildTopPanels,
  cardFacetBadges,
  cardToInspect,
  classifyCardTruth,
  filterCards,
  humanKind,
  humanRisk,
  modeMatches,
  readinessTone,
  sourceToInspect,
  STATUS_TOKENS,
  statusTone,
  buildAnswerRibbon,
  buildUncertainty,
  buildTopology,
  buildEventTape,
  cardFreshness,
  freshnessFromAge,
  nodeMatchesFilter,
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
    track_portfolio: { active_count: 11, closed_count: 4, tracks: [], proposed_tracks: [], broken_register: {} },
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
    git: { main: { branch: "telos-ai-seed-v0-from-sandbox", branch_line: "## telos-ai-seed-v0-from-sandbox...origin/telos-ai-seed-v0-from-sandbox [ahead 2]" } },
    live_ops: { enabled: true, summary: { total: 17, by_status: { live: 4, stale: 2, blocked: 2, stopped: 9 } } },
    onboarding: { status: "wired", target: "make onboard" },
    runtime_receipts: { runtime_dbs: [], receipt_count: 19, recent_receipts: [] },
    operator_surfaces: { surfaces: [], abandoned_dashboard_candidates: [] },
    preservation_ledger: { at_risk_worktree_count: 11 },
    pr_ci_triage: { enabled: false, reason: "gh_auth_unavailable" },
    definition_answers: {},
  } as Parameters<typeof buildTopPanels>[0];
}

test("MODES exposes the operator board lenses incl. topology/recursive/errors", () => {
  const ids = MODES.map((m) => m.id);
  for (const expected of [
    "overview",
    "triage",
    "topology",
    "recursive",
    "git",
    "runtime",
    "tracks",
    "preservation",
    "evidence",
    "errors",
    "design",
  ]) {
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
  assert.ok(TRUTH_TAXONOMY.some((truth) => truth.code === "CANONICAL_ORIGIN_MAIN"));
  assert.equal(classifyCardTruth(card()).code, "LOCAL_ONLY_BRANCH");
  assert.equal(classifyCardTruth(card({ facets: { ...card().facets, local_only: false, live: true } })).code, "LIVE_RUNTIME_PROOF");
  assert.equal(classifyCardTruth(card({ facets: { ...card().facets, local_only: false, stale: true } })).code, "STALE_RECEIPT");
  const badges = cardFacetBadges(card());
  for (const expected of ["untracked", "not preserved", "rogue", "local-only", "operator decision"]) {
    assert.ok(badges.includes(expected), `missing facet badge ${expected}`);
  }
});

test("authority inspect uses report fields and labels missing canonical proof as uncertainty", () => {
  const inspect = buildAuthorityInspect(report());
  assert.equal(inspect.status, "local 11/— active tracks · report snapshot");
  assert.match(inspect.subtitle ?? "", /telos-ai-seed-v0-from-sandbox/);
  assert.match(inspect.risk ?? "", /missing canonical baseline evidence is uncertainty/);
  assert.ok(inspect.evidence?.some((ev) => ev.source.includes("/api/operator-coherence/report")));
});

test("lane admission contract exposes required packet fields for UI rendering", () => {
  for (const expected of ["lane_id", "agent_or_provider", "canonicality", "preservation_status", "promotion_recommendation"]) {
    assert.ok(LANE_ADMISSION_FIELDS.includes(expected as (typeof LANE_ADMISSION_FIELDS)[number]));
  }
  const inspect = buildLaneAdmissionInspect();
  assert.equal(inspect.status, "schema defined; live packets pending backplane ingestion");
  assert.ok(inspect.evidence?.[0]?.path?.includes("agent_lane_admission_packet.schema.json"));
});

test("buildAnswerRibbon answers the 8 under-60-second questions from definition_answers", () => {
  const r = report() as Record<string, unknown>;
  r.definition_answers = {
    what_is_safe: [card({ id: "safe:1", title: "safe a" })],
    what_is_dirty: [card({ id: "dirty:1", title: "dirty a" }), card({ id: "dirty:2", title: "dirty b" })],
    what_is_abandoned: [card({ id: "ab:1", title: "abandoned a" })],
    what_is_live: [],
    what_is_blocked: [card({ id: "bl:1", title: "blocked a" })],
    what_might_be_rogue: [card({ id: "rg:1", title: "rogue a" })],
    what_should_i_do_next: [{ title: "do x", kind: "preservation_risk", risk: "local", next_action: "push", evidence: [] }],
  };
  const answers = buildAnswerRibbon(r as Parameters<typeof buildAnswerRibbon>[0]);
  const byKey = Object.fromEntries(answers.map((a) => [a.key, a]));
  for (const k of ["safe", "dirty", "abandoned", "live", "blocked", "rogue", "next", "readiness"]) {
    assert.ok(byKey[k], `missing answer ${k}`);
  }
  assert.equal(byKey.dirty.value, "2");
  // Empty live must read as uncertainty, never blank success.
  assert.equal(byKey.live.tone, "warn");
  assert.match(byKey.live.topEvidence, /uncertainty/);
  assert.equal(byKey.readiness.value, "41.5%");
});

test("buildUncertainty surfaces gh/tmux/gcx and raw source errors, never hides them", () => {
  const r = report() as Record<string, unknown>;
  r.source_errors = [
    { source: "tmux.ls", error: "no socket", timestamp: "2026-06-23T00:00:00Z" },
    { source: "github.auth", error: "gh auth unavailable; PR/CI triage omitted", timestamp: "2026-06-23T00:00:00Z" },
  ];
  const items = buildUncertainty(r as Parameters<typeof buildUncertainty>[0]);
  const labels = items.map((i) => i.id);
  assert.ok(labels.some((l) => l.includes("tmux")), "tmux uncertainty missing");
  assert.ok(labels.some((l) => l.includes("github") || l.includes("gh")), "gh uncertainty missing");
  assert.ok(labels.includes("external:gcx"), "gcx uncertainty missing");
  // No uncertainty item may ever read as a healthy/ok state.
  for (const item of items) {
    assert.ok(["unavailable", "partial", "degraded"].includes(item.state), `bad uncertainty state ${item.state}`);
  }
});

test("buildTopology derives stable nodes/edges with readiness root and uncertain source-error edges", () => {
  const r = report() as Record<string, unknown>;
  r.source_errors = [{ source: "tmux.ls", error: "no socket" }];
  (r as { live_ops: Record<string, unknown> }).live_ops = {
    enabled: true,
    summary: { total: 1, by_status: { live: 1 } },
    surfaces: [{ id: "s.live", label: "Live surface", status: "live", desired_state: "live", age_hours: 1 }],
  };
  (r as { runtime_receipts: Record<string, unknown> }).runtime_receipts = {
    receipt_count: 1,
    runtime_dbs: [],
    recent_receipts: [{ path: "reports/a/receipt.jsonl", age_hours: 2 }],
  };
  (r as { cards: ReturnType<typeof card>[] }).cards = [
    card({ id: "branch:demo", kind: "branch" }),
    card({ id: "wt:demo", kind: "worktree", title: "worktree demo", risk: "dirty_worktree" }),
  ];
  const graph = buildTopology(r as Parameters<typeof buildTopology>[0]);
  assert.ok(graph.nodes.find((n) => n.id === "system:readiness"), "missing readiness root");
  for (const kind of ["branch", "worktree", "receipt", "action"] as const) {
    assert.ok(graph.nodes.some((n) => n.kind === kind), `missing ${kind} node`);
  }
  // stable IDs are unique
  const ids = new Set(graph.nodes.map((n) => n.id));
  assert.equal(ids.size, graph.nodes.length, "node ids must be unique/stable");
  // every edge connects real nodes
  for (const edge of graph.edges) {
    assert.ok(ids.has(edge.source), `dangling edge source ${edge.source}`);
    assert.ok(ids.has(edge.target), `dangling edge target ${edge.target}`);
    assert.ok(Array.isArray(edge.evidence), `edge ${edge.id} lacks evidence array`);
  }
  // source-error nodes are always uncertain and never pulse
  const errNodes = graph.nodes.filter((n) => n.kind === "source_error");
  assert.ok(errNodes.length >= 1);
  for (const n of errNodes) {
    assert.equal(n.freshness, "unknown");
    assert.equal(n.pulse, false);
  }
  // live+fresh surface may pulse; stale/unknown may not
  const liveNode = graph.nodes.find((n) => n.kind === "surface" && n.status === "live");
  assert.ok(liveNode, "missing live surface node");
  assert.equal(liveNode?.pulse, true);
  assert.ok(nodeMatchesFilter(liveNode!, "live surface"));
});

test("topology never pulses a stale or unknown surface (REQ-034)", () => {
  const r = report() as Record<string, unknown>;
  (r as { live_ops: Record<string, unknown> }).live_ops = {
    enabled: true,
    summary: { total: 2 },
    surfaces: [
      { id: "s.stale", label: "Stale claim", status: "live", desired_state: "live", age_hours: 5000 },
      { id: "s.unknown", label: "Unknown", status: "unknown", desired_state: "live", age_hours: null },
    ],
  };
  const graph = buildTopology(r as Parameters<typeof buildTopology>[0]);
  for (const n of graph.nodes.filter((x) => x.kind === "surface")) {
    assert.equal(n.pulse, false, `surface ${n.label} should not pulse when not live+fresh`);
  }
});

test("buildEventTape includes report event + pr/ci unavailable, labeled honestly", () => {
  const r = report() as Record<string, unknown>;
  r.source_errors = [{ source: "tmux.ls", error: "no socket" }];
  const events = buildEventTape(r as Parameters<typeof buildEventTape>[0]);
  assert.ok(events.find((e) => e.kind === "report"), "missing report event");
  assert.ok(events.find((e) => e.kind === "pr_ci"), "missing pr/ci unavailable event");
  assert.ok(events.find((e) => e.kind === "source_error"), "missing source error event");
});

test("freshness: live wins, stale evidence reads stale, missing age is unknown", () => {
  assert.equal(freshnessFromAge(1), "fresh");
  assert.equal(freshnessFromAge(48), "aging");
  assert.equal(freshnessFromAge(1000), "stale");
  assert.equal(freshnessFromAge(null), "unknown");
  assert.equal(cardFreshness(card({ facets: { ...card().facets, live: true } })), "fresh");
  assert.equal(cardFreshness(card({ evidence: [] })), "unknown");
});

test("every status token maps to a visual tone (machine-readable coverage)", () => {
  for (const token of STATUS_TOKENS) {
    const tone = statusTone(token);
    assert.ok(["ok", "warn", "danger", "info", "muted"].includes(tone), `status ${token} has no tone`);
  }
  // unknown/garbage falls back to muted, never throws
  assert.equal(statusTone("garbage-status"), "muted");
});

test("buildActionPackets makes recommendations proposal-only and evidence-traceable", () => {
  const packets = buildActionPackets(report());
  assert.equal(packets.length, 1);
  assert.equal(packets[0].allowedNow, false);
  assert.equal(packets[0].rank, 1);
  assert.equal(packets[0].operatorDecision, true);
  assert.ok(packets[0].evidence.length > 0);
});

test("buildReportSourceSummary marks source errors and stale generated_at prominently", () => {
  const r = report() as ReturnType<typeof report>;
  const partial = buildReportSourceSummary({ ...r, source_errors: [{ source: "tmux.ls", error: "no socket" }] });
  assert.equal(partial.mode, "partial");
  assert.equal(partial.tone, "danger");
  const stale = buildReportSourceSummary({ ...r, generated_at: "2026-06-01T00:00:00Z", source_errors: [] }, new Date("2026-06-23T00:00:00Z"));
  assert.equal(stale.mode, "stale");
});
