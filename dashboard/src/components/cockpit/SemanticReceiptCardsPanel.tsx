"use client";

import { AlertTriangle, BrainCircuit, CircleCheck, Clock3 } from "lucide-react";
import { useSemanticReceiptCards } from "@/hooks/useControlSurface";
import type { SemanticReceiptBoardCard } from "@/lib/types";
import { colors } from "@/lib/theme";

function bodyLine(card: SemanticReceiptBoardCard, key: string): string {
  const prefix = `${key}:`;
  const line = card.body.split("\n").find((item) => item.startsWith(prefix));
  return line?.replace(prefix, "").trim() || "";
}

function statusColor(status: string): string {
  if (status === "done" || status === "review") {
    return colors.rokusho;
  }
  if (status === "blocked" || status === "failed") {
    return colors.botan;
  }
  return colors.kinpaku;
}

function StatusIcon({ status }: { status: string }) {
  if (status === "blocked" || status === "failed") {
    return <AlertTriangle size={13} style={{ color: statusColor(status) }} />;
  }
  if (status === "review" || status === "done") {
    return <CircleCheck size={13} style={{ color: statusColor(status) }} />;
  }
  return <Clock3 size={13} style={{ color: statusColor(status) }} />;
}

export function SemanticReceiptCardsPanel() {
  const { cards, isLoading, error } = useSemanticReceiptCards("", "", 8);
  const semanticCount = cards.filter((card) => bodyLine(card, "semantic_reply_claim") === "True").length;
  const blockedCount = cards.filter((card) => card.status === "blocked" || card.status === "failed").length;

  return (
    <section className="rounded-md border border-sumi-700/30 bg-sumi-950/60">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sumi-800/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <BrainCircuit size={14} className="text-rokusho" />
          <span className="text-[10px] font-semibold uppercase text-sumi-500">
            Semantic Receipts
          </span>
        </div>
        <div className="flex gap-3 text-[10px] text-sumi-500">
          <span>
            Semantic <strong className="text-sumi-200">{semanticCount}</strong>
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
          <div className="flex min-h-[68px] min-w-[260px] items-center text-xs text-sumi-500">
            Loading semantic receipts...
          </div>
        ) : error ? (
          <div className="flex min-h-[68px] min-w-[260px] items-center text-xs text-bengara">
            Semantic receipts unavailable
          </div>
        ) : cards.length === 0 ? (
          <div className="flex min-h-[68px] min-w-[260px] items-center text-xs text-sumi-500">
            No SemanticReceipt cards
          </div>
        ) : (
          cards.map((card) => {
            const color = statusColor(card.status);
            const verdict = bodyLine(card, "verdict") || "unknown";
            const provider = bodyLine(card, "provider") || "provider";
            const model = bodyLine(card, "model") || "model";
            const confidence = bodyLine(card, "confidence") || "n/a";
            const capability = bodyLine(card, "capability_match") || "n/a";
            return (
              <div
                key={card.id}
                className="min-w-[320px] rounded-md border border-sumi-800/50 bg-sumi-900/40 px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-sumi-200">{card.title}</div>
                    <div className="mt-1 truncate text-[10px] text-sumi-500">
                      {provider} / {model}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1 rounded-md border border-sumi-700/40 px-1.5 py-0.5">
                    <StatusIcon status={card.status} />
                    <span className="text-[10px] font-semibold uppercase" style={{ color }}>
                      {verdict}
                    </span>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-1 text-[10px] text-sumi-500">
                  <span className="truncate">confidence {confidence}</span>
                  <span className="truncate">capability {capability}</span>
                  <span className="truncate">receipts {card.receipt_refs.length}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
