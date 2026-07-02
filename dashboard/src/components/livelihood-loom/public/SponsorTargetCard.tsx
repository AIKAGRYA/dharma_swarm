import { ArrowUpRight, CheckCircle2, Globe, HelpCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import type { LivelihoodLoomSponsorTarget } from "@/lib/livelihoodLoom";

export interface SponsorTargetCardProps {
  target: LivelihoodLoomSponsorTarget;
  className?: string;
}

export function SponsorTargetCard({ target, className }: SponsorTargetCardProps) {
  const basis = target.safety_basis;

  return (
    <article className={cn("rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8", className)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold uppercase text-[#60736b]">Draft sponsor target</p>
          <h1 className="mt-2 font-heading text-3xl font-semibold text-[#181a20]">{target.name}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-[#5d5f68]">
            {target.target_type && (
              <span className="rounded-md bg-[#f4f1ea] px-2 py-1 text-xs font-semibold text-[#0d615f]">
                {target.target_type}
              </span>
            )}
            {target.website && (
              <a
                href={target.website}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[#0d615f] hover:text-[#181a20]"
              >
                <Globe size={14} aria-hidden="true" />
                Website
                <ArrowUpRight size={14} aria-hidden="true" />
              </a>
            )}
            {target.partner_page && (
              <a
                href={target.partner_page}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[#0d615f] hover:text-[#181a20]"
              >
                Partner page
                <ArrowUpRight size={14} aria-hidden="true" />
              </a>
            )}
          </div>
        </div>
        {target.selection_status && <StatusBadge status={target.selection_status} />}
      </div>

      {target.fit_thesis && (
        <div className="mt-6">
          <p className="text-sm font-semibold text-[#181a20]">Fit thesis</p>
          <p className="mt-2 text-sm leading-7 text-[#4e5060]">{target.fit_thesis}</p>
        </div>
      )}

      {basis && (
        <div className="mt-8">
          <p className="text-sm font-semibold text-[#181a20]">Safety basis</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-4">
              <div className="flex items-center gap-2 text-rokusho">
                <CheckCircle2 size={16} aria-hidden="true" />
                <span className="text-xs font-semibold uppercase">Allowed</span>
              </div>
              <p className="mt-2 font-heading text-2xl font-semibold text-[#181a20]">{basis.allowed}</p>
            </div>
            <div className="rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-4">
              <div className="flex items-center gap-2 text-kinpaku">
                <HelpCircle size={16} aria-hidden="true" />
                <span className="text-xs font-semibold uppercase">Needs review</span>
              </div>
              <p className="mt-2 font-heading text-2xl font-semibold text-[#181a20]">{basis.needs_review}</p>
            </div>
            <div className="rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-4">
              <div className="flex items-center gap-2 text-bengara">
                <XCircle size={16} aria-hidden="true" />
                <span className="text-xs font-semibold uppercase">Blocked</span>
              </div>
              <p className="mt-2 font-heading text-2xl font-semibold text-[#181a20]">{basis.blocked}</p>
            </div>
          </div>
        </div>
      )}

      {target.selected_wedge && (
        <div className="mt-8 rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-4">
          <p className="text-xs font-semibold uppercase text-[#60736b]">Selected wedge</p>
          <p className="mt-1 font-heading text-lg font-semibold text-[#181a20]">{target.selected_wedge.label}</p>
          <p className="text-sm text-[#5d5f68]">ROI score {target.selected_wedge.roi_score.toFixed(3)}</p>
        </div>
      )}
    </article>
  );
}
