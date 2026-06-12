"use client";

import { AlertTriangle, CircleCheck, Clock3, RadioTower } from "lucide-react";
import { useA2ASendCards } from "@/hooks/useControlSurface";
import type { A2ASendBoardCard } from "@/lib/types";
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

function bodyLine(card: A2ASendBoardCard, key: string): string {
  const prefix = `${key}:`;
  const line = card.body.split("\n").find((item) => item.startsWith(prefix));
  return line?.replace(prefix, "").trim() || "";
}

export function A2ASendCardsPanel() {
  const { cards, isLoading, error } = useA2ASendCards("", 12);
  const ackedCount = cards.filter((card) => (
    bodyLine(card, "live_contact_claim") === "True" || card.status === "done"
  )).length;
  const blockedCount = cards.filter((card) => card.status === "blocked").length;

  return (
    <section className="rounded-md border border-sumi-700/30 bg-sumi-950/60">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sumi-800/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <RadioTower size={14} className="text-kinpaku" />
          <span className="text-[10px] font-semibold uppercase text-sumi-500">
            A2A Contact Receipts
          </span>
        </div>
        <div className="flex gap-3 text-[10px] text-sumi-500">
          <span>
            Acked <strong className="text-sumi-200">{ackedCount}</strong>
          </span>
          <span>
            Blocked <strong className="text-sumi-200">{blockedCount}</strong>
          </span>
          <span>
            Total <strong className="text-sumi-200">{cards.length}</strong>
          </span>
        </div>
      </div>

      <div className="flex min-h-[92px] gap-2 overflow-x-auto p-3">
        {isLoading ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-sumi-500">
            Loading A2A receipts...
          </div>
        ) : error ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-bengara">
            A2A receipts unavailable
          </div>
        ) : cards.length === 0 ? (
          <div className="flex min-h-[68px] min-w-[240px] items-center text-xs text-sumi-500">
            No A2A receipts
          </div>
        ) : (
          cards.map((card) => {
            const color = statusColor(card.status);
            const kind = bodyLine(card, "kind");
            const target = bodyLine(card, "to") || bodyLine(card, "agent_uid") || "peer";
            const tier = bodyLine(card, "contact_evidence_tier") || "unknown";
            return (
              <div
                key={card.id}
                className="min-w-[300px] rounded-md border border-sumi-800/50 bg-sumi-900/40 px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-sumi-200">{target}</div>
                    <div className="mt-1 truncate text-[10px] text-sumi-500">
                      {kind ? `${kind} / ${tier}` : tier}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1 rounded-md border border-sumi-700/40 px-1.5 py-0.5">
                    <StatusIcon status={card.status} />
                    <span className="text-[10px] font-semibold uppercase" style={{ color }}>
                      {card.status}
                    </span>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-1 text-[10px] text-sumi-500">
                  <span className="truncate">receipts {card.receipt_refs.length}</span>
                  <span className="truncate">claim {bodyLine(card, "collaboration_claim") || "none"}</span>
                  <span className="truncate">lane {card.render_hints.lane_hint || "a2a"}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
