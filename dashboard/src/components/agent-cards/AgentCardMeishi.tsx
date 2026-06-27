"use client";

import {
  AlertTriangle,
  BriefcaseBusiness,
  CheckCircle2,
  CircleDashed,
  Cpu,
  IdCard,
  Network,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import {
  agentCardBlocked,
  agentCardHandoffReady,
  agentCardLabel,
  countAgentCardFindings,
} from "@/lib/agentCards";
import { colors } from "@/lib/theme";
import { cn } from "@/lib/utils";
import type { AgentCardOut } from "@/lib/types";
import type { ReactNode } from "react";

interface AgentCardMeishiProps {
  agent: AgentCardOut;
  selected: boolean;
  onSelect: (agent: AgentCardOut) => void;
}

function trustColor(trustGrade: string): string {
  if (trustGrade === "verified") return colors.rokusho;
  if (trustGrade === "registered") return colors.aozora;
  if (trustGrade === "discovery") return colors.kinpaku;
  if (trustGrade === "evidence_only") return colors.fuji;
  if (trustGrade === "quarantine") return colors.bengara;
  return colors.sumi[600];
}

function TrustIcon({ agent }: { agent: AgentCardOut }) {
  if (agentCardBlocked(agent)) {
    return <ShieldAlert size={15} style={{ color: colors.bengara }} />;
  }
  if (agent.trust_grade === "verified") {
    return <ShieldCheck size={15} style={{ color: colors.rokusho }} />;
  }
  return <CircleDashed size={15} style={{ color: trustColor(agent.trust_grade) }} />;
}

export function AgentCardMeishi({
  agent,
  selected,
  onSelect,
}: AgentCardMeishiProps) {
  const accent = trustColor(agent.trust_grade);
  const errors = countAgentCardFindings(agent, "error");
  const warnings = countAgentCardFindings(agent, "warning");
  const handoffReady = agentCardHandoffReady(agent);
  const sourceCount = Object.values(agent.sources).reduce(
    (count, paths) => count + paths.length,
    0,
  );

  return (
    <button
      type="button"
      onClick={() => onSelect(agent)}
      aria-pressed={selected}
      className={cn(
        "group flex min-h-[244px] w-full flex-col justify-between rounded-lg border bg-sumi-950/70 p-4 text-left transition-all",
        selected
          ? "border-aozora/70 shadow-[0_0_0_1px_color-mix(in_srgb,var(--color-aozora)_45%,transparent)]"
          : "border-sumi-700/40 hover:border-sumi-600/70 hover:bg-sumi-900/70",
      )}
      style={{
        borderTopColor: accent,
      }}
    >
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <IdCard size={15} style={{ color: accent }} />
              <span className="truncate font-heading text-[15px] font-semibold text-torinoko">
                {agentCardLabel(agent)}
              </span>
            </div>
            <div className="mt-1 truncate font-mono text-[11px] text-sumi-500">
              {agent.agent_uid}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1 rounded-md border border-sumi-700/50 px-1.5 py-1">
            <TrustIcon agent={agent} />
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-sumi-300">
              {agent.trust_grade}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <MetaCell icon={<BriefcaseBusiness size={12} />} label="Role" value={agent.role || "unknown"} />
          <MetaCell icon={<Cpu size={12} />} label="Model" value={agent.model || agent.provider || "unknown"} />
          <MetaCell icon={<Network size={12} />} label="Harness" value={agent.harness || "unknown"} />
          <MetaCell icon={<IdCard size={12} />} label="Cards" value={String(agent.a2a.card_count_for_agent ?? agent.card_names.length)} />
        </div>

        <div className="flex flex-wrap gap-1.5">
          {agent.capabilities.slice(0, 5).map((capability) => (
            <span
              key={capability}
              className="max-w-full truncate rounded-md border border-sumi-700/50 bg-sumi-900/70 px-2 py-1 font-mono text-[10px] text-sumi-300"
            >
              {capability}
            </span>
          ))}
          {agent.capabilities.length > 5 && (
            <span className="rounded-md border border-sumi-700/50 px-2 py-1 font-mono text-[10px] text-sumi-500">
              +{agent.capabilities.length - 5}
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-sumi-800/80 pt-3">
        <div className="flex items-center gap-3 font-mono text-[10px] text-sumi-500">
          <span className="inline-flex items-center gap-1">
            {handoffReady ? (
              <CheckCircle2 size={12} style={{ color: colors.rokusho }} />
            ) : (
              <CircleDashed size={12} style={{ color: colors.kinpaku }} />
            )}
            handoff
          </span>
          <span>{sourceCount} src</span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[10px]">
          {errors > 0 && (
            <span className="inline-flex items-center gap-1 text-bengara">
              <AlertTriangle size={12} />
              {errors}
            </span>
          )}
          {warnings > 0 && <span className="text-kinpaku">{warnings} warn</span>}
          {errors === 0 && warnings === 0 && (
            <span className="text-rokusho">clean</span>
          )}
        </div>
      </div>
    </button>
  );
}

function MetaCell({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0 rounded-md border border-sumi-800/80 bg-sumi-900/40 px-2 py-1.5">
      <div className="flex items-center gap-1.5 text-sumi-600">
        {icon}
        <span className="font-mono text-[9px] uppercase tracking-[0.08em]">
          {label}
        </span>
      </div>
      <div className="mt-0.5 truncate text-[11px] text-sumi-300">{value}</div>
    </div>
  );
}
