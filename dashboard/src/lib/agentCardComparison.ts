import {
  agentCardBlocked,
  agentCardHandoffReady,
  agentCardLabel,
  compareAgentCards,
  countAgentCardFindings,
} from "./agentCards";
import type { AgentCardOut } from "./types";

export type AgentCardHandoffState = "ready" | "public" | "partial" | "blocked" | "none";

export interface AgentCardComparisonRow {
  agentUid: string;
  label: string;
  trustGrade: string;
  blocked: boolean;
  role: string;
  status: string;
  model: string;
  harness: string;
  endpoint: string;
  authority: string;
  team: string;
  squad: string;
  semanticObject: string;
  semanticName: string;
  cardCount: number;
  sourceCount: number;
  capabilityCount: number;
  findingCount: number;
  errorCount: number;
  warningCount: number;
  handoffState: AgentCardHandoffState;
  publicReady: boolean;
  extendedReady: boolean;
  operatorReady: boolean;
  natsSubjects: string[];
}

export interface AgentCardComparisonSummary {
  rowCount: number;
  blockedCount: number;
  verifiedCount: number;
  readyCount: number;
}

function clean(value: unknown): string {
  return String(value ?? "").trim();
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => clean(item)).filter(Boolean);
}

function sourceCount(agent: AgentCardOut): number {
  return Object.values(agent.sources).reduce(
    (count, paths) => count + paths.length,
    0,
  );
}

function handoffState(agent: AgentCardOut): AgentCardHandoffState {
  if (agentCardBlocked(agent)) return "blocked";
  if (agentCardHandoffReady(agent)) return "ready";
  if (agent.handoff.public_card_ready) return "public";
  if (agent.handoff.extended_card_ready || agent.handoff.operator_card_ready) {
    return "partial";
  }
  return "none";
}

export function buildAgentCardComparisonRow(
  agent: AgentCardOut,
): AgentCardComparisonRow {
  const errorCount = countAgentCardFindings(agent, "error");
  const warningCount = countAgentCardFindings(agent, "warning");
  return {
    agentUid: agent.agent_uid,
    label: agentCardLabel(agent),
    trustGrade: clean(agent.trust_grade),
    blocked: agentCardBlocked(agent),
    role: clean(agent.role),
    status: clean(agent.status),
    model: clean(agent.model || agent.provider),
    harness: clean(agent.harness),
    endpoint: clean(agent.endpoint),
    authority: clean(agent.authority),
    team: clean(agent.team_id),
    squad: clean(agent.squad_id),
    semanticObject: clean(agent.semantic.canonical_object_id),
    semanticName: clean(agent.semantic.canonical_name),
    cardCount: Number(agent.a2a.card_count_for_agent ?? agent.card_names.length) || 0,
    sourceCount: sourceCount(agent),
    capabilityCount: agent.capabilities.length,
    findingCount: agent.findings.length,
    errorCount,
    warningCount,
    handoffState: handoffState(agent),
    publicReady: Boolean(agent.handoff.public_card_ready),
    extendedReady: Boolean(agent.handoff.extended_card_ready),
    operatorReady: Boolean(agent.handoff.operator_card_ready),
    natsSubjects: stringList(agent.nats.subjects),
  };
}

export function buildAgentCardComparisonRows(
  agents: AgentCardOut[],
): AgentCardComparisonRow[] {
  return [...agents].sort(compareAgentCards).map(buildAgentCardComparisonRow);
}

export function summarizeAgentCardComparisonRows(
  rows: AgentCardComparisonRow[],
): AgentCardComparisonSummary {
  return {
    rowCount: rows.length,
    blockedCount: rows.filter((row) => row.blocked).length,
    verifiedCount: rows.filter((row) => row.trustGrade === "verified").length,
    readyCount: rows.filter((row) => row.handoffState === "ready").length,
  };
}
