import Link from "next/link";
import { ArrowLeft, ExternalLink, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import type { LivelihoodLoomCandidateDetail } from "@/lib/livelihoodLoom";

export interface CandidateCardProps {
  candidate: LivelihoodLoomCandidateDetail;
  className?: string;
}

export function CandidateCard({ candidate, className }: CandidateCardProps) {
  return (
    <article className={cn("rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8", className)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold uppercase text-[#60736b]">
            Rank {candidate.rank} · Source rank {candidate.source_rank}
          </p>
          <h1 className="mt-2 font-heading text-3xl font-semibold text-[#181a20] sm:text-4xl">
            {candidate.name}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-[#5d5f68]">
            <span className="inline-flex items-center gap-1.5">
              <Globe size={16} aria-hidden="true" />
              {candidate.country}
            </span>
            {candidate.domain && candidate.domain !== "unknown" && (
              <span className="text-[#4e5060]">{candidate.domain}</span>
            )}
            {candidate.wedge_label && (
              <span className="rounded-md bg-[#f4f1ea] px-2 py-1 text-xs font-semibold text-[#0d615f]">
                {candidate.wedge_label}
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-col items-start gap-2 sm:items-end">
          <span className="rounded-lg bg-[#d4a855]/14 px-3 py-2 font-mono text-xl text-[#9c6f16]">
            {candidate.prioritization_score.toFixed(3)}
          </span>
          <StatusBadge status={candidate.safety_status ?? "unknown"} />
        </div>
      </div>

      {candidate.description && (
        <p className="mt-6 text-base leading-7 text-[#4e5060]">{candidate.description}</p>
      )}

      {candidate.reasons && candidate.reasons.length > 0 && (
        <div className="mt-8">
          <h2 className="font-heading text-lg font-semibold text-[#181a20]">Why it ranks</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-[#5d5f68]">
            {candidate.reasons.map((reason, index) => (
              <li key={index}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {candidate.score_components && Object.keys(candidate.score_components).length > 0 && (
        <div className="mt-8">
          <h2 className="font-heading text-lg font-semibold text-[#181a20]">Score components</h2>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(candidate.score_components).map(([key, value]) => (
              <div key={key} className="rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-3">
                <dt className="text-xs font-semibold uppercase text-[#60736b]">{key}</dt>
                <dd className="mt-1 font-mono text-lg text-[#181a20]">
                  {typeof value === "number" ? value.toFixed(3) : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {candidate.evidence_refs && candidate.evidence_refs.length > 0 && (
        <div className="mt-8">
          <h2 className="font-heading text-lg font-semibold text-[#181a20]">Evidence references</h2>
          <ul className="mt-3 space-y-2">
            {candidate.evidence_refs.map((ref, index) => (
              <li key={index}>
                <a
                  href={ref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 break-all text-sm text-[#0d615f] hover:text-[#181a20]"
                >
                  <ExternalLink size={14} aria-hidden="true" />
                  {ref}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {candidate.safety_review && (
        <div className="mt-8 rounded-lg border border-[#181a20]/10 bg-[#f9f7f1] p-5">
          <h2 className="font-heading text-lg font-semibold text-[#181a20]">Safety review</h2>
          <div className="mt-3">
            <StatusBadge status={candidate.safety_review.safety_status} />
          </div>
          {candidate.safety_review.flags.length > 0 && (
            <>
              <p className="mt-4 text-xs font-semibold uppercase text-[#60736b]">Flags</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[#5d5f68]">
                {candidate.safety_review.flags.map((flag, index) => (
                  <li key={index}>{flag}</li>
                ))}
              </ul>
            </>
          )}
          {candidate.safety_review.notes.length > 0 && (
            <>
              <p className="mt-4 text-xs font-semibold uppercase text-[#60736b]">Notes</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[#5d5f68]">
                {candidate.safety_review.notes.map((note, index) => (
                  <li key={index}>{note}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      <div className="mt-8">
        <Link
          href="/livelihood-loom/market-map"
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#0d615f] hover:text-[#181a20]"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Back to market map
        </Link>
      </div>
    </article>
  );
}
