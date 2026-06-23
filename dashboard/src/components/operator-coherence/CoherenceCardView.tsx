"use client";

import { ExternalLink } from "lucide-react";
import type { CoherenceCard } from "@/lib/operatorCoherence";

function facetLabel(card: CoherenceCard): string[] {
  const labels = [];
  labels.push(card.facets.tracked ? "tracked" : "untracked");
  labels.push(card.facets.live ? "live" : card.facets.stale ? "stale" : "not-live");
  labels.push(card.facets.preserved ? "preserved" : "not-preserved");
  labels.push(card.facets.intentional ? "intentional" : "rogue/unknown");
  labels.push(card.facets.local_only ? "local-only" : card.facets.origin_backed ? "origin-backed" : "origin-unknown");
  labels.push(card.facets.operator_decision ? "operator decision" : "engineering task");
  return labels;
}

export function CoherenceCardView({
  card,
  compact = false,
}: {
  card: CoherenceCard;
  compact?: boolean;
}) {
  return (
    <article className="rounded-lg border border-sumi-800/60 bg-sumi-950/45 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <code className="rounded bg-sumi-800/70 px-1.5 py-0.5 text-[10px] text-sumi-400">
              {card.kind}
            </code>
            <span className="rounded bg-sumi-800/40 px-1.5 py-0.5 text-[10px] uppercase text-sumi-500">
              {card.status}
            </span>
          </div>
          <h3 className="mt-1 line-clamp-2 text-sm font-semibold text-sumi-100">
            {card.title}
          </h3>
        </div>
        {card.evidence?.[0]?.path ? (
          <span title={card.evidence[0].path} className="text-sumi-600">
            <ExternalLink size={13} />
          </span>
        ) : null}
      </div>
      {!compact ? (
        <>
          <div className="mt-2 text-xs text-sumi-400">{card.next_action}</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {facetLabel(card).map((facet) => (
              <span
                key={facet}
                className="rounded-full border border-sumi-800/70 px-1.5 py-0.5 text-[10px] text-sumi-500"
              >
                {facet}
              </span>
            ))}
          </div>
          <div className="mt-2 text-[10px] text-sumi-600">
            Evidence: {card.evidence?.[0]?.source ?? "missing"} · Track: {card.track || "unknown"}
          </div>
        </>
      ) : null}
    </article>
  );
}
