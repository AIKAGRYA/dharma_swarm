"use client";

import { AlertTriangle, CircleCheck, Clock3, ListChecks } from "lucide-react";
import { useDsGoalCards } from "@/hooks/useControlSurface";
import type { DsGoalBoardCard } from "@/lib/types";
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

function cardMission(card: DsGoalBoardCard): string {
  const line = card.body.split("\n").find((item) => item.startsWith("mission_id:"));
  return line?.replace("mission_id:", "").trim() || card.parent_objective || "mission";
}

export function DsGoalMissionCardsPanel() {
  const { cards, isLoading, error } = useDsGoalCards();
  const openCount = cards.filter((card) => card.status !== "done" && card.status !== "cancelled").length;
  const doneCount = cards.filter((card) => card.status === "done").length;

  return (
    <section className="rounded-md border border-sumi-700/30 bg-sumi-950/60">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sumi-800/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <ListChecks size={14} className="text-rokusho" />
          <span className="text-[10px] font-semibold uppercase text-sumi-500">
            ds-goal Mission Cards
          </span>
        </div>
        <div className="flex gap-3 text-[10px] text-sumi-500">
          <span>
            Open <strong className="text-sumi-200">{openCount}</strong>
          </span>
          <span>
            Done <strong className="text-sumi-200">{doneCount}</strong>
          </span>
          <span>
            Total <strong className="text-sumi-200">{cards.length}</strong>
          </span>
        </div>
      </div>

      <div className="flex min-h-[92px] gap-2 overflow-x-auto p-3">
        {isLoading ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-sumi-500">
            Loading mission cards...
          </div>
        ) : error ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-bengara">
            Mission cards unavailable
          </div>
        ) : cards.length === 0 ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-sumi-500">
            No ds-goal cards
          </div>
        ) : (
          cards.slice(0, 12).map((card) => {
            const color = statusColor(card.status);
            return (
              <div
                key={card.id}
                className="min-w-[260px] rounded-md border border-sumi-800/50 bg-sumi-900/40 px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-sumi-200">{card.title}</div>
                    <div className="mt-1 truncate text-[10px] text-sumi-500">{cardMission(card)}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1 rounded-md border border-sumi-700/40 px-1.5 py-0.5">
                    <StatusIcon status={card.status} />
                    <span className="text-[10px] font-semibold uppercase" style={{ color }}>
                      {card.status}
                    </span>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-1 text-[10px] text-sumi-500">
                  <span className="truncate">agent {card.created_by || "unknown"}</span>
                  <span className="truncate">receipts {card.receipt_refs.length}</span>
                  <span className="truncate">lane {card.render_hints.lane_hint || "board"}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
