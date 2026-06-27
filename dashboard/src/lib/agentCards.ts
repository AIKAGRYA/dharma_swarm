import type { AgentCardOut } from "./types";

export const AGENT_CARD_TRUST_GRADES = [
  "quarantine",
  "verified",
  "registered",
  "discovery",
  "evidence_only",
] as const;

export type AgentCardReadinessFilter = "all" | "handoff" | "public" | "blocked";

export interface AgentCardFilters {
  search?: string;
  trustGrade?: string;
  role?: string;
  readiness?: AgentCardReadinessFilter;
}

const TRUST_RANK: Record<string, number> = {
  quarantine: 0,
  verified: 1,
  registered: 2,
  discovery: 3,
  evidence_only: 4,
};

function clean(value: unknown): string {
  return String(value ?? "").trim();
}

function normalize(value: unknown): string {
  return clean(value).toLowerCase();
}

export function agentCardLabel(agent: AgentCardOut): string {
  return clean(agent.display_name) || clean(agent.callsign) || agent.agent_uid;
}

export function countAgentCardFindings(
  agent: AgentCardOut,
  severity?: string,
): number {
  if (!severity) return agent.findings.length;
  const needle = normalize(severity);
  return agent.findings.filter((finding) => normalize(finding.severity) === needle)
    .length;
}

export function agentCardHandoffReady(agent: AgentCardOut): boolean {
  return Boolean(
    agent.handoff.public_card_ready &&
      agent.handoff.extended_card_ready &&
      agent.handoff.operator_card_ready,
  );
}

export function agentCardPublicReady(agent: AgentCardOut): boolean {
  return Boolean(agent.handoff.public_card_ready);
}

export function agentCardBlocked(agent: AgentCardOut): boolean {
  return (
    normalize(agent.trust_grade) === "quarantine" ||
    countAgentCardFindings(agent, "error") > 0
  );
}

export function compareAgentCards(left: AgentCardOut, right: AgentCardOut): number {
  const rankLeft = TRUST_RANK[normalize(left.trust_grade)] ?? 99;
  const rankRight = TRUST_RANK[normalize(right.trust_grade)] ?? 99;
  if (rankLeft !== rankRight) return rankLeft - rankRight;

  const errorDelta =
    countAgentCardFindings(right, "error") - countAgentCardFindings(left, "error");
  if (errorDelta !== 0) return errorDelta;

  return agentCardLabel(left).localeCompare(agentCardLabel(right));
}

function searchHaystack(agent: AgentCardOut): string {
  return [
    agent.agent_uid,
    agent.display_name,
    agent.callsign,
    agent.role,
    agent.department,
    agent.team_id,
    agent.squad_id,
    agent.provider,
    agent.model,
    agent.harness,
    agent.endpoint,
    agent.authority,
    agent.semantic.canonical_object_id,
    agent.semantic.canonical_name,
    ...agent.card_names,
    ...agent.capabilities,
    ...agent.skills,
  ]
    .map(normalize)
    .join(" ");
}

function readinessMatches(
  agent: AgentCardOut,
  readiness: AgentCardReadinessFilter,
): boolean {
  if (readiness === "handoff") return agentCardHandoffReady(agent);
  if (readiness === "public") return agentCardPublicReady(agent);
  if (readiness === "blocked") return agentCardBlocked(agent);
  return true;
}

export function filterAgentCards(
  agents: AgentCardOut[],
  filters: AgentCardFilters,
): AgentCardOut[] {
  const search = normalize(filters.search);
  const trustGrade = normalize(filters.trustGrade);
  const role = normalize(filters.role);
  const readiness = filters.readiness ?? "all";

  return agents
    .filter((agent) => {
      if (search && !searchHaystack(agent).includes(search)) return false;
      if (trustGrade && trustGrade !== "all" && normalize(agent.trust_grade) !== trustGrade) {
        return false;
      }
      if (role && role !== "all" && normalize(agent.role) !== role) return false;
      return readinessMatches(agent, readiness);
    })
    .sort(compareAgentCards);
}

export function uniqueAgentCardRoles(agents: AgentCardOut[]): string[] {
  return Array.from(
    new Set(
      agents
        .map((agent) => clean(agent.role))
        .filter((role): role is string => Boolean(role)),
    ),
  ).sort((left, right) => left.localeCompare(right));
}
