import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LivelihoodLoomWedgeDetail } from "@/lib/livelihoodLoom";

export interface WedgeCardProps {
  wedge: LivelihoodLoomWedgeDetail;
  className?: string;
}

export function WedgeCard({ wedge, className }: WedgeCardProps) {
  return (
    <article
      className={cn(
        "group rounded-lg border border-[#181a20]/10 bg-white p-5 transition hover:border-[#181a20]/20 hover:shadow-lg",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase text-[#60736b]">
          Wedge {String(wedge.rank).padStart(2, "0")}
        </span>
        <span className="rounded-lg bg-[#d4a855]/14 px-2.5 py-1 font-mono text-sm text-[#9c6f16]">
          {wedge.roi_score.toFixed(3)}
        </span>
      </div>
      <h3 className="mt-5 font-heading text-xl font-semibold text-[#181a20]">{wedge.label}</h3>
      <p className="mt-3 text-sm leading-7 text-[#5d5f68]">{wedge.roi_thesis}</p>
      <div className="mt-5 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase text-[#0d615f]">
          {wedge.candidate_count_in_top_50} Top 50 candidates
        </p>
        {wedge.country_count ? (
          <p className="text-xs font-semibold uppercase text-[#60736b]">{wedge.country_count} countries</p>
        ) : null}
      </div>
      <Link
        href={`/livelihood-loom/wedges/${wedge.wedge_id}`}
        className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#0d615f] transition hover:text-[#181a20]"
      >
        Explore wedge
        <ArrowRight size={16} />
      </Link>
    </article>
  );
}
