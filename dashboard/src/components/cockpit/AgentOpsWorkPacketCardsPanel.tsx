"use client";

import { AlertTriangle, BriefcaseBusiness, CircleCheck, Clock3 } from "lucide-react";
import { useAgentOpsCards } from "@/hooks/useControlSurface";
import type { AgentOpsBoardCard } from "@/lib/types";
import { colors } from "@/lib/theme";

function statusColor(status: string): string {
  if (status === "done") {
    return colors.rokusho;
  }
  if (status === "blocked" || status === "failed") {
    return colors.botan;
  }
  if (status === "running" || status === "claimed" || status === "review") {
    return colors.kinpaku;
  }
  return colors.aozora;
}

function StatusIcon({ status }: { status: string }) {
  if (status === "done") {
    return <CircleCheck size={13} style={{ color: statusColor(status) }} />;
  }
  if (status === "blocked" || status === "failed") {
    return <AlertTriangle size={13} style={{ color: statusColor(status) }} />;
  }
  return <Clock3 size={13} style={{ color: statusColor(status) }} />;
}

function bodyLine(card: AgentOpsBoardCard, key: string): string {
  const prefix = `${key}:`;
  const line = card.body.split("\n").find((item) => item.startsWith(prefix));
  return line?.replace(prefix, "").trim() || "";
}

export function AgentOpsWorkPacketCardsPanel() {
  const { cards, isLoading, error } = useAgentOpsCards("", 12);
  const activeCount = cards.filter((card) => card.status !== "done" && card.status !== "cancelled").length;
  const approvalCount = cards.filter((card) =>
    card.acceptance_criteria.some((criterion) => criterion.kind === "manual"),
  ).length;

  return (
    <section className="rounded-md border border-sumi-700/30 bg-sumi-950/60">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sumi-800/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <BriefcaseBusiness size={14} className="text-aozora" />
          <span className="text-[10px] font-semibold uppercase text-sumi-500">
            AgentOps Work Packets
          </span>
        </div>
        <div className="flex gap-3 text-[10px] text-sumi-500">
          <span>
            Active <strong className="text-sumi-200">{activeCount}</strong>
          </span>
          <span>
            Approval <strong className="text-sumi-200">{approvalCount}</strong>
          </span>
          <span>
            Total <strong className="text-sumi-200">{cards.length}</strong>
          </span>
        </div>
      </div>

      <div className="flex min-h-[92px] gap-2 overflow-x-auto p-3">
        {isLoading ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-sumi-500">
            Loading work packets...
          </div>
        ) : error ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-bengara">
            Work packets unavailable
          </div>
        ) : cards.length === 0 ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-sumi-500">
            No AgentOps cards
          </div>
        ) : (
          cards.map((card) => {
            const color = statusColor(card.status);
            const branch = bodyLine(card, "branch") || bodyLine(card, "worktree") || "agentops";
            const gateCount = card.acceptance_criteria.filter((criterion) => criterion.kind === "test").length;
            return (
              <div
                key={card.id}
                className="min-w-[300px] rounded-md border border-sumi-800/50 bg-sumi-900/40 px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-sumi-200">{card.title}</div>
                    <div className="mt-1 truncate text-[10px] text-sumi-500">{branch}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1 rounded-md border border-sumi-700/40 px-1.5 py-0.5">
                    <StatusIcon status={card.status} />
                    <span className="text-[10px] font-semibold uppercase" style={{ color }}>
                      {card.status}
                    </span>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-1 text-[10px] text-sumi-500">
                  <span className="truncate">gates {gateCount}</span>
                  <span className="truncate">receipts {card.receipt_refs.length}</span>
                  <span className="truncate">lane {card.render_hints.lane_hint || "agentops"}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
