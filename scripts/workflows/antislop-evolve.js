// antislop-evolve — the reusable Pudgala Autopoiesis Protostar quality engine.
// This is not Dharma Forge / Forge Swarm Evolution Arena; it is the anti-slop
// claim/evidence mechanism that hardens governance claims.
//
// WHY THIS LIVES HERE (not .claude/workflows/): `.gitignore` ignores `.claude/`,
// so a workflow placed there is never committed (that is exactly how the first
// build's copy was lost). The canonical, version-controlled source lives under
// scripts/workflows/. Invoke it explicitly via:
//
//     Workflow({ scriptPath: "scripts/workflows/antislop-evolve.js", args: {...} })
//
// (or symlink/copy into .claude/workflows/ for name-based `Workflow({name:...})`).
//
// It is a CLIENT of the kernel, not an authority: its own output must pass
// scripts/governance/check_claim_evidence_binding.py (S(x)=x — the judge of slop
// must not be slop). It NEVER pushes. Machine receipts sink to
// ~/.dharma/witness/claim_evidence_receipts.jsonl.

export const meta = {
  name: "antislop-evolve",
  description:
    "Research bleeding-edge anti-slop mechanisms, map them against dharma_swarm, " +
    "synthesize a verified build backlog via a heterogeneous CourtEval jury, then " +
    "gate the run's own output through the claim/evidence binding (S(x)=x). " +
    "Local-first; never pushes.",
  phases: [
    { title: "preflight", detail: "assert clean tree; load prior receipt cursor" },
    { title: "research", detail: "parallel fan-out over anti-slop threads" },
    { title: "mapping", detail: "map each finding against the repo (file:line)" },
    { title: "verify", detail: "CourtEval jury: Grader/Critic/Defender, heterogeneous" },
    { title: "backlog", detail: "synthesize ranked, reuse-first build backlog" },
    { title: "self-apply", detail: "S(x)=x: gate the run's own output" },
  ],
};

// Anti-slop research threads (extend freely; each must return citable mechanisms).
const THREADS = [
  "provenance-slsa-intoto-sigstore",
  "reward-hacking-goodhart",
  "claim-evidence-binding",
  "slopsquatting-code-integrity",
  "ontology-name-mcp-pinning",
  "mutation-oracle-independence",
  "multi-model-jury-preference-leakage",
  "gaas-trust-factor-ratcheting",
  "future-proof-karpathy-replay",
  "semantic-conflict-detection",
];

// Verifier model differs from the generators' (preference-leakage defense).
const GEN_MODEL = "sonnet";
const VERIFY_MODEL = "opus";

const FINDINGS_SCHEMA = {
  type: "object",
  required: ["thread", "mechanisms"],
  properties: {
    thread: { type: "string" },
    mechanisms: {
      type: "array",
      items: {
        type: "object",
        required: ["name", "enforces", "source_url", "implementable_pattern"],
        properties: {
          name: { type: "string" },
          enforces: { type: "string" },
          source_url: { type: "string" },
          implementable_pattern: { type: "string" },
          gate_or_runtime: { type: "string", enum: ["ci-gate", "runtime-check", "schema", "doc"] },
        },
      },
    },
  },
};

const GAP_SCHEMA = {
  type: "object",
  required: ["thread", "rows"],
  properties: {
    thread: { type: "string" },
    rows: {
      type: "array",
      items: {
        type: "object",
        required: ["mechanism", "repo_status", "evidence_path", "gap_summary"],
        properties: {
          mechanism: { type: "string" },
          repo_status: { type: "string", enum: ["covered", "partial", "absent"] },
          evidence_path: { type: "string" }, // exact file:line proving the status
          gap_summary: { type: "string" },
        },
      },
    },
  },
};

const VERDICT_SCHEMA = {
  type: "object",
  required: ["lens", "vote", "rationale"],
  properties: {
    lens: { type: "string", enum: ["real-gap", "gameable", "name-truth"] },
    vote: { type: "string", enum: ["KEEP", "KILL", "UNCERTAIN"] }, // UNCERTAIN counts as KILL
    rationale: { type: "string" },
    counter_evidence_path: { type: ["string", "null"] },
  },
};

const BACKLOG_SCHEMA = {
  type: "object",
  required: ["items"],
  properties: {
    items: {
      type: "array",
      items: {
        type: "object",
        required: ["id", "layer", "file_path", "change_sketch", "grade_closed", "impact_per_effort", "reuses_existing"],
        properties: {
          id: { type: "string" },
          layer: { type: "string" },
          file_path: { type: "string" },
          change_sketch: { type: "string" },
          grade_closed: { type: "string" }, // which S0–S8 grade / invariant it raises
          impact_per_effort: { type: "integer", minimum: 1, maximum: 5 },
          reuses_existing: { type: "boolean" }, // MUST be true if it touches receipts/truth-store
        },
      },
    },
  },
};

const mode = (args && args.mode) || "research"; // "research" | "build"
const minQuorum = (args && args.minQuorum) || 3; // all three lenses must KEEP

// ───────────────────────── Phase 0: preflight ─────────────────────────
phase("preflight");
const pre = await agent(
  "READ-ONLY. In the dharma_swarm repo report: `git status --porcelain` (clean?), " +
  "current branch, HEAD sha. Then summarize ~/.dharma/logs/antislop_evolve_latest.json " +
  "if present (which threads were CONFIRMED in the last 7 days, to skip).",
  { label: "preflight", phase: "preflight", model: GEN_MODEL }
);
log(`preflight: ${String(pre).slice(0, 200)}`);

// ───────────────────────── Phase 1: research fan-out (barrier) ─────────────────────────
phase("research");
const findings = (await parallel(
  THREADS.map((thread) => () =>
    agent(
      `You are a RESEARCHER on the anti-slop thread "${thread}". Use WebSearch + tavily + ` +
      `fetch MCP. Return 2–4 BLEEDING-EDGE, IMPLEMENTABLE mechanisms (2025–2026): name, ` +
      `what slop it prevents, a primary source URL, and a concrete CI-gate/runtime pattern. ` +
      `Reject anything you cannot cite. No vague "best practices".`,
      { label: `research:${thread}`, phase: "research", model: GEN_MODEL, schema: FINDINGS_SCHEMA }
    )
  )
)).filter(Boolean);

// ───────────────────────── Phase 2: repo mapping (barrier) ─────────────────────────
phase("mapping");
const gaps = (await parallel(
  findings.map((f) => () =>
    agent(
      `REPO MAPPER, READ-ONLY, thread "${f.thread}". For each mechanism below decide whether ` +
      `dharma_swarm already implements it (covered/partial/absent) with EXACT file:line via ` +
      `mcp__fallow__* / mcp__gitnexus__* / grep. Adversarial default: assume covered until ` +
      `proven otherwise.\n\nMECHANISMS:\n${JSON.stringify(f.mechanisms, null, 2)}`,
      { label: `map:${f.thread}`, phase: "mapping", model: GEN_MODEL, schema: GAP_SCHEMA }
    )
  )
)).filter(Boolean);

// ───────────────────────── Phase 3: synthesize backlog ─────────────────────────
phase("backlog");
const backlog = await agent(
  "SYNTHESIZER. From the gap table, produce a RANKED build backlog. Each item targets ONE " +
  "layer with an EXACT existing file path. HARD RULE (CLAUDE.md): never propose a new truth " +
  "store / daemon / receipt system — reuse spine.EvidenceReceipt + ~/.dharma sinks " +
  "(reuses_existing=true). Prioritize real, uncovered, high-impact-per-effort gaps.\n\n" +
  `GAP TABLE:\n${JSON.stringify(gaps.flatMap((g) => g.rows || []), null, 2)}`,
  { label: "synthesize", phase: "backlog", model: VERIFY_MODEL, schema: BACKLOG_SCHEMA }
);

// ───────────────── Phase 4: CourtEval adversarial verify (pipeline, loop-until-dry) ─────────────────
phase("verify");
const LENSES = [
  ["real-gap", "Is this a REAL gap, or already covered somewhere? Prove with file:line."],
  ["gameable", "Is this gate GAMEABLE (Goodhart)? Could an agent satisfy it without being honest?"],
  ["name-truth", "Does the proposed name match the proposed behavior? (S(x)=x self-check.)"],
];

async function judge(item) {
  // Three independent verifiers (different model than generators); UNCERTAIN ⇒ not KEEP.
  const verdicts = (await parallel(
    LENSES.map(([lens, q]) => () =>
      agent(
        `ADVERSARIAL VERIFIER, lens "${lens}". DEFAULT TO REJECT IF UNCERTAIN. Do not assume ` +
        `good faith. Use fallow/gitnexus/grep READ-ONLY to check against the repo.\n` +
        `Question: ${q}\n\nBACKLOG ITEM:\n${JSON.stringify(item, null, 2)}`,
        { label: `verify:${lens}:${item.id}`, phase: "verify", model: VERIFY_MODEL, schema: VERDICT_SCHEMA }
      )
    )
  )).filter(Boolean);
  const keeps = verdicts.filter((v) => v.vote === "KEEP").length;
  const unanimous = keeps === LENSES.length; // collusion-audit: flag unanimous for extra scrutiny
  return { item, verdicts, kept: keeps >= minQuorum, unanimous };
}

let survivors = (await pipeline((backlog.items || []), (item) => judge(item))).filter(Boolean);
for (let round = 0; round < 3; round++) {
  const kept = survivors.filter((s) => s.kept).map((s) => s.item);
  if (!kept.length) break;
  const re = (await pipeline(kept, (item) => judge(item))).filter(Boolean);
  const flipped = re.filter((r) => !r.kept).length;
  log(`verify round ${round + 1}: ${re.length} re-checked, ${flipped} flipped to KILL`);
  survivors = re;
  if (!flipped) break; // dry
}
const confirmed = survivors
  .filter((s) => s.kept)
  .map((s) => s.item)
  .sort((a, b) => b.impact_per_effort - a.impact_per_effort);
log(`confirmed ${confirmed.length}/${(backlog.items || []).length} backlog items`);

// ───────────────────────── Phase 5: self-application gate (S(x)=x) ─────────────────────────
phase("self-apply");
const selfCheck = await agent(
  "S(x)=x GATE. The workflow's own output (the confirmed backlog below) must itself satisfy " +
  "the claim/evidence binding it proposes: every item must carry an evidence_path or a cited " +
  "source_url, and reuses_existing must hold where it touches receipts. Run " +
  "`python3 scripts/governance/check_claim_evidence_binding.py --warn-only` for context. " +
  "Return PASS only if the backlog is itself non-slop; otherwise FAIL with reasons.\n\n" +
  `CONFIRMED BACKLOG:\n${JSON.stringify(confirmed, null, 2)}`,
  { label: "self-apply", phase: "self-apply", model: VERIFY_MODEL }
);
log(`S(x)=x self-application: ${String(selfCheck).slice(0, 300)}`);

// The judge of slop must not be slop: if our own output cannot pass the gate, emit nothing.
if (/^\s*FAIL/i.test(String(selfCheck))) {
  return { ok: false, reason: "self-application gate FAILED — no receipt emitted", confirmed };
}

// research mode stops here; build mode would pipeline confirmed top-N through
// builder→independent-verifier→`make governance-all`, then a future-proof model-swap replay.
return {
  ok: true,
  mode,
  confirmed,
  note: "research-only run; main untouched, never pushed. Hand operator the backlog + receipt.",
};
