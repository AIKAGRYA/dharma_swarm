import assert from "node:assert/strict";
import test from "node:test";

import {
  AUTOCATALYTIC_NODE_COUNT,
  authorityPresentation,
  canonicalConsumer,
  canonicalPredecessor,
  cycleWitnessPresentation,
  hasClosedTenNodeRing,
  normalizeAuthority,
  orderedPortfolioNodes,
  promotionRuleLines,
  semanticReceiptCountForWitness,
  summarizePortfolio,
  type AutocatalyticCycleWitness,
  type AutocatalyticNode,
  type AutocatalyticPortfolio,
} from "./autocatalyticPortfolio.ts";

function node(ordinal: number): AutocatalyticNode {
  const nextOrdinal = ordinal === AUTOCATALYTIC_NODE_COUNT ? 1 : ordinal + 1;
  return {
    id: `node-${ordinal}`,
    label: `Node ${ordinal}`,
    ordinal,
    role: `Transform ${ordinal}`,
    project_bindings: [`track-${ordinal}`],
    authority: ordinal === 1 ? "local_rehearsal" : "projection_only",
    input_signal: `signal-${ordinal}`,
    output_signal: `signal-${nextOrdinal}`,
    transform: `Convert ${ordinal} to ${nextOrdinal}`,
    page: `docs/node-${ordinal}.md`,
    proof_refs: [`tests/test_node_${ordinal}.py`],
    proof_obligations: ["emit a typed semantic artifact"],
    next_node: `node-${nextOrdinal}`,
  };
}

function portfolio(): AutocatalyticPortfolio {
  const nodes = Array.from({ length: AUTOCATALYTIC_NODE_COUNT }, (_, index) => node(index + 1));
  return {
    id: "autocatalytic-ten",
    label: "Autocatalytic Ten",
    claim_ceiling: "local_rehearsal",
    nodes: [...nodes].reverse(),
    edges: nodes.map((entry) => ({
      source: entry.id,
      target: entry.next_node,
      signal: entry.output_signal,
      kind: "feeds",
    })),
    promotion_rule: {
      transport_ack_promotes: false,
      structural_hop_requires: ["typed semantic artifact"],
      receipt_consistent_cycle_requires: ["exactly ten structural hops"],
    },
  };
}

function witness(overrides: Partial<AutocatalyticCycleWitness> = {}): AutocatalyticCycleWitness {
  return {
    schema_version: "dharma.a2a.cycle_witness.v1",
    cycle_id: "cycle-test",
    trace_id: "trace-test",
    correlation_id: "correlation-test",
    mode: "local_rehearsal",
    claim_ceiling: "local_rehearsal",
    generated_at: "2026-08-05T00:00:00Z",
    structural_proof_valid: true,
    local_receipt_consistency_valid: true,
    cycle_closed: true,
    completed_hops: 10,
    required_hops: 10,
    turns_proven: 2,
    transport_evidence: "in_process_local",
    runtime_receipts_recorded: true,
    execution_evidence_scope: "local_mutable_runtime_receipt_consistency",
    execution_provenance_authenticated: false,
    external_effects_proven: false,
    proofs: [],
    witness_path: "~/.dharma/a2a/autocatalytic_portfolio/latest.json",
    ...overrides,
  };
}

test("authority presentation keeps node evidence distinct from cycle rehearsal and live authority", () => {
  assert.deepEqual(
    ["live", "local-evidence", "local-rehearsal", "projection only", "external_gated"].map(
      normalizeAuthority,
    ),
    ["live", "local_evidence", "local_rehearsal", "projection_only", "external_gated"],
  );
  assert.equal(normalizeAuthority("completed"), "unknown");
  assert.equal(authorityPresentation("local_evidence").label, "Local evidence");
  assert.equal(authorityPresentation("local_rehearsal").label, "Local rehearsal");
  assert.match(authorityPresentation("projection_only").description, /not been proven/i);
});

test("portfolio topology sorts by ordinal and closes one canonical ten-node ring", () => {
  const value = portfolio();
  const ordered = orderedPortfolioNodes(value);

  assert.equal(ordered[0]?.id, "node-1");
  assert.equal(ordered[9]?.id, "node-10");
  assert.equal(hasClosedTenNodeRing(value), true);
  assert.equal(summarizePortfolio(value).authorityCounts.projection_only, 9);
  assert.equal(canonicalPredecessor(value, "node-1")?.id, "node-10");
  assert.equal(canonicalConsumer(value, ordered[0]!)?.id, "node-2");
});

test("a broken or undersized declaration cannot be presented as a closed ten-node ring", () => {
  const value = portfolio();
  value.nodes[0] = { ...value.nodes[0]!, next_node: "node-4" };
  assert.equal(hasClosedTenNodeRing(value), false);

  value.nodes = value.nodes.slice(0, 9);
  assert.equal(hasClosedTenNodeRing(value), false);
});

test("cycle witness presentation requires structure and exact local receipt consistency", () => {
  assert.equal(cycleWitnessPresentation(witness()).state, "receipt_consistent");
  assert.equal(
    cycleWitnessPresentation(witness({ structural_proof_valid: false })).state,
    "unverified",
  );
  assert.equal(
    cycleWitnessPresentation(witness({ local_receipt_consistency_valid: false })).state,
    "unverified",
  );
  assert.equal(cycleWitnessPresentation(witness({ cycle_closed: false })).state, "unverified");
  assert.equal(cycleWitnessPresentation(witness({ completed_hops: 9 })).state, "unverified");
  assert.equal(cycleWitnessPresentation(witness({ required_hops: 11 })).state, "unverified");
  assert.equal(
    cycleWitnessPresentation(witness({ runtime_receipts_recorded: false })).state,
    "unverified",
  );
  assert.equal(
    cycleWitnessPresentation(witness({ execution_evidence_scope: "self_asserted" })).state,
    "unverified",
  );
  assert.equal(
    cycleWitnessPresentation(witness({ execution_provenance_authenticated: true })).state,
    "unverified",
  );
  assert.equal(cycleWitnessPresentation(null).state, "missing");
});

test("semantic receipt count follows the witnessed turn count", () => {
  assert.equal(semanticReceiptCountForWitness(witness()), 41);
  assert.equal(semanticReceiptCountForWitness(witness({ turns_proven: 3 })), 61);
  assert.equal(semanticReceiptCountForWitness(witness({ turns_proven: 1 })), null);
  assert.equal(semanticReceiptCountForWitness(witness({ turns_proven: 2.5 })), null);
  assert.equal(semanticReceiptCountForWitness(null), null);
});

test("transport acknowledgement is stated as a non-promotion rule", () => {
  const lines = promotionRuleLines(portfolio().promotion_rule);
  assert.ok(lines.some((line) => /transport acknowledgement cannot promote/i.test(line)));
  assert.ok(lines.some((line) => /typed semantic artifact/i.test(line)));
  assert.ok(lines.some((line) => /exactly ten structural hops/i.test(line)));
});
