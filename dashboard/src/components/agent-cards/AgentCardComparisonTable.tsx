"use client";

import { AlertTriangle, CheckCircle2, CircleDashed, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { colors } from "@/lib/theme";
import type { AgentCardComparisonRow } from "@/lib/agentCardComparison";

interface AgentCardComparisonTableProps {
  rows: AgentCardComparisonRow[];
  selectedUid: string | null;
  onSelect: (agentUid: string) => void;
}

function valueOrDash(value: string | number): string {
  const text = String(value ?? "").trim();
  return text || "-";
}

function trustColor(row: AgentCardComparisonRow): string {
  if (row.blocked) return colors.bengara;
  if (row.trustGrade === "verified") return colors.rokusho;
  if (row.trustGrade === "registered") return colors.aozora;
  if (row.trustGrade === "discovery") return colors.kinpaku;
  if (row.trustGrade === "evidence_only") return colors.fuji;
  return colors.sumi[600];
}

function handoffColor(row: AgentCardComparisonRow): string {
  if (row.handoffState === "ready") return colors.rokusho;
  if (row.handoffState === "blocked") return colors.bengara;
  if (row.handoffState === "public") return colors.aozora;
  if (row.handoffState === "partial") return colors.kinpaku;
  return colors.sumi[600];
}

export function AgentCardComparisonTable({
  rows,
  selectedUid,
  onSelect,
}: AgentCardComparisonTableProps) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-sumi-700/40 bg-sumi-950/60 px-4 py-12 text-center text-sm text-sumi-500">
        No cards match the current comparison filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-sumi-700/40 bg-sumi-950/60">
      <table className="min-w-[1180px] w-full border-collapse text-left text-xs">
        <thead className="border-b border-sumi-800/80 bg-sumi-900/50">
          <tr className="font-mono text-[10px] uppercase tracking-[0.12em] text-sumi-600">
            <HeaderCell>Agent</HeaderCell>
            <HeaderCell>Trust</HeaderCell>
            <HeaderCell>Handoff</HeaderCell>
            <HeaderCell>Findings</HeaderCell>
            <HeaderCell>Role</HeaderCell>
            <HeaderCell>Model</HeaderCell>
            <HeaderCell>Harness</HeaderCell>
            <HeaderCell>Authority</HeaderCell>
            <HeaderCell>Semantic</HeaderCell>
            <HeaderCell>Endpoint</HeaderCell>
            <HeaderCell>Proof</HeaderCell>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const selected = row.agentUid === selectedUid;
            const color = trustColor(row);
            return (
              <tr
                key={row.agentUid}
                className={`border-b border-sumi-900/80 transition-colors last:border-b-0 ${
                  selected ? "bg-aozora/10" : "hover:bg-sumi-900/50"
                }`}
              >
                <td className="max-w-[210px] px-3 py-3">
                  <button
                    type="button"
                    onClick={() => onSelect(row.agentUid)}
                    className="flex w-full min-w-0 flex-col text-left"
                  >
                    <span className="truncate font-heading text-sm font-semibold text-torinoko">
                      {row.label}
                    </span>
                    <span className="mt-0.5 truncate font-mono text-[10px] text-sumi-500">
                      {row.agentUid}
                    </span>
                  </button>
                </td>
                <td className="px-3 py-3">
                  <Chip color={color} label={row.trustGrade || "unknown"} />
                </td>
                <td className="px-3 py-3">
                  <HandoffChip row={row} />
                </td>
                <td className="px-3 py-3">
                  <FindingCell row={row} />
                </td>
                <BodyCell>{valueOrDash(row.role)}</BodyCell>
                <BodyCell>{valueOrDash(row.model)}</BodyCell>
                <BodyCell>{valueOrDash(row.harness)}</BodyCell>
                <BodyCell>{valueOrDash(row.authority)}</BodyCell>
                <BodyCell>{valueOrDash(row.semanticObject || row.semanticName)}</BodyCell>
                <BodyCell>{valueOrDash(row.endpoint)}</BodyCell>
                <td className="px-3 py-3">
                  <div className="grid grid-cols-3 gap-1 font-mono text-[10px] text-sumi-500">
                    <span>{row.cardCount} cards</span>
                    <span>{row.sourceCount} src</span>
                    <span>{row.capabilityCount} cap</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function HeaderCell({ children }: { children: ReactNode }) {
  return <th className="px-3 py-2 font-medium">{children}</th>;
}

function BodyCell({ children }: { children: ReactNode }) {
  return (
    <td className="max-w-[150px] px-3 py-3">
      <div className="truncate text-sumi-300">{children}</div>
    </td>
  );
}

function Chip({ color, label }: { color: string; label: string }) {
  return (
    <span
      className="inline-flex max-w-[130px] items-center rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.08em]"
      style={{
        borderColor: `color-mix(in srgb, ${color} 35%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 8%, transparent)`,
        color,
      }}
    >
      <span className="truncate">{label}</span>
    </span>
  );
}

function HandoffChip({ row }: { row: AgentCardComparisonRow }) {
  const color = handoffColor(row);
  const Icon =
    row.handoffState === "ready"
      ? CheckCircle2
      : row.handoffState === "blocked"
        ? ShieldAlert
        : CircleDashed;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.08em]"
      style={{
        borderColor: `color-mix(in srgb, ${color} 35%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 8%, transparent)`,
        color,
      }}
    >
      <Icon size={12} />
      {row.handoffState}
    </span>
  );
}

function FindingCell({ row }: { row: AgentCardComparisonRow }) {
  if (row.findingCount === 0) {
    return <span className="font-mono text-[10px] text-rokusho">clean</span>;
  }
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[10px]">
      <AlertTriangle
        size={12}
        style={{ color: row.errorCount > 0 ? colors.bengara : colors.kinpaku }}
      />
      <span className={row.errorCount > 0 ? "text-bengara" : "text-kinpaku"}>
        {row.errorCount}/{row.warningCount}
      </span>
    </span>
  );
}
