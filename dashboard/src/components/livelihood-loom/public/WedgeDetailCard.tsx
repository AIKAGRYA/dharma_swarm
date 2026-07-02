import Link from "next/link";
import { ArrowLeft, ExternalLink, Globe, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LivelihoodLoomWedgeDetail } from "@/lib/livelihoodLoom";

export interface WedgeDetailCardProps {
  wedge: LivelihoodLoomWedgeDetail;
  className?: string;
}

export function WedgeDetailCard({ wedge, className }: WedgeDetailCardProps) {
  return (
    <div className={cn("rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8", className)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase text-[#60736b]">
            Wedge {String(wedge.rank).padStart(2, "0")}
          </p>
          <h1 className="mt-2 font-heading text-4xl font-semibold text-[#181a20]">{wedge.label}</h1>
        </div>
        <span className="w-fit rounded-lg bg-[#d4a855]/14 px-3 py-2 font-mono text-lg text-[#9c6f16]">
          {wedge.roi_score.toFixed(3)}
        </span>
      </div>

      <p className="mt-6 text-lg leading-8 text-[#4e5060]">{wedge.roi_thesis}</p>

      <div className="mt-6 flex flex-wrap gap-6 text-sm text-[#5d5f68]">
        <div className="flex items-center gap-2">
          <Users size={18} className="text-[#0d615f]" aria-hidden="true" />
          {wedge.candidate_count_in_top_50} Top 50 candidates
        </div>
        <div className="flex items-center gap-2">
          <Globe size={18} className="text-[#0d615f]" aria-hidden="true" />
          {wedge.country_count} countries
        </div>
      </div>

      {wedge.safety_caveats && wedge.safety_caveats.length > 0 && (
        <div className="mt-8 rounded-lg border border-[#d4a855]/30 bg-[#d4a855]/10 p-4">
          <p className="text-sm font-semibold text-[#9c6f16]">Safety caveats</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[#5d5f68]">
            {wedge.safety_caveats.map((caveat, index) => (
              <li key={index}>{caveat}</li>
            ))}
          </ul>
        </div>
      )}

      {wedge.evidence_refs && wedge.evidence_refs.length > 0 && (
        <div className="mt-8">
          <p className="text-sm font-semibold text-[#181a20]">Evidence references</p>
          <ul className="mt-2 space-y-1">
            {wedge.evidence_refs.map((ref, index) => (
              <li key={index}>
                <a
                  href={ref}
                  className="inline-flex items-center gap-1 break-all text-sm text-[#0d615f] hover:text-[#181a20]"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink size={14} aria-hidden="true" />
                  {ref}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <h2 className="mt-10 font-heading text-2xl font-semibold text-[#181a20]">Top candidates</h2>
      <div className="mt-4 overflow-x-auto rounded-lg border border-[#181a20]/10">
        <table className="w-full min-w-[600px] text-left text-sm">
          <thead className="bg-[#f4f1ea] text-xs font-semibold uppercase text-[#60736b]">
            <tr>
              <th className="px-4 py-3">Rank</th>
              <th className="px-4 py-3">Candidate</th>
              <th className="px-4 py-3">Country</th>
              <th className="px-4 py-3">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#181a20]/10 bg-white">
            {wedge.top_candidates.map((candidate) => (
              <tr key={candidate.company_id}>
                <td className="px-4 py-4 font-mono text-xs text-[#60736b]">{candidate.rank}</td>
                <td className="px-4 py-4">
                  <Link
                    href={`/livelihood-loom/candidates/${candidate.company_id}`}
                    className="font-semibold text-[#181a20] hover:underline"
                  >
                    {candidate.name}
                  </Link>
                </td>
                <td className="px-4 py-4 text-[#5d5f68]">{candidate.country}</td>
                <td className="px-4 py-4 font-mono text-xs text-[#9c6f16]">{candidate.score.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-8">
        <Link
          href="/livelihood-loom/market-map"
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#0d615f] hover:text-[#181a20]"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Back to market map
        </Link>
      </div>
    </div>
  );
}
