import Link from "next/link";
import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import type { LivelihoodLoomCandidateDetail } from "@/lib/livelihoodLoom";

export interface CandidateTableProps {
  candidates: LivelihoodLoomCandidateDetail[];
  className?: string;
}

export function CandidateTable({ candidates, className }: CandidateTableProps) {
  return (
    <div className={cn("overflow-x-auto rounded-lg border border-[#181a20]/10", className)}>
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-[#f4f1ea] text-xs font-semibold uppercase text-[#60736b]">
          <tr>
            <th className="px-4 py-3">Rank</th>
            <th className="px-4 py-3">Candidate</th>
            <th className="px-4 py-3">Country</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Safety</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#181a20]/10 bg-white">
          {candidates.map((candidate) => (
            <tr key={candidate.company_id} className="transition hover:bg-[#f9f7f1]">
              <td className="px-4 py-4 font-mono text-xs text-[#60736b]">{candidate.rank}</td>
              <td className="px-4 py-4">
                <Link
                  href={`/livelihood-loom/candidates/${candidate.company_id}`}
                  className="font-semibold text-[#181a20] hover:underline"
                >
                  {candidate.name}
                  {candidate.domain && candidate.domain !== "unknown" ? (
                    <span className="ml-2 font-normal text-[#5d5f68]">({candidate.domain})</span>
                  ) : null}
                </Link>
              </td>
              <td className="px-4 py-4 text-[#5d5f68]">{candidate.country}</td>
              <td className="px-4 py-4 font-mono text-xs text-[#9c6f16]">
                {candidate.prioritization_score.toFixed(3)}
              </td>
              <td className="px-4 py-4">
                <StatusBadge status={candidate.safety_status ?? "unknown"} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
