/**
 * Read-only presentation contracts for the ten-node autocatalytic portfolio.
 *
 * The dashboard never promotes transport evidence into semantic completion.
 * A cycle is shown as verified only when the backend witness satisfies the
 * complete ten-hop proof rule encoded in cycleWitnessPresentation().
 */

export const AUTOCATALYTIC_NODE_COUNT = 10;

export const AUTHORITY_STATES = [
  "live",
  "local_evidence",
  "local_rehearsal",
  "projection_only",
  "external_gated",
] as const;

export type AuthorityState = (typeof AUTHORITY_STATES)[number];
export type PresentedAuthorityState = AuthorityState | "unknown";

export interface AutocatalyticNode {
  id: string;
  label: string;
  ordinal: number;
  role: string;
  project_bindings: string[];
  authority: AuthorityState | string;
  input_signal: string;
  output_signal: string;
  transform: string;
  page: string;
  proof_refs: string[];
  proof_obligations: string[];
  promotion_checks?: string[];
  next_node: string;
}

export interface AutocatalyticEdge {
  source: string;
  target: string;
  signal: string;
  kind: string;
}

export interface AutocatalyticPromotionRule {
  id?: string;
  schema?: string;
  statement?: string;
  transport_ack_promotes?: boolean;
  structural_hop_requires?: string[];
  receipt_consistent_cycle_requires?: string[];
  required_evidence?: string[];
  forbidden_promotions?: string[];
  [key: string]: unknown;
}

export interface AutocatalyticPortfolio {
  id: string;
  label: string;
  claim_ceiling: AuthorityState | string;
  nodes: AutocatalyticNode[];
  edges: AutocatalyticEdge[];
  promotion_rule: AutocatalyticPromotionRule | string;
}

export interface AutocatalyticCycleTurnProof {
  turn: number;
  proof_hash: string;
  completed_hops: number;
  cycle_closed: boolean;
  hop_receipt_hashes: string[];
  hops: AutocatalyticStructuralHop[];
}

export interface AutocatalyticProjectSource {
  path: string;
  present: boolean;
  sha256: string | null;
  schema: string | null;
  generated_at: string | null;
  declared_digest_valid: boolean | null;
  facts: Record<string, unknown>;
}

export interface AutocatalyticSignalEnvelope {
  schema_version: string;
  type: string;
  state: string;
  modality: string;
  promotion_authorized: boolean;
  external_effects_proven: boolean;
  blockers: string[];
}

export interface AutocatalyticPromotionCheckEvaluation {
  predicate: string;
  actual: boolean | null;
  expected: boolean;
  passed: boolean;
}

export interface AutocatalyticPromotionGate {
  schema: "dharma.autocatalytic.promotion_gate.v1" | string;
  node_id: string;
  checks: AutocatalyticPromotionCheckEvaluation[];
  satisfied: boolean;
  state: "blocked" | string;
  authority_upgrade_authorized: boolean;
  authority_requirement: string;
}

export interface AutocatalyticProjectEvidence {
  schema_version: string;
  adapter_version: string;
  adapter_id: string;
  node_id: string;
  project_bindings: string[];
  authority: string;
  claim_ceiling: string;
  execution_mode: string;
  side_effects_performed: boolean;
  external_effects_proven: boolean;
  project_source_causally_linked_to_input: boolean;
  input_ref: {
    artifact_hash: string;
    message_id: string;
    signal_type: string;
    signal_state: string;
  };
  sources: AutocatalyticProjectSource[];
  signal: AutocatalyticSignalEnvelope;
  promotion_gate: AutocatalyticPromotionGate;
  details: Record<string, unknown>;
  evidence_hash: string;
}

export interface AutocatalyticStructuralHop {
  turn: number;
  ordinal: number;
  node_id: string;
  task_id: string;
  run_id: string;
  status: string;
  completion_hash: string;
  artifact: {
    signal: AutocatalyticSignalEnvelope;
    project_evidence: AutocatalyticProjectEvidence;
    consumed_cross_feeds: Record<string, unknown>[];
    emitted_cross_feeds: Record<string, unknown>[];
    [key: string]: unknown;
  };
}

export interface AutocatalyticCycleWitness {
  schema_version: "dharma.a2a.cycle_witness.v1" | string;
  cycle_id: string;
  trace_id: string;
  correlation_id: string;
  mode: "local_rehearsal" | string;
  claim_ceiling: AuthorityState | string;
  generated_at: string;
  structural_proof_valid: boolean;
  local_receipt_consistency_valid: boolean;
  cycle_closed: boolean;
  completed_hops: number;
  required_hops: number;
  turns_proven: number;
  transport_evidence: string;
  runtime_receipts_recorded: boolean;
  execution_evidence_scope?: "local_mutable_runtime_receipt_consistency" | string;
  execution_provenance_authenticated?: boolean;
  external_effects_proven: boolean;
  proofs: AutocatalyticCycleTurnProof[];
  witness_path: string;
}

export interface AutocatalyticTopologyContract {
  required_nodes: number;
  strongly_connected: boolean;
  one_autocatalytic_set: boolean;
  contract_valid: boolean;
  validation_errors: string[];
  [key: string]: unknown;
}

export interface AutocatalyticPortfolioResponse {
  schema_version: string;
  portfolio: AutocatalyticPortfolio;
  topology: AutocatalyticTopologyContract;
  latest_cycle?: AutocatalyticCycleWitness | null;
}

export interface AuthorityPresentation {
  state: PresentedAuthorityState;
  label: string;
  description: string;
  color: string;
}

const AUTHORITY_PRESENTATIONS: Record<PresentedAuthorityState, Omit<AuthorityPresentation, "state">> = {
  live: {
    label: "Live",
    description: "A live-system claim is permitted only while current runtime evidence remains valid.",
    color: "#8FA89B",
  },
  local_evidence: {
    label: "Local evidence",
    description:
      "Executable producer or test evidence exists locally; this rehearsal has not promoted it to live authority.",
    color: "#D47DB5",
  },
  local_rehearsal: {
    label: "Local rehearsal",
    description:
      "Claim scope is bounded to local semantic rehearsal; no external or production claim is permitted.",
    color: "#4FD1D9",
  },
  projection_only: {
    label: "Projection only",
    description: "The topology is declared, but execution has not been proven.",
    color: "#A89DB9",
  },
  external_gated: {
    label: "External gated",
    description: "Execution depends on authority or state outside this runtime.",
    color: "#D4A855",
  },
  unknown: {
    label: "Unknown",
    description: "The backend supplied no recognized authority classification.",
    color: "#4E5060",
  },
};

export function normalizeAuthority(value: unknown): PresentedAuthorityState {
  if (typeof value !== "string") return "unknown";
  const normalized = value.trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  return (AUTHORITY_STATES as readonly string[]).includes(normalized)
    ? (normalized as AuthorityState)
    : "unknown";
}

export function authorityPresentation(value: unknown): AuthorityPresentation {
  const state = normalizeAuthority(value);
  return { state, ...AUTHORITY_PRESENTATIONS[state] };
}

export function orderedPortfolioNodes(portfolio: AutocatalyticPortfolio): AutocatalyticNode[] {
  return [...portfolio.nodes].sort((left, right) => {
    if (left.ordinal !== right.ordinal) return left.ordinal - right.ordinal;
    return left.id.localeCompare(right.id);
  });
}

export function portfolioNodeHref(nodeId: string): string {
  return `/dashboard/organism/${encodeURIComponent(nodeId)}`;
}

export function findPortfolioNode(
  portfolio: AutocatalyticPortfolio,
  nodeId: string,
): AutocatalyticNode | undefined {
  return portfolio.nodes.find((node) => node.id === nodeId);
}

export function incomingPortfolioEdges(
  portfolio: AutocatalyticPortfolio,
  nodeId: string,
): AutocatalyticEdge[] {
  return portfolio.edges.filter((edge) => edge.target === nodeId);
}

export function outgoingPortfolioEdges(
  portfolio: AutocatalyticPortfolio,
  nodeId: string,
): AutocatalyticEdge[] {
  return portfolio.edges.filter((edge) => edge.source === nodeId);
}

export function canonicalPredecessor(
  portfolio: AutocatalyticPortfolio,
  nodeId: string,
): AutocatalyticNode | undefined {
  return portfolio.nodes.find((node) => node.next_node === nodeId);
}

export function canonicalConsumer(
  portfolio: AutocatalyticPortfolio,
  node: AutocatalyticNode,
): AutocatalyticNode | undefined {
  return findPortfolioNode(portfolio, node.next_node);
}

export function hasClosedTenNodeRing(portfolio: AutocatalyticPortfolio): boolean {
  const nodes = orderedPortfolioNodes(portfolio);
  if (nodes.length !== AUTOCATALYTIC_NODE_COUNT) return false;
  if (new Set(nodes.map((node) => node.id)).size !== AUTOCATALYTIC_NODE_COUNT) return false;

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const start = nodes[0];
  if (!start) return false;

  const visited = new Set<string>();
  let current: AutocatalyticNode | undefined = start;
  for (let index = 0; index < AUTOCATALYTIC_NODE_COUNT; index += 1) {
    if (!current || visited.has(current.id)) return false;
    visited.add(current.id);
    current = byId.get(current.next_node);
  }

  return current?.id === start.id && visited.size === AUTOCATALYTIC_NODE_COUNT;
}

export interface PortfolioSummary {
  nodeCount: number;
  edgeCount: number;
  closedTenNodeRing: boolean;
  authorityCounts: Record<PresentedAuthorityState, number>;
}

export function summarizePortfolio(portfolio: AutocatalyticPortfolio): PortfolioSummary {
  const authorityCounts: Record<PresentedAuthorityState, number> = {
    live: 0,
    local_evidence: 0,
    local_rehearsal: 0,
    projection_only: 0,
    external_gated: 0,
    unknown: 0,
  };
  for (const node of portfolio.nodes) {
    authorityCounts[normalizeAuthority(node.authority)] += 1;
  }
  return {
    nodeCount: portfolio.nodes.length,
    edgeCount: portfolio.edges.length,
    closedTenNodeRing: hasClosedTenNodeRing(portfolio),
    authorityCounts,
  };
}

export type CycleWitnessState = "receipt_consistent" | "unverified" | "missing";

export interface CycleWitnessPresentation {
  state: CycleWitnessState;
  label: string;
  description: string;
  color: string;
}

export function semanticReceiptCountForWitness(
  witness: AutocatalyticCycleWitness | null | undefined,
): number | null {
  const turns = witness?.turns_proven;
  if (!Number.isSafeInteger(turns) || turns === undefined || turns < 2) return null;
  return turns * AUTOCATALYTIC_NODE_COUNT * 2 + 1;
}

export function cycleWitnessPresentation(
  witness: AutocatalyticCycleWitness | null | undefined,
): CycleWitnessPresentation {
  if (!witness) {
    return {
      state: "missing",
      label: "No cycle witness",
      description: "Declared wiring is available, but no runtime cycle proof was returned.",
      color: "#4E5060",
    };
  }

  const verified =
    witness.structural_proof_valid === true &&
    witness.local_receipt_consistency_valid === true &&
    witness.cycle_closed === true &&
    witness.completed_hops === AUTOCATALYTIC_NODE_COUNT &&
    witness.required_hops === AUTOCATALYTIC_NODE_COUNT &&
    witness.completed_hops === witness.required_hops &&
    witness.runtime_receipts_recorded === true &&
    witness.execution_evidence_scope === "local_mutable_runtime_receipt_consistency" &&
    witness.execution_provenance_authenticated === false;

  if (verified) {
    return {
      state: "receipt_consistent",
      label: "Locally receipt-consistent cycle",
      description:
        "Exactly ten typed hops closed the cycle and match persisted local mutable receipts; execution provenance is not independently authenticated.",
      color: "#8FA89B",
    };
  }

  return {
    state: "unverified",
    label: "Cycle not verified",
    description:
      "A witness or transport record exists, but it does not satisfy structural proof plus 10/10 local receipt consistency.",
    color: "#D4A855",
  };
}

export function promotionRuleLines(
  rule: AutocatalyticPortfolio["promotion_rule"],
): string[] {
  if (typeof rule === "string") return rule.trim() ? [rule] : [];

  const lines: string[] = [];
  if (typeof rule.statement === "string" && rule.statement.trim()) {
    lines.push(rule.statement);
  }
  if (rule.transport_ack_promotes === false) {
    lines.push("Transport acknowledgement cannot promote a hop to semantic completion.");
  }
  if (Array.isArray(rule.structural_hop_requires)) {
    lines.push(
      ...rule.structural_hop_requires.map((item) => `Structural hop requires: ${item}`),
    );
  }
  if (Array.isArray(rule.receipt_consistent_cycle_requires)) {
    lines.push(
      ...rule.receipt_consistent_cycle_requires.map(
        (item) => `Receipt-consistent cycle requires: ${item}`,
      ),
    );
  }
  if (Array.isArray(rule.required_evidence)) {
    lines.push(...rule.required_evidence.map((item) => `Required evidence: ${humanizeIdentifier(item)}`));
  }
  if (Array.isArray(rule.forbidden_promotions)) {
    lines.push(
      ...rule.forbidden_promotions.map(
        (item) => `Forbidden promotion: ${humanizeIdentifier(item)}`,
      ),
    );
  }
  return [...new Set(lines)];
}

export function humanizeIdentifier(value: string): string {
  return value
    .replaceAll("-", " ")
    .replaceAll("_", " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
