import Link from "next/link";
import { AlertTriangle, ArrowLeft, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import type { LivelihoodLoomPacketDetail } from "@/lib/livelihoodLoom";

export interface PacketDetailCardProps {
  packet: LivelihoodLoomPacketDetail;
  className?: string;
}

export function PacketDetailCard({ packet, className }: PacketDetailCardProps) {
  return (
    <article className={cn("rounded-lg border border-[#181a20]/10 bg-white p-6 sm:p-8", className)}>
      <div className="flex items-start gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-[#0d615f]/10 text-[#0d615f]">
          <FileText size={24} aria-hidden="true" />
        </span>
        <div>
          <p className="text-sm font-semibold uppercase text-[#60736b]">Enablement packet</p>
          <h1 className="mt-1 font-heading text-3xl font-semibold text-[#181a20]">{packet.packet_id}</h1>
          {packet.cell_id && <p className="text-sm text-[#5d5f68]">{packet.cell_id}</p>}
        </div>
      </div>

      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {packet.target_wedge && (
          <div>
            <p className="text-xs font-semibold uppercase text-[#60736b]">Target wedge</p>
            <p className="mt-1 text-sm font-semibold text-[#181a20]">{packet.target_wedge}</p>
          </div>
        )}
        {packet.beneficiary && (
          <div>
            <p className="text-xs font-semibold uppercase text-[#60736b]">Beneficiary</p>
            <p className="mt-1 text-sm font-semibold text-[#181a20]">{packet.beneficiary}</p>
          </div>
        )}
        {packet.friction && (
          <div>
            <p className="text-xs font-semibold uppercase text-[#60736b]">Friction</p>
            <p className="mt-1 text-sm text-[#4e5060]">{packet.friction}</p>
          </div>
        )}
        {packet.sponsor_value && (
          <div>
            <p className="text-xs font-semibold uppercase text-[#60736b]">Sponsor value</p>
            <p className="mt-1 text-sm text-[#4e5060]">{packet.sponsor_value}</p>
          </div>
        )}
      </div>

      {packet.welfare_metric && (
        <div className="mt-8 rounded-lg border border-[#0d615f]/20 bg-[#0d615f]/5 p-4">
          <p className="text-xs font-semibold uppercase text-[#0d615f]">Welfare metric</p>
          <p className="mt-2 text-sm leading-6 text-[#4e5060]">{packet.welfare_metric}</p>
        </div>
      )}

      <h2 className="mt-10 font-heading text-xl font-semibold text-[#181a20]">Candidate partners</h2>
      <div className="mt-4 overflow-x-auto rounded-lg border border-[#181a20]/10">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-[#f4f1ea] text-xs font-semibold uppercase text-[#60736b]">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Country</th>
              <th className="px-4 py-3">Score</th>
              <th className="px-4 py-3">Safety</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#181a20]/10 bg-white">
            {packet.candidate_partners.map((partner) => (
              <tr key={partner.company_id}>
                <td className="px-4 py-4">
                  <Link
                    href={`/livelihood-loom/candidates/${partner.company_id}`}
                    className="font-semibold text-[#181a20] hover:underline"
                  >
                    {partner.name}
                  </Link>
                </td>
                <td className="px-4 py-4 text-[#5d5f68]">{partner.country}</td>
                <td className="px-4 py-4 font-mono text-xs text-[#9c6f16]">
                  {partner.prioritization_score.toFixed(3)}
                </td>
                <td className="px-4 py-4">
                  <StatusBadge status={partner.safety_status ?? "unknown"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {packet.risks && packet.risks.length > 0 && (
        <div className="mt-8 rounded-lg border border-[#d4a855]/30 bg-[#d4a855]/10 p-4">
          <div className="flex items-center gap-2 text-[#9c6f16]">
            <AlertTriangle size={18} aria-hidden="true" />
            <p className="text-sm font-semibold">Risks</p>
          </div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[#5d5f68]">
            {packet.risks.map((risk, index) => (
              <li key={index}>{risk}</li>
            ))}
          </ul>
        </div>
      )}

      {packet.next_safe_action && (
        <div className="mt-8 rounded-lg border border-[#0d615f]/20 bg-[#0d615f]/5 p-4">
          <p className="text-xs font-semibold uppercase text-[#0d615f]">Next safe action</p>
          <p className="mt-2 text-sm leading-6 text-[#181a20]">{packet.next_safe_action}</p>
        </div>
      )}

      <div className="mt-8">
        <Link
          href="/livelihood-loom/proof-packet"
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#0d615f] hover:text-[#181a20]"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Back to proof packets
        </Link>
      </div>
    </article>
  );
}
